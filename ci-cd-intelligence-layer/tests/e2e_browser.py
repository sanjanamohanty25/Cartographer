"""Headless browser E2E — drives the React dashboard against a live gateway.

Assumes Gateway API (:8000) and Vite (:5173) are running. Neuro-SAN optional:
without it (or a key) the gateway uses the deterministic fallback draft, so the
full flow still completes.

Submits via the UI, then locates the freshly-created request via the API and
opens its detail page directly (avoids row-ordering ambiguity), then verifies
findings + diagram render and approves — all through the browser UI.

Run: python -m playwright install chromium   (once)
     python tests/e2e_browser.py
"""
import sys
import time
import requests
from playwright.sync_api import sync_playwright, expect

WEB = "http://localhost:5173"
API = "http://localhost:8000"


def newest_request_id():
    reqs = requests.get(f"{API}/api/v1/migration/list", timeout=10).json()
    if not reqs:
        return None
    reqs.sort(key=lambda r: r["submitted_at"], reverse=True)
    return reqs[0]["request_id"]


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(20000)

        # 1. Launch a migration through the UI
        page.goto(WEB)
        page.get_by_role("link", name="Launch New Migration").click()
        expect(page.get_by_role("heading", name="Launch New Migration")).to_be_visible()
        page.get_by_role("button", name="Launch Migration Analysis").click()
        page.wait_for_url(WEB + "/")

        # 2. Find the request we just created and wait for analysis to finish
        rid = None
        for _ in range(40):
            rid = newest_request_id()
            if rid:
                st = requests.get(f"{API}/api/v1/migration/status/{rid}", timeout=10).json()["status"]
                if st in ("in_review", "blocked"):
                    break
            time.sleep(2)
        assert rid, "no request created"
        st = requests.get(f"{API}/api/v1/migration/status/{rid}", timeout=10).json()["status"]
        assert st == "in_review", f"expected in_review, got {st}"

        # 3. Open its detail page in the browser and verify the UI renders findings
        page.goto(f"{WEB}/request/{rid}")
        expect(page.get_by_text("Consolidated Findings Summary")).to_be_visible(timeout=60000)
        expect(page.get_by_text("Monthly Cost Est.")).to_be_visible()
        assert page.locator("img.diagram-img").count() >= 1, "architecture diagram <img> missing"

        # 4. Approve through the UI and confirm success
        page.get_by_role("button", name="Authorize Blueprint").click()
        page.wait_for_timeout(3000)
        final = requests.get(f"{API}/api/v1/migration/status/{rid}", timeout=10).json()["status"]
        assert final == "approved", f"expected approved after UI click, got {final}"

        print("E2E PASS: UI launch -> analyze -> findings+diagram rendered -> approve")
        browser.close()


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        # ASCII-only to survive cp1252 consoles
        msg = str(e).encode("ascii", "replace").decode("ascii")
        print("E2E FAIL: " + msg)
        sys.exit(1)
