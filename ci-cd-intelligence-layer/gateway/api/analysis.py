"""Deterministic analysis orchestration — the single source of truth for findings.

Per the architecture decision (see IMPLEMENTATION_PLAN.md): the neuro-san agent
network is the LLM reasoning/narrative layer (it drafts the Terraform). This
module runs the coded tools ONCE against that draft to produce the findings that
are persisted — no double-run, cost grounded and cited, fully testable.
"""
import os
import json
import logging
from typing import List, Optional, Tuple

from pydantic import BaseModel, ValidationError

from coded_tools.migration_intelligence._paths import request_dir, cost_rate_card_path
from coded_tools.migration_intelligence.security_scan_tool import SecurityScanTool
from coded_tools.migration_intelligence.reliability_check_tool import ReliabilityCheckTool
from coded_tools.migration_intelligence.cost_reference_tool import CostReferenceTool
from coded_tools.migration_intelligence.report_render_tool import ReportRenderTool
from coded_tools.migration_intelligence.diagram_render_tool import DiagramRenderTool
from coded_tools.migration_intelligence.terraform_validate_tool import TerraformValidateTool
from coded_tools.migration_intelligence.smtp_dispatch_tool import SmtpDispatchTool

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# project.json schema (#10) — validated at API-01, no more raw-file-only store
# --------------------------------------------------------------------------
class Hardware(BaseModel):
    physical_cores_per_node: int = 0
    ram_gb_per_node: float = 8.0
    storage_capacity_tb: float = 0.5
    storage_type: str = ""


class SecurityPosture(BaseModel):
    ssl_tls_required: bool = True
    data_at_rest_encrypted: bool = True
    public_access_permitted: bool = False


class DBProfile(BaseModel):
    database_engine: str
    hardware: Hardware = Hardware()
    security_posture: SecurityPosture = SecurityPosture()


class MigrationScope(BaseModel):
    target_cloud_provider: str
    preferred_region: str = ""


class ReliabilityReq(BaseModel):
    high_availability_required: bool = False
    backup_retention_days: int = 0
    target_sla: float = 0.0


class ProjectSpec(BaseModel):
    project_name: str = "migration"
    migration_scope: MigrationScope
    database_source_profile: DBProfile
    reliability_requirements: ReliabilityReq = ReliabilityReq()


