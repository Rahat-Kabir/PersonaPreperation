#!/usr/bin/env python3
"""Test script for backend/cli.py — verify it imports cleanly and the main function exists."""

import sys
sys.path.insert(0, sys.path[0] + "/..")

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS  {name}")
        passed += 1
    else:
        print(f"  FAIL  {name} — {detail}")
        failed += 1


print("=== test_cli.py ===\n")

# Import test
from cli import main
import inspect

check("cli.main imports", main is not None)
check("main is a coroutine function", inspect.iscoroutinefunction(main))

# Verify cli uses the refactored modules (not the old monolith)
import cli
source = inspect.getsource(cli)
check("imports from agent module", "from agent import" in source)
check("imports from tools module", "from tools import" in source)
check("imports from utils module", "from utils import" in source)
check("does NOT import persona_agent_tools", "persona_agent_tools" not in source)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
