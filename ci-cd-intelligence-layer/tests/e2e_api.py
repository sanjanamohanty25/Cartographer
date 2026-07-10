"""Backend E2E — drives the live Gateway API through the full lifecycle.
Assumes the gateway is running on :8000. Neuro-SAN optional (fallback draft).

Run: python tests/e2e_api.py
"""
import sys
import time
import json
import requests

API = "http://localhost:8000"

SPEC = {
    "migration_scope": {"target_cloud_provider": "aws", "preferred_region": "us-east-1"},
    "database_source_profile": {
        "database_engine": "Oracle Database Enterprise Edition",
        "hardware": {"ram_gb_per_node": 64, "storage_capacity_tb": 2.5},
        "security_posture": {"data_at_rest_encrypted": True, "public_access_permitted": False},
    },
    "reliability_requirements": {"high_availability_required": True, "backup_retention_days": 14},
}


def main():
    r = requests.post(f"{API}/api/v1/migration/request", json={
        "submitted_by": "stakeholder-123",
        "prompt": "Migrate our legacy Oracle database to AWS, optimize for high availability",
        "project_json": json.dumps(SPEC),
    }, timeout=20)
    assert r.status_code == 201, f"submit failed: {r.status_code} {r.text}"
    rid = r.json()["request_id"]
    print(f"submitted: {rid}")

    # poll for terminal-of-analysis
    status = None
    for _ in range(60):
        s = requests.get(f"{API}/api/v1/migration/status/{rid}", timeout=10).json()
        status = s["status"]
        if status in ("in_review", "blocked"):
            break
        time.sleep(2)
    print(f"analysis status: {status}")
    assert status == "in_review", f"expected in_review, got {status}"
    assert "max_redraft_attempts" in s

    rep = requests.get(f"{API}/api/v1/migration/report/{rid}", timeout=10).json()
    fs = rep["findings_summary"]
    assert fs["cost"]["monthly_cost"] > 0, "cost not grounded"
    assert fs["cost"]["rate_card_citations"], "no cost citations"
    assert fs["reliability"]["redundancy_score"] >= 0
    print(f"report OK: cost=${fs['cost']['monthly_cost']} cites={fs['cost']['rate_card_citations']} risk={rep['risk_band']}")

    # files served
    for name, ctype in (("diagram.svg", "svg"), ("report.pdf", "pdf"), ("blueprint.tf", "")):
        fr = requests.get(f"{API}/api/v1/migration/files/{rid}/{name}", timeout=10)
        assert fr.status_code == 200, f"{name} not served: {fr.status_code}"
    print("files served: diagram.svg, report.pdf, blueprint.tf")

    dec = requests.post(f"{API}/api/v1/migration/decision/{rid}", json={
        "approver_id": "approver-456", "decision": "approved",
    }, timeout=10)
    assert dec.status_code == 200, f"decision failed: {dec.text}"
    final = requests.get(f"{API}/api/v1/migration/status/{rid}", timeout=10).json()
    assert final["status"] == "approved", f"expected approved, got {final['status']}"
    print("APPROVED — backend E2E PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"BACKEND E2E FAIL: {e}")
        sys.exit(1)
