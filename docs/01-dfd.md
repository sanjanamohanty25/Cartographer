# Cartographer — Data Flow Diagrams (DFD)

**Derived from:** [00-problem-statement.md](00-problem-statement.md) (authoritative — problem + solution). Companion documents: [HLD](02-hld.md) · [LLD](03-lld.md) · [Architecture Diagrams](04-architecture-diagram.md).
**Levels:** L0 (context) → L1 (system decomposition) → L2 (drill-downs of P1, P5, P7).

## 0. Notation

Mermaid cannot draw strict Gane–Sarson symbols; the mapping used throughout:

| DFD element | Rendered as | Naming |
|---|---|---|
| External entity | Rectangle | `E# Name` |
| Process | Rounded node | `P# Name` (L2: `P#.# Name`) |
| Data store | Cylinder | `D# Name` |
| Data flow | Labeled arrow | flow name, defined in the Data Dictionary (§4) |

---

## 1. Level 0 — Context Diagram

The system boundary is the **Cartographer** (Migration Orchestrator + Neuro-SAN agent network + data stores). Everything else is external.

```mermaid
flowchart LR
    E1["E1 Enterprise IT Professional /<br/>Cloud Stakeholder"]
    E2["E2 IT Project Manager /<br/>Infrastructure Director"]
    E3["E3 Static Scan Tools<br/>(Checkov / Tfsec)"]
    E4["E4 SMTP Service"]

    S(("P0<br/>Cartographer<br/>Layer"))

    E1 -- "F1 migration prompt (source + target) + project.json" --> S
    S -- "F2 approval request email" --> E2
    E2 -- "F3 approve / reject decision (+ notes)" --> S
    S -- "F4 outcome status" --> E2
    S -- "F5 scan request" --> E3
    E3 -- "F6 vulnerability findings" --> S
    S -- "F7 email dispatch" --> E4
```

**External entity register**

| ID | Entity | Direction | Notes |
|---|---|---|---|
| E1 | Enterprise IT Professional / Cloud Stakeholder | in | Submits the migration request that starts the workflow |
| E2 | IT Project Manager / Infrastructure Director | in/out | Receives the report, approves/rejects, receives outcome status |
| E3 | Static Scan Tools (Checkov / Tfsec) | in/out | Supplies vulnerability findings to the Security & Compliance Agent |
| E4 | SMTP Service | out | Delivers the approval-request and status emails |

