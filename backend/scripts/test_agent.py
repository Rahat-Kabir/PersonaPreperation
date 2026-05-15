#!/usr/bin/env python3
"""Test script for backend/agent.py — verify deduplicated agent loop with mocked Anthropic client."""

import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, AsyncMock
from types import SimpleNamespace

sys.path.insert(0, sys.path[0] + "/..")

# Isolate the cache from the real backend/cache.db. Must be set BEFORE
# importing `agent`, which imports `cache` at module load time.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP_DB.close()
os.environ["CACHE_DB_PATH"] = _TMP_DB.name

import cache  # noqa: E402
cache.init_db()

from agent import (
    _build_query_plan,
    _build_user_prompt,
    _compact_tool_result_for_model,
    disambiguate_person_name,
    _make_event,
    _summarize_tool_result,
    _run_agent_loop,
    research_person_with_tools,
    research_person_with_tools_stream,
)

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


print("=== test_agent.py ===\n")

# --- Helper functions ---
print("-- _build_query_plan --")

plan = _build_query_plan("John Doe", "sales call")
check("query plan has identity_query", "identity_query" in plan and "John Doe" in plan["identity_query"])
check("query plan has recency_query", "recency_query" in plan and "2025" in plan["recency_query"])
check("query plan has perspective_query", "perspective_query" in plan and "sales call" in plan["perspective_query"])

print("-- _build_user_prompt --")

prompt = _build_user_prompt("John Doe", "")
check("prompt contains person name", "John Doe" in prompt)
check("prompt without context has no 'Meeting context'", "Meeting context" not in prompt)

prompt_ctx = _build_user_prompt("Jane Smith", "sales call")
check("prompt with context includes it", "sales call" in prompt_ctx)
check("prompt with context has 'Meeting context'", "Meeting context" in prompt_ctx)
check("prompt includes deterministic query plan", "Follow this search plan first" in prompt_ctx)

selected_prompt = _build_user_prompt(
    "Jane Smith",
    "sales call",
    selected_identity={
        "name": "Jane Smith",
        "title": "VP Sales",
        "organization": "Acme",
        "profile_url": "https://example.com/jane",
    },
)
check("selected identity prompt includes anchor block", "Selected identity" in selected_prompt)
check("selected identity prompt includes profile URL", "https://example.com/jane" in selected_prompt)

print("\n-- _make_event --")

event = _make_event("start", {"person_name": "Test"}, 1)
check("event has event_type", event["event_type"] == "start")
check("event has data", event["data"]["person_name"] == "Test")
check("event has timestamp", "timestamp" in event)
check("event has iteration", event["iteration"] == 1)

event_no_iter = _make_event("error", {"error": "oops"})
check("event without iteration defaults to None", event_no_iter["iteration"] is None)

print("\n-- _summarize_tool_result --")

summary = _summarize_tool_result("tavily_search", {"count": 5, "results": []})
check("search summary success", summary["success"] is True)
check("search summary message", "5" in summary["message"])

summary_err = _summarize_tool_result("tavily_search", {"error": "API down"})
check("error summary", summary_err["success"] is False)
check("error has message", "API down" in summary_err["error"])

summary_scrape = _summarize_tool_result("firecrawl_scrape", {"markdown": "x" * 500, "url": "http://example.com"})
check("scrape summary success", summary_scrape["success"] is True)
check("scrape summary has char count", "500" in summary_scrape["message"])

print("\n-- _compact_tool_result_for_model --")
compact_search = _compact_tool_result_for_model(
    "tavily_search",
    {"query": "q", "count": 1, "results": [{"title": "T", "url": "https://a.com", "content": "x" * 1000}]},
)
check("compact search keeps results", len(compact_search["results"]) == 1)
check("compact search truncates summary", len(compact_search["results"][0]["summary"]) <= 400)

compact_scrape = _compact_tool_result_for_model("firecrawl_scrape", {"url": "https://a.com", "markdown": "y" * 5000, "success": True})
check("compact scrape has excerpt", "markdown_excerpt" in compact_scrape)
check("compact scrape truncates excerpt", len(compact_scrape["markdown_excerpt"]) <= 1800)

# --- Mock Anthropic client for agent loop tests ---
print("\n-- _run_agent_loop (mocked, end_turn immediately) --")


def make_mock_client_end_turn(text="Mock brief content"):
    """Create a mock Anthropic client that returns end_turn immediately."""
    text_block = SimpleNamespace(type="text", text=text)
    response = SimpleNamespace(stop_reason="end_turn", content=[text_block])
    client = MagicMock()
    client.messages.create = MagicMock(return_value=response)
    return client


def make_mock_tool_executor():
    """Create a mock ToolExecutor."""
    executor = MagicMock()
    executor.execute_tool = AsyncMock(return_value={"count": 3, "results": [], "query": "test"})
    return executor


