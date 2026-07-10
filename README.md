# CI/CD Intelligence Layer

Smart Infrastructure Migration & Deployment Gating — a multi-agent system built on [Neuro-SAN](neuro-san-studio/) that automates cloud migration analysis and recommendation. Built for the Cognizant Internal Hackathon.

Given a natural-language migration prompt (e.g. _"Migrate our on-prem Oracle cluster to AWS"_) and a `project.json` describing the on-prem estate, the agent network drafts a Terraform blueprint, critiques it in parallel for security, cost, and reliability, compiles an executive PDF report with an architecture diagram, and emails it to a stakeholder for a time-bound approval decision. Nothing is ever provisioned — "approve" records a decision, it does not run `terraform apply`.

## How it works

```
Prompt + project.json
        │
        ▼
P1 Lead Architect ──── drafts .tf, self-validates, renders diagram
        │ (valid draft fans out)
   ┌────┼────┐
   ▼    ▼    ▼
  P2    P3   P4        Security (Checkov/Tfsec) · FinOps (local rate-card) · Reliability
   └────┼────┘
        ▼
P5 Executive Reviewer ─ compiles Report.pdf (unfiltered findings)
        ▼
P6 Communications ───── emails report summary + diagram + dashboard link
        ▼
P7 48-hour Approval Gate
   ├─ APPROVED  → terminal success
   ├─ REJECTED  → redraft loop back to P1 (capped at MAX_REDRAFT_ATTEMPTS)
   └─ EXPIRED   → closed, files discarded (decision history kept)
```

All agents share one LLM (NVIDIA NIM). Findings are advisory, never a gate — the human approver decides with full information.

## Repository layout

| Path                                                   | What it is                                                                    |
| ------------------------------------------------------ | ----------------------------------------------------------------------------- |
| [ci-cd-intelligence-layer/](ci-cd-intelligence-layer/) | The application: agent network, coded tools, gateway API, dashboard           |
| [docs/](docs/README.md)                                | Design document set — problem statement, DFD, HLD, LLD, architecture diagrams |
| [neuro-san-studio/](neuro-san-studio/)                 | Neuro-SAN multi-agent framework (vendored)                                    |

Inside `ci-cd-intelligence-layer/`:

- `registries/` — agent network definition (HOCON)
- `coded_tools/migration_intelligence/` — Terraform validate, Checkov/Tfsec scan, cost rate-card lookup, reliability check, diagram render, PDF render, SMTP dispatch
- `gateway/` — FastAPI gateway (request lifecycle, approval gate, Neuro-SAN invoker)
- `dashboard-web/` — React/Vite dashboard (request list + per-request detail with live agent graph)
- `config/cost_rate_card.json` — local pricing reference (no live cloud pricing API)
- `sample_files/` — example inputs

## Running it

Prereqs: Python 3.12+ venv at `.venv/` (workspace root), Node.js for the dashboard.

```powershell
cd ci-cd-intelligence-layer
.\run.ps1
```

Starts three services:

| Service               | Port |
| --------------------- | ---- |
| Neuro-SAN server      | 8080 |
| Gateway API (FastAPI) | 8000 |
| Dashboard (Vite dev)  | 5173 |

Ctrl+C stops everything. `run.py` / `run.bat` are cross-platform alternatives.

### Configuration

Create `ci-cd-intelligence-layer/.env` (loaded by the launcher). Key variables:

| Variable                                                  | Purpose                                                    |
| --------------------------------------------------------- | ---------------------------------------------------------- |
| `NVIDIA_API_KEY`                                          | NIM LLM access — empty falls back to a deterministic draft |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Report email dispatch                                      |
| `NOTIFY_RECIPIENT`                                        | Stakeholder email address                                  |
| `APPROVAL_WINDOW_HOURS`                                   | Review window (default 48)                                 |
| `MAX_REDRAFT_ATTEMPTS`                                    | Rejection redraft cap (default 4)                          |
| `DASHBOARD_URL`                                           | Link embedded in the notification email                    |

## Documentation

Read [docs/README.md](docs/README.md) for the full set. Reading order: [problem statement](docs/00-problem-statement.md) → [architecture diagrams](docs/04-architecture-diagram.md) → [HLD](docs/02-hld.md) → [DFD](docs/01-dfd.md) → [LLD](docs/03-lld.md). Diagrams are Mermaid — render on GitHub and in VS Code.

## Scope boundaries

- **No deployment runner.** No Terraform apply, no live cloud provider calls. Ever, in this release.
- **FinOps is LLM-native**, grounded by the local rate-card file — no live pricing API.
- **Files are disposable, decisions are not.** Non-approved terminal outcomes delete generated artifacts, but the decision log is append-only and never deleted.
