#!/usr/bin/env python3
"""CLI entry point for PersonaPreparation — research people from the terminal."""

import argparse
import asyncio
import os

from dotenv import load_dotenv
from anthropic import Anthropic

import cache
from agent import research_person_with_tools
from tools import ToolExecutor
from utils import save_brief_to_file


async def main() -> None:
    parser = argparse.ArgumentParser(description="PersonaPreparation CLI")
    parser.add_argument(
        "--force-refresh",
        "--no-cache",
        dest="force_refresh",
        action="store_true",
        help="Bypass the cache and re-run searches + agent loop from scratch.",
    )
    args = parser.parse_args()

    load_dotenv()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or api_key.startswith("your-"):
        print("\nERROR: Missing or invalid ANTHROPIC_API_KEY in .env")
        print("Get your key from: https://console.anthropic.com/")
        return

    cache.init_db()

    client = Anthropic(api_key=api_key)
    tool_executor = ToolExecutor()

    # Show available tools
    available = []
    if tool_executor.tavily_client:
        available.append("Tavily")
    if tool_executor.firecrawl_client:
        available.append("Firecrawl")
    if tool_executor.brave_api_key:
        available.append("Brave")

    print("\n" + "=" * 60)
    print("PersonaPreparation CLI")
    print("=" * 60)
    if available:
        print(f"Tools: {', '.join(available)}")
    else:
        print("WARNING: No research tools configured. Add API keys to .env")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            person_name = input("Person to research: ").strip()
            if not person_name:
                continue
            if person_name.lower() in ("quit", "exit", "q"):
                break

            meeting_context = input("Meeting context (optional): ").strip()

            print(f"\nResearching {person_name}...\n")
            brief = await research_person_with_tools(
                client,
                tool_executor,
                person_name,
                meeting_context,
                force_refresh=args.force_refresh,
            )

            if brief:
                print("\n" + "=" * 60)
                print(brief)
                print("=" * 60)

                save = input("\nSave to file? (y/n): ").strip().lower()
                if save == "y":
                    path = save_brief_to_file(person_name, brief, meeting_context)
                    if path:
                        print(f"Saved to: {path}")
            else:
                print("\nFailed to generate brief.\n")

        except (KeyboardInterrupt, EOFError):
            print("\n")
            break


if __name__ == "__main__":
    asyncio.run(main())
