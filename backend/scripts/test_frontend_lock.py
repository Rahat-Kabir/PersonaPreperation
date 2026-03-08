#!/usr/bin/env python3
"""Verify the frontend lockfile explicitly pins baseline-browser-mapping."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"
PACKAGE_JSON = FRONTEND_DIR / "package.json"
PACKAGE_LOCK = FRONTEND_DIR / "package-lock.json"
PACKAGE_NAME = "baseline-browser-mapping"

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


print("=== test_frontend_lock.py ===\n")

package_json = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
package_lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))

package_dev_dependencies = package_json.get("devDependencies", {})
lock_root_packages = package_lock.get("packages", {})
lock_root = lock_root_packages.get("", {})
lock_root_dev_dependencies = lock_root.get("devDependencies", {})
lock_package = lock_root_packages.get(f"node_modules/{PACKAGE_NAME}", {})

declared_range = package_dev_dependencies.get(PACKAGE_NAME)
lock_declared_range = lock_root_dev_dependencies.get(PACKAGE_NAME)
lock_version = lock_package.get("version")

check(
    "package.json declares baseline-browser-mapping",
    isinstance(declared_range, str) and len(declared_range) > 0,
    "frontend/package.json is missing the direct devDependency",
)
check(
    "package-lock root records the same dependency range",
    declared_range == lock_declared_range,
    f"package.json has {declared_range!r}, package-lock root has {lock_declared_range!r}",
)
check(
    "package-lock contains installed baseline-browser-mapping package",
    isinstance(lock_version, str) and len(lock_version) > 0,
    "frontend/package-lock.json is missing node_modules/baseline-browser-mapping",
)
check(
    "installed version matches the declared minimum",
    lock_version == declared_range.removeprefix("^"),
    f"expected installed version {declared_range!r}, found {lock_version!r}",
)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
