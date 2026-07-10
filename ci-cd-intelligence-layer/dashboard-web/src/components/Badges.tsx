export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`pill s-${status}`}>
      <span className="led" style={{ background: "currentColor" }} />
      {status.replace("_", " ").toUpperCase()}
    </span>
  );
}

export function RiskBadge({ risk }: { risk: string }) {
  return <span className={`pill risk risk-${risk}`}>{risk} risk</span>;
}
