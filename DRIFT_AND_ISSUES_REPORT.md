# CI/CD Intelligence Layer — Drift & Issues Report

**Scope:** `ci-cd-intelligence-layer/` only. `neuro-san-studio/` excluded (cloned framework, not authored here).
**Baseline docs:** `docs/00-problem-statement.md` (authoritative) + `01-dfd`, `02-hld`, `03-lld`, `04-architecture-diagram`.
**Date:** 2026-07-10.

Legend: 🔴 blocker (won't run / core promise broken) · 🟠 major drift (behaves differently than spec) · 🟡 minor drift / gap.

---

## ✅ RESOLUTION STATUS (2026-07-10)

**All 19 issues fixed.** See [FIX.md](FIX.md) for per-issue fixes and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) / [TASKLIST.md](TASKLIST.md) for execution. Highlights:
- **#1** dynamic paths (`coded_tools/migration_intelligence/_paths.py`, `__file__`-derived + env override) — 0 hardcoded refs.
- **#2** `max_redraft_attempts` now served by `/status`; React UI reads it (no undefined var).
- **#3/#4** gateway orchestrates the coded tools **once** as source of truth (new `gateway/api/analysis.py`); cost right-sized + rate-card-grounded + cited; duplicate re-run and bad summation removed.
- **#5/#10/#11** project.json Pydantic-validated at API-01; source/target resolved from the validated spec with `SUPPORTED_CLOUD_PROVIDERS` allow-list.
- **#6/#7/#8/#16/#19** diagram derived from resource mapping (local SVG default), validate retry/backoff, checkov JSON parsed, SMTP both-attachments gate.
- **#9** single NVIDIA NIM model for all agents (user decision; docs updated).
- **Frontend** migrated Streamlit → **React + Vite** (`dashboard-web/`); `run.ps1` launches the whole stack.
- **Verified headless:** pytest 9/9; backend E2E (grounded cost, files, approve); browser E2E (chromium, full UI flow); reject→redraft cycle. LLM path pending real `NVIDIA_API_KEY`.

Individual entries below are retained as the original findings record.

---

## Summary

Code compiles and the FastAPI + Streamlit + Neuro-SAN scaffold is wired, but **it does not run on any machine except the original author's**, and the **multi-agent analysis is largely decorative** — the persisted findings come from the gateway re-running two tools + an inline cost calc in Python, not from the agent network. Several core doc promises (LLM extraction of source/target, rate-card-grounded cost with citation rejection, resource-derived architecture diagram, per-agent LLM assignment) are not implemented as specified.

| #   | Issue                                                                                            | Severity |
| --- | ------------------------------------------------------------------------------------------------ | -------- |
| 1   | Hardcoded absolute path `c:\Users\KIIT\New folder\...` in 9 files                                | 🔴       |
| 2   | Dashboard `MAX_REDRAFT_ATTEMPTS` undefined → NameError on detail page                            | 🔴       |
| 3   | Agent network output discarded; gateway re-runs tools in Python                                  | 🔴       |
| 4   | Cost estimate not grounded/cited by FinOps agent; wrong summation logic                          | 🔴       |
| 5   | Source/target extracted by gateway keyword-match, not by P1 LLM                                  | 🟠       |
| 6   | Architecture diagram is a fixed template, ignores resource mapping                               | 🟠       |
| 7   | terraform_validate: no deterministic retry/backoff per ADR-11/§12                                | 🟠       |
| 8   | Checkov CLI branch never parses output → 0 findings if installed                                 | 🟠       |
| 9   | Per-agent LLM assignment (LLD §6) not implemented; single model                                  | 🟠       |
| 10  | project.json stored as raw file, no schema validation at API-01                                  | 🟠       |
| 11  | `SUPPORTED_CLOUD_PROVIDERS` allow-list not enforced                                              | 🟠       |
| 12  | Expiry only evaluated on GET/POST poll; no gate timer                                            | 🟡       |
| 13  | PostgreSQL → SQLite; no `deploy/` (docker-compose, k8s)                                          | 🟡       |
| 14  | WeasyPrint → reportlab; stack-table drift                                                        | 🟡       |
| 15  | Missing `db/migrations` (Alembic), `tests/`, `custom_llm_info.hocon`                             | 🟡       |
| 16  | Diagram render depends on external `mermaid.ink` API                                             | 🟡       |
| 17  | Env vars in LLD §2.1 mostly unused (`REQUEST_RESPONSE_ROOT`, `COST_RATE_CARD_PATH`, `DIAGRAM_*`) | 🟡       |
| 18  | No `__init__.py`; gateway imports rely on namespace-package luck                                 | 🟡       |
| 19  | SMTP does not gate on both attachments existing (DFD invariant)                                  | 🟡       |

