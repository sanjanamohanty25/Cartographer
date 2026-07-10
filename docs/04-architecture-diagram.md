# Cartographer — Architecture Diagrams

**Derived from:** [00-problem-statement.md](00-problem-statement.md) · [02-hld.md](02-hld.md). Companions: [DFD](01-dfd.md) · [LLD](03-lld.md).

Six views: system landscape, container view, agent network topology, cross-phase signal flow, production deployment, and hackathon deployment.

> **Note:** these are *system* architecture diagrams describing how the Cartographer itself is built. They are distinct from the **migration architecture diagram** that P1 (Lead Architect Agent) generates as a product deliverable for each migration request — that per-request diagram is a rendered SVG/PNG of the target cloud resources being proposed for the stakeholder's own workload, attached to the approval-request email alongside a `Report.pdf` summary (see [00 §7 — P1](00-problem-statement.md#7-agent-by-agent-specification), [DFD D3](01-dfd.md#4-data-stores), [LLD §4.2](03-lld.md#42-blueprint)).

> **Scope reminder carried through every view below:** there is no live target-cloud-provider integration and no deployment runner in this release. Nothing in this document depicts a `terraform apply` call or a connection to AWS/Azure/GCP as a running system — the target cloud provider is only ever a string P1 uses to select which Terraform provider block to draft.

---

## V1 — System Landscape

```mermaid
flowchart LR
    subgraph Users
        IT["Enterprise IT Professional /<br/>Cloud Stakeholder"]
        PM["IT Project Manager /<br/>Infrastructure Director"]
    end

    subgraph System["Cartographer"]
        ORCH["Migration Orchestrator"]
        AGENTS["Neuro-SAN Agent Network<br/>(P1-P6)"]
        GATE["Approval Gate + Attempt Cap (P7)"]
    end

    subgraph External["External Services"]
        SCAN["Checkov / Tfsec"]
        SMTP["SMTP Service"]
    end

    IT --> ORCH
    ORCH --> AGENTS
    AGENTS --> SCAN
    AGENTS --> SMTP
    ORCH --> GATE
    SMTP --> PM
    PM --> GATE
    GATE -- "reject, attempts remaining" --> AGENTS
```

## V2 — Container View (Deployable Units)

```mermaid
flowchart TB
    subgraph "Gateway Container"
        API["REST API"]
        WS["Request Intake Service"]
        APPR["Approval Service<br/>(attempt-cap logic)"]
    end

    subgraph "Neuro-SAN Container"
        NET["migration_intelligence<br/>agent network (HOCON)"]
    end

    subgraph "Database Container"
        PG[("PostgreSQL 16<br/>(requests, current blueprint,<br/>findings, report, decision log)")]
    end

    subgraph "File Storage"
        FILES[("request_response/&lt;request_id&gt;/<br/>.tf, report.pdf, diagram.svg —<br/>current attempt only")]
        RATECARD[("Cost rate-card file<br/>(maintained reference)")]
    end

    subgraph "Dashboard Container"
        UI["React + Vite SPA<br/>— list page + detail page"]
    end

    API --> NET
    NET --> PG
    NET --> FILES
    NET --> RATECARD
    APPR --> PG
    UI --> API
    NET -->|"invokes"| ToolLayer["Coded Tools:<br/>validate, diagram render,<br/>scan, cost lookup, SMTP"]
```

## V3 — Agent Network Topology (Inside Neuro-SAN)

```mermaid
graph TD
    P1("P1: Lead Architect<br/>(draft + validate +<br/>architecture diagram)")
    P2("P2: Security & Compliance")
    P3("P3: FinOps Cost<br/>(rate-card grounded)")
    P4("P4: Reliability")
    P5("P5: Executive Reviewer")
    P6("P6: Communications")

    P1 -- "self-validated draft" --> P2
    P1 -- "self-validated draft" --> P3
    P1 -- "self-validated draft" --> P4
    P2 --> P5
    P3 --> P5
    P4 --> P5
    P5 -- "Report.pdf +<br/>diagram ref" --> P6

    class P1,P5,P6 primary
    class P2,P3,P4 critic
    classDef primary fill:#D9EAFB,stroke:#2E6FBA,color:#0F2E4D
    classDef critic fill:#F7D9D9,stroke:#C0504D,color:#4D1B19
```

> P1's self-validation loop (draft → `terraform_validate_tool` → retry or proceed) happens before this fan-out — see [DFD §3.1](01-dfd.md#31-p1--lead-architect-agent) for the detailed steps. There is no P8 in this topology.

## V4 — Cross-Phase Signal Flow (The Differentiator)

This is what separates this system from a simple pipeline: **Phase 1 (fully automated analysis)** and **Phase 2 (the human approval gate)** are strictly separated by one signal — the approval decision — and that decision now branches three ways instead of two.

```mermaid
flowchart LR
    subgraph Phase1["Phase 1: Autonomous Analysis (no external side effects)"]
        A["Draft + self-validate blueprint"] --> B["Parallel review<br/>(security / cost / reliability)"]
        B --> C["Consolidated report"]
        C --> D["Dispatch email + dashboard link"]
    end

    subgraph Gate["48-Hour Approval Gate + Attempt Cap"]
        E{"Human decision"}
    end

    subgraph Outcome["Terminal Outcomes"]
        F["Approved —<br/>success, files retained"]
        G["Closed —<br/>failed, files discarded,<br/>rows retained"]
    end

    D --> E
    E -- "APPROVE" --> F
    E -- "REJECT, attempts remaining" --> A
    E -- "REJECT at cap" --> G
    E -- "EXPIRED" --> G
```

> The prior version of this diagram routed both "expired" and "rejected" to the *same* redraft arrow back into Phase 1, and Phase 2 was labeled "Live Execution" with a `terraform apply` step. Both are corrected here: only a reject *under* the attempt cap redrafts; expiry and a reject *at* the cap both close the request with no further automation, and there is no execution phase in this release.

## V5 — Production Deployment (Conceptual)

```mermaid
flowchart TB
    subgraph K8s["Kubernetes Cluster (cloud-agnostic)"]
        direction TB
        subgraph NS1["neuro-san namespace"]
            POD1["Agent Network Pods<br/>(HPA-scaled)"]
        end
        subgraph NS2["gateway namespace"]
            POD2["Orchestrator/API Pods<br/>(HPA-scaled)"]
        end
        subgraph NS3["dashboard namespace"]
            POD3["Dashboard Pods"]
        end
    end
    DB[("Managed PostgreSQL")]
    LB["Ingress / Load Balancer"]

    LB --> POD2
    LB --> POD3
    POD2 --> POD1
    POD1 --> DB
    POD2 --> DB
```

> **Open item, not resolved in this diagram:** generated files (`report.pdf`, diagram, `.tf`) need an actual object/file store here — local-disk storage (fine for the hackathon topology in V6) does not survive these pods being horizontally scaled or restarted. Flagged in [HLD §6.2](02-hld.md#62-production-topology-target); intentionally left as an open item rather than designed further here.

## V6 — Hackathon Deployment (docker-compose)

```mermaid
flowchart LR
    DC["docker-compose"] --> N1["neuro-san container"]
    DC --> N2["orchestrator container"]
    DC --> N3["postgres container"]
    DC --> N4["dashboard container"]
    N2 --> N1
    N2 --> N3
    N4 --> N2
    N2 -.->|"mounted volume"| VOL[("request_response/<br/>local folder")]
```
