#!/usr/bin/env python3
"""Test script for backend/tools.py — verify ToolExecutor init, graceful degradation, and timeouts."""

import asyncio
import sys
import time

sys.path.insert(0, sys.path[0] + "/..")

from tools import ToolExecutor

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


print("=== test_tools.py ===\n")

# --- ToolExecutor initialization ---
print("-- ToolExecutor init (no real API keys expected) --")

executor = ToolExecutor()
check("ToolExecutor created", executor is not None)
check("has tavily_client attr", hasattr(executor, "tavily_client"))
check("has firecrawl_client attr", hasattr(executor, "firecrawl_client"))
check("has brave_api_key attr", hasattr(executor, "brave_api_key"))

# --- Graceful degradation with missing keys ---
print("\n-- Graceful degradation (missing API keys) --")

result = executor.tavily_search("test query")
if executor.tavily_client is None:
    check("tavily returns error when no key", "error" in result)
else:
    check("tavily has client (key present)", True)

result = executor.brave_search("test query")
if executor.brave_api_key is None:
    check("brave returns error when no key", "error" in result)
else:
    check("brave has key (key present)", True)

result = executor.firecrawl_scrape("https://example.com")
if executor.firecrawl_client is None:
    check("firecrawl returns error when no key", "error" in result)
else:
    check("firecrawl has client (key present)", True)

# --- URL normalization + low-value filtering ---
print("\n-- URL normalization and filtering --")

normalized = executor._normalize_url("https://Example.com/news/item/?utm_source=x#section")
check("normalize_url strips query/fragment", normalized == "https://Example.com/news/item")
check("low-value URL detected", executor._is_low_value_url("https://example.com/login") is True)
check("high-value URL allowed", executor._is_low_value_url("https://example.com/blog/ceo-interview") is False)

# --- Search refinement ---
print("\n-- Search refinement (dedup + per-domain cap) --")
raw_results = [
    {"title": "A", "url": "https://a.com/post/1", "content": "recent interview 2025", "score": 1},
    {"title": "A duplicate", "url": "https://a.com/post/1?utm_source=x", "content": "recent interview 2025", "score": 2},
    {"title": "B", "url": "https://a.com/post/2", "content": "background", "score": 1},
    {"title": "C", "url": "https://a.com/post/3", "content": "background", "score": 1},
    {"title": "D", "url": "https://b.com/news/ceo", "content": "announced product", "score": 1},
    {"title": "E", "url": "https://c.com/search?q=john", "content": "search page", "score": 10},
]
refined = executor._refine_search_results("john doe interview", raw_results, max_results=8)
urls = [r.get("url") for r in refined]
check("dedup removes same canonical URL", urls.count("https://a.com/post/1") == 1)
check("per-domain cap enforced", sum(1 for u in urls if u and "a.com" in u) <= 2)
check("low-value search URL removed", all("/search" not in (u or "") for u in urls))

# --- Scrape low-value prefilter ---
print("\n-- firecrawl prefilter --")
skip_login = executor.firecrawl_scrape("https://example.com/login")
check("login URL skipped before client call", "error" in skip_login and "low-value" in skip_login["error"])


# --- execute_tool routing ---
print("\n-- execute_tool routing --")


async def test_execute_tool():
    # Unknown tool
    result = await executor.execute_tool("nonexistent_tool", {})
    check("unknown tool returns error", "error" in result)
    check("error mentions tool name", "nonexistent_tool" in result.get("error", ""))

    # Known tools route correctly (they'll return API key errors, which is fine)
    result = await executor.execute_tool("tavily_search", {"query": "test"})
    check("tavily_search routes without crash", isinstance(result, dict))

    result = await executor.execute_tool("brave_search", {"query": "test"})
    check("brave_search routes without crash", isinstance(result, dict))

    result = await executor.execute_tool("firecrawl_scrape", {"url": "https://example.com"})
    check("firecrawl_scrape routes without crash", isinstance(result, dict))


asyncio.run(test_execute_tool())

# --- Timeout mechanism ---
print("\n-- Timeout mechanism (execute_tool is async) --")


async def test_async_nature():
    """Verify execute_tool is async and doesn't block."""
    start = time.time()
    # This should return quickly (either error or actual result)
    result = await executor.execute_tool("tavily_search", {"query": "test"})
    elapsed = time.time() - start
    check("execute_tool returns in < 20s", elapsed < 20, f"took {elapsed:.1f}s")
    check("execute_tool returns dict", isinstance(result, dict))


asyncio.run(test_async_nature())

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
