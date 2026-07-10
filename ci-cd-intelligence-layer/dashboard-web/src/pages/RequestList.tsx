import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { StatusBadge, RiskBadge } from "../components/Badges";

const DISCARDED = ["rejected", "expired"];

export default function RequestList() {
  const navigate = useNavigate();
  const [statusF, setStatusF] = useState("All");
  const [riskF, setRiskF] = useState("All");
  const [decisionF, setDecisionF] = useState("All");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["requests"],
    queryFn: api.listRequests,
    refetchInterval: 5000,
  });

  const rows = (data ?? []).filter(
    (r) =>
      (statusF === "All" || r.status === statusF) &&
      (riskF === "All" || r.risk_band === riskF) &&
      (decisionF === "All" || r.decision === decisionF)
  );

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">Fleet Overview</span>
        <h1 className="h1">Migration Requests</h1>
        <p className="sub">Review and gate legacy&#8202;&#8594;&#8202;cloud migration blueprints drafted by the agent network.</p>
      </div>

      <div className="toolbar">
        <Select value={statusF} onChange={setStatusF} opts={["All", "received", "drafting", "blocked", "in_review", "approved", "rejected", "expired"]} />
        <Select value={riskF} onChange={setRiskF} opts={["All", "low", "medium", "high", "critical"]} />
        <Select value={decisionF} onChange={setDecisionF} opts={["All", "pending", "approved", "rejected"]} />
        <button className="ghost" onClick={() => refetch()}>&#8635; Refresh</button>
        <button className="primary" style={{ marginLeft: "auto" }} onClick={() => navigate("/launch")}>+ New Migration</button>
      </div>

      {isLoading && <p className="sub">Loading fleet…</p>}
      {error && <div className="hint" style={{ borderColor: "rgba(255,92,122,.4)", color: "#ffb9c6" }}>Cannot reach Gateway API at {api.base}. Is the stack running?</div>}
      {!isLoading && !error && rows.length === 0 && <div className="hint">No migration requests match the current filters.</div>}

      {rows.map((r) => {
        const discarded = DISCARDED.includes(r.status);
        const [src, tgt] = r.target.split("->").map((s) => s.trim());
        return (
          <div className="req-row" key={r.request_id}>
            <div>
              <div className="req-target">{src}<span className="arrow">&#8594;</span>{tgt}</div>
              <div className="req-id">{r.request_id.slice(0, 18)}… · {r.submitted_at.slice(0, 16).replace("T", " ")}</div>
            </div>
            <div><div className="col-k">State</div><StatusBadge status={r.status} /></div>
            <div><div className="col-k">Risk</div><RiskBadge risk={r.risk_band} /></div>
            <div><div className="col-k">Decision</div><span className="mono" style={{ color: "var(--txt-2)", fontSize: ".82rem" }}>{r.decision}</span></div>
            <div>
              {discarded ? (
                <span className="mono" style={{ color: "var(--red)", fontSize: ".78rem" }}>{r.status} — no report</span>
              ) : (
                <button className="primary" onClick={() => navigate(`/request/${r.request_id}`)}>Open &#8594;</button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Select({ value, onChange, opts }: { value: string; onChange: (v: string) => void; opts: string[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} style={{ width: "auto", minWidth: 130 }}>
      {opts.map((o) => <option key={o}>{o}</option>)}
    </select>
  );
}
