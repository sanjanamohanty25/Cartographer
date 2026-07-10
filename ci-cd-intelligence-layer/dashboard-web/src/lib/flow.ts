export type NodeState = "pending" | "active" | "done" | "fail";

export interface FlowNode {
  id: string;
  label: string;
  role: string;
  x: number;
  y: number;
}

// P1 -> (P2,P3,P4 parallel) -> P5 -> P6 -> P7
export const NODES: FlowNode[] = [
  { id: "P1", label: "Lead Architect", role: "draft + validate + diagram", x: 30, y: 150 },
  { id: "P2", label: "Security", role: "checkov / tfsec", x: 250, y: 30 },
  { id: "P3", label: "FinOps Cost", role: "rate-card grounded", x: 250, y: 150 },
  { id: "P4", label: "Reliability", role: "redundancy score", x: 250, y: 270 },
  { id: "P5", label: "Reviewer", role: "consolidate report", x: 480, y: 150 },
  { id: "P6", label: "Comms", role: "email + dashboard", x: 700, y: 150 },
  { id: "P7", label: "Approval Gate", role: "48h human sign-off", x: 890, y: 150 },
];

export const EDGES: [string, string][] = [
  ["P1", "P2"], ["P1", "P3"], ["P1", "P4"],
  ["P2", "P5"], ["P3", "P5"], ["P4", "P5"],
  ["P5", "P6"], ["P6", "P7"],
];

const CRITIC = new Set(["scanning", "costing", "reliability"]);
const DRAFT = new Set(["drafting", "validating", "diagram", "queued", "received"]);

/** Map coarse status + fine stage -> per-node states + a human label. */
export function computeFlow(status: string, stage: string): { states: Record<string, NodeState>; label: string } {
  const st: Record<string, NodeState> = { P1: "pending", P2: "pending", P3: "pending", P4: "pending", P5: "pending", P6: "pending", P7: "pending" };
  const done = (...ids: string[]) => ids.forEach((i) => (st[i] = "done"));
  const active = (...ids: string[]) => ids.forEach((i) => (st[i] = "active"));

  // terminal states first
  if (status === "approved") { done("P1", "P2", "P3", "P4", "P5", "P6"); st.P7 = "done"; return { states: st, label: "Approved" }; }
  if (status === "rejected" || status === "expired") { done("P1", "P2", "P3", "P4", "P5", "P6"); st.P7 = "fail"; return { states: st, label: status === "expired" ? "Expired — window closed" : "Rejected" }; }
  if (status === "blocked") {
    if (DRAFT.has(stage)) { st.P1 = "fail"; return { states: st, label: "Blocked — draft/validation failed" }; }
    if (CRITIC.has(stage)) { done("P1"); active(); st.P2 = st.P3 = st.P4 = "fail"; return { states: st, label: "Blocked — analysis failed" }; }
    done("P1", "P2", "P3", "P4"); st.P5 = "fail"; return { states: st, label: "Blocked — report failed" };
  }

  // in-flight
  if (DRAFT.has(stage)) { active("P1"); return { states: st, label: stage === "queued" || stage === "received" ? "Queued" : "P1 drafting blueprint" }; }
  if (CRITIC.has(stage)) { done("P1"); active("P2", "P3", "P4"); return { states: st, label: "Parallel review — security · cost · reliability" }; }
  if (stage === "reporting") { done("P1", "P2", "P3", "P4"); active("P5"); return { states: st, label: "P5 compiling report" }; }
  if (stage === "notifying") { done("P1", "P2", "P3", "P4", "P5"); active("P6"); return { states: st, label: "P6 dispatching notification" }; }
  if (stage === "gated" || status === "in_review") { done("P1", "P2", "P3", "P4", "P5", "P6"); active("P7"); return { states: st, label: "Awaiting human decision" }; }

  return { states: st, label: "Queued" };
}

/** An edge animates when its source is done/active and its target is active. */
export function edgeActive(states: Record<string, NodeState>, from: string, to: string): boolean {
  return states[to] === "active" && (states[from] === "done" || states[from] === "active");
}
