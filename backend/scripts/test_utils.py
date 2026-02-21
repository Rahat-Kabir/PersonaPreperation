#!/usr/bin/env python3
"""Test script for backend/utils.py — verify validation, sanitization, and file saving."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, sys.path[0] + "/..")

from utils import validate_person_name, sanitize_filename, save_brief_to_file

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


print("=== test_utils.py ===\n")

# --- validate_person_name ---
print("-- validate_person_name --")

valid, msg = validate_person_name("John Doe")
check("valid name accepted", valid and msg == "")

valid, msg = validate_person_name("")
check("empty name rejected", not valid)

valid, msg = validate_person_name("   ")
check("whitespace-only rejected", not valid)

valid, msg = validate_person_name("A" * 201)
check("over-length rejected", not valid)

valid, msg = validate_person_name("Name<script>")
check("angle brackets rejected", not valid)

valid, msg = validate_person_name("Name{bad}")
check("curly braces rejected", not valid)

valid, msg = validate_person_name("Name\\path")
check("backslash rejected", not valid)

valid, msg = validate_person_name("Normal Person III")
check("normal name with roman numerals accepted", valid)

valid, msg = validate_person_name("José García")
check("unicode name accepted", valid)

# --- sanitize_filename ---
print("\n-- sanitize_filename --")

check("spaces to underscores", sanitize_filename("John Doe") == "john_doe")
check("strips special chars", sanitize_filename('File<>:"/\\|?*Name') == "filename")
check("truncates to 100", len(sanitize_filename("A" * 150)) <= 100)
check("empty becomes unnamed", sanitize_filename("") == "unnamed")
check("dots stripped from edges", sanitize_filename("...name...") == "name")
check("lowercase output", sanitize_filename("UPPERCASE") == "uppercase")

# --- save_brief_to_file ---
print("\n-- save_brief_to_file --")

with tempfile.TemporaryDirectory() as tmpdir:
    tmp_path = Path(tmpdir)

    result = save_brief_to_file("Test Person", "Brief content here", "sales call", tmp_path)
    check("returns a Path", result is not None and isinstance(result, Path))
    check("file exists", result.exists())

    content = result.read_text(encoding="utf-8")
    check("contains person name", "Test Person" in content)
    check("contains meeting context", "sales call" in content)
    check("contains brief content", "Brief content here" in content)
    check("contains generated timestamp", "Generated:" in content)

    # Without context
    result2 = save_brief_to_file("Another Person", "Some brief", "", tmp_path)
    check("works without context", result2 is not None and result2.exists())
    content2 = result2.read_text(encoding="utf-8")
    check("no context line when empty", "Meeting Context" not in content2)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
