import os
import uuid
import json
import shutil
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import asyncio
from sqlalchemy.orm import Session
from database.db_session import get_db, SessionLocal, init_db
from database.schema import (
    MigrationRequest, Blueprint, SecurityFinding, CostEstimate,
    ReliabilityFinding, ConsolidatedReport, ApprovalDecision, UserAccount
)
from gateway.invoker.neuro_san_client import NeuroSanClient
from coded_tools.migration_intelligence._paths import request_dir
from gateway.api import analysis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CI/CD Intelligence Layer Gateway API", version="2.0")

# Enable CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Project Constants
MAX_REDRAFT_ATTEMPTS = int(os.environ.get("MAX_REDRAFT_ATTEMPTS", 4))
APPROVAL_WINDOW_HOURS = int(os.environ.get("APPROVAL_WINDOW_HOURS", 48))
SUPPORTED_CLOUD_PROVIDERS = [p.strip().lower() for p in os.environ.get("SUPPORTED_CLOUD_PROVIDERS", "aws,azure,gcp").split(",") if p.strip()]
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:5173")
NOTIFY_RECIPIENT = os.environ.get("NOTIFY_RECIPIENT") or os.environ.get("SMTP_USER")

EXPIRY_SWEEP_MINUTES = int(os.environ.get("EXPIRY_SWEEP_MINUTES", 15))


@app.on_event("startup")
async def _on_startup():
    # Tables + seed users must exist before any query
    init_db()
    # #12 — background sweep so in_review requests expire even if nobody polls.
    # ponytail: simple interval loop; swap for a real scheduler if volume grows.
    asyncio.create_task(_expiry_sweep_loop())


async def _expiry_sweep_loop():
    while True:
        await asyncio.sleep(EXPIRY_SWEEP_MINUTES * 60)
        try:
            _sweep_expired()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Expiry sweep error: {e}")


def _sweep_expired():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=APPROVAL_WINDOW_HOURS)
        overdue = db.query(MigrationRequest).filter(
            MigrationRequest.status == "in_review",
            MigrationRequest.submitted_at < cutoff,
        ).all()
        for req in overdue:
            req.status = "expired"
            db.commit()
            _cleanup_artifacts(req.request_id)
            logger.info(f"Swept request {req.request_id} -> expired.")
    finally:
        db.close()


# Request/Response schemas
class SubmitRequest(BaseModel):
    submitted_by: str
    prompt: str
    project_json: str  # Raw specifications as string

class SubmitDecision(BaseModel):
    approver_id: str
    decision: str  # approved | rejected
    rejection_notes: Optional[str] = None

