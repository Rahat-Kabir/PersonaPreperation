#!/usr/bin/env python3
"""Prompt contract test for backend/config.py SYSTEM_PROMPT."""

import sys

sys.path.insert(0, sys.path[0] + "/..")

from config import SYSTEM_PROMPT

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name} - {detail}")
        failed += 1


print("=== test_prompt_contract.py ===\n")

required_headers = [
    "## Executive Summary",
    "## Professional Background",
    "## Recent Activity & Current Focus (Last 6-12 Months)",
    "## DO's (With Reasoning)",
    "## DON'Ts (With Reasoning)",
    "## Conversation Openers (3-5)",
    "## Bottom Line Recommendation",
    "## Unknowns & Evidence Gaps",
    "## Sources",
]

for header in required_headers:
    check(f"prompt includes '{header}'", header in SYSTEM_PROMPT)

check("prompt enforces no fabrication", "never fabricate unknown facts" in SYSTEM_PROMPT.lower())
check("prompt enforces URL-backed claims", "supported by at least one source URL" in SYSTEM_PROMPT)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
