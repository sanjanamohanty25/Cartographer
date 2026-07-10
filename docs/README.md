# Cartographer — Design Document Set (v2)

Built on **Neuro-SAN** as the multi-agent orchestrator.

This is a from-scratch revision of the original document set, incorporating a review pass plus a set of scope decisions made afterward. It is **not** an edit of the original files — everything here has been rewritten for internal consistency, and content that was already correct in the original set has been carried forward unchanged.

| # | Document | Purpose |
|---|---|---|
| 00 | [Problem Statement & Proposed Solution](00-problem-statement.md) | **Master specification** — the single source of truth: the business problem, solution overview, agent network, phase-gate trust model, tech stack, success metrics, hackathon scope. |
| 01 | [Data Flow Diagrams](01-dfd.md) | DFD Level 0 (context), Level 1 (system), Level 2 (drill-downs of P1, P5, P7) + data dictionary + flow invariants. |
| 02 | [High-Level Design](02-hld.md) | Quality attributes, logical/component/runtime views, deployment, security, scalability, observability, ADRs, risks. |
| 03 | [Low-Level Design](03-lld.md) | Document control, project layout, agent network HOCON, JSON data contracts, coded tools, LLM config, Gateway API catalogue, database schema, dashboard spec, testing, error handling. |
| 04 | [Architecture Diagrams](04-architecture-diagram.md) | Six views: landscape, containers, agent network topology, cross-phase signal flow, production deployment, hackathon deployment. |

**Reading order:** 00 → 04 (visual overview) → 02 → 01 → 03.

Diagrams are Mermaid — render natively on GitHub and in VS Code (Markdown Preview Mermaid extension).

---

## What changed from the original set

This revision resolves a set of internal contradictions found in the original documents, and layers in a round of scope decisions on top. Both are summarized here so the "why" behind the current docs isn't lost.

**Contradictions resolved:**
- The original problem statement described rejection/expiry as a future "halt," while every other document already assumed an active redraft-back-to-P1 loop. This is now fully specified (see 00 §8, 03 §12) with an explicit, bounded distinction between manual rejection (redraft, capped) and expiry (no redraft, ever).
- The LLD's logical data model had two entity-relationship cardinality errors (a mandatory 1:1 request→blueprint that contradicted versioning, and a mandatory 1:1 report→decision that contradicted the expiry path). Both are corrected in 03 §8, and made moot in one case by the scope decision below (one blueprint per request).
- The DFD's Level 1 diagram silently dropped three external entities that Level 0 declared (Cloud Pricing API, Static Scan Tools, SMTP) — 01 §1–2 now keeps the diagram levels balanced.
- A stale reference to a `.docx` companion document (an artifact from an earlier version of the LLD, not part of this set) has been removed.
- Section numbering in the LLD's data-model section had a leftover heading number from a prior restructuring; renumbered.

**Scope decisions (applied throughout):**
- **One blueprint per request.** A migration request now holds exactly one blueprint, one report, one diagram, and one `.tf` file at a time — a rejection redraft overwrites these in place rather than creating a new version. See 03 §3–4.
- **Bounded, distinct rejection paths.** Manual rejection loops back to P1 for a redraft, capped at `MAX_REDRAFT_ATTEMPTS` (default 4, configurable). Expiry (the 48-hour window closing with no decision) never redrafts — it discards and closes immediately. Reaching the redraft cap on a manual rejection is treated the same as expiry.
- **Files are disposable, decision history is not.** On any non-approved terminal outcome, the generated files (`Report.pdf`, the diagram, the `.tf`) are deleted from disk — but no database rows are ever deleted. Every decision made against every attempt is retained as an append-only log, so the request stays visible and auditable even with its artifacts gone.
- **No deployment runner in this scope.** P8 (the Terraform-apply execution agent), the `deployment_execution` table, and all live target-cloud-provider integration have been removed. "Approve" is a recorded decision and a success-metric flag — it does not trigger any real provisioning. This is a scope cut, not a future promise; nothing in this set implies live execution is coming in a later phase.
- **FinOps goes LLM-native, grounded by a local reference file.** P3 no longer calls a live Cloud Pricing API. It's LLM-driven, grounded by a maintained local cost rate-card file. Checkov/Tfsec and SMTP remain real coded-tool integrations (unchanged) — the project's "LLM agents, not APIs" direction was scoped to the one component (pricing) where a live external dependency wasn't otherwise required.
- **P1 self-validates.** A `terraform_validate_tool` runs against P1's own draft before it fans out to the critic agents, so malformed Terraform is caught before Checkov/Tfsec ever sees it.
- **No target on findings severity.** The report goes out with whatever the critic agents found, unfiltered — there is no "0 critical vulnerabilities" gate. Success is defined purely by the human decision: approved = success, everything else that reaches a terminal state (rejected, attempts-exhausted, expired, or blocked before ever reaching a human) = failed.
- **Two-page dashboard, specified in detail** (see 03 §9): a list view of all requests, and a per-request detail view with a live agent-network graph, a structured findings summary (not a raw embedded PDF), the diagram, and a link to the `.tf` file. No aggregate approval/rejection percentage is shown in the UI — the success metric is tracked and reported separately, not surfaced as a dashboard stat.
