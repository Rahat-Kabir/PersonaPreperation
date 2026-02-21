#!/usr/bin/env python3
"""Evaluate brief quality across fixed persona/context cases.

Usage:
  uv run python scripts/eval_quality.py --output scripts/eval_baseline.json
  uv run python scripts/eval_quality.py --output scripts/eval_after.json
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import research_person_with_tools
from tools import ToolExecutor


@dataclass
class EvalCase:
    person_name: str
    meeting_context: str


CASES: list[EvalCase] = [
    EvalCase("Satya Nadella", "Enterprise software partnership discussion"),
    EvalCase("Jensen Huang", "AI infrastructure procurement conversation"),
    EvalCase("Mary Barra", "Automotive technology partnership pitch"),
    EvalCase("Reed Hastings", "Media strategy advisory call"),
    EvalCase("Adena Friedman", "Fintech market-data integration meeting"),
    EvalCase("Demis Hassabis", "Applied AI research collaboration call"),
    EvalCase("Susan Wojcicki", "Creator economy product strategy interview"),
    EvalCase("Arvind Krishna", "Enterprise AI transformation workshop"),
    EvalCase("Melanie Perkins", "B2B design platform integration pitch"),
    EvalCase("Patrick Collison", "Payments infrastructure partner review"),
]


REQUIRED_SECTIONS = [
    "Executive Summary",
    "Professional Background",
    "Recent Activity",
    "DO",
    "DON'T",
    "Conversation Openers",
    "Bottom Line Recommendation",
]


def _count_bullets(section_text: str) -> int:
    return len(re.findall(r"(?m)^\s*[-*]\s+", section_text))


def _extract_section(brief: str, section_label: str) -> str:
    pattern = rf"(?is)(?:^|\n)#+\s*{re.escape(section_label)}.*?(?=\n#+\s|\Z)"
    match = re.search(pattern, brief)
    return match.group(0) if match else ""


def score_brief(brief: str) -> dict[str, Any]:
    lowered = brief.lower()
    section_hits = sum(1 for section in REQUIRED_SECTIONS if section.lower() in lowered)
    url_count = len(re.findall(r"https?://[^\s)>\]]+", brief))
    fact_like_count = len(re.findall(r"\b(20\d{2}|announced|launched|appointed|published|reported)\b", lowered))

    dos_text = _extract_section(brief, "DO's")
    donts_text = _extract_section(brief, "DON'Ts")
    openers_text = _extract_section(brief, "Conversation Openers")
    unknown_text = _extract_section(brief, "Unknown")

    actionable_score = min(_count_bullets(dos_text), 5) + min(_count_bullets(donts_text), 5) + min(
        _count_bullets(openers_text), 5
    )
    grounding_score = min(url_count, 8) + min(fact_like_count, 6)
    uncertainty_score = 2 if unknown_text else 0

    total = section_hits + actionable_score + grounding_score + uncertainty_score
    return {
        "section_hits": section_hits,
        "url_count": url_count,
        "fact_like_count": fact_like_count,
        "actionable_score": actionable_score,
        "grounding_score": grounding_score,
        "uncertainty_score": uncertainty_score,
        "total_score": total,
    }


async def run_eval(limit: int) -> dict[str, Any]:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required for evaluation.")

    client = Anthropic(api_key=api_key)
    tool_executor = ToolExecutor()

    started = time.time()
    case_results: list[dict[str, Any]] = []
    selected_cases = CASES[:limit]

    for idx, case in enumerate(selected_cases, start=1):
        case_start = time.time()
        brief = await research_person_with_tools(
            client=client,
            tool_executor=tool_executor,
            person_name=case.person_name,
            meeting_context=case.meeting_context,
        )
        elapsed = round(time.time() - case_start, 2)
        if not brief:
            case_results.append(
                {
                    "index": idx,
                    "person_name": case.person_name,
                    "meeting_context": case.meeting_context,
                    "success": False,
                    "elapsed_seconds": elapsed,
                    "scores": {
                        "section_hits": 0,
                        "url_count": 0,
                        "fact_like_count": 0,
                        "actionable_score": 0,
                        "grounding_score": 0,
                        "uncertainty_score": 0,
                        "total_score": 0,
                    },
                }
            )
            continue

        scores = score_brief(brief)
        case_results.append(
            {
                "index": idx,
                "person_name": case.person_name,
                "meeting_context": case.meeting_context,
                "success": True,
                "elapsed_seconds": elapsed,
                "scores": scores,
            }
        )

    total_elapsed = round(time.time() - started, 2)
    successes = [r for r in case_results if r["success"]]
    failures = [r for r in case_results if not r["success"]]
    total_scores = [r["scores"]["total_score"] for r in case_results]

    return {
        "generated_at": datetime.now().isoformat(),
        "case_count": len(case_results),
        "success_count": len(successes),
        "failure_count": len(failures),
        "success_rate": round(len(successes) / len(case_results), 4) if case_results else 0.0,
        "average_total_score": round(sum(total_scores) / len(total_scores), 2) if total_scores else 0.0,
        "average_latency_seconds": round(
            sum(r["elapsed_seconds"] for r in case_results) / len(case_results), 2
        )
        if case_results
        else 0.0,
        "total_elapsed_seconds": total_elapsed,
        "cases": case_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate brief quality for fixed persona cases.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--limit", type=int, default=10, help="Number of fixed cases to run (default: 10).")
    args = parser.parse_args()

    if args.limit <= 0 or args.limit > len(CASES):
        raise ValueError(f"--limit must be between 1 and {len(CASES)}.")

    result = asyncio.run(run_eval(args.limit))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote evaluation results to {output_path}")
    print(
        f"Cases={result['case_count']} Success={result['success_count']} "
        f"AvgScore={result['average_total_score']} AvgLatency={result['average_latency_seconds']}s"
    )


if __name__ == "__main__":
    main()
