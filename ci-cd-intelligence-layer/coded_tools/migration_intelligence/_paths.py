"""Dynamic path resolution — no hardcoded absolute paths anywhere.

Root is derived from this file's own location (works on any machine / OS),
with optional env-var overrides (LLD §2.1). Lives beside the coded tools so it
imports as `from _paths import ...` when neuro-san loads a tool, and as
`from coded_tools.migration_intelligence._paths import ...` from the gateway.
"""
import os

# .../ci-cd-intelligence-layer/coded_tools/migration_intelligence/_paths.py
#   -> up 3 = ci-cd-intelligence-layer
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def package_root() -> str:
    """Absolute path to the ci-cd-intelligence-layer package root."""
    return _PKG_ROOT


def request_response_root() -> str:
    root = os.environ.get("REQUEST_RESPONSE_ROOT") or os.path.join(_PKG_ROOT, "request_response")
    os.makedirs(root, exist_ok=True)
    return root


def request_dir(request_id: str) -> str:
    """Per-request folder (created if missing)."""
    d = os.path.join(request_response_root(), request_id)
    os.makedirs(d, exist_ok=True)
    return d


def cost_rate_card_path() -> str:
    return os.environ.get("COST_RATE_CARD_PATH") or os.path.join(_PKG_ROOT, "config", "cost_rate_card.json")


def database_path() -> str:
    d = os.path.join(_PKG_ROOT, "database")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "migration_intelligence.db")


def emails_dir() -> str:
    d = os.path.join(_PKG_ROOT, "logs", "emails")
    os.makedirs(d, exist_ok=True)
    return d


if __name__ == "__main__":
    # ponytail: one runnable check — root must resolve to the package dir on any machine
    assert os.path.basename(package_root()) == "ci-cd-intelligence-layer", package_root()
    assert os.path.isfile(cost_rate_card_path()), cost_rate_card_path()
    print("paths OK:", package_root())
