import type { ReportResp } from "../types";

export default function FindingsPanel({ findings }: { findings: ReportResp["findings_summary"] }) {
  const { security: sec, cost, reliability: rel } = findings;
  return (
    <div className="panel">
      <div className="panel-title"><span className="tick" /> Consolidated Findings</div>

      <Section title="Security & Compliance" meta={`${sec.count} finding${sec.count === 1 ? "" : "s"}`}>
        {sec.findings.map((f, i) => (
          <div className="finding" key={i}>
            <span className={`sev sev-${f.severity.toLowerCase()}`}>{f.severity.toUpperCase()}</span>
            <span>{f.description}</span>
          </div>
        ))}
      </Section>

      <Section title="FinOps Cost" meta={`$${cost.monthly_cost.toFixed(2)} / mo`}>
        <div style={{ color: "var(--txt-3)", fontSize: ".78rem", marginBottom: 4 }}>Grounded in rate-card entries:</div>
        {cost.rate_card_citations.map((c) => <span className="cite" key={c}>{c}</span>)}
      </Section>

      <Section title="Reliability" meta={`${rel.redundancy_score}/100`}>
        {rel.notes.split("\n").filter((l) => l.trim()).map((l, i) => (
          <div className="finding" key={i}><span>{l}</span></div>
        ))}
      </Section>
    </div>
  );
}

function Section({ title, meta, children }: { title: string; meta: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <span style={{ fontFamily: "Sora", fontWeight: 700, fontSize: ".92rem" }}>{title}</span>
        <span className="mono" style={{ color: "var(--cyan)", fontSize: ".8rem" }}>{meta}</span>
      </div>
      {children}
    </div>
  );
}