# Background worker
async def run_analysis_workflow(request_id: str, prompt: str, project_json: str, feedback: Optional[str] = None):
    """Deterministic orchestration (source of truth). Neuro-SAN provides the LLM
    draft; the coded tools are then run ONCE here to produce persisted findings.
    See IMPLEMENTATION_PLAN.md 'open decision'."""
    db = SessionLocal()
    try:
        req = db.query(MigrationRequest).filter(MigrationRequest.request_id == request_id).first()
        if not req:
            logger.error(f"Migration request {request_id} not found in background task.")
            return

        req.status = "drafting"
        req.stage = "drafting"
        db.commit()
        attempt = req.attempt_number

        def _stage(s):
            req.stage = s
            db.commit()

        # Clear any prior-attempt artifacts so this run (esp. a redraft) starts clean
        # and never silently reuses a stale blueprint/diagram/report.
        _cleanup_artifacts(request_id)

        # project.json already validated at API-01; re-parse for structured access
        spec = analysis.validate_project_json(project_json)
        source_platform, target_cloud = analysis.resolve_source_target(spec, prompt, SUPPORTED_CLOUD_PROVIDERS)

        # 1. LLM reasoning layer — let the agent network draft the blueprint.
        #    Best-effort: if it errors, we fall back to a deterministic draft.
        composed_prompt = prompt
        if feedback:
            composed_prompt += f"\n\n[FEEDBACK ON PREVIOUS REJECTION ATTEMPT {attempt - 1}]:\n{feedback}"
        try:
            await NeuroSanClient().trigger_migration_analysis(request_id, composed_prompt, project_json)
        except Exception as e:  # noqa: BLE001 - LLM layer is best-effort, not the source of truth
            logger.warning(f"Neuro-SAN draft unavailable for {request_id} ({e}); using deterministic fallback.")

        # 2. Ensure a validated blueprint.tf (retry/backoff inside the tool; ADR-11)
        _stage("validating")
        if not analysis.ensure_blueprint(request_id, spec, source_platform, target_cloud):
            req.status = "blocked"
            req.stage = "done"
            db.commit()
            logger.error(f"Terraform validation failed for {request_id} after retries — blocked.")
            return

        # 3. Ensure architecture diagram, then run critics ONCE (source of truth)
        _stage("diagram")
        analysis.ensure_diagram(request_id, spec, source_platform, target_cloud)
        _stage("scanning")
        sec_findings = analysis.run_security_scan(request_id)
        _stage("reliability")
        rel_score, rel_notes = analysis.run_reliability(request_id)
        _stage("costing")
        try:
            monthly_cost, rate_refs = analysis.estimate_cost(request_id, target_cloud, spec)
        except ValueError as e:
            req.status = "blocked"
            req.stage = "done"
            db.commit()
            logger.error(f"Cost grounding failed for {request_id}: {e} — blocked (QA6).")
            return

        # 4. Render the consolidated PDF report
        _stage("reporting")
        sec_summary = "\n".join(f"[{f.get('severity','low').upper()}] {f.get('description','')}" for f in sec_findings) or "No findings."
        cost_summary = f"Estimated monthly cost: ${monthly_cost:.2f} USD.\nCited rate-card entries: {', '.join(rate_refs)}"
        rel_summary = f"Redundancy score: {rel_score}/100.\n{rel_notes}"
        pdf_path = analysis.render_report(request_id, sec_summary, cost_summary, rel_summary)

        dir_path = request_dir(request_id)
        tf_path = os.path.join(dir_path, "blueprint.tf")
        svg_path = os.path.join(dir_path, "diagram.svg")
        if not pdf_path or not os.path.exists(tf_path) or not os.path.exists(svg_path):
            req.status = "blocked"
            req.stage = "done"
            db.commit()
            logger.error(f"Required artifacts missing for {request_id} — blocked.")
            return

        # 4b. P6 — dispatch approval-request email (best-effort; mock-to-disk fallback)
        _stage("notifying")
        if NOTIFY_RECIPIENT:
            try:
                dash = f"{DASHBOARD_URL}/request/{request_id}"
                subject = f"[Migration Review] {source_platform.upper()} → {target_cloud.upper()} — action required"
                body = (
                    "<h2>Cloud Migration Analysis — Approval Requested</h2>"
                    f"<p><b>Migration:</b> {source_platform.upper()} &#8594; {target_cloud.upper()}</p>"
                    f"<p><b>Estimated monthly cost:</b> ${monthly_cost:.2f} USD &nbsp;|&nbsp; "
                    f"<b>Reliability:</b> {rel_score}/100</p>"
                    f"<h3>Security &amp; Compliance</h3><pre>{sec_summary}</pre>"
                    f"<p>Review the blueprint and record your decision:<br>"
                    f"<a href='{dash}'>{dash}</a></p>"
                    "<p>The full Report PDF and the architecture diagram are attached.</p>"
                )
                result = analysis.send_notification(request_id, NOTIFY_RECIPIENT, subject, body)
                logger.info(f"Notification for {request_id}: smtp_sent={result.get('smtp_sent')} ({result.get('mock_path')})")
            except Exception as e:  # noqa: BLE001 - email is a side channel, never blocks the gate
                logger.warning(f"Notification dispatch failed for {request_id}: {e}")

        # 5. Persist (overwrite in place across redrafts; ADR-8)
        req = db.query(MigrationRequest).filter(MigrationRequest.request_id == request_id).first()
        existing_bp = db.query(Blueprint).filter(Blueprint.request_id == request_id).first()
        if existing_bp:
            db.delete(existing_bp)
            db.commit()

        blueprint_id = str(uuid.uuid4())
        db.add(Blueprint(
            blueprint_id=blueprint_id, request_id=request_id, attempt_number=attempt,
            source_platform=source_platform, target_cloud_provider=target_cloud,
            terraform_code_ref=tf_path, architecture_diagram_ref=svg_path,
            validated_at=datetime.utcnow(), drafted_at=datetime.utcnow(),
        ))
        db.commit()

        for f in sec_findings:
            db.add(SecurityFinding(
                finding_id=str(uuid.uuid4()), blueprint_id=blueprint_id,
                severity=f.get("severity", "low"), description=f.get("description", ""),
                scanned_at=datetime.utcnow(),
            ))
        db.add(CostEstimate(
            estimate_id=str(uuid.uuid4()), blueprint_id=blueprint_id,
            monthly_cost=monthly_cost, currency="USD", rate_card_refs=rate_refs,
            generated_at=datetime.utcnow(),
        ))
        db.add(ReliabilityFinding(
            finding_id=str(uuid.uuid4()), blueprint_id=blueprint_id,
            redundancy_score=rel_score, notes=rel_notes, validated_at=datetime.utcnow(),
        ))
        db.add(ConsolidatedReport(
            report_id=str(uuid.uuid4()), blueprint_id=blueprint_id,
            report_pdf_ref=pdf_path, architecture_diagram_ref=svg_path,
            compiled_at=datetime.utcnow(),
        ))

        req.status = "in_review"
        req.stage = "gated"
        db.commit()
        logger.info(f"Migration request {request_id} processed -> in_review (attempt {attempt}).")

    except ValueError as e:
        # Resolution / validation failure — request cannot proceed
        logger.error(f"Analysis rejected for {request_id}: {e}")
        req = db.query(MigrationRequest).filter(MigrationRequest.request_id == request_id).first()
        if req:
            req.status = "blocked"
            req.stage = "done"
            db.commit()
    except Exception as e:
        logger.error(f"Error in background task for request {request_id}: {e}")
        req = db.query(MigrationRequest).filter(MigrationRequest.request_id == request_id).first()
        if req:
            req.status = "blocked"
            req.stage = "done"
            db.commit()
    finally:
        db.close()

