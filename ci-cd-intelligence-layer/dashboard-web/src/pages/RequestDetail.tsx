import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { StatusBadge, RiskBadge } from "../components/Badges";
import AgentFlow from "../components/AgentFlow";
import FindingsPanel from "../components/FindingsPanel";
import DecisionForm from "../components/DecisionForm";

const TERMINAL = ["approved", "rejected", "expired", "blocked"];

export default function RequestDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();

  const statusQ = useQuery({
    queryKey: ["status", id],
    queryFn: () => api.getStatus(id),
    refetchInterval: (q) => (TERMINAL.includes(q.state.data?.status ?? "") ? false : 2000),
  });

  const status = statusQ.data?.status ?? "received";
  const stage = statusQ.data?.stage ?? "queued";
  const reportReady = status === "in_review" || status === "approved";

  const reportQ = useQuery({
    queryKey: ["report", id],
    queryFn: () => api.getReport(id),
    enabled: reportReady,
    refetchInterval: (q) => (q.state.data ? false : 2500),
  });
  const rep = reportQ.data;

  return (
    <div>
      <button className="back" onClick={() => navigate("/")}>&#8592; Back to fleet</button>
      <div className="page-head">
        <span className="eyebrow">Migration Detail</span>
        <h1 className="h1">Blueprint Review</h1>
        <p className="sub mono" style={{ fontSize: ".82rem" }}>{id}</p>
      </div>

      <div className="stat-grid">
        <Stat k="Status" node={<StatusBadge status={status} />} />
        <Stat k="Risk Band" node={rep ? <RiskBadge risk={rep.risk_band} /> : <span className="mono" style={{ color: "var(--txt-3)" }}>—</span>} />
        <Stat k="Monthly Cost" v={rep ? `$${rep.findings_summary.cost.monthly_cost.toFixed(2)}` : "—"} />
        <Stat k="Attempt" v={statusQ.data ? `${statusQ.data.attempt_number} / ${statusQ.data.max_redraft_attempts}` : "—"} />
      </div>

      {/* One agent-network graph — animates live during the run, settles on terminal */}
      <div className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-title"><span className="tick" /> Neuro-SAN Agent Network</div>
        <AgentFlow status={status} stage={stage} />
      </div>

      {status === "blocked" && (
        <div className="hint" style={{ borderColor: "rgba(255,92,122,.4)", color: "#ffb9c6" }}>
          This request was blocked during analysis (validation or grounding failed). No report available.
        </div>
      )}

      {!reportReady && status !== "blocked" && (
        <div className="hint">Agent network is analyzing this request — findings, diagram and cost will appear here as soon as the run completes.</div>
      )}

      {rep && (
        <div className="two-col">
          <FindingsPanel findings={rep.findings_summary} />
          <div className="panel">
            <div className="panel-title"><span className="tick" /> Target Architecture</div>
            <img className="diagram-img" src={api.fileUrl(id, "diagram.svg")} alt="component-wise architecture mapping" />
            <div className="dl">
              <a href={api.fileUrl(id, "report.pdf")} target="_blank" rel="noreferrer">&#8595; Report PDF</a>
              <a href={api.fileUrl(id, "blueprint.tf")} target="_blank" rel="noreferrer">&#8595; Terraform HCL</a>
              <a href={api.fileUrl(id, "diagram.svg")} target="_blank" rel="noreferrer">&#8595; Diagram SVG</a>
            </div>
          </div>
        </div>
      )}

      {status === "in_review" && <div style={{ marginTop: 18 }}><DecisionForm requestId={id} /></div>}
    </div>
  );
}

function Stat({ k, v, node }: { k: string; v?: string; node?: React.ReactNode }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v small">{node ?? v}</div>
    </div>
  );
}
