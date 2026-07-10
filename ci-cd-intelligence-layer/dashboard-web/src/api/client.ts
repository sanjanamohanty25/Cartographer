import type { RequestSummary, StatusResp, ReportResp } from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let detail: string | undefined;
    try {
      detail = (await r.json()).detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail || `HTTP ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export interface DecisionBody {
  approver_id: string;
  decision: "approved" | "rejected";
  rejection_notes?: string | null;
}

export interface SubmitBody {
  submitted_by: string;
  prompt: string;
  project_json: string;
}

export const api = {
  base: BASE,
  listRequests: () => fetch(`${BASE}/api/v1/migration/list`).then((r) => j<RequestSummary[]>(r)),
  getStatus: (id: string) => fetch(`${BASE}/api/v1/migration/status/${id}`).then((r) => j<StatusResp>(r)),
  getReport: (id: string) => fetch(`${BASE}/api/v1/migration/report/${id}`).then((r) => j<ReportResp>(r)),
  submitDecision: (id: string, body: DecisionBody) =>
    fetch(`${BASE}/api/v1/migration/decision/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => j<{ status: string; message: string }>(r)),
  submitRequest: (body: SubmitBody) =>
    fetch(`${BASE}/api/v1/migration/request`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => j<{ request_id: string; status: string }>(r)),
  fileUrl: (id: string, name: string) => `${BASE}/api/v1/migration/files/${id}/${name}`,
};
