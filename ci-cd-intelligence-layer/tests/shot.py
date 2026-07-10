import sys, time, json, requests
from playwright.sync_api import sync_playwright

WEB, API = "http://localhost:5173", "http://localhost:8000"
OUT = sys.argv[1] if len(sys.argv) > 1 else "."

SPEC = {
    "migration_scope": {"target_cloud_provider": "aws", "preferred_region": "us-east-1"},
    "database_source_profile": {"database_engine": "Oracle Database Enterprise Edition", "topology": "2-Node RAC Cluster",
        "hardware": {"physical_cores_per_node": 16, "ram_gb_per_node": 64, "storage_capacity_tb": 2.5, "storage_type": "SAN SSD"},
        "security_posture": {"data_at_rest_encrypted": True, "public_access_permitted": False}},
    "reliability_requirements": {"high_availability_required": True, "backup_retention_days": 14},
}

rid = requests.post(f"{API}/api/v1/migration/request", json={
    "submitted_by": "stakeholder-123", "prompt": "Migrate our legacy Oracle database to AWS RDS MySQL, optimize for high availability",
    "project_json": json.dumps(SPEC)}, timeout=20).json()["request_id"]
print("rid", rid)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 1600})
    # list page
    pg.goto(WEB); pg.wait_for_timeout(1500); pg.screenshot(path=f"{OUT}/ui_list.png")
    # detail mid-run (animated flow)
    pg.goto(f"{WEB}/request/{rid}"); pg.wait_for_timeout(2500); pg.screenshot(path=f"{OUT}/ui_running.png", full_page=True)
    # wait for in_review
    for _ in range(100):
        s = requests.get(f"{API}/api/v1/migration/status/{rid}", timeout=10).json()["status"]
        if s in ("in_review", "blocked"): break
        time.sleep(3)
    print("final", s)
    pg.reload(); pg.wait_for_timeout(3500); pg.screenshot(path=f"{OUT}/ui_report.png", full_page=True)
    # launch page (upload UI)
    pg.goto(f"{WEB}/launch"); pg.wait_for_timeout(1200)
    pg.get_by_role("button", name="Upload project.json").click(); pg.wait_for_timeout(600)
    pg.screenshot(path=f"{OUT}/ui_launch.png")
    b.close()
print("shots saved")
