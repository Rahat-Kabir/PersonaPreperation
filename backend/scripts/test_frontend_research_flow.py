#!/usr/bin/env python3
"""Verify the redesigned frontend research flow keeps its core states and UI hooks."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAGE_FILE = ROOT / "frontend" / "src" / "app" / "page.tsx"
GLOBALS_FILE = ROOT / "frontend" / "src" / "app" / "globals.css"
LAYOUT_FILE = ROOT / "frontend" / "src" / "app" / "layout.tsx"

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


print("=== test_frontend_research_flow.py ===\n")

page_source = PAGE_FILE.read_text(encoding="utf-8")
globals_source = GLOBALS_FILE.read_text(encoding="utf-8")
layout_source = LAYOUT_FILE.read_text(encoding="utf-8")

check(
    "page declares the 4-state app flow",
    'type AppState = "input" | "disambiguation" | "researching" | "result";' in page_source,
    "frontend/src/app/page.tsx should keep the explicit 4-state UI contract",
)
check(
    "researching state keeps the progress ring",
    "function ProgressRing" in page_source and "iteration={currentIteration}" in page_source,
    "frontend/src/app/page.tsx should render the progress ring during research",
)
check(
    "disambiguation flow keeps confirm and skip actions",
    "Confirm &amp; Research" in page_source and "Skip &mdash; research without selecting" in page_source,
    "frontend/src/app/page.tsx should preserve both disambiguation actions",
)
check(
    "result state keeps copy and restart controls",
    '{copied ? "Copied" : "Copy"}' in page_source and "New" in page_source,
    "frontend/src/app/page.tsx should preserve result actions for copy and new research",
)
check(
    "dark theme stylesheet keeps dossier styling",
    ".prose-dossier" in globals_source and "--accent: #E8C872;" in globals_source,
    "frontend/src/app/globals.css should keep the dark dossier theme tokens",
)
check(
    "root layout forces dark mode",
    '<html lang="en" className="dark">' in layout_source,
    "frontend/src/app/layout.tsx should opt the app into dark mode",
)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
