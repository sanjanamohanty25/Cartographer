"""Unit tests for the critic tools + analysis helpers (LLD §11).
Run: python -m pytest tests/ -q   (from ci-cd-intelligence-layer/)
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.api import analysis  # noqa: E402
from coded_tools.migration_intelligence._paths import request_dir  # noqa: E402
from coded_tools.migration_intelligence.security_scan_tool import SecurityScanTool  # noqa: E402
from coded_tools.migration_intelligence.reliability_check_tool import ReliabilityCheckTool  # noqa: E402


SAMPLE = json.dumps({
    "migration_scope": {"target_cloud_provider": "aws", "preferred_region": "us-east-1"},
    "database_source_profile": {
        "database_engine": "Oracle Database Enterprise Edition",
        "hardware": {"ram_gb_per_node": 64, "storage_capacity_tb": 2.5},
        "security_posture": {"data_at_rest_encrypted": False, "public_access_permitted": True},
    },
    "reliability_requirements": {"high_availability_required": True, "backup_retention_days": 14},
})


def test_validate_rejects_malformed_json():
    try:
        analysis.validate_project_json("{not json")
        assert False, "should have raised"
    except ValueError:
        pass


def test_resolve_allowlist_enforced():
    spec = analysis.validate_project_json(SAMPLE)
    src, tgt = analysis.resolve_source_target(spec, "migrate oracle to aws", ["aws", "azure", "gcp"])
    assert (src, tgt) == ("oracle", "aws")
    # target not in allow-list -> raises
    bad = json.loads(SAMPLE)
    bad["migration_scope"]["target_cloud_provider"] = "digitalocean"
    spec2 = analysis.validate_project_json(json.dumps(bad))
    try:
        analysis.resolve_source_target(spec2, "migrate to digitalocean", ["aws", "azure", "gcp"])
        assert False, "should reject unsupported target"
    except ValueError:
        pass


def test_cost_grounded_and_cited():
    spec = analysis.validate_project_json(SAMPLE)
    monthly, cites = analysis.estimate_cost("test-cost", "aws", spec)
    assert monthly > 0
    assert cites and all(isinstance(c, str) for c in cites)
    # every citation must be a real rate-card id (grounding contract, QA6)
    with open(analysis.cost_rate_card_path(), encoding="utf-8") as f:
        ids = {c["id"] for c in json.load(f)}
    assert set(cites).issubset(ids)


def test_security_flags_unencrypted_and_public():
    rid = "test-sec"
    tf = request_dir(rid) + os.sep + "blueprint.tf"
    with open(tf, "w", encoding="utf-8") as f:
        f.write('resource "aws_db_instance" "d" {\n  encrypted = false\n  publicly_accessible = true\n}\n')
    findings = SecurityScanTool().invoke({"request_id": rid}, {})["findings"]
    sevs = {x["severity"] for x in findings}
    assert "critical" in sevs  # publicly_accessible = true


def test_reliability_scores_multi_az():
    rid = "test-rel"
    tf = request_dir(rid) + os.sep + "blueprint.tf"
    with open(tf, "w", encoding="utf-8") as f:
        f.write('resource "aws_db_instance" "d" {\n  multi_az = true\n  backup_retention_period = 14\n}\n')
    res = ReliabilityCheckTool().invoke({"request_id": rid}, {})
    assert res["redundancy_score"] >= 70


def test_stub_or_invalid_agent_draft_falls_back():
    """A truncated/placeholder agent blueprint must trigger the deterministic fallback."""
    import shutil
    spec = analysis.validate_project_json(SAMPLE)
    for junk in ("...", 'terraform {}\nprovider "aws" {}\n# [Rest of the configuration...]'):
        rid = "test-stub"
        d = request_dir(rid)
        with open(d + os.sep + "blueprint.tf", "w", encoding="utf-8") as f:
            f.write(junk)
        assert analysis.ensure_blueprint(rid, spec, "oracle", "aws") is True
        code = open(d + os.sep + "blueprint.tf", encoding="utf-8").read()
        assert analysis._is_complete_blueprint(code), "fallback must be resource-complete"
        assert "rest of the config" not in code.lower() and "..." not in code
        shutil.rmtree(d, ignore_errors=True)


def test_fallback_is_provider_correct():
    for tgt, marker in (("aws", "aws_db_instance"), ("azure", "azurerm_mssql_database"), ("gcp", "google_sql_database_instance")):
        bad = json.loads(SAMPLE)
        bad["migration_scope"]["target_cloud_provider"] = tgt
        spec = analysis.validate_project_json(json.dumps(bad))
        code = analysis.fallback_terraform(spec, "oracle", tgt)
        assert marker in code, f"{tgt} fallback missing {marker}"


def test_scanner_flags_azure_highrisk():
    """Azure unencrypted + public must produce critical + high (provider-aware scan)."""
    import shutil
    spec = analysis.validate_project_json(json.dumps({
        "migration_scope": {"target_cloud_provider": "azure"},
        "database_source_profile": {"database_engine": "Microsoft SQL Server",
            "security_posture": {"data_at_rest_encrypted": False, "public_access_permitted": True}},
        "reliability_requirements": {"high_availability_required": False, "backup_retention_days": 0},
    }))
    rid = "test-azrisk"
    analysis.ensure_blueprint(rid, spec, "mssql", "azure")
    sevs = {f["severity"] for f in SecurityScanTool().invoke({"request_id": rid}, {})["findings"]}
    assert "critical" in sevs and "high" in sevs, sevs
    shutil.rmtree(request_dir(rid), ignore_errors=True)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("all tool tests passed")
