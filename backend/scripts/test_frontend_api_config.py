#!/usr/bin/env python3
"""Verify frontend API config is resolved lazily inside request functions."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_FILE = ROOT / "frontend" / "src" / "lib" / "api.ts"

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


print("=== test_frontend_api_config.py ===\n")

source = API_FILE.read_text(encoding="utf-8")

check(
    "lazy API base-url helper exists",
    "function getApiBaseUrl()" in source,
    "frontend/src/lib/api.ts must expose a lazy getApiBaseUrl helper",
)
check(
    "no module-scope API base-url constant remains",
    "const API_BASE_URL =" not in source,
    "frontend/src/lib/api.ts should not resolve NEXT_PUBLIC_API_URL at module scope",
)
check(
    "generateBrief resolves API base-url lazily",
    "export async function generateBrief" in source and "const apiBaseUrl = getApiBaseUrl();" in source,
    "generateBrief should call getApiBaseUrl() inside the function body",
)
check(
    "streaming API uses lazy API base-url",
    "export async function generateBriefStream" in source
    and "fetch(`${apiBaseUrl}/api/research/stream`" in source,
    "generateBriefStream should fetch with a lazily resolved apiBaseUrl",
)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