# API Endpoints

@app.post("/api/v1/migration/request", status_code=201)
async def submit_migration_request(payload: SubmitRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """API-01: Submit Migration Request"""
    # Verify submitter
    user = db.query(UserAccount).filter(UserAccount.user_id == payload.submitted_by).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid submitted_by User ID.")

    # #10 — validate project.json against schema before creating any row/file
    try:
        spec = analysis.validate_project_json(payload.project_json)
        analysis.resolve_source_target(spec, payload.prompt, SUPPORTED_CLOUD_PROVIDERS)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid project.json: {e}")

    request_id = str(uuid.uuid4())
    
    # Save project.json locally under request folder
    dir_path = request_dir(request_id)
    json_path = os.path.join(dir_path, "project.json")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(payload.project_json)

    # Save to database
    req = MigrationRequest(
        request_id=request_id,
        submitted_by=payload.submitted_by,
        prompt=payload.prompt,
        project_json_ref=json_path,
        submitted_at=datetime.utcnow(),
        attempt_number=1,
        status="received"
    )
    db.add(req)
    db.commit()

    # Trigger background agent network execution
    background_tasks.add_task(run_analysis_workflow, request_id, payload.prompt, payload.project_json)

    return {"request_id": request_id, "status": "received"}

@app.get("/api/v1/migration/status/{request_id}")
async def get_request_status(request_id: str, db: Session = Depends(get_db)):
    """API-02: Get Request Status"""
    req = db.query(MigrationRequest).filter(MigrationRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    
    # Handle Expiration Gate timer (48 hours)
    if req.status == "in_review" and (datetime.utcnow() - req.submitted_at) > timedelta(hours=APPROVAL_WINDOW_HOURS):
        logger.info(f"Request {request_id} has expired (exceeded {APPROVAL_WINDOW_HOURS}h window). Discarding artifacts...")
        req.status = "expired"
        db.commit()
        # Delete generated files
        _cleanup_artifacts(request_id)

    return {
        "status": req.status,
        "stage": req.stage,
        "attempt_number": req.attempt_number,
        "max_redraft_attempts": MAX_REDRAFT_ATTEMPTS
    }

@app.get("/api/v1/migration/blueprint/{request_id}")
async def get_blueprint_detail(request_id: str, db: Session = Depends(get_db)):
    """API-03: Get Blueprint Detail"""
    bp = db.query(Blueprint).filter(Blueprint.request_id == request_id).first()
    if not bp:
        raise HTTPException(status_code=404, detail="Blueprint not found or request is in-progress.")
    
    return {
        "blueprint_id": bp.blueprint_id,
        "attempt_number": bp.attempt_number,
        "source_platform": bp.source_platform,
        "target_cloud_provider": bp.target_cloud_provider,
        "terraform_code_ref": bp.terraform_code_ref,
        "architecture_diagram_ref": bp.architecture_diagram_ref,
        "validated_at": bp.validated_at,
        "drafted_at": bp.drafted_at
    }

@app.get("/api/v1/migration/report/{request_id}")
async def get_consolidated_report(request_id: str, db: Session = Depends(get_db)):
    """API-04: Get Consolidated Report details"""
    req = db.query(MigrationRequest).filter(MigrationRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")

    bp = db.query(Blueprint).filter(Blueprint.request_id == request_id).first()
    if not bp or not bp.report:
        raise HTTPException(status_code=404, detail="Consolidated report not compiled yet.")

    # Calculate Risk Band
    risk_band = _calculate_risk_band(bp)

    # Fetch findings details
    security_findings = []
    worst_finding = "None"
    highest_sev = 0
    sev_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    for sf in bp.security_findings:
        security_findings.append({
            "severity": sf.severity,
            "description": sf.description
        })
        curr_sev = sev_map.get(sf.severity.lower(), 1)
        if curr_sev > highest_sev:
            highest_sev = curr_sev
            worst_finding = sf.description

    # Cost estimate details
    cost_est = bp.cost_estimates[0] if bp.cost_estimates else None
    monthly_cost = float(cost_est.monthly_cost) if cost_est else 0.0
    rate_refs = cost_est.rate_card_refs if cost_est else []

    # Reliability details
    reliability = bp.reliability_findings[0] if bp.reliability_findings else None
    red_score = reliability.redundancy_score if reliability else 0
    rel_notes = reliability.notes if reliability else ""

    # Decision details
    latest_decision = db.query(ApprovalDecision).filter(
        ApprovalDecision.request_id == request_id,
        ApprovalDecision.attempt_number == req.attempt_number
    ).first()

    return {
        "report_id": bp.report.report_id,
        "report_pdf_ref": bp.report.report_pdf_ref,
        "architecture_diagram_ref": bp.report.architecture_diagram_ref,
        "compiled_at": bp.report.compiled_at,
        "risk_band": risk_band,
        "findings_summary": {
            "security": {
                "count": len(security_findings),
                "worst_finding": worst_finding,
                "findings": security_findings
            },
            "cost": {
                "monthly_cost": monthly_cost,
                "rate_card_citations": rate_refs
            },
            "reliability": {
                "redundancy_score": red_score,
                "notes": rel_notes
            },
            "decision": {
                "status": req.status,
                "attempt_number": req.attempt_number,
                "decided_by": latest_decision.approver_id if latest_decision else None,
                "notes": latest_decision.rejection_notes if latest_decision else None
            }
        }
    }

@app.post("/api/v1/migration/decision/{request_id}")
async def submit_approval_decision(request_id: str, payload: SubmitDecision, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """API-05: Submit Approval Decision"""
    req = db.query(MigrationRequest).filter(MigrationRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")

    if req.status in ["approved", "rejected", "expired", "blocked"]:
        raise HTTPException(status_code=400, detail=f"Cannot submit decision against a terminal state: {req.status}")

    # Expiry Gate Check
    if (datetime.utcnow() - req.submitted_at) > timedelta(hours=APPROVAL_WINDOW_HOURS):
        req.status = "expired"
        db.commit()
        _cleanup_artifacts(request_id)
        raise HTTPException(status_code=400, detail="Decision rejected: The 48-hour approval window has expired.")

    # Check approver credentials
    approver = db.query(UserAccount).filter(
        UserAccount.user_id == payload.approver_id,
        UserAccount.role == "approver"
    ).first()
    if not approver:
        raise HTTPException(status_code=400, detail="Invalid approver ID or user is not authorized to approve.")

    # Record decision (Append-only)
    decision = ApprovalDecision(
        decision_id=str(uuid.uuid4()),
        request_id=request_id,
        attempt_number=req.attempt_number,
        approver_id=payload.approver_id,
        decision=payload.decision,
        rejection_notes=payload.rejection_notes,
        decided_at=datetime.utcnow()
    )
    db.add(decision)

    if payload.decision.lower() == "approved":
        req.status = "approved"
        db.commit()
        return {"status": "approved", "message": "Migration blueprint approved successfully."}

    elif payload.decision.lower() == "rejected":
        if req.attempt_number < MAX_REDRAFT_ATTEMPTS:
            # Under the cap: route back to P1 LeadArchitect for redraft
            req.attempt_number += 1
            req.status = "drafting"
            db.commit()

            # Read specs from disk to rerun
            json_path = req.project_json_ref
            with open(json_path, "r", encoding="utf-8") as f:
                project_json = f.read()

            background_tasks.add_task(
                run_analysis_workflow, 
                request_id, 
                req.prompt, 
                project_json, 
                feedback=payload.rejection_notes
            )
            return {
                "status": "drafting",
                "message": f"Blueprint rejected. Sent back for redraft (Attempt {req.attempt_number} of {MAX_REDRAFT_ATTEMPTS})."
            }
        else:
            # Reached attempt cap
            req.status = "rejected"
            db.commit()
            # Discard files
            _cleanup_artifacts(request_id)
            return {"status": "rejected", "message": "Blueprint rejected and maximum attempt cap reached. Files discarded."}

    raise HTTPException(status_code=400, detail="Invalid decision. Must be 'approved' or 'rejected'.")

@app.get("/api/v1/migration/list")
async def list_migration_requests(status_filter: Optional[str] = Query(None, alias="status"), db: Session = Depends(get_db)):
    """API-06: List Migration Requests for Dashboard"""
    query = db.query(MigrationRequest)
    if status_filter:
        query = query.filter(MigrationRequest.status == status_filter)
    
    requests = query.all()
    out = []
    for req in requests:
        bp = db.query(Blueprint).filter(Blueprint.request_id == req.request_id).first()
        target = f"{bp.source_platform.upper()} -> {bp.target_cloud_provider.upper()}" if bp else "Unknown"
        risk_band = _calculate_risk_band(bp) if bp else "low"
        
        # Get decision status
        latest_dec = db.query(ApprovalDecision).filter(
            ApprovalDecision.request_id == req.request_id
        ).order_by(ApprovalDecision.decided_at.desc()).first()
        
        decision = "pending"
        if latest_dec:
            decision = latest_dec.decision

        out.append({
            "request_id": req.request_id,
            "target": target,
            "status": req.status,
            "risk_band": risk_band,
            "decision": decision,
            "submitted_at": req.submitted_at.isoformat()
        })
    return out

@app.get("/api/v1/migration/pending/{approver_id}")
async def list_pending_approvals(approver_id: str, db: Session = Depends(get_db)):
    """API-07: List Pending Approvals for Approver"""
    # Verify approver
    user = db.query(UserAccount).filter(UserAccount.user_id == approver_id, UserAccount.role == "approver").first()
    if not user:
        raise HTTPException(status_code=404, detail="Approver not found.")

    requests = db.query(MigrationRequest).filter(MigrationRequest.status == "in_review").all()
    out = []
    for req in requests:
        bp = db.query(Blueprint).filter(Blueprint.request_id == req.request_id).first()
        target = f"{bp.source_platform.upper()} -> {bp.target_cloud_provider.upper()}" if bp else "Unknown"
        out.append({
            "request_id": req.request_id,
            "target": target,
            "submitted_at": req.submitted_at.isoformat()
        })
    return out

@app.get("/api/v1/migration/files/{request_id}/{filename}")
async def download_file(request_id: str, filename: str):
    """File download gateway endpoint to serve reports, diagrams and terraform files"""
    file_path = os.path.join(request_dir(request_id), filename)
    if not os.path.exists(file_path):
         raise HTTPException(status_code=404, detail="Requested file not found or deleted from disk.")
    media_type = None
    if filename.endswith(".svg"):
        media_type = "image/svg+xml"
    elif filename.endswith(".pdf"):
        media_type = "application/pdf"
    return FileResponse(file_path, media_type=media_type)

# Helper functions

def _calculate_risk_band(bp: Optional[Blueprint]) -> str:
    if not bp:
        return "low"
    
    # 1. Highest severity across security findings
    highest_severity = "low"
    sev_map = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    rev_sev = {1: "low", 2: "medium", 3: "high", 4: "critical"}
    
    for sf in bp.security_findings:
        if sev_map.get(sf.severity.lower(), 1) > sev_map.get(highest_severity, 1):
            highest_severity = sf.severity.lower()

    # 2. Map reliability score to scale
    rel_finding = bp.reliability_findings[0] if bp.reliability_findings else None
    rel_score = rel_finding.redundancy_score if rel_finding else 100
    
    rel_severity = "low"
    if rel_score < 30:
        rel_severity = "critical"
    elif rel_score < 60:
        rel_severity = "high"
    elif rel_score < 80:
        rel_severity = "medium"
        
    # Worst of two
    final_severity_val = max(sev_map[highest_severity], sev_map[rel_severity])
    return rev_sev[final_severity_val]

def _cleanup_artifacts(request_id: str):
    dir_path = request_dir(request_id)
    if os.path.exists(dir_path):
        for name in ["blueprint.tf", "report.pdf", "diagram.svg"]:
            f_path = os.path.join(dir_path, name)
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    logger.info(f"Cleaned up file: {f_path}")
                except Exception as e:
                    logger.error(f"Error removing file {f_path}: {e}")