---

## 🔴 Blockers

### 1. Hardcoded absolute path in 9 files

Every tool + `db_session.py` + `gateway/api/main.py` hardcodes:

```python
project_root = r"c:\Users\KIIT\New folder\ci-cd-intelligence-layer"
```

Files: `cost_reference_tool.py`, `diagram_render_tool.py`, `reliability_check_tool.py`, `report_render_tool.py`, `security_scan_tool.py`, `smtp_dispatch_tool.py`, `terraform_validate_tool.py`, `database/db_session.py`, `gateway/api/main.py`.

**Impact:** On any other machine, `os.makedirs` either fails or writes files to a phantom `c:\Users\KIIT\...` tree — never to the repo's `request_response/`. Gateway then checks the repo path (also KIIT), so tf/pdf/svg "missing" → every request → `blocked`. Nothing works off the author's box.
**Doc conflict:** LLD §2.1 specifies `REQUEST_RESPONSE_ROOT` and `COST_RATE_CARD_PATH` env vars for exactly this. Unused.
**Fix:** derive root from `__file__` or read the env vars. One shared helper.

### 2. `MAX_REDRAFT_ATTEMPTS` undefined in dashboard

`dashboard/app.py:249` renders `{attempt_num} / {MAX_REDRAFT_ATTEMPTS}` but the name is never defined or imported in that file (only exists in `gateway/api/main.py`).
**Impact:** `NameError` the moment any request-detail page renders → Page 2 (the core gating UI, LLD §9.2) crashes.
**Fix:** `MAX_REDRAFT_ATTEMPTS = int(os.environ.get("MAX_REDRAFT_ATTEMPTS", 4))` in the dashboard.

### 3. Multi-agent output discarded; gateway re-runs tools

