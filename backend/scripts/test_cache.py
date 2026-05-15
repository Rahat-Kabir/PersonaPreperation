#!/usr/bin/env python3
"""Test script for backend/cache.py — SQLite tool/brief cache.

Covers:
  * basic get/set/expiry/delete
  * key normalization (case + whitespace)
  * tool-cache hit through ToolExecutor.execute_tool (stubbed)
  * cache_bypass + force_refresh skipping the cache
  * brief cache key stability across context/identity changes
  * ResearchRequest accepts force_refresh
"""

import asyncio
import os
import sys
import tempfile
import time

sys.path.insert(0, sys.path[0] + "/..")

# Use a throwaway DB for the test — must be set BEFORE importing cache.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["CACHE_DB_PATH"] = _TMP_DB.name

import cache  # noqa: E402
from agent import _brief_cache_key  # noqa: E402
from models import ResearchRequest  # noqa: E402
from tools import ToolExecutor, _normalize_tool_input  # noqa: E402

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


print("=== test_cache.py ===\n")

cache.init_db()
cache.clear_all()

# --- Basic get/set/delete -------------------------------------------------
key = cache.build_key("test", {"q": "hello"})
check("key is sha256 hex", len(key) == 64 and all(c in "0123456789abcdef" for c in key))

check("miss returns None before set", cache.get(key) is None)

cache.set(key, {"answer": 42}, ttl_seconds=60)
hit = cache.get(key)
check("hit returns stored value", hit == {"answer": 42}, detail=str(hit))

cache.delete(key)
check("delete removes the entry", cache.get(key) is None)

# --- Expiry ---------------------------------------------------------------
short_key = cache.build_key("test", {"k": "expiring"})
cache.set(short_key, "stale", ttl_seconds=1)
time.sleep(1.2)
check("expired entry treated as miss", cache.get(short_key) is None)

# --- purge_expired --------------------------------------------------------
cache.set(cache.build_key("test", {"p": 1}), "v1", ttl_seconds=1)
cache.set(cache.build_key("test", {"p": 2}), "v2", ttl_seconds=120)
time.sleep(1.2)
removed = cache.purge_expired()
check("purge_expired returns at least one removed", removed >= 1, detail=f"removed={removed}")

# --- Key normalization (tool inputs) -------------------------------------
norm_a = _normalize_tool_input({"query": "Rahat Kabir", "max_results": 5})
norm_b = _normalize_tool_input({"query": "  rahat   kabir  ", "max_results": 5})
check("normalize collapses case + whitespace", norm_a == norm_b, detail=f"{norm_a} vs {norm_b}")

key_a = cache.build_key("tool:tavily_search", norm_a)
key_b = cache.build_key("tool:tavily_search", norm_b)
check("normalized inputs hash to same key", key_a == key_b)

key_diff = cache.build_key("tool:tavily_search", _normalize_tool_input({"query": "rahat kabir", "max_results": 10}))
check("different max_results = different key", key_a != key_diff)

# --- Tool cache through ToolExecutor (stubbed network call) ---------------
cache.clear_all()
executor = ToolExecutor()

call_count = {"n": 0}

def fake_tavily(query: str, max_results: int = 5):
    call_count["n"] += 1
    return {
        "query": query,
        "count": 1,
        "results": [{"title": "x", "url": "https://example.com", "content": "y"}],
        "selected_urls": ["https://example.com"],
    }

executor.tavily_search = fake_tavily  # type: ignore[assignment]

async def _call(query: str, *, bypass: bool = False):
    return await executor.execute_tool(
        "tavily_search",
        {"query": query, "max_results": 5},
        cache_bypass=bypass,
    )

r1 = asyncio.run(_call("Rahat Kabir"))
check("first call invokes underlying tool", call_count["n"] == 1, detail=f"n={call_count['n']}")

r2 = asyncio.run(_call("rahat   kabir"))
check("second normalized call served from cache", call_count["n"] == 1, detail=f"n={call_count['n']}")

r3 = asyncio.run(_call("rahat kabir", bypass=True))
check("cache_bypass forces a fresh call", call_count["n"] == 2, detail=f"n={call_count['n']}")
check("cached result equals original payload", r1 == r2)
check("bypass result has same shape", "results" in r3)

# --- Errors must NOT be cached -------------------------------------------
cache.clear_all()
err_count = {"n": 0}

def fake_tavily_err(query: str, max_results: int = 5):
    err_count["n"] += 1
    return {"error": "Tavily blew up"}

executor.tavily_search = fake_tavily_err  # type: ignore[assignment]

async def _run_error_scenario():
    await executor.execute_tool("tavily_search", {"query": "boom"})
    await executor.execute_tool("tavily_search", {"query": "boom"})

asyncio.run(_run_error_scenario())
check("errors are NOT cached (both calls hit underlying tool)", err_count["n"] == 2, detail=f"n={err_count['n']}")

# --- Brief cache key behaviour -------------------------------------------
k_base = _brief_cache_key("Rahat Kabir", "AI engineer", None, False)
k_same = _brief_cache_key("rahat   kabir", "ai   engineer", None, False)
check("brief key normalises name + context", k_base == k_same)

k_other_context = _brief_cache_key("Rahat Kabir", "student of NSU", None, False)
check("different context = different brief key", k_base != k_other_context)

identity_a = {"name": "Rahat Kabir", "organization": "Acme", "profile_url": "https://example.com/a"}
identity_b = {"name": "Rahat Kabir", "organization": "Acme", "profile_url": "https://example.com/b"}
k_id_a = _brief_cache_key("Rahat Kabir", "AI engineer", identity_a, False)
k_id_b = _brief_cache_key("Rahat Kabir", "AI engineer", identity_b, False)
check("different selected identities = different brief keys", k_id_a != k_id_b)

k_continue = _brief_cache_key("Rahat Kabir", "AI engineer", None, True)
check("continue_anyway flips brief key", k_base != k_continue)

# Same profile_url + name + org but different title => different brief.
identity_title_a = {"name": "Jane Smith", "title": "VP Sales", "organization": "Acme", "profile_url": "https://example.com/jane"}
identity_title_b = {"name": "Jane Smith", "title": "CTO", "organization": "Acme", "profile_url": "https://example.com/jane"}
k_title_a = _brief_cache_key("Jane Smith", "intro", identity_title_a, False)
k_title_b = _brief_cache_key("Jane Smith", "intro", identity_title_b, False)
check("identity title difference flips brief key", k_title_a != k_title_b)

# --- ResearchRequest accepts force_refresh -------------------------------
req_default = ResearchRequest(person_name="Rahat Kabir", meeting_context="AI engineer")
check("force_refresh defaults to False", req_default.force_refresh is False)

req_force = ResearchRequest(person_name="Rahat Kabir", meeting_context="AI engineer", force_refresh=True)
check("force_refresh stored when set", req_force.force_refresh is True)

# --- Cleanup --------------------------------------------------------------
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
