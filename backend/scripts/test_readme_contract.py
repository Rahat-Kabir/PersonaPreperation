#!/usr/bin/env python3
"""Verify README keeps the core product flow and setup guidance accurate."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
README_FILE = ROOT / "README.md"

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name} - {detail}")
        failed += 1


print("=== test_readme_contract.py ===\n")

source = README_FILE.read_text(encoding="utf-8")

check(
    "README explains input -> identity check -> research flow near the top",
    "The app first checks who the person likely is" in source
    and "asks you to confirm if the name is ambiguous" in source
    and "then researches that person" in source,
    "README should describe the real user flow before diving into implementation details",
)
check(
    "README includes a How It Works section",
    "## How It Works" in source
    and "PersonaPreparation runs a quick identity check." in source,
    "README should document the core end-user workflow",
)
check(
    "README distinguishes required auth token from optional Anthropic key",
    "- `API_AUTH_TOKEN` is required." in source
    and "`ANTHROPIC_API_KEY` is optional if users provide their own key in the frontend." in source,
    "README should match the current backend auth and API-key behavior",
)
check(
    "README notes web UI context requirement",
    "- In the current web UI, meeting context is required." in source,
    "README should explain that the web app currently requires meeting context",
)
check(
    "README documents disambiguation-first API flow",
    "### Typical Flow" in source
    and "Call `/api/research/disambiguate`" in source
    and "selected_identity" in source
    and "continue_anyway=true" in source,
    "README should describe the intended API usage pattern",
)
check(
    "README documents the saved-briefs (history) feature",
    "## Saved Briefs (History)" in source
    and "GET /api/history" in source
    and "DELETE /api/history/{id}" in source,
    "README should explain that briefs are persisted and list the history endpoints",
)
check(
    "README documents the cache + force-refresh escape hatch",
    "## Caching" in source
    and "Force fresh research" in source
    and "--force-refresh" in source
    and "force_refresh: true" in source,
    "README should explain caching and how to bypass it from web/CLI/API",
)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