> **Not modeled as external in this release:** a cloud pricing service (FinOps now reads a locally maintained rate-card file — an internal store, not an external system, see D4 below) and a target cloud provider (no live provisioning occurs — see [00 §8](00-problem-statement.md#8-the-phase-gate-trust-model)).

---

## 2. Level 1 — System Decomposition

Every external entity named at L0 reappears here, preserving DFD balancing.

```mermaid
graph TD

IT["Enterprise IT Professional /<br/>Cloud Stakeholder"]
PM["IT Project Manager /<br/>Infrastructure Director"]
ScanTools["Static Scan Tools<br/>(Checkov / Tfsec)"]
SMTPService["SMTP Service"]

specDB[("D1: project.json<br/>(PostgreSQL)")]
reportDB[("D2: Report.pdf")]
diagramDB[("D3: Architecture Diagram")]
rateCard[("D4: Cost Rate Card<br/>(maintained reference file)")]

A1("P1: Lead Architect Agent<br/>drafts + self-validates blueprint,<br/>renders architecture diagram")
A2("P2: Security Agent<br/>checks compliance")
A3("P3: FinOps Cost Agent<br/>estimates budget")
A4("P4: Reliability Agent<br/>checks uptime")
A5("P5: Reviewer Agent<br/>compiles report")
A6("P6: Comms Agent<br/>sends approval email")
Gate{"P7: Approval Gate<br/>(48h + attempt cap)"}

IT -- "migration request" --> A1
specDB -- "specs & requirements" --> A1
A1 -- "scan request" --> ScanTools
ScanTools -- "vulnerability findings" --> A1
A1 -- "valid draft .tf blueprint" --> A2
A1 -- "valid draft .tf blueprint" --> A3
A1 -- "valid draft .tf blueprint" --> A4
A1 -- "architecture diagram" --> diagramDB
rateCard -- "rate-card entries" --> A3

A2 -- "security findings" --> A5
A3 -- "cost estimate" --> A5
A4 -- "reliability report" --> A5

A5 -- "consolidated report" --> reportDB
A5 -- "consolidated report + diagram ref" --> A6
diagramDB -- "architecture diagram" --> A6
A6 -- "email dispatch" --> SMTPService
SMTPService -- "approval request email<br/>(report summary + diagram attached)" --> PM
PM -- "approve / reject (+ notes)" --> Gate

Gate -- "approved" --> PM
Gate -- "rejected, attempts remaining" --> A1
Gate -- "rejected at cap, or expired —<br/>discard files, retain rows" --> PM
```

> Note: P2/P3/P4's individual interactions with `project.json` (D1) for reading security posture / utilization data are omitted here for readability and shown in the Level 2 drill-downs where relevant; the diagram above preserves every *external* interface declared at L0 (`IT`, `PM`, `ScanTools`, `SMTPService`), which is the balancing requirement DFD levels must satisfy.

---

## 3. Level 2 Drill-Downs

### 3.1 P1 — Lead Architect Agent

```mermaid
flowchart TD
    IN1["migration prompt<br/>(free text)"] --> P10["P1.1 Parse prompt to extract<br/>source platform + target cloud provider"]
    IN2["project.json specs"] --> P11
    P10 -- "valid" --> P11["P1.2 Validate extracted source/target<br/>against project.json schema"]
    P10 -- "source/target not identifiable" --> ERR["Return validation error<br/>to submitter"]
    P11 -- "invalid" --> ERR
    P11 -- "valid" --> P12["P1.3 Retrieve legacy specs,<br/>utilization, security posture"]
    P12 --> P13["P1.4 Map legacy resources to<br/>the stated target's cloud-native equivalents"]
    P13 --> P14["P1.5 Draft Terraform (.tf)<br/>blueprint for the stated target"]
    P14 --> P14V["P1.6 Self-validate via<br/>terraform validate / fmt --check"]
    P14V -- "invalid, retries exhausted" --> BLOCK["Block request<br/>(counts as failed — never reaches P2-P6)"]
    P14V -- "valid" --> P15["P1.7 Persist blueprint<br/>(request_id, attempt_number,<br/>source_platform, target_cloud_provider)"]
    P13 --> P16["P1.8 Render architecture diagram<br/>(SVG/PNG) from the same resource mapping"]
    P16 --> P17["P1.9 Persist architecture diagram<br/>(overwrites prior attempt, if any)"]
    P15 --> OUT["Emit draft blueprint to<br/>P2, P3, P4 in parallel"]
    P17 --> OUT2["Hold diagram reference for<br/>P5 → P6 handoff (email attachment)"]
```

### 3.2 P5 — Executive Reviewer Agent

```mermaid
flowchart TD
    IN1["security findings (P2)"] --> WAIT["P5.1 Wait for all three<br/>critic agents to report"]
    IN2["cost estimate (P3)"] --> WAIT
    IN3["reliability report (P4)"] --> WAIT
    WAIT -- "all three received" --> MERGE["P5.2 Merge findings into<br/>Risk / Security / Cost pillars<br/>(no severity filtering — Design Principle 6)"]
    WAIT -- "timeout on any agent" --> ESC["Escalate to orchestrator<br/>(no partial report)"]
    MERGE --> RENDER["P5.3 Render Report.pdf"]
    RENDER --> PERSIST["P5.4 Persist consolidated report<br/>(overwrites prior attempt, if any;<br/>includes architecture_diagram_ref from P1)"]
    PERSIST --> HANDOFF["Hand off Report.pdf +<br/>architecture diagram ref to P6<br/>Communications Agent"]
```

### 3.3 P7 — Approval Gate

```mermaid
flowchart TD
    START["Approval request email sent"] --> TIMER["Start 48-hour gate timer"]
    TIMER --> DEC{"Decision received<br/>within window?"}
    DEC -- "APPROVE" --> APPR["Mark request approved<br/>(terminal — success).<br/>Retain files."]
    DEC -- "REJECT" --> CAPCHECK{"attempt_number <<br/>MAX_REDRAFT_ATTEMPTS?"}
    DEC -- "no response / expired" --> DISCARD["Mark request expired<br/>(terminal — failed).<br/>Discard files, retain all rows.<br/>Never redrafts."]
    CAPCHECK -- "yes" --> LOG1["Log decision against<br/>current attempt_number"] --> BACK["Increment attempt_number,<br/>route back to P1 for redraft.<br/>Overwrites prior blueprint/report/diagram/.tf."]
    CAPCHECK -- "no — cap reached" --> LOG2["Log decision against<br/>final attempt_number"] --> DISCARD2["Mark request rejected<br/>(terminal — failed).<br/>Discard files, retain all rows."]
```

---

## 4. Data Stores

| ID | Store | Contents | Written By | Read By |
|---|---|---|---|---|
| D1 | project.json | Legacy server specs, utilization metrics, security posture (relational, PostgreSQL) | Ingested at request time | P1 |
| D2 | Report.pdf | Consolidated Risk/Security/Cost report for the current attempt only. Deleted from disk on any non-approved terminal outcome; the underlying database row is retained. | P5 (overwrites each attempt) | P6, IT Project Manager (via dashboard, while the file exists) |
| D3 | Architecture Diagram | Rendered SVG/PNG of the mapped target-cloud architecture, for the current attempt only. Deleted from disk on any non-approved terminal outcome; the underlying database row is retained. | P1 (overwrites each attempt) | P5 (reference passthrough), P6 (email attachment), IT Project Manager (via dashboard, while the file exists) |
| D4 | Cost Rate Card | A locally maintained reference file (JSON/CSV) of cloud instance/service rates, used to ground P3's cost estimates. Not a live API; maintained out-of-band by the project team. | Maintained externally by the team | P3 |

> **The Terraform State Store from the prior draft of this document has been removed.** There is no live `terraform apply` in this release, so there is no execution state to track — see [00 §8](00-problem-statement.md#8-the-phase-gate-trust-model) and [ADR-10](02-hld.md#11-design-decisions-adr-summary).

## 5. Data Dictionary (Flows)

| Flow | From → To | Payload |
|---|---|---|
| F1 / migration request | E1 → P1 | Free-text request + `project.json` reference |
| scan request / findings | P1 ↔ E3 | Terraform code out; severity-tagged vulnerability list back |
| draft .tf blueprint | P1 → P2, P3, P4 | Self-validated Terraform code, current attempt number |
| architecture diagram | P1 → D3 | Rendered SVG/PNG, linked to the current attempt |
| rate-card entries | D4 → P3 | Cited unit rates used to ground the cost estimate |
| security findings | P2 → P5 | Severity-tagged vulnerability list, unfiltered |
| cost estimate | P3 → P5 | Monthly cost projection, currency, cited rate-card entry IDs |
| reliability report | P4 → P5 | Redundancy score, notes |
| consolidated report | P5 → D2, P6 | Merged PDF report reference + architecture diagram reference |
| email dispatch | P6 → E4 | Email content + attachments |
| approval request email | E4 → E2 | Email + `Report.pdf` attachment + architecture diagram attachment + dashboard access token |
| approve / reject (+ notes) | E2 → P7 | Decision, approver ID, timestamp, optional rejection notes (fed back to P1 on redraft) |
| outcome status | P7 → E2 | Approved / rejected / expired |

**Flow invariants:**
- A `consolidated report` is only ever produced once security, cost, and reliability findings for the *same* attempt are all present (see §3.2).
- A `rejected` decision with attempts remaining always routes back to P1 with the decision logged first; the previous attempt's blueprint, report, diagram, and `.tf` are overwritten, never versioned alongside the new one.
- An `expired` outcome never routes back to P1, regardless of `attempt_number`.
- A `rejected` decision at the attempt cap is treated identically to `expired`: terminal, files discarded, rows retained.
- An `approval request email` is only dispatched once both the `consolidated report` (P5) and the `architecture diagram` (D3) exist for the *same* attempt — P6 never sends an email with one attachment missing.
- No database row for `migration_request`, `blueprint`, `finding`, `consolidated_report`, or `approval_decision` is ever deleted. Only the physical files referenced by `report_pdf_ref` and `architecture_diagram_ref` are deleted, and only on a non-approved terminal outcome.
