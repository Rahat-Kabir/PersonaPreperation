#!/usr/bin/env python3
"""Test script for backend/config.py — verify all constants, prompt, and tool definitions load."""

import sys
sys.path.insert(0, sys.path[0] + "/..")

from config import (
    DEFAULT_MODEL,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY,
    MAX_TOOL_ITERATIONS,
    MAX_PERSON_NAME_LENGTH,
    MAX_SEARCH_RESULTS,
    MAX_RESULTS_PER_DOMAIN,
    MAX_SCRAPE_MARKDOWN_CHARS,
    MIN_EVIDENCE_SOURCES,
    MAX_CONSECUTIVE_LOW_VALUE_ITERATIONS,
    ANTHROPIC_TIMEOUT,
    TAVILY_TIMEOUT,
    FIRECRAWL_TIMEOUT,
    BRAVE_TIMEOUT,
    OUTPUT_DIR,
    SYSTEM_PROMPT,
    TOOLS,
    logger,
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


print("=== test_config.py ===\n")

# Constants exist and have sane values
check("DEFAULT_MODEL is string", isinstance(DEFAULT_MODEL, str) and len(DEFAULT_MODEL) > 0)
check("DEFAULT_MAX_TOKENS > 0", DEFAULT_MAX_TOKENS > 0)
check("DEFAULT_MAX_RETRIES > 0", DEFAULT_MAX_RETRIES > 0)
check("DEFAULT_RETRY_DELAY > 0", DEFAULT_RETRY_DELAY > 0)
check("MAX_TOOL_ITERATIONS > 0", MAX_TOOL_ITERATIONS > 0)
check("MAX_PERSON_NAME_LENGTH > 0", MAX_PERSON_NAME_LENGTH > 0)
check("MAX_SEARCH_RESULTS > 0", MAX_SEARCH_RESULTS > 0)
check("MAX_RESULTS_PER_DOMAIN > 0", MAX_RESULTS_PER_DOMAIN > 0)
check("MAX_SCRAPE_MARKDOWN_CHARS > 0", MAX_SCRAPE_MARKDOWN_CHARS > 0)
check("MIN_EVIDENCE_SOURCES > 0", MIN_EVIDENCE_SOURCES > 0)
check("MAX_CONSECUTIVE_LOW_VALUE_ITERATIONS > 0", MAX_CONSECUTIVE_LOW_VALUE_ITERATIONS > 0)

# Timeout constants
check("ANTHROPIC_TIMEOUT > 0", ANTHROPIC_TIMEOUT > 0)
check("TAVILY_TIMEOUT > 0", TAVILY_TIMEOUT > 0)
check("FIRECRAWL_TIMEOUT > 0", FIRECRAWL_TIMEOUT > 0)
check("BRAVE_TIMEOUT > 0", BRAVE_TIMEOUT > 0)

# OUTPUT_DIR is a Path
from pathlib import Path
check("OUTPUT_DIR is Path", isinstance(OUTPUT_DIR, Path))

# System prompt
check("SYSTEM_PROMPT is non-empty string", isinstance(SYSTEM_PROMPT, str) and len(SYSTEM_PROMPT) > 100)
check("SYSTEM_PROMPT mentions PersonaPreparation", "PersonaPreparation" in SYSTEM_PROMPT)
check("SYSTEM_PROMPT mentions tavily_search", "tavily_search" in SYSTEM_PROMPT)
check("SYSTEM_PROMPT mentions brave_search", "brave_search" in SYSTEM_PROMPT)
check("SYSTEM_PROMPT mentions firecrawl_scrape", "firecrawl_scrape" in SYSTEM_PROMPT)

# Tool definitions
check("TOOLS is a list", isinstance(TOOLS, list))
check("TOOLS has 3 tools", len(TOOLS) == 3)

tool_names = [t["name"] for t in TOOLS]
check("tavily_search in TOOLS", "tavily_search" in tool_names)
check("brave_search in TOOLS", "brave_search" in tool_names)
check("firecrawl_scrape in TOOLS", "firecrawl_scrape" in tool_names)

for tool in TOOLS:
    name = tool["name"]
    check(f"{name} has description", "description" in tool and len(tool["description"]) > 0)
    check(f"{name} has input_schema", "input_schema" in tool)
    check(f"{name} schema has required", "required" in tool["input_schema"])

# Logger
check("logger exists", logger is not None)
check("logger has name", logger.name == "persona_preparation")

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
