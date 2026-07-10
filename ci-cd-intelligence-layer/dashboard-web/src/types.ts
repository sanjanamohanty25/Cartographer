export interface RequestSummary {
  request_id: string;
  target: string;
  status: string;
  risk_band: string;
  decision: string;
  submitted_at: string;
}

export interface StatusResp {
  status: string;
  stage: string;
  attempt_number: number;
  max_redraft_attempts: number;
}

export interface SecurityFinding {
  severity: string;
  description: string;
}

export interface ReportResp {
  report_pdf_ref: string;
  architecture_diagram_ref: string;
  compiled_at: string;
  risk_band: string;
  findings_summary: {
    security: { count: number; worst_finding: string; findings: SecurityFinding[] };
    cost: { monthly_cost: number; rate_card_citations: string[] };
    reliability: { redundancy_score: number; notes: string };
    decision: { status: string; attempt_number: number; decided_by: string | null; notes: string | null };
  };
}
