# CI/CD Intelligence Layer — Fix Plan

Companion to [DRIFT_AND_ISSUES_REPORT.md](DRIFT_AND_ISSUES_REPORT.md). One entry per issue, same numbering. Each: **what**, **where**, **fix** (concrete). Last section = Streamlit → React + Vite migration.

Legend: 🔴 blocker · 🟠 major · 🟡 minor.

---

## Shared prerequisite — kill the hardcoded root (blocks #1, #3, #4, #6, #16, #17)

Add one path helper, use it everywhere. This single change unblocks most of the 🔴 list.

`ci-cd-intelligence-layer/common/paths.py` (new):
```python
import os

# repo root = parent of this file's parent (common/ -> ci-cd-intelligence-layer/)
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def request_response_root() -> str:
    root = os.environ.get("REQUEST_RESPONSE_ROOT", os.path.join(_PKG_ROOT, "request_response"))
    os.makedirs(root, exist_ok=True)
    return root

def request_dir(request_id: str) -> str:
    d = os.path.join(request_response_root(), request_id)
    os.makedirs(d, exist_ok=True)
    return d

def cost_rate_card_path() -> str:
    return os.environ.get("COST_RATE_CARD_PATH", os.path.join(_PKG_ROOT, "config", "cost_rate_card.json"))

def package_root() -> str:
    return _PKG_ROOT
```
Add empty `common/__init__.py`. Then in every tool + `db_session.py` + `gateway/api/main.py`, delete the `project_root = r"c:\Users\KIIT\..."` line and use these helpers.

---

## 🔴 Blockers

### 1. Hardcoded absolute path (9 files)
**Where:** all 7 tools, `database/db_session.py`, `gateway/api/main.py`.
**Fix:** use the helper above.
- Tools: `dir_path = request_dir(request_id)`; `tf_path = os.path.join(dir_path, "blueprint.tf")` etc. Cost tool: `rate_card_path = cost_rate_card_path()`.
- `db_session.py`: `db_path = os.path.join(package_root(), "database", "migration_intelligence.db")` (keep the `DATABASE_URL` env override in front).
- `main.py`: replace `PROJECT_ROOT` uses with `request_dir()` / `package_root()`.

### 2. `MAX_REDRAFT_ATTEMPTS` undefined in dashboard
**Where:** `dashboard/app.py:249`.
**Fix (Streamlit, if kept short-term):** near top, `MAX_REDRAFT_ATTEMPTS = int(os.environ.get("MAX_REDRAFT_ATTEMPTS", 4))`.
**Better:** expose it from the API so the UI never guesses — add to the `GET /status` response: `"max_redraft_attempts": MAX_REDRAFT_ATTEMPTS`, and read it from `status_data`. (This also serves the React rewrite.)

### 3. Agent network output discarded; gateway re-runs tools
**Where:** `gateway/api/main.py` `run_analysis_workflow` (136–195); `gateway/invoker/neuro_san_client.py`.
**Fix:**
1. Have each critic agent return a **structured JSON block** in its final AAOSA `Response` (instruct in the HOCON: "return findings as a JSON object `{severity, description}[]` / `{monthly_cost, currency, rate_card_refs}` / `{redundancy_score, notes}`").
2. In `neuro_san_client`, keep accumulating streamed lines but extract the frontman's final consolidated payload (last message with the merged findings). Return it structured.
3. In `run_analysis_workflow`, parse that payload into `SecurityFinding` / `CostEstimate` / `ReliabilityFinding`. **Delete** the direct `SecurityScanTool()` / `ReliabilityCheckTool()` re-invocations and the inline cost loop.
- Pragmatic fallback if the LLM payload is unreliable: have the **tools themselves persist** their structured result to `request_dir/<name>.json`, and the gateway reads those files (still tool-produced, single source of truth) instead of re-running. Pick one; do not keep both the agent path and the re-run path.

