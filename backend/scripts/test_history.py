#!/usr/bin/env python3
"""Test script for backend/history.py — saved brief history.

Covers:
  * insert + list + get + delete roundtrip
  * pagination correctness (limit/offset slice the right window)
  * total count returned alongside paged items
  * delete-missing returns False (404 path on the API)
  * cache hit on agent loop does NOT create a duplicate history row
  * blank brief is rejected
"""

import asyncio
import os
import sys
import tempfile
from unittest.mock import MagicMock
from types import SimpleNamespace

sys.path.insert(0, sys.path[0] + "/..")

# Isolate the DB BEFORE importing cache/history/agent.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["CACHE_DB_PATH"] = _TMP_DB.name

import cache  # noqa: E402
import history  # noqa: E402

cache.init_db()  # also initialises history table

from agent import _run_agent_loop, _brief_cache_key  # noqa: E402

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


print("=== test_history.py ===\n")

# --- Schema sanity --------------------------------------------------------
history.clear_all()
empty = history.list_items()
check("list returns total=0 on empty table", empty["total"] == 0 and empty["items"] == [])

# --- Insert + get ---------------------------------------------------------
identity = {"name": "Rahat Kabir", "title": "AI engineer", "organization": "Acme", "profile_url": "https://example.com/rahat"}
row_id = history.insert("Rahat Kabir", "intro chat", identity, "## Brief\n\nHello world.")
check("insert returns a row id", isinstance(row_id, int) and row_id > 0, detail=f"id={row_id}")

fetched = history.get(row_id)
check("get returns the row", fetched is not None and fetched["id"] == row_id)
check("get includes brief body", fetched and fetched["brief"] == "## Brief\n\nHello world.")
check("selected_identity round-trips as dict", fetched and fetched["selected_identity"]["name"] == "Rahat Kabir")
check("created_at is populated", fetched and isinstance(fetched["created_at"], int) and fetched["created_at"] > 0)

# --- list_items omits brief body ------------------------------------------
listed = history.list_items()
check("list returns total=1", listed["total"] == 1 and len(listed["items"]) == 1)
check("list item omits brief body", "brief" not in listed["items"][0])

# --- Blank brief is rejected ----------------------------------------------
bad_id = history.insert("Nobody", "", None, "   ")
check("blank brief is not inserted", bad_id is None and history.list_items()["total"] == 1)

# --- Pagination -----------------------------------------------------------
history.clear_all()
ids = []
for i in range(5):
    new_id = history.insert(f"Person {i}", f"context {i}", None, f"brief {i}")
    assert new_id is not None
    ids.append(new_id)

page = history.list_items(limit=2, offset=1)
check("pagination total stays at 5", page["total"] == 5)
check("limit=2 returns 2 items", len(page["items"]) == 2, detail=str(len(page["items"])))
# Most recent first: ids inserted in order [0..4], so DESC = [4,3,2,1,0]; offset=1 -> [3,2]
expected_names = ["Person 3", "Person 2"]
got_names = [item["person_name"] for item in page["items"]]
check("pagination slices correct window in DESC order", got_names == expected_names, detail=f"got {got_names}")

# --- Delete ---------------------------------------------------------------
deleted = history.delete(ids[0])
check("delete returns True for existing row", deleted is True)
check("row is gone after delete", history.get(ids[0]) is None)
check("total decremented after delete", history.list_items()["total"] == 4)

missing = history.delete(99999)
check("delete returns False for missing row", missing is False)

# --- Agent loop wiring: cache hit must NOT create duplicate history row ---
history.clear_all()
cache.clear_all()


def make_mock_client_end_turn(text: str):
    """A minimal mock Anthropic client whose first response ends the turn."""
    response = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )
    client = MagicMock()
    client.messages.create.return_value = response
    return client


class _DummyExecutor:
    async def execute_tool(self, tool_name, tool_input, cache_bypass=False):
        return {"results": [], "count": 0}


async def _noop_event(_event):
    pass


async def _run_first():
    return await _run_agent_loop(
        make_mock_client_end_turn("Generated brief #1"),
        _DummyExecutor(),
        "Cache Hit Person",
        "test context",
        _noop_event,
    )


async def _run_second():
    # Same name + context + identity -> identical brief cache key -> hit.
    return await _run_agent_loop(
        make_mock_client_end_turn("Should not be used"),
        _DummyExecutor(),
        "Cache Hit Person",
        "test context",
        _noop_event,
    )


brief_first = asyncio.run(_run_first())
check("first run returned a brief", brief_first == "Generated brief #1")
check("first run inserted exactly 1 history row", history.list_items()["total"] == 1)

# Sanity: the brief cache actually has the entry now.
key = _brief_cache_key("Cache Hit Person", "test context", None, False)
check("brief cache populated after first run", cache.get(key) == "Generated brief #1")

brief_second = asyncio.run(_run_second())
check("second run served the cached brief", brief_second == "Generated brief #1")
check("cache hit did NOT create a duplicate history row", history.list_items()["total"] == 1)

# --- Cleanup --------------------------------------------------------------
history.clear_all()
cache.clear_all()
try:
    os.unlink(_TMP_DB.name)
except OSError:
    pass

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