def validate_project_json(raw: str) -> ProjectSpec:
    """Parse + validate project.json. Raises ValueError on malformed input (#10)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"project_json is not valid JSON: {e}")
    try:
        return ProjectSpec.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"project_json failed schema validation: {e}")


# --------------------------------------------------------------------------
# Source / target resolution (#5, #11) — from validated structured input
# --------------------------------------------------------------------------
_SOURCE_KEYWORDS = {
    "oracle": "oracle",
    "sql server": "mssql", "mssql": "mssql", "ms sql": "mssql",
    "db2": "db2",
    "postgres": "postgresql", "postgresql": "postgresql",
    "mysql": "mysql",
}


def _normalize_source(engine: str, prompt: str) -> str:
    hay = f"{engine} {prompt}".lower()
    for kw, norm in _SOURCE_KEYWORDS.items():
        if kw in hay:
            return norm
    return "oracle"  # documented default when unidentifiable


def resolve_source_target(spec: ProjectSpec, prompt: str, allowed: List[str]) -> Tuple[str, str]:
    """Resolve (source_platform, target_cloud_provider). Enforces allow-list (#11)."""
    target = (spec.migration_scope.target_cloud_provider or "").strip().lower()
    if target not in allowed:
        # try to recover from the prompt before giving up
        for p in allowed:
            if p in prompt.lower():
                target = p
                break
    if target not in allowed:
        raise ValueError(
            f"target_cloud_provider '{target or '(none)'}' is not in the supported list {allowed}"
        )
    source = _normalize_source(spec.database_source_profile.database_engine, prompt)
    return source, target


# --------------------------------------------------------------------------
# Cost estimate (#4) — right-sized, grounded in the rate card, every line cited
# --------------------------------------------------------------------------
def estimate_cost(request_id: str, target: str, spec: ProjectSpec) -> Tuple[float, List[str]]:
    """Right-size one compute + one database + storage for the target provider,
    ground every line in a cited rate-card entry (validated by CostReferenceTool).
    Raises ValueError if grounding fails (QA6 — never fabricate a figure)."""
    ram = spec.database_source_profile.hardware.ram_gb_per_node
    storage_gb = float(spec.database_source_profile.hardware.storage_capacity_tb) * 1024.0
    ha = spec.reliability_requirements.high_availability_required

    with open(cost_rate_card_path(), "r", encoding="utf-8") as f:
        card = json.load(f)
    by_provider = [c for c in card if c.get("provider") == target]
    if not by_provider:
        raise ValueError(f"no rate-card entries for provider '{target}'")

    def pick(kind: str, prefer_large: bool):
        items = sorted([c for c in by_provider if c.get("type") == kind],
                       key=lambda c: c.get("monthly_rate", 0.0))
        if not items:
            return None
        return items[-1] if prefer_large else items[0]

    db = pick("database", prefer_large=ha)          # HA -> larger/Multi-AZ SKU
    compute = pick("compute", prefer_large=ram >= 8)  # size by source RAM
    storage = pick("storage", prefer_large=False)

    chosen = [x for x in (db, compute, storage) if x]
    citations = [x["id"] for x in chosen]

    # Ground: reject any citation not present in the rate card (QA6)
    grounded = CostReferenceTool().invoke({"request_id": request_id, "resources": citations}, {})
    if grounded.get("status") != "success":
        raise ValueError(f"cost grounding failed: {grounded.get('message')}")

    monthly = 0.0
    if db:
        monthly += float(db["monthly_rate"])
    if compute:
        monthly += float(compute["monthly_rate"])
    if storage:
        monthly += float(storage["monthly_rate"]) * storage_gb
    return round(monthly, 2), citations


# --------------------------------------------------------------------------
# Terraform draft — LLM-first, deterministic fallback so the pipeline never
# stalls when the agent network is unavailable (ponytail: labeled fallback).
# --------------------------------------------------------------------------
_PROVIDER_BLOCK = {"aws": "aws", "azure": "azurerm", "gcp": "google"}


def fallback_terraform(spec: ProjectSpec, source: str, target: str) -> str:
    """Deterministic, provider-correct, resource-complete HCL derived from
    project.json. Uses each cloud's real resource types + attributes so the
    downloadable .tf is coherent and the (provider-aware) scanners read it."""
    sp = spec.database_source_profile.security_posture
    rel = spec.reliability_requirements
    region = spec.migration_scope.preferred_region or "us-east-1"
    ha = bool(rel.high_availability_required)
    enc = bool(sp.data_at_rest_encrypted)
    pub = bool(sp.public_access_permitted)
    days = int(rel.backup_retention_days)
    gb = int(spec.database_source_profile.hardware.storage_capacity_tb * 1024)
    b = lambda x: "true" if x else "false"

    if target == "azure":
        return f"""# Auto-drafted fallback blueprint ({source} -> azure)
provider "azurerm" {{
  features {{}}
}}

resource "azurerm_mssql_database" "target_db" {{
  name                                = "migration-target-db"
  sku_name                            = "GP_Gen5_2"
  max_size_gb                         = {max(gb, 32)}
  zone_redundant                      = {b(ha)}
  transparent_data_encryption_enabled = {b(enc)}
  short_term_retention_policy {{
    retention_days = {days}
  }}
}}

resource "azurerm_managed_disk" "data_volume" {{
  name                 = "migration-data-disk"
  storage_account_type = "Premium_LRS"
  disk_size_gb         = 128
  public_network_access_enabled = {b(pub)}
}}

resource "azurerm_network_security_group" "db_nsg" {{
  name = "migration-db-nsg"
  security_rule {{
    name                       = "db-ingress"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    destination_port_range     = "1433"
    source_address_prefix      = "{'0.0.0.0/0' if pub else '10.100.0.0/16'}"
    destination_address_prefix = "*"
  }}
}}
"""
    if target == "gcp":
        # GCP Cloud SQL encrypts at rest by default; ipv4_enabled reflects public exposure.
        return f"""# Auto-drafted fallback blueprint ({source} -> gcp)
provider "google" {{
  region = "{region}"
}}

resource "google_sql_database_instance" "target_db" {{
  name             = "migration-target-db"
  database_version = "MYSQL_8_0"
  settings {{
    tier              = "db-custom-2-7680"
    availability_type = "{'REGIONAL' if ha else 'ZONAL'}"
    disk_size         = {max(gb, 10)}
    backup_configuration {{
      enabled                        = {b(days > 0)}
      point_in_time_recovery_enabled = {b(ha)}
      retention_days                 = {days}
    }}
    ip_configuration {{
      ipv4_enabled = {b(pub)}
    }}
  }}
}}

resource "google_compute_disk" "data_volume" {{
  name = "migration-data-disk"
  type = "pd-ssd"
  size = 128
}}

resource "google_compute_firewall" "db_fw" {{
  name          = "migration-db-fw"
  network       = "default"
  source_ranges = ["{'0.0.0.0/0' if pub else '10.100.0.0/16'}"]
  allow {{
    protocol = "tcp"
    ports    = ["3306"]
  }}
}}
"""
    # default: aws
    return f"""# Auto-drafted fallback blueprint ({source} -> aws)
provider "aws" {{
  region = "{region}"
}}

resource "aws_db_instance" "target_db" {{
  engine                  = "mysql"
  instance_class          = "db.m5.large"
  allocated_storage       = {gb}
  multi_az                = {b(ha)}
  backup_retention_period = {days}
  storage_encrypted       = {b(enc)}
  publicly_accessible     = {b(pub)}
}}

resource "aws_ebs_volume" "data_volume" {{
  availability_zone = "{region}a"
  size              = 128
  encrypted         = {b(enc)}
}}

resource "aws_security_group" "db_sg" {{
  ingress {{
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["{'0.0.0.0/0' if pub else '10.100.0.0/16'}"]
  }}
}}
"""


# Markers that reveal a truncated / placeholder LLM draft rather than a real blueprint.
_STUB_MARKERS = (
    "rest of the config", "rest of config", "...", "todo", "placeholder",
    "your config", "add your", "<insert", "omitted", "truncated", "// ...",
    "# ...", "remaining resources", "etc.", "and so on",
)


def _is_complete_blueprint(code: str) -> bool:
    """A usable agent draft has >=2 real resource blocks and no truncation markers."""
    import re
    low = code.lower()
    if any(m in low for m in _STUB_MARKERS):
        return False
    return len(re.findall(r'resource\s+"[^"]+"\s+"[^"]+"', code)) >= 2


def ensure_blueprint(request_id: str, spec: ProjectSpec, source: str, target: str) -> bool:
    """Ensure a *valid, complete* blueprint.tf exists. Prefer the agent's draft,
    but fall back to the deterministic draft whenever the agent produced nothing
    usable — empty, a placeholder/stub (e.g. "..." or "# rest of the config"),
    fewer than two real resource blocks, or HCL that fails validation."""
    tf_path = os.path.join(request_dir(request_id), "blueprint.tf")
    if os.path.exists(tf_path):
        with open(tf_path, "r", encoding="utf-8") as f:
            code = f.read()
        if _is_complete_blueprint(code):
            res = TerraformValidateTool().invoke({"request_id": request_id, "terraform_code": code}, {})
            if res.get("status") == "valid":
                return True
            logger.warning(f"Agent blueprint for {request_id} failed validation; using deterministic fallback.")
        else:
            logger.warning(f"Agent blueprint for {request_id} is a stub/incomplete draft; using deterministic fallback.")
    # deterministic fallback (always valid, resource-complete HCL derived from project.json)
    code = fallback_terraform(spec, source, target)
    res = TerraformValidateTool().invoke({"request_id": request_id, "terraform_code": code}, {})
    return res.get("status") == "valid"


# Cloud-native equivalents per provider, for the component-wise diagram.
_TARGET_DB = {"aws": "AWS RDS (MySQL)", "azure": "Azure SQL Database", "gcp": "GCP Cloud SQL (MySQL)"}
_TARGET_COMPUTE = {"aws": "EC2 (RDS-managed compute)", "azure": "Azure VM / SQL compute", "gcp": "GCE / Cloud SQL compute"}
_TARGET_STORAGE = {"aws": "EBS gp3", "azure": "Azure Premium SSD", "gcp": "GCP Persistent Disk SSD"}
_TARGET_NET = {"aws": "VPC + Security Group", "azure": "VNet + NSG", "gcp": "VPC + Firewall"}
_SOURCE_DB_LABEL = {"oracle": "Oracle Database", "mssql": "MS SQL Server", "db2": "IBM DB2",
                    "postgresql": "PostgreSQL", "mysql": "MySQL"}


def build_resource_mapping(spec: ProjectSpec, source: str, target: str) -> list:
    """Explicit on-prem-component -> cloud-component pairs for the architecture diagram."""
    hw = spec.database_source_profile.hardware
    rel = spec.reliability_requirements
    db_src = _SOURCE_DB_LABEL.get(source, source)
    topo = getattr(spec.database_source_profile, "topology", "") or ""
    db_target = _TARGET_DB.get(target, "Managed Database")
    if rel.high_availability_required:
        db_target += " · Multi-AZ"
    pairs = [
        {"source": f"{db_src}" + (f"\n({topo})" if topo else ""),
         "target": db_target, "note": "database"},
        {"source": f"Compute node\n{int(hw.physical_cores_per_node)} vCPU / {int(hw.ram_gb_per_node)} GB",
         "target": _TARGET_COMPUTE.get(target, "Managed compute"), "note": "compute"},
        {"source": f"{hw.storage_type or 'On-prem storage'}\n{hw.storage_capacity_tb} TB",
         "target": _TARGET_STORAGE.get(target, "Block storage"), "note": "storage"},
        {"source": "On-prem subnet\n+ ingress rules",
         "target": _TARGET_NET.get(target, "Virtual network"), "note": "network / security"},
    ]
    if rel.backup_retention_days:
        pairs.append({"source": f"Backup policy\n{rel.backup_retention_days}-day retention",
                      "target": "Automated backups\n+ snapshots", "note": "resilience"})
    return pairs


def ensure_diagram(request_id: str, spec: ProjectSpec, source: str, target: str) -> None:
    # Always render the deterministic component-wise mapping (source of truth),
    # overwriting any generic diagram an agent may have produced.
    pairs = build_resource_mapping(spec, source, target)
    DiagramRenderTool().invoke({
        "request_id": request_id,
        "resource_mappings": json.dumps({
            "provider": target,
            "region": spec.migration_scope.preferred_region or "us-east-1",
            "pairs": pairs,
        }),
    }, {})


def run_security_scan(request_id: str) -> List[dict]:
    res = SecurityScanTool().invoke({"request_id": request_id}, {})
    return res.get("findings", [])


def run_reliability(request_id: str) -> Tuple[int, str]:
    res = ReliabilityCheckTool().invoke({"request_id": request_id}, {})
    return res.get("redundancy_score", 0), "\n".join(res.get("findings", []))


def send_notification(request_id: str, recipient: str, subject: str, body: str) -> dict:
    """P6 — dispatch the approval-request email (Gmail SMTP) with PDF + diagram
    attached. Best-effort: the tool also writes a mock copy to logs/emails/."""
    return SmtpDispatchTool().invoke(
        {"request_id": request_id, "recipient_email": recipient, "subject": subject, "body": body}, {}
    )


def render_report(request_id: str, security_summary: str, cost_summary: str, reliability_summary: str) -> Optional[str]:
    res = ReportRenderTool().invoke({
        "request_id": request_id,
        "security_summary": security_summary,
        "cost_summary": cost_summary,
        "reliability_summary": reliability_summary,
    }, {})
    return res.get("file_path") if res.get("status") == "success" else None


if __name__ == "__main__":
    # ponytail: one runnable check — validation + resolution + grounded cost
    sample = json.dumps({
        "migration_scope": {"target_cloud_provider": "aws", "preferred_region": "us-east-1"},
        "database_source_profile": {"database_engine": "Oracle", "hardware": {"ram_gb_per_node": 64, "storage_capacity_tb": 2.5}},
        "reliability_requirements": {"high_availability_required": True, "backup_retention_days": 14},
    })
    spec = validate_project_json(sample)
    src, tgt = resolve_source_target(spec, "migrate oracle to aws", ["aws", "azure", "gcp"])
    assert (src, tgt) == ("oracle", "aws"), (src, tgt)
    cost, cites = estimate_cost("selftest", tgt, spec)
    assert cost > 0 and cites, (cost, cites)
    try:
        validate_project_json("{bad json")
        raise AssertionError("should have rejected malformed json")
    except ValueError:
        pass
    print("analysis self-check OK:", src, tgt, cost, cites)
