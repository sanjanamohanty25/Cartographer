import { NODES, EDGES, computeFlow, edgeActive, type NodeState } from "../lib/flow";

const NW = 156, NH = 58, VW = 1060, VH = 340;

const COLORS: Record<NodeState, { fill: string; stroke: string; text: string; led: string }> = {
  pending: { fill: "#0f1729", stroke: "#1e2a44", text: "#647592", led: "#33415c" },
  active: { fill: "#0d2033", stroke: "#4aa3ff", text: "#e8eef8", led: "#4aa3ff" },
  done: { fill: "#0c2320", stroke: "#35e0c8", text: "#dff6f1", led: "#35e0c8" },
  fail: { fill: "#26121a", stroke: "#ff5c7a", text: "#ffe0e6", led: "#ff5c7a" },
};

function anchor(id: string, side: "l" | "r") {
  const n = NODES.find((x) => x.id === id)!;
  return { x: n.x + (side === "r" ? NW : 0), y: n.y + NH / 2 };
}

function path(from: string, to: string) {
  const a = anchor(from, "r"), b = anchor(to, "l");
  const mx = (a.x + b.x) / 2;
  return `M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`;
}

export default function AgentFlow({ status, stage }: { status: string; stage: string }) {
  const { states, label } = computeFlow(status, stage);
  const live = !["approved", "rejected", "expired", "blocked"].includes(status);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        {live && <span className="spin" />}
        <span style={{ color: "var(--txt-2)", fontWeight: 600, fontSize: ".92rem" }}>{label}</span>
      </div>
      <div className="flow-wrap">
        <svg viewBox={`0 0 ${VW} ${VH}`} width="100%" style={{ minWidth: 720 }}>
          <defs>
            <linearGradient id="fe" x1="0" x2="1">
              <stop offset="0" stopColor="#35e0c8" />
              <stop offset="1" stopColor="#4aa3ff" />
            </linearGradient>
            <marker id="tip" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 z" fill="#4aa3ff" />
            </marker>
          </defs>

          {EDGES.map(([f, t]) => {
            const on = edgeActive(states, f, t);
            const complete = states[f] === "done" && states[t] === "done";
            return (
              <path
                key={`${f}-${t}`}
                d={path(f, t)}
                fill="none"
                stroke={on ? "url(#fe)" : complete ? "#245047" : "#1a2540"}
                strokeWidth={on ? 3 : 2}
                markerEnd={on ? "url(#tip)" : undefined}
                className={on ? "flow-edge-active" : undefined}
              />
            );
          })}

          {NODES.map((n) => {
            const s = states[n.id];
            const c = COLORS[s];
            return (
              <g key={n.id} className={s === "active" ? "flow-node-active" : undefined}
                 style={s === "active" ? { filter: "drop-shadow(0 0 14px rgba(74,163,255,.55))" } : s === "done" ? { filter: "drop-shadow(0 0 8px rgba(53,224,200,.3))" } : undefined}>
                <rect x={n.x} y={n.y} width={NW} height={NH} rx={13} fill={c.fill} stroke={c.stroke} strokeWidth={1.6} />
                <circle cx={n.x + 15} cy={n.y + 19} r={4.5} fill={c.led} />
                <text x={n.x + 28} y={n.y + 23} fill={c.text} fontFamily="Sora, sans-serif" fontWeight="700" fontSize="13.5">
                  {n.id} · {n.label}
                </text>
                <text x={n.x + 15} y={n.y + 42} fill="#647592" fontFamily="JetBrains Mono, monospace" fontSize="9.5">
                  {n.role}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="flow-legend">
        <span><i className="lg" style={{ background: "#35e0c8" }} /> done</span>
        <span><i className="lg" style={{ background: "#4aa3ff" }} /> active</span>
        <span><i className="lg" style={{ background: "#33415c" }} /> pending</span>
        <span><i className="lg" style={{ background: "#ff5c7a" }} /> failed</span>
      </div>
    </div>
  );
}
