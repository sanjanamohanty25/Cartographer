# Implementation Plan — CI/CD Intelligence Layer Fixes + React Migration

**Companion:** [DRIFT_AND_ISSUES_REPORT.md](DRIFT_AND_ISSUES_REPORT.md), [FIX.md](FIX.md), [TASKLIST.md](TASKLIST.md).
**Rule:** execute phases in order. Update [TASKLIST.md](TASKLIST.md) after each task. No work outside this plan without asking.

## Decisions locked with user
- **LLM:** single NVIDIA NIM model for **all** agents (overrides LLD §6 per-agent table). Docs updated to match.
- **Frontend:** Streamlit fully replaced by React + Vite this pass.
- **.env:** created with variables + safe defaults; user pastes real `NVIDIA_API_KEY`. Test only after user confirms key.
- **Docs:** after code fixes, update every doc that drifts from the resulting codebase.

## Open decision (asking before Phase 2)
- **#3/#4 architecture:** how the DB gets its findings. See question raised alongside this plan. Default proposal: **gateway orchestrates the coded tools once as the deterministic source of truth (grounded, testable); neuro-san agent network is the LLM reasoning/narrative layer.** Removes the double-run bug and grounds cost, stays testable without depending on flaky LLM free-text JSON. Docs will be updated to describe this honestly.

---

## Phase 0 — Setup & scaffolding
- **0.1** Create `.env` (package root) with all LLD §2.1 vars + NVIDIA NIM defaults, empty `NVIDIA_API_KEY`.
- **0.2** Create `common/paths.py` + `coded_tools/_paths.py` (importable on `AGENT_TOOL_PATH`) path helpers — `__file__`-derived default + env override.
- **0.3** Add `__init__.py` to `common/`, `coded_tools/`, `coded_tools/migration_intelligence/`, `database/`, `gateway/`, `gateway/api/`, `gateway/invoker/`.

## Phase 1 — Dynamic paths (#1, #17, #18)
- **1.1** Strip hardcoded `KIIT` root from 7 tools → use `_paths` helper (`request_dir`, `cost_rate_card_path`).
- **1.2** Strip from `database/db_session.py` → `package_root()`.
- **1.3** Strip from `gateway/api/main.py` → helper; remove `PROJECT_ROOT`.
- **1.4** Wire `REQUEST_RESPONSE_ROOT`, `COST_RATE_CARD_PATH` env overrides.

## Phase 2 — Backend core (#3, #4, #5, #10, #11) — after open decision resolved
- **2.1** `#10` Pydantic model for `project.json`; validate at API-01, reject malformed (422) before any row/file.
- **2.2** `#5/#11` source/target resolution: single deterministic resolver, `SUPPORTED_CLOUD_PROVIDERS` allow-list, error (not default) on unknown. (If agent-driven per open decision, P1 returns them.)
- **2.3** `#4` cost: right-size SKUs from `project.json` utilization/storage, ground via `cost_reference_tool`, cite entry IDs, drop bad summation + AWS-only fallback.
- **2.4** `#3` remove duplicate tool re-run; single source of truth per open decision.

## Phase 3 — Coded tools (#6, #7, #8, #16, #19)
- **3.1** `#7` `terraform_validate_tool`: 3-attempt exponential backoff (2/4/8s), definitive invalid → blocked.
- **3.2** `#6/#16` `diagram_render_tool`: build graph from `resource_mappings`; local engine via `DIAGRAM_RENDER_ENGINE`; honor `DIAGRAM_OUTPUT_FORMAT`; `mermaid.ink` off by default, static SVG last resort.
- **3.3** `#8` `security_scan_tool`: parse Checkov JSON into findings, or drop dead branch (keep working regex mock).
- **3.4** `#19` `smtp_dispatch_tool`: require both PDF+SVG before send; else escalate.

## Phase 4 — LLM config (#9)
- **4.1** `config/llm_config.hocon` + registry: all agents → single NVIDIA NIM model. Remove per-agent/gpt-4o divergence.
- **4.2** `.env` NVIDIA NIM vars consumed by neuro-san.

## Phase 5 — Lifecycle + API (#2, #12)
- **5.1** `#2` add `max_redraft_attempts` to `GET /status` response.
- **5.2** `#12` keep poll-time expiry; add lightweight startup sweep task (documented ceiling).
- **5.3** `#6`/SVG: set `media_type="image/svg+xml"` on `/files` SVG for `<img>`.

## Phase 6 — React + Vite frontend (frontend migration)
- **6.1** Scaffold `dashboard-web/` (Vite React-TS) + deps (react-router, TanStack Query, mermaid).
- **6.2** `api/client.ts` + `types.ts` for all 7 endpoints; `vite.config.ts` proxy; `.env` `VITE_API_URL`.
- **6.3** Pages: `RequestList`, `RequestDetail`, `LaunchMigration`.
- **6.4** Components: `AgentGraph` (mermaid, live via polling), `StatusBadge`, `RiskBadge`, `FindingsPanel`, `DecisionForm`.
- **6.5** Remove `dashboard/app.py`; drop `streamlit` from `requirements.txt`.

## Phase 7 — Runner
- **7.1** `run.ps1`: launch neuro-san (8080) → gateway (8000) → Vite (5173); stream logs; Ctrl+C stops all; venv + node detection.

## Phase 8 — Tests + deploy parity (#13, #14, #15)
- **8.1** `#15` `tests/`: unit tests for 3 critic tools + API contract (API-01 reject, API-05 enum). Minimal, assert-based.
- **8.2** `#13` `deploy/docker-compose.yaml` (postgres + gateway + neuro-san + nginx-served React) as parity stub; SQLite stays dev default.
- **8.3** `#14/#15` doc-only: reportlab, custom_llm_info.hocon, alembic decision noted.

## Phase 9 — Install & verify
- **9.1** `pip install -r requirements.txt` (+ new deps).
- **9.2** `npm install` in `dashboard-web/`.
- **9.3** Install Playwright headless browser.
- **9.4** **STOP — ask user to paste `NVIDIA_API_KEY` into `.env`.**
- **9.5** Launch via `run.ps1`; headless-browser drive React: launch migration → agent graph → findings populate → approve/reject → file downloads. Report pass/fail with output.

## Phase 10 — Doc reconciliation
- **10.1** LLD §6: per-agent models → single NVIDIA NIM; add decision note.
- **10.2** `00 §9` + `HLD §13` stack tables: LLM providers → NVIDIA NIM; WeasyPrint→reportlab; Streamlit→React/Vite.
- **10.3** Update `DRIFT_AND_ISSUES_REPORT.md` (mark resolved) + `FIX.md` #9.
- **10.4** Update any diagram/text referencing Streamlit or per-agent LLMs.

## Verification gates
- Each phase: code compiles / imports clean.
- Phase 9: full headless E2E green (or LLM path flagged if key issue).
- Phase 10: no doc claims contradict shipped code.
