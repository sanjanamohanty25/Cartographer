# Task List — Fixes + React Migration

Status: ⬜ todo · 🔄 in progress · ✅ done · ⏭️ skipped · ❌ blocked
Updated after each task. Mirrors [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Phase 0 — Setup
- ✅ 0.1 Create `.env` with defaults (empty `NVIDIA_API_KEY`)
- ✅ 0.2 Path helper `coded_tools/migration_intelligence/_paths.py` (single canonical, self-check passed)
- ✅ 0.3 Add `__init__.py` to all packages

## Phase 1 — Dynamic paths (#1, #17, #18) ✅
- ✅ 1.1 Strip KIIT path from 7 tools
- ✅ 1.2 Strip from `db_session.py`
- ✅ 1.3 Strip from `gateway/api/main.py`
- ✅ 1.4 Wire `REQUEST_RESPONSE_ROOT`, `COST_RATE_CARD_PATH` (verified: 0 KIIT refs, AST parse OK)

## Phase 2 — Backend core (#3, #4, #5, #10, #11) ✅
- ✅ 2.1 project.json Pydantic validation at API-01 (#10) — `analysis.validate_project_json`, 422 on bad
- ✅ 2.2 source/target resolver + allow-list (#5, #11) — from structured spec, `SUPPORTED_CLOUD_PROVIDERS`
- ✅ 2.3 grounded + cited cost (#4) — right-size + `CostReferenceTool` grounding, storage from project.json, no AWS fallback
- ✅ 2.4 gateway orchestrates tools once as source of truth (#3) — removed duplicate re-run + keyword-match + bad cost loop; new `analysis.py`
- Decision: neuro-san = LLM draft layer; deterministic fallback draft when LLM unavailable (labeled). AST parse OK.

## Phase 3 — Coded tools (#6, #7, #8, #16, #19) ✅
- ✅ 3.1 terraform_validate retry/backoff 2/4/8s (#7) — `_validate_once` + loop
- ✅ 3.2 diagram from resource_mappings, builtin local SVG default, mermaid.ink opt-in (#6, #16)
- ✅ 3.3 checkov JSON parsed into findings, clean fallback (#8) — `_parse_checkov`
- ✅ 3.4 SMTP both-attachments gate (#19) — never dispatch partial (DFD §5)

## Phase 4 — LLM config (#9) ✅
- ✅ 4.1 all agents → single NVIDIA NIM model (network-level llm_config, env-driven model_name)
- ✅ 4.2 .env NVIDIA NIM vars consumed (NVIDIA_API_KEY, NVIDIA_NIM_MODEL)
- Note: HOCON parse validation deferred to Phase 9 (pyhocon not yet installed)

## Phase 5 — Lifecycle + API (#2, #12) ✅
- ✅ 5.1 max_redraft_attempts in /status (#2)
- ✅ 5.2 expiry sweep + init_db() on startup (#12) — nobody called init_db before; fixed
- ✅ 5.3 SVG/PDF media_type on /files

## Phase 6 — React + Vite (frontend) ✅
- ✅ 6.1 Scaffold dashboard-web (package.json, vite/tsconfig, index.html, .env, .gitignore)
- ✅ 6.2 api/client.ts + types.ts (direct API base, CORS) + main.tsx/App.tsx + styles
- ✅ 6.3 Pages: RequestList, RequestDetail (polling), LaunchMigration
- ✅ 6.4 Components: AgentGraph (mermaid), Badges, FindingsPanel, DecisionForm
- ✅ 6.5 Deleted dashboard/app.py; dropped streamlit from requirements.txt (added requests, pydantic, python-dotenv)

## Phase 7 — Runner ✅
- ✅ 7.1 run.ps1 (loads .env, neuro-san + gateway + vite, auto npm install, Ctrl+C tree-kill)

## Phase 8 — Tests + deploy (#13, #14, #15)
- ✅ 8.1 tests/ (test_tools.py, test_api.py) — runnable via pytest; execute in Phase 9
- ✅ 8.2 deploy/docker-compose.yaml parity stub (postgres+neuro-san+gateway+dashboard)
- ✅ 8.3 doc-only notes folded into Phase 10 (reportlab, custom_llm_info removed, create_all vs alembic)

## Phase 9 — Install & verify
- ✅ 9.1 pip install (venv .venv; neuro-san 0.6.69 + langchain-nvidia + fastapi/uvicorn/sqlalchemy/reportlab/pydantic + pytest) — all imports OK
- ✅ 9.2 npm install (dashboard-web; vite present)
- ✅ 9.3 Playwright chromium installed
- ✅ 9.1b pytest: 9/9 passed (tools + API contract; full workflow ran via fallback)
- ✅ 9.5 Headless E2E (deterministic path, no key):
  - Backend E2E PASS (submit→analyze→grounded cost $501.18 cited→files→approve)
  - Browser E2E PASS (headless chromium: UI launch→findings+diagram→approve)
  - Redraft PASS (reject→attempt 2→in_review; azure+mssql resolved, provider-correct citations)
  - Removed stale committed migration_intelligence.db (init_db recreates+seeds)
- ✅ 9.4 NVIDIA_API_KEY added by user
- ✅ 9.6 REAL-LLM E2E PASS — fixed 3 integration bugs found only with the live agent network:
  - registry cross-tree `include` failed (CWD-relative) → inlined llm_config + aaosa into registry (self-contained); deleted config/llm_config.hocon
  - neuro_san_client hit wrong route `/streaming_chat/LeadArchitect` (404) → `/api/v1/{network}/streaming_chat`
  - coded-tool resolution: absolute AGENT_TOOL_PATH collapsed module + collided with studio's coded_tools → AGENT_TOOL_PATH="coded_tools" (relative), neuro-san CWD=package root, studio on PYTHONPATH
  - Verified: agent authored real multi-resource HCL (VPC/subnets/RDS); scanner flagged the LLM's own 0.0.0.0/0 (critical); cost grounded+cited; browser E2E PASS on live stack

## ✅ ALL PHASES COMPLETE — 19/19 issues fixed, React migration done, real-LLM path verified.
- Env: Python 3.12.1, Node v22.11, npm 10.9. neuro-san==0.6.69 (pip).

## Phase 10 — Doc reconciliation ✅
- ✅ 10.1 LLD §6 single NVIDIA NIM decision + table
- ✅ 10.2 00 §9 stack table (LLM/reporting/UI/diagram/datastore) + HLD §13 summary
- ✅ 10.3 Drift report resolution banner + FIX.md #9 (single NVIDIA)
- ✅ 10.4 Streamlit→React, WeasyPrint→ReportLab, per-agent LLM→NVIDIA, PostgreSQL→SQLite/Postgres across 00/02/03/04; gateway-orchestration note in HLD §4.2; LLD §1 layout (dashboard-web, database/, no custom_llm_info/alembic)

## Phase 11 — Enhancements (redesign + detailed diagram + live graph + upload) ✅
- ✅ 11.1 Accurate `stage` tracking (schema col + workflow sets drafting→validating→diagram→scanning→reliability→costing→reporting→gated; /status exposes it)
- ✅ 11.2 Component-wise architecture diagram — analysis.build_resource_mapping (src→tgt pairs), dark SVG renderer; verified Oracle→RDS Multi-AZ, node→EC2, SAN SSD→EBS gp3, subnet→VPC+SG, backup→auto backups
- ✅ 11.3 Full dark redesign ("migration control room": Sora/Manrope/JetBrains Mono, cyan/blue, grid+glow) — build clean (90 modules)
- ✅ 11.4 Single custom animated SVG agent-flow (AgentFlow.tsx + lib/flow.ts): animated dataflow edges, pulsing active node from stage, settles on terminal — fixes blank box; verified mid-run (P1 active) + settled (P7 gate)
- ✅ 11.5 Launch page .json upload (segmented Template/Upload) — verified db2→gcp upload drove full pipeline (blueprint db2→gcp, GCP citations)
- ✅ 11.6 Verified via headless screenshots (list/running/report/launch) + upload-flow assertion

## ✅ PHASE 11 COMPLETE — all 5 enhancement asks delivered and screenshot-verified.

## Phase 12 — Architecture diagram upgrade (Option A) ✅
- ✅ Zoned AWS-reference-style SVG: ON-PREMISES DATA CENTER + REGION → VPC → PRIVATE SUBNET nesting, numbered service tiles with provider-colored icon glyphs (RDS/EC2/EBS/SG/BAK), migration-pipeline arrows + note pills.
- ✅ Provider-adaptive (aws/azure/gcp region + VPC/VNet + service codes) and real region label from project.json.
- ✅ Fixed region/VPC label overlap via explicit vertical bands. Screenshot-verified aws + gcp. Hand-built SVG, no new deps, stays in the download/email pipeline.

## Phase 13 — Correctness pass (stub blueprints + provider fidelity) ✅
- ✅ Stub/truncated LLM draft (e.g. `# [Rest of the configuration...]`, `...`) no longer accepted — `_is_complete_blueprint` requires ≥2 real `resource` blocks + no truncation markers, else deterministic fallback (was: blocked / empty scan).
- ✅ Provider-correct fallback HCL: aws (`aws_db_instance`/`aws_ebs_volume`/`aws_security_group`), azure (`azurerm_mssql_database`/`azurerm_managed_disk`/`azurerm_network_security_group`), gcp (`google_sql_database_instance`/`google_compute_disk`/`google_compute_firewall`) — real resource types + attributes.
- ✅ Provider-aware scanners: security flags `storage_encrypted`/`transparent_data_encryption_enabled`/`encrypted=false`, `publicly_accessible`/`public_network_access_enabled`/`ipv4_enabled=true`, `0.0.0.0/0`; reliability reads `multi_az`/`zone_redundant`/`availability_type=REGIONAL` + `backup_retention_period`/`retention_days`.
- ✅ Fixed reliability `"lb"` bare-substring false-positive (inflated score to 100) → precise LB/replica/count regex.
- ✅ Redraft correctness: clear prior-attempt artifacts at workflow start so a redraft never reuses a stale blueprint/diagram/report.
- ✅ +3 regression tests (stub→fallback, provider-correct fallback, azure high-risk scan). Suite 12/12. Live E2E: postgres_aws_saas.json → in_review, 7-resource blueprint, grounded cost, correct risk band + AWS diagram.

## Notes / deviations
_(appended as work proceeds)_