### 4. Cost estimate not grounded/cited; wrong summation
**Where:** `gateway/api/main.py:152–171`.
**Fix:** remove the inline loop entirely. FinOpsAgent must call `cost_reference_tool` with the **specific** SKU IDs it right-sized from `project.json` utilization metrics, and return `{monthly_cost, currency, rate_card_refs}`. Persist those.
- Right-sizing rule (make it explicit, not "sum everything"): pick one compute SKU + one database SKU matching the source vCPU/RAM band, + storage = `rate * storage_capacity_gb` (from `project.json`, not a hardcoded 500).
- Kill the `monthly_cost = 150.00; rate_refs = ["aws-ec2-t3-medium"]` fallback — never cite an AWS ID for azure/gcp. If no match, surface the `cost_reference_tool` rejection (QA6) and mark P3 blocked per LLD §12.

---

## 🟠 Major Drift

### 5. Source/target resolved by gateway keyword-match
**Where:** `main.py:99–111`.
**Fix:** have P1 return resolved `{source_platform, target_cloud_provider}` in its structured payload (extends #3). Gateway persists P1's values into `Blueprint`, no substring matching. If P1 can't identify them → validation error to submitter (DFD §3.1 `ERR`), not a silent `oracle`/`aws` default.

### 6. Architecture diagram is a fixed template
**Where:** `coded_tools/.../diagram_render_tool.py` `_generate_mermaid`.
**Fix:** build the Mermaid/Graphviz graph **from `resource_mappings`** actually passed in (the tool already receives the arg — use it). Parse the resource list P1 mapped and emit one node per resource + edges from the topology. Drive engine/format from `DIAGRAM_RENDER_ENGINE` / `DIAGRAM_OUTPUT_FORMAT` (#17). Prefer local Mermaid CLI/Graphviz over `mermaid.ink` (#16); keep the static SVG only as a true last-resort fallback.

### 7. terraform_validate: no retry/backoff
**Where:** `terraform_validate_tool.py`.
**Fix:** wrap validation in a loop — 3 attempts, sleeps 2/4/8s, per ADR-11/§12. Return a definitive `{"status":"invalid"}` after exhaustion so the orchestrator sets `blocked`. Keep the mock `_check_syntax` as the no-binary fallback, but still honor the retry contract.
```python
for i, delay in enumerate((2, 4, 8)):
    ok, errs = self._validate_once(...)
    if ok: return {"status": "valid", ...}
    if i < 2: time.sleep(delay)
return {"status": "invalid", "errors": ...}
```

### 8. Checkov branch returns 0 findings
**Where:** `security_scan_tool.py:36–44`.
**Fix:** parse Checkov JSON into findings, or (lazy, honest) drop the dead branch and keep only the regex mock until real parsing is implemented — don't ship a branch that silently zeroes findings. If parsing: map `results.failed_checks[]` → `{id: check_id, severity, description: check_name}`.

### 9. LLM assignment — DECISION: single NVIDIA NIM model for all agents
**Where:** `config/llm_config.hocon`.
**Decision (user-directed):** do NOT split models per agent. All agents (P1–P6) inherit one
network-level NVIDIA NIM model (`mistralai/mistral-small-4-119b-2603`, env-overridable via
`NVIDIA_NIM_MODEL`). `NVIDIA_API_KEY` read from `.env`. LLD §6 and the 00/HLD stack tables
updated to describe the single-model design (per-agent GPT-4o/Claude split retired).

### 10. project.json unvalidated raw file
**Where:** `main.py` `submit_migration_request` (API-01).
**Fix:** parse + validate the body against a Pydantic model mirroring `sample_files/project.json` (migration_scope, database_source_profile, reliability_requirements). Reject malformed at API-01 with a structured 422 (LLD §12 row 1) **before** creating any row/file. Persist key derived fields to columns if you want true "structured store" (ADR-5); at minimum validate.

### 11. `SUPPORTED_CLOUD_PROVIDERS` allow-list unenforced
**Where:** P1 resolution path (with #5).
**Fix:** `allowed = os.environ.get("SUPPORTED_CLOUD_PROVIDERS","aws,azure,gcp").split(",")`. If P1's resolved target ∉ allowed → validation error, do not default.

---

## 🟡 Minor Drift / Gaps

### 12. Expiry has no timer
**Fix:** lazy — keep the poll-time check but also add a lightweight sweep: a startup `asyncio` task (or APScheduler if already present) that every N minutes moves overdue `in_review` → `expired` + cleanup. Avoids "sits forever if nobody polls." `# ponytail: poll-based sweep, upgrade to real scheduler if request volume grows.`

### 13. PostgreSQL + deploy artifacts
**Fix:** keep SQLite default for dev, but make Postgres real via `DATABASE_URL` (already supported in `db_session.py`). Add `deploy/docker-compose.yaml` (postgres:16 + gateway + neuro-san + the new React app served by nginx) and `deploy/k8s/` stubs per LLD §10. Document that SQLite is dev-only.

### 14. WeasyPrint vs reportlab
**Fix:** cheapest = update the stack tables (00 §9, HLD §13) to say reportlab — the code works. Only swap to WeasyPrint if HTML/CSS templating is actually wanted. Recommend doc edit, not code churn.

### 15. Missing layout items
**Fix:** add `tests/` with the LLD §11 cases (start with unit tests for the 3 critic tools + an API contract test for API-01/API-05), `db/migrations/` via `alembic init` (or document that `create_all` is the chosen dev approach), and `config/custom_llm_info.hocon` (or remove it from the LLD layout if unused).

### 16. Diagram render hits mermaid.ink
**Fix:** folded into #6 — prefer local render engine, external API off by default.

### 17. Documented env vars unused
**Fix:** wired by the shared helper (#1) + #6. Ensure `REQUEST_RESPONSE_ROOT`, `COST_RATE_CARD_PATH`, `DIAGRAM_OUTPUT_FORMAT`, `DIAGRAM_RENDER_ENGINE` are all read.

### 18. No `__init__.py`
**Fix:** add `__init__.py` to `coded_tools/`, `coded_tools/migration_intelligence/`, `database/`, `gateway/`, `gateway/api/`, `gateway/invoker/`, `common/`. Removes reliance on namespace-package + cwd luck.

### 19. SMTP one-attachment invariant
**Where:** `smtp_dispatch_tool.py`.
**Fix:** before sending, require both `has_pdf and has_svg`; if either missing → return error / escalate instead of shipping a partial email (DFD §5 invariant). Still write the mock JSON for the demo.

---

## Dashboard migration — Streamlit → React + Vite

The dashboard already talks only to the gateway REST API, so this is a **frontend replacement, not a backend change**. Gateway CORS is already `*` (main.py:27) — keep it (tighten to the Vite origin in prod).

### Target stack
- **Vite + React + TypeScript** (`npm create vite@latest dashboard-web -- --template react-ts`).
- Data fetching: **TanStack Query** (polling for live agent-graph updates) + `axios`/`fetch`.
- Routing: **react-router-dom** — `/` (list) and `/request/:id` (detail).
- Diagram: **mermaid** npm package for the agent-network graph; the P1 architecture diagram is served as SVG by the gateway (`/files/{id}/diagram.svg`) — render via `<img>`.
- Styling: keep it light — CSS modules or Tailwind. Port the existing badge palette from `dashboard/app.py` CSS.

### Folder layout (`ci-cd-intelligence-layer/dashboard-web/`)
```
dashboard-web/
├── index.html
├── vite.config.ts            # proxy /api -> http://localhost:8000
├── .env                      # VITE_API_URL=http://localhost:8000
├── src/
│   ├── main.tsx
│   ├── App.tsx               # router + QueryClientProvider
│   ├── api/client.ts         # typed wrappers for API-01..07
│   ├── types.ts              # RequestSummary, ReportDetail, etc.
│   ├── pages/
│   │   ├── RequestList.tsx   # replaces render_request_list()
│   │   ├── RequestDetail.tsx # replaces render_request_detail()
│   │   └── LaunchMigration.tsx # replaces render_create_request()
│   ├── components/
│   │   ├── AgentGraph.tsx    # mermaid, replaces render_agent_graph()
│   │   ├── StatusBadge.tsx
│   │   ├── RiskBadge.tsx
│   │   ├── FindingsPanel.tsx
│   │   └── DecisionForm.tsx  # replaces _submit_decision()
│   └── styles/badges.css
```

### API client (mirror the 7 endpoints)
```ts
// src/api/client.ts
const BASE = import.meta.env.VITE_API_URL ?? "";
export const listRequests = () => get(`/api/v1/migration/list`);
export const getStatus   = (id: string) => get(`/api/v1/migration/status/${id}`);
export const getReport   = (id: string) => get(`/api/v1/migration/report/${id}`);
export const submitDecision = (id: string, body: DecisionBody) =>
  post(`/api/v1/migration/decision/${id}`, body);
export const submitRequest  = (body: SubmitBody) => post(`/api/v1/migration/request`, body);
export const fileUrl = (id: string, name: string) => `${BASE}/api/v1/migration/files/${id}/${name}`;
```

### Page-by-page port
| Streamlit (`app.py`) | React equivalent |
|---|---|
| `render_request_list()` | `RequestList.tsx` — table of `listRequests()`; status/risk/decision filter dropdowns; row click → `/request/:id`; discarded (`rejected`/`expired`) rows non-clickable with inline note (LLD §9.1). |
| `render_request_detail()` | `RequestDetail.tsx` — `useQuery` on status+report with `refetchInterval` (e.g. 3s) while status ∈ {received,drafting,in_review} for the live graph; stat cards (status, risk, monthly cost, `attempt/max`). |
| `render_agent_graph()` | `AgentGraph.tsx` — mermaid graph, node fill driven by status; re-render on status change. |
| findings expanders | `FindingsPanel.tsx` — security list + worst finding, cost + citations, reliability score + notes (LLD §9.3). No raw PDF embed; offer PDF/TF as download links via `fileUrl()`. |
| architecture diagram | `<img src={fileUrl(id,'diagram.svg')} />`. |
| decision form | `DecisionForm.tsx` — approve/reject; reject requires notes; POST `submitDecision`; invalidate queries on success. Shown only when `status === 'in_review'`. |
| `render_create_request()` | `LaunchMigration.tsx` — source/target selects + prompt textarea; POST `submitRequest`; redirect to list. |

### Backend touch-points (small)
- Add `max_redraft_attempts` to `GET /status` response (fixes #2 for React too — UI never hardcodes the cap).
- `/files/...` already returns `FileResponse`; set an explicit `media_type="image/svg+xml"` for the SVG so `<img>` renders reliably.
- Keep `run.py` launching the gateway; replace the Streamlit launch with `npm run dev` (dev) or serve the built `dist/` behind nginx (prod / docker-compose #13).

### Migration steps
1. Scaffold Vite app, add router + TanStack Query + mermaid.
2. Build `api/client.ts` + `types.ts` from the 7 endpoints.
3. Port pages/components per table above; reuse the badge CSS palette.
4. Add `max_redraft_attempts` + SVG media type to the gateway.
5. Update `run.py` / `deploy/` to launch React instead of Streamlit.
6. Delete `dashboard/app.py` (and `streamlit` from `requirements.txt`) once parity is confirmed.
7. Verify: launch a request → watch the agent graph animate via polling → approve/reject → confirm state + file downloads.

> `# ponytail:` no SSR, no component library, no state manager beyond TanStack Query — two pages don't need them. Add only if the UI grows past the LLD §9 two-page scope.