async def test_agent_loop_end_turn():
    cache.clear_all()
    client = make_mock_client_end_turn("Test brief output")
    executor = make_mock_tool_executor()
    events = []

    async def collect(event):
        events.append(event)

    result = await _run_agent_loop(client, executor, "John Doe", "meeting", collect)

    check("returns brief text", result == "Test brief output")

    event_types = [e["event_type"] for e in events]
    check("emits start event", "start" in event_types)
    check("emits thinking event", "thinking" in event_types)
    check("emits complete event", "complete" in event_types)
    check("no error events", "error" not in event_types)

    complete_event = [e for e in events if e["event_type"] == "complete"][0]
    check("complete has brief", complete_event["data"]["brief"] == "Test brief output")
    check("complete has person_name", complete_event["data"]["person_name"] == "John Doe")


asyncio.run(test_agent_loop_end_turn())

# --- Agent loop with tool use then end_turn ---
print("\n-- _run_agent_loop (mocked, tool_use then end_turn) --")


def make_mock_client_with_tool():
    """Mock client that first requests a tool, then returns end_turn."""
    tool_block = SimpleNamespace(
        type="tool_use",
        name="tavily_search",
        input={"query": "John Doe"},
        id="tool_123",
    )
    tool_response = SimpleNamespace(stop_reason="tool_use", content=[tool_block])

    text_block = SimpleNamespace(type="text", text="Final brief after tools")
    final_response = SimpleNamespace(stop_reason="end_turn", content=[text_block])

    client = MagicMock()
    client.messages.create = MagicMock(side_effect=[tool_response, final_response])
    return client


async def test_agent_loop_with_tool():
    cache.clear_all()
    client = make_mock_client_with_tool()
    executor = make_mock_tool_executor()
    events = []

    async def collect(event):
        events.append(event)

    result = await _run_agent_loop(client, executor, "John Doe", "", collect)

    check("returns final brief", result == "Final brief after tools")

    event_types = [e["event_type"] for e in events]
    check("emits tool_call event", "tool_call" in event_types)
    check("emits tool_result event", "tool_result" in event_types)
    check("emits complete event", "complete" in event_types)

    tool_call = [e for e in events if e["event_type"] == "tool_call"][0]
    check("tool_call has tool_name", tool_call["data"]["tool_name"] == "tavily_search")

    executor.execute_tool.assert_called_once()
    check("executor called with correct tool", True)


asyncio.run(test_agent_loop_with_tool())

# --- Duplicate tool call skipping ---
print("\n-- _run_agent_loop (duplicate tool calls are skipped) --")


def make_mock_client_with_duplicate_tool_calls():
    """Mock client requests the same tool input twice before end_turn."""
    tool_block_1 = SimpleNamespace(
        type="tool_use",
        name="tavily_search",
        input={"query": "John Doe"},
        id="tool_1",
    )
    tool_block_2 = SimpleNamespace(
        type="tool_use",
        name="tavily_search",
        input={"query": "John Doe"},
        id="tool_2",
    )

    first_response = SimpleNamespace(stop_reason="tool_use", content=[tool_block_1])
    second_response = SimpleNamespace(stop_reason="tool_use", content=[tool_block_2])
    final_response = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Done")])

    client = MagicMock()
    client.messages.create = MagicMock(side_effect=[first_response, second_response, final_response])
    return client


async def test_duplicate_skip():
    cache.clear_all()
    client = make_mock_client_with_duplicate_tool_calls()
    executor = make_mock_tool_executor()
    events = []

    async def collect(event):
        events.append(event)

    result = await _run_agent_loop(client, executor, "John Doe", "", collect)
    check("returns final text after duplicate scenario", result == "Done")
    check("duplicate tool call skipped (executor called once)", executor.execute_tool.call_count == 1)
    tool_result_events = [e for e in events if e["event_type"] == "tool_result"]
    check(
        "duplicate skip emits explicit skip error summary",
        any("Skipped duplicate tool call" in str(e.get("data", {})) for e in tool_result_events),
    )


asyncio.run(test_duplicate_skip())

# --- max_tokens continuation handling ---
print("\n-- _run_agent_loop (max_tokens continuation) --")


def make_mock_client_max_tokens_then_end():
    """Mock client that first returns max_tokens, then completes."""
    partial = SimpleNamespace(type="text", text="Partial brief...")
    first_response = SimpleNamespace(stop_reason="max_tokens", content=[partial])
    final_text = SimpleNamespace(type="text", text="Final completed brief")
    second_response = SimpleNamespace(stop_reason="end_turn", content=[final_text])
    client = MagicMock()
    client.messages.create = MagicMock(side_effect=[first_response, second_response])
    return client


async def test_max_tokens_continuation():
    cache.clear_all()
    client = make_mock_client_max_tokens_then_end()
    executor = make_mock_tool_executor()
    events = []

    async def collect(event):
        events.append(event)

    result = await _run_agent_loop(client, executor, "John Doe", "board meeting", collect)
    check("max_tokens path still returns final brief", result == "Final completed brief")
    check("max_tokens path ends with complete event", any(e["event_type"] == "complete" for e in events))


asyncio.run(test_max_tokens_continuation())

