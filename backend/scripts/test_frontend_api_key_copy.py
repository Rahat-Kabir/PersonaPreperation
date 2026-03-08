#!/usr/bin/env python3
"""Verify frontend API-key copy matches the actual request flow."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE_FILE = ROOT / "frontend" / "src" / "app" / "page.tsx"

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


print("=== test_frontend_api_key_copy.py ===\n")

source = PAGE_FILE.read_text(encoding="utf-8")

check(
    "frontend copy says key is stored locally",
    "Your key is stored locally in your browser" in source,
    "settings copy should explain that the key is stored in localStorage only",
)
check(
    "frontend copy says key is sent only to backend for research",
    "sent only to the PersonaPreparation backend when you run research." in source,
    "settings copy should not claim the key is never sent to the server",
)
check(
    "frontend copy no longer claims key is never sent to servers",
    "Never sent to our servers." not in source,
    "settings copy is inaccurate because research requests include anthropic_api_key",
)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
