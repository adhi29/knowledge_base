#!/usr/bin/env python3
"""
Smoke test for live connectors — tests without real credentials.
Verifies:
  1. All connector classes import correctly.
  2. Credential validation raises ValueError (not a crash) when .env vars are absent.
  3. RawDocument schema matches what the pipeline expects.

Run from project root:
    python3 scripts/test_live_connectors.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch settings to have no credentials so we can test validation
import src.config as _cfg
_cfg.settings.confluence_url = None
_cfg.settings.confluence_user = None
_cfg.settings.confluence_api_token = None
_cfg.settings.jira_url = None
_cfg.settings.jira_user = None
_cfg.settings.jira_api_token = None
_cfg.settings.ms_tenant_id = None
_cfg.settings.ms_client_id = None
_cfg.settings.ms_client_secret = None
_cfg.settings.ms_mailbox = None
_cfg.settings.ms_sharepoint_site_id = None
_cfg.settings.ms_sharepoint_drive_id = None

from src.ingestion.connectors.live_connectors import (  # noqa: E402
    ConfluenceConnector,
    JiraConnector,
    OutlookConnector,
    SharePointConnector,
    _html_to_text,
)
from src.ingestion.connectors.base import RawDocument  # noqa: E402

passed = 0
failed = 0

def ok(label):
    global passed
    passed += 1
    print(f"  ✅  {label}")

def fail(label, reason=""):
    global failed
    failed += 1
    print(f"  ❌  {label}" + (f" — {reason}" if reason else ""))


print("=" * 60)
print("  Live Connectors — Smoke Test")
print("=" * 60)

# ── 1. Import check ───────────────────────────────────────────────────────────
print("\n[Imports]")
try:
    assert ConfluenceConnector and JiraConnector and OutlookConnector and SharePointConnector
    ok("All 4 connectors imported successfully")
except Exception as e:
    fail("Import", str(e))

# ── 2. html_to_text helper ────────────────────────────────────────────────────
print("\n[HTML → Text conversion]")
try:
    result = _html_to_text("<h1>Hello</h1><p>World</p>")
    assert "Hello" in result and "World" in result
    ok(f"html_to_text works: {result!r}")
except Exception as e:
    fail("html_to_text", str(e))

# ── 3. Credential validation ──────────────────────────────────────────────────
print("\n[Credential validation — should raise ValueError]")

tests = [
    ("ConfluenceConnector", lambda: ConfluenceConnector(space_key="OPS").fetch()),
    ("JiraConnector", lambda: JiraConnector(project_key="BANK").fetch()),
    ("OutlookConnector", lambda: OutlookConnector(mailbox="ops@org.com").fetch()),
    ("SharePointConnector", lambda: SharePointConnector(site_id="x", drive_id="y").fetch()),
]

for name, fn in tests:
    try:
        fn()
        fail(f"{name} should have raised ValueError for missing credentials")
    except ValueError as e:
        ok(f"{name} raises ValueError: {str(e)[:70]}...")
    except Exception as e:
        # ImportError for msal/atlassian is also acceptable in CI without packages
        if "not installed" in str(e).lower() or "import" in str(e).lower():
            ok(f"{name} raises ImportError (package not installed — expected in CI): {e}")
        else:
            fail(f"{name} raised unexpected {type(e).__name__}: {e}")

# ── 4. RawDocument schema ─────────────────────────────────────────────────────
print("\n[RawDocument schema check]")
try:
    doc = RawDocument(
        source_id="test-1",
        source_name="Test Doc",
        source_path="https://example.atlassian.net/page/1",
        source_type="confluence",
        content="Sample banking content",
        metadata={"page_id": "123"},
        pages=[{"page_num": 1, "text": "Sample banking content"}],
        allowed_roles=["analyst", "admin"],
        sensitivity_level="internal",
    )
    assert doc.source_type == "confluence"
    assert doc.sensitivity_level == "internal"
    ok("RawDocument schema is compatible")
except Exception as e:
    fail("RawDocument schema", str(e))

# ── Summary ───────────────────────────────────────────────────────────────────
total = passed + failed
print("\n" + "=" * 60)
print(f"  Results: {passed}/{total} passed  |  {failed} failures")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