`run_analysis_workflow` (main.py) calls the Neuro-SAN network, but only inspects the response for `"error"` and for file existence. It then **re-instantiates and re-invokes `SecurityScanTool` and `ReliabilityCheckTool` directly in Python** (main.py:136–195) to populate the DB, and computes cost inline. P2/P4 agent reasoning, P5 ExecutiveReviewer synthesis, and P6 output are never parsed into the data model.
**Impact:** The "network of specialized agents running parallel assessments" (00 §4, HLD §4.2) contributes nothing to the persisted findings — it's a side-effect trigger for writing `blueprint.tf`. The system is effectively single-process Python analysis wearing an agent costume. Also duplicates work and re-reads `blueprint.tf` from the hardcoded path.
**Doc conflict:** DFD §3.2 (P5 merges the three critics' findings), HLD QA1/§5.1.
**Fix:** parse structured agent findings from the stream response and persist those; drop the in-gateway re-run.

### 4. Cost estimate neither grounded nor cited correctly

Docs (00 §7-P3, ADR-7, QA6, HLD risk row): P3 calls `cost_reference_tool`, cites the rate-card entry ID per line item, and a citation to a non-existent ID is rejected+retried. The tool implements the rejection correctly — **but the gateway never uses the tool.** Instead (main.py:152–171):

```python
for item in card:
    if item["provider"] == target_cloud:
        if item["type"] in ["compute", "database"]:
            monthly_cost += float(item["monthly_rate"])   # sums EVERY compute+db entry
        elif item["type"] == "storage":
            monthly_cost += float(item["monthly_rate"]) * 500
```

**Impact:**

- Sums **all** compute AND all database SKUs for the provider (e.g. aws: t3.micro + t3.medium + m5.large + rds-t3 + rds-m5-multiaz), which is meaningless — no right-sizing from utilization metrics (contradicts 00 §7-P3 "map utilization to right-sized instances").
- Storage hardcoded at 500 GB regardless of `project.json` (`storage_capacity_tb: 2.5`).
- Fallback `monthly_cost = 150.00; rate_refs = ["aws-ec2-t3-medium"]` cites an **AWS** entry even for azure/gcp requests → false citation, the exact failure QA6 forbids.
- The tool's "reject invalid citation ID" guarantee is bypassed entirely on the persisted path.
  **Fix:** let FinOpsAgent/`cost_reference_tool` produce the estimate and citations; persist those.

---

## 🟠 Major Drift

### 5. Source/target resolution done by gateway, not P1

Docs (00 §7-P1, DFD §3.1, LLD §4.2): P1 (LLM) parses the prompt to extract `source_platform` + `target_cloud_provider`, persists the resolved values so P2–P4 read one consistent pair. Actual: `main.py:99–111` does Python substring matching (`if "azure" in prompt.lower()`), defaulting to `oracle`/`aws`. The agent's parse (if any) is ignored.
**Impact:** "PostgreSQL"/"MySQL" sources (offered in the dashboard dropdown) both silently fall through to `oracle`. Target defaults to `aws` on any unrecognized string.

### 6. Architecture diagram is a fixed placeholder

`diagram_render_tool._generate_mermaid` ignores `resource_mappings` entirely and always emits the same 3-node generic graph; the fallback SVG is fully static HTML. ADR-6 / 00 §7-P1 require the diagram to be "derived from the same resource mapping used to draft the `.tf` code."
**Impact:** Every request produces an identical diagram; it does not reflect the proposed resources. The "show, don't just tell" design principle (00 §5.5) is not met.

### 7. terraform_validate has no retry/backoff

ADR-11 + LLD §12: "Retry with exponential backoff (3 attempts, 2s/4s/8s); if still failing, set status `blocked`." The tool runs a single validate; retry is delegated to LLM prose ("if it fails, fix and validate again"). No deterministic backoff, no attempt counter, no guaranteed `blocked` transition from the tool.

### 8. Checkov branch produces zero findings

`security_scan_tool.py:36–44`: if `checkov` is on PATH, it runs the subprocess but **never parses the JSON** (`is_mock_run = False`, `findings` stays `[]`). So a machine that actually has Checkov installed reports **no** security findings — worse than the mock path.
**Impact:** The one "real" static-scan integration is a no-op; only the regex mock works.

### 9. Per-agent LLM assignment not implemented

LLD §6 assigns distinct models (P1 GPT-4o, P3 Haiku, P5 Sonnet, etc.). Actual: `config/llm_config.hocon` sets a single global fallback to `nvidia mistral-small`; the registry's top-level `llm_config` is `gpt-4o`. No agent overrides its model. Also depends on `NVIDIA_API_KEY` (per PROGRESS.md) with no `.env` shipped.

### 10. project.json stored as a raw file, not validated/structured

Docs (ADR-5, 00 §9 note, LLD §12 first row): ingest `project.json` into schema-validated relational fields; reject malformed payload at API-01. Actual: API-01 writes the raw string to disk and stores a path in `project_json_ref`. No JSON parse, no schema validation, no derived fields. A malformed body is accepted and only fails later inside an agent.

### 11. `SUPPORTED_CLOUD_PROVIDERS` allow-list not enforced

LLD §2.1 + 00 §7-P1: "P1 rejects a prompt naming a target outside this list rather than guessing." No such check anywhere; unknown targets default to `aws`.

---

## 🟡 Minor Drift / Gaps

### 12. Expiry has no timer

The 48h expiry (P7) is only evaluated inside `GET /status` and `POST /decision`. If nobody polls, a request sits in `in_review` forever. Docs model a gate timer that starts on dispatch. Acceptable for a demo, but it is drift.

### 13. Datastore + deployment artifacts

- Docs mandate **PostgreSQL** (ADR-5) with `docker-compose` (postgres:16) and `deploy/k8s/`. Actual: SQLite default, and **no `deploy/` directory at all** (neither compose nor k8s). LLD §10 artifacts don't exist.

### 14. Reporting engine substitution

Stack table (00 §9, HLD §13) names **WeasyPrint**; code uses **reportlab**. Functionally fine, but the documented stack is wrong.

### 15. Missing project-layout items (LLD §1)

Absent: `config/custom_llm_info.hocon` (referenced in layout), `db/migrations/` (Alembic — code uses `Base.metadata.create_all` instead), `tests/` (only a root-level `test_real.py` smoke script exists — no unit/integration/contract/e2e suites from LLD §11).

### 16. Diagram render reaches out to the internet

`diagram_render_tool` calls `https://mermaid.ink/svg/...`. Docs specify **Mermaid CLI / Graphviz** (local). External dependency + latency + offline-fragility; falls back to the static SVG (see #6).

### 17. Documented env vars unused

`REQUEST_RESPONSE_ROOT`, `COST_RATE_CARD_PATH`, `DIAGRAM_OUTPUT_FORMAT`, `DIAGRAM_RENDER_ENGINE` (LLD §2.1) are never read. Paths and formats are hardcoded (see #1, #6).

### 18. No `__init__.py` — imports rely on namespace packages

`gateway/api/main.py` does `from database...`, `from gateway.invoker...`, `from coded_tools.migration_intelligence...`. No package `__init__.py` exists; this works only via PEP-420 namespace packages with cwd on `sys.path` (fragile across launch methods).

### 19. SMTP does not enforce both-attachments invariant

DFD §5 invariant: P6 never sends with an attachment missing. `smtp_dispatch_tool` attaches PDF/SVG only "if exists" and sends regardless — a missing diagram silently ships a one-attachment email.

---

## What is correct / matches docs

- Overall service topology (Neuro-SAN + FastAPI gateway + Streamlit dashboard) and `run.py` orchestration.
- HOCON agent network P1–P6 with AAOSA wiring, downstream fan-out to P2/P3/P4, and P7 as deterministic gateway logic (not an agent) — matches LLD §3.
- Coded-tool folder/name convention (`coded_tools/migration_intelligence/` matching network name) resolves correctly against `AGENT_TOOL_PATH`.
- DB schema (`schema.py`) matches LLD §8 data contracts closely: 1:1 request↔blueprint, append-only `approval_decision`, cascade delete of findings/report, no `deployment_execution`.
- Redraft/cap/approve/reject/expire state machine in `submit_approval_decision` matches 00 §8 and DFD §3.3 (cap check, in-place overwrite via delete+reinsert, file cleanup on non-approved terminal, rows retained).
- `cost_reference_tool` itself correctly rejects citations to non-existent rate-card IDs (QA6) — it's just not used by the gateway (#4).
- Role separation enforced (submitter ≠ approver) at API-05.
- Dashboard = two pages, no aggregate success % shown, non-clickable discarded rows with inline note — matches LLD §9.
- `report_render_tool` renders the three unfiltered pillars (Risk/Cost/Resilience) — matches P5 spec / Design Principle 6.

---

## Recommended fix order

1. **#1** hardcoded paths (nothing runs without it) → **#2** dashboard NameError → **#3/#4** make the agent network actually feed the DB and ground cost. These four restore a working, honest system.
2. Then **#5, #6, #7, #8** to make P1/P2/P3 behave as specified.
3. **#10, #11** for input integrity; **#9, #13–#19** are polish/parity with the stated stack.
