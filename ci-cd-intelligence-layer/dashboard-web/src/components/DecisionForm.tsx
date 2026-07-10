import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";

export default function DecisionForm({ requestId }: { requestId: string }) {
  const [notes, setNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const qc = useQueryClient();

  const mutation = useMutation({
    mutationFn: (decision: "approved" | "rejected") =>
      api.submitDecision(requestId, { approver_id: "approver-456", decision, rejection_notes: notes || null }),
    onSuccess: () => { qc.invalidateQueries(); setErr(null); },
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <div className="panel">
      <div className="panel-title"><span className="tick" /> Gating Decision</div>
      <div className="hint">Findings are advisory. Confirm security, cost and reliability align with policy before authorizing — approval is recorded, not a provisioning trigger.</div>
      <div className="field" style={{ marginTop: 16 }}>
        <label>Rejection notes <span style={{ color: "var(--txt-3)", fontWeight: 400 }}>(required on reject — fed back to P1 for redraft)</span></label>
        <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. Restrict the 0.0.0.0/0 ingress to the corporate CIDR; add a read replica." />
      </div>
      {err && <p className="err">{err}</p>}
      {mutation.isSuccess && <p style={{ color: "var(--green)" }}>{mutation.data?.message}</p>}
      <div style={{ display: "flex", gap: 12 }}>
        <button className="primary" disabled={mutation.isPending} onClick={() => mutation.mutate("approved")}>&#10003; Authorize Blueprint</button>
        <button className="danger" disabled={mutation.isPending} onClick={() => {
          if (!notes.trim()) { setErr("Provide rejection notes describing the required changes."); return; }
          mutation.mutate("rejected");
        }}>&#10007; Reject for Redraft</button>
      </div>
    </div>
  );
}
