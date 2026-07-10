"""API contract tests (LLD §11 Contract row). Uses FastAPI TestClient.
Run: python -m pytest tests/ -q   (from ci-cd-intelligence-layer/)
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from gateway.api.main import app  # noqa: E402

client = TestClient(app)


def test_submit_rejects_malformed_project_json():
    r = client.post("/api/v1/migration/request", json={
        "submitted_by": "stakeholder-123",
        "prompt": "migrate oracle to aws",
        "project_json": "{ this is not valid json",
    })
    assert r.status_code == 422, r.text


def test_submit_rejects_unsupported_target():
    spec = {
        "migration_scope": {"target_cloud_provider": "digitalocean"},
        "database_source_profile": {"database_engine": "Oracle"},
    }
    r = client.post("/api/v1/migration/request", json={
        "submitted_by": "stakeholder-123",
        "prompt": "migrate to digitalocean",
        "project_json": json.dumps(spec),
    })
    assert r.status_code == 422, r.text


def test_decision_on_unknown_request_404():
    r = client.post("/api/v1/migration/decision/does-not-exist", json={
        "approver_id": "approver-456",
        "decision": "approved",
    })
    assert r.status_code == 404, r.text


def test_status_includes_max_redraft_attempts_after_submit():
    spec = {
        "migration_scope": {"target_cloud_provider": "aws"},
        "database_source_profile": {"database_engine": "Oracle", "hardware": {"ram_gb_per_node": 8, "storage_capacity_tb": 1}},
        "reliability_requirements": {"high_availability_required": False, "backup_retention_days": 7},
    }
    r = client.post("/api/v1/migration/request", json={
        "submitted_by": "stakeholder-123",
        "prompt": "migrate oracle to aws",
        "project_json": json.dumps(spec),
    })
    assert r.status_code == 201, r.text
    rid = r.json()["request_id"]
    s = client.get(f"/api/v1/migration/status/{rid}")
    assert s.status_code == 200
    assert "max_redraft_attempts" in s.json()


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("all api tests passed")
