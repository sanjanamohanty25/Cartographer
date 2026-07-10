import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

const BASE_SPEC = {
  project_name: "Core-Banking-Legacy-Database",
  organization: "Cognizant Smart Infrastructure",
  migration_scope: { source_environment: "on-premises-datacenter-zone-b", target_cloud_provider: "aws", preferred_region: "us-east-1" },
  database_source_profile: {
    database_engine: "Oracle Database Enterprise Edition", version: "19c", topology: "2-Node RAC Cluster", active_connections: 450,
    hardware: { physical_cores_per_node: 16, ram_gb_per_node: 64, storage_capacity_tb: 2.5, storage_type: "SAN SSD" },
    utilization_metrics: { average_cpu_percent: 35, peak_cpu_percent: 82, average_ram_percent: 55, peak_ram_percent: 78 },
    security_posture: { ssl_tls_required: true, data_at_rest_encrypted: true, public_access_permitted: false },
  },
  reliability_requirements: { target_sla: 99.99, rto_minutes: 15, rpo_minutes: 5, backup_retention_days: 14, high_availability_required: true },
};

const SOURCES = ["Oracle Database Enterprise Edition", "Microsoft SQL Server", "IBM DB2", "PostgreSQL", "MySQL"];
const TARGETS = ["aws", "azure", "gcp"];

export default function LaunchMigration() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"template" | "upload">("template");
  const [source, setSource] = useState(SOURCES[0]);
  const [target, setTarget] = useState(TARGETS[0]);
  const [prompt, setPrompt] = useState("");
  const [uploadName, setUploadName] = useState<string | null>(null);
  const [uploadJson, setUploadJson] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const defaultPrompt = () => `Migrate our legacy ${source} database to ${target}. Optimize for high availability, security-scan policy, and cost-efficiency.`;

  function onFile(f: File | undefined) {
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || "");
      try { JSON.parse(text); } catch { setErr(`"${f.name}" is not valid JSON.`); return; }
      setUploadJson(text); setUploadName(f.name); setErr(null);
    };
    reader.readAsText(f);
  }

  async function launch() {
    setErr(null);
    let project_json: string;
    let promptOut = prompt.trim();

    if (mode === "upload") {
      if (!uploadJson) { setErr("Upload a project.json file first."); return; }
      project_json = uploadJson; // uploaded spec flows through the entire pipeline
      if (!promptOut) {
        const tgt = (() => { try { return JSON.parse(uploadJson)?.migration_scope?.target_cloud_provider ?? "the target cloud"; } catch { return "the target cloud"; } })();
        promptOut = `Analyze and migrate the uploaded legacy database specification to ${tgt}.`;
      }
    } else {
      const spec = structuredClone(BASE_SPEC);
      spec.migration_scope.target_cloud_provider = target;
      spec.database_source_profile.database_engine = source;
      spec.database_source_profile.topology = source.toLowerCase().includes("oracle") ? "2-Node RAC Cluster"
        : source.toLowerCase().includes("sql server") ? "Active-Passive Failover Cluster" : "Single Node Instance";
      project_json = JSON.stringify(spec, null, 2);
      if (!promptOut) promptOut = defaultPrompt();
    }

    try {
      setBusy(true);
      await api.submitRequest({ submitted_by: "stakeholder-123", prompt: promptOut, project_json });
      navigate("/");
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <div>
      <div className="page-head">
        <span className="eyebrow">New Analysis</span>
        <h1 className="h1">Launch Migration</h1>
        <p className="sub">Describe the migration, or upload a full <code>project.json</code> — the agent network drafts, validates, critiques and reports.</p>
      </div>

      <div className="panel" style={{ maxWidth: 720 }}>
        <div style={{ marginBottom: 18 }}>
          <div className="seg">
            <button className={mode === "template" ? "on" : ""} onClick={() => setMode("template")}>Guided Template</button>
            <button className={mode === "upload" ? "on" : ""} onClick={() => setMode("upload")}>Upload project.json</button>
          </div>
        </div>

        {mode === "template" ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div className="field">
              <label>Source Database</label>
              <select value={source} onChange={(e) => setSource(e.target.value)}>{SOURCES.map((s) => <option key={s}>{s}</option>)}</select>
            </div>
            <div className="field">
              <label>Target Cloud</label>
              <select value={target} onChange={(e) => setTarget(e.target.value)}>{TARGETS.map((t) => <option key={t}>{t}</option>)}</select>
            </div>
          </div>
        ) : (
          <div className="field">
            <label>Project specification (.json)</label>
            <div className={`upload-drop ${uploadName ? "have" : ""}`} onClick={() => fileRef.current?.click()}>
              {uploadName ? <><strong>{uploadName}</strong><div style={{ fontSize: ".8rem", marginTop: 4 }}>Loaded — used through the entire pipeline. Click to replace.</div></>
                : <><strong>Click to choose a project.json</strong><div style={{ fontSize: ".8rem", marginTop: 4 }}>Full legacy spec: engine, hardware, utilization, security posture, SLA.</div></>}
            </div>
            <input ref={fileRef} type="file" accept=".json,application/json" style={{ display: "none" }}
              onChange={(e) => onFile(e.target.files?.[0])} />
          </div>
        )}

        <div className="field">
          <label>Migration prompt <span style={{ color: "var(--txt-3)", fontWeight: 400 }}>(optional — auto-generated if blank)</span></label>
          <textarea rows={3} value={prompt} placeholder={mode === "template" ? defaultPrompt() : "Analyze and migrate the uploaded specification…"} onChange={(e) => setPrompt(e.target.value)} />
        </div>

        <div className="hint">The agent network resolves source &amp; target from the specification, drafts Terraform, self-validates, scans, right-sizes cost against the rate card, and compiles a report.</div>
        {err && <p className="err">{err}</p>}
        <button className="primary" disabled={busy} style={{ marginTop: 16 }} onClick={launch}>
          {busy ? "Launching…" : "Launch Analysis →"}
        </button>
      </div>
    </div>
  );
}