# --- Invalid name ---
print("\n-- _run_agent_loop (invalid name) --")


async def test_agent_loop_invalid_name():
    client = make_mock_client_end_turn()
    executor = make_mock_tool_executor()
    events = []

    async def collect(event):
        events.append(event)

    result = await _run_agent_loop(client, executor, "", "", collect)

    check("returns None for invalid name", result is None)
    check("emits error event", any(e["event_type"] == "error" for e in events))


asyncio.run(test_agent_loop_invalid_name())

# --- research_person_with_tools (non-streaming) ---
print("\n-- research_person_with_tools (non-streaming) --")


async def test_non_streaming():
    cache.clear_all()
    client = make_mock_client_end_turn("Non-streaming brief")
    executor = make_mock_tool_executor()

    result = await research_person_with_tools(client, executor, "Test Person", "interview")

    check("non-streaming returns brief", result == "Non-streaming brief")


asyncio.run(test_non_streaming())

# --- research_person_with_tools_stream (streaming) ---
print("\n-- research_person_with_tools_stream (streaming) --")


async def test_streaming():
    cache.clear_all()
    client = make_mock_client_end_turn("Streaming brief")
    executor = make_mock_tool_executor()

    events = []
    async for event in research_person_with_tools_stream(client, executor, "Test Person", "meeting"):
        events.append(event)

    event_types = [e["event_type"] for e in events]
    check("streaming yields start", "start" in event_types)
    check("streaming yields complete", "complete" in event_types)

    complete = [e for e in events if e["event_type"] == "complete"][0]
    check("streaming complete has brief", complete["data"]["brief"] == "Streaming brief")


asyncio.run(test_streaming())

# --- disambiguate_person_name ---
print("\n-- disambiguate_person_name --")


class MockDisambiguationExecutor:
    def __init__(self, tavily_results):
        self._tavily_results = tavily_results

    async def execute_tool(self, tool_name, tool_input, cache_bypass=False):
        if tool_name == "tavily_search":
            return {"results": self._tavily_results, "count": len(self._tavily_results)}
        if tool_name == "brave_search":
            return {"results": [], "count": 0}
        return {"error": "unexpected"}


async def test_disambiguation_statuses():
    no_match_exec = MockDisambiguationExecutor([{"title": "Unrelated", "url": "https://x.com", "content": "none"}])
    no_match = await disambiguate_person_name(no_match_exec, "Jane Smith", "")
    check("disambiguation no_match status", no_match["status"] == "no_match")

    direct_exec = MockDisambiguationExecutor([
        {
            "title": "Jane Smith - VP Sales at Acme",
            "url": "https://www.linkedin.com/in/janesmith",
            "content": "Jane Smith is VP Sales at Acme",
        }
    ])
    direct = await disambiguate_person_name(direct_exec, "Jane Smith", "")
    check("disambiguation direct status", direct["status"] == "direct")
    check("disambiguation returns candidate", len(direct["candidates"]) == 1)

    ambiguous_exec = MockDisambiguationExecutor([
        {
            "title": "Jane Smith - VP Sales at Acme",
            "url": "https://www.linkedin.com/in/janesmith",
            "content": "Jane Smith at Acme",
        },
        {
            "title": "Jane Smith - Product Director at Beta",
            "url": "https://www.linkedin.com/in/janesmith-beta",
            "content": "Jane Smith at Beta",
        },
    ])
    ambiguous = await disambiguate_person_name(ambiguous_exec, "Jane Smith", "")
    check("disambiguation ambiguous status", ambiguous["status"] == "ambiguous")
    check("disambiguation requires selection", ambiguous["needs_disambiguation"] is True)

    enriched = await disambiguate_person_name(
        direct_exec,
        "Jane Smith, VP Sales at Acme",
        "intro meeting",
    )
    check("enriched person input still resolves direct", enriched["status"] == "direct")

    # strict-hint fallback: no hint overlap but still return closest candidates
    fallback_exec = MockDisambiguationExecutor([
        {
            "title": "Jane Smith - VP Sales at Acme",
            "url": "https://www.linkedin.com/in/janesmith",
            "content": "Jane Smith at Acme",
        },
        {
            "title": "Jane Smith - Product Director at Beta",
            "url": "https://www.linkedin.com/in/janesmith-beta",
            "content": "Jane Smith at Beta",
        },
    ])
    fallback = await disambiguate_person_name(fallback_exec, "Jane Smith from NSU", "")
    check("strict hint fallback returns ambiguous list", fallback["status"] == "ambiguous")
    check("strict hint fallback provides candidates", len(fallback["candidates"]) > 0)

    weak_single_exec = MockDisambiguationExecutor([
        {
            "title": "Jane at Acme",
            "url": "https://example.com/jane",
            "content": "Profile page",
        }
    ])
    weak_single = await disambiguate_person_name(weak_single_exec, "Jane Smith", "")
    check("single weak candidate is not auto-direct", weak_single["status"] == "ambiguous")


asyncio.run(test_disambiguation_statuses())

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
