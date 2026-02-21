#!/usr/bin/env python3
"""Test script for quick disambiguation helpers in backend/agent.py."""

import sys

sys.path.insert(0, sys.path[0] + "/..")

from agent import (
    _extract_candidate_from_result,
    _extract_loose_candidate_from_result,
    _extract_fallback_candidate_from_result,
    _dedup_and_rank_candidates,
    _is_noise_candidate,
    _candidate_hint_match_count,
    _parse_name_and_hint,
    _matches_name_tokens,
)

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


print("=== test_disambiguation.py ===\n")

candidate = _extract_candidate_from_result(
    {
        "title": "Rahat Kabir - Software Engineer at Acme",
        "url": "https://www.linkedin.com/in/rahatkabir",
        "content": "Rahat Kabir leads backend systems at Acme",
    },
    "Rahat Kabir",
    "Rahat Kabir",
    "backend engineering discussion",
    ["backend", "engineering"],
)
check("extract candidate for exact name", candidate is not None)
check("candidate has id", bool(candidate and candidate.get("id")))
check("candidate has confidence", bool(candidate and candidate.get("confidence", 0) > 0))

no_candidate = _extract_candidate_from_result(
    {
        "title": "John Doe - Product Manager",
        "url": "https://example.com/john",
        "content": "Profile",
    },
    "Rahat Kabir",
    "Rahat Kabir",
    "",
    [],
)
check("ignore unrelated title", no_candidate is None)

parsed_name, parsed_hint = _parse_name_and_hint("Rahat Kabir, Student of North South University")
check("parse base name from enriched input", parsed_name == "Rahat Kabir")
check("parse inline hint from enriched input", parsed_hint == "Student of North South University")

from_name, from_hint = _parse_name_and_hint("Nabeel Mohammed from NSU")
check("parse base name from natural phrasing", from_name == "Nabeel Mohammed")
check("parse from-hint from natural phrasing", from_hint.lower() == "from nsu")

fuzzy_match = _matches_name_tokens(
    "Rahat Kabir - Student at North South University",
    "Profile page",
    "Rahat Kabir",
)
check("fuzzy token matching works for base name", fuzzy_match is True)

nsu_hint_hits = _candidate_hint_match_count(
    "Dr. Nabeel Mohammed at North South University",
    "Profile",
    "https://ece.northsouth.edu/people",
    ["nsu"],
)
check("nsu acronym hint matches north south university", nsu_hint_hits >= 1)

strict_filtered_out = _extract_candidate_from_result(
    {
        "title": "Rahat Kabir - Consumer Services Specialist at Newell Brands",
        "url": "https://theorg.com/org/newell-brands/org-chart/rahat-kabir",
        "content": "Newell Brands profile",
    },
    "Rahat Kabir",
    "Rahat Kabir",
    "Bangladesh student",
    ["bangladesh", "north", "south", "university"],
)
check("candidate still extracted before strict post-filter", strict_filtered_out is not None)

noise = _is_noise_candidate(
    '60+ "Rahat Kabir" profiles',
    "https://www.linkedin.com/pub/dir/Rahat/Kabir",
    "Directory listing",
    "Rahat Kabir",
)
check("filters profile directory pages", noise is True)

contact_noise = _is_noise_candidate(
    "Contact Rahat Kabir, Email and Phone",
    "https://www.zoominfo.com/p/Rahat-Kabir/123",
    "Email and phone details",
    "Rahat Kabir",
)
check("filters contact dump pages", contact_noise is True)

author_noise = _is_noise_candidate(
    'Browsing by Author "Dr. Nabeel Mohammed (NbM)"',
    "https://repository.northsouth.edu/browse/author",
    "Browsing by Author at NSU IR",
    "Nabeel Mohammed",
)
check("filters repository author browse pages", author_noise is True)

check("candidate includes summary", bool(candidate and candidate.get("summary")))

loose_candidate = _extract_loose_candidate_from_result(
    {
        "title": "Nabeel M. - Faculty profile",
        "url": "https://example.edu/people/nabeel-mohammed",
        "content": "Nabeel works in Electrical and Computer Engineering at North South University.",
    },
    "Nabeel Mohammed from NSU",
    "Nabeel Mohammed",
    ["nsu"],
)
check("loose extractor finds partial-name profile result", loose_candidate is not None)

fallback_candidate = _extract_fallback_candidate_from_result(
    {
        "title": "Profile of Nabeel",
        "url": "https://example.edu/faculty/nabeel",
        "content": "Faculty page at North South University",
    },
    "Nabeel Mohammed from NSU",
    "Nabeel Mohammed",
)
check("fallback extractor provides low-confidence candidate", fallback_candidate is not None)

ranked = _dedup_and_rank_candidates(
    [
        {"id": "a", "name": "Rahat Kabir", "confidence": 0.7},
        {"id": "a", "name": "Rahat Kabir", "confidence": 0.9},
        {"id": "b", "name": "Rahat Kabir", "confidence": 0.8},
    ],
    max_candidates=5,
)
check("dedup removes duplicate ids", len(ranked) == 2)
check("ranked by confidence", ranked[0]["confidence"] >= ranked[1]["confidence"])

ranked_person = _dedup_and_rank_candidates(
    [
        {
            "id": "url-1",
            "name": "Nabeel Mohammed",
            "organization": "North South University",
            "profile_url": "https://example.edu/people/nabeel-mohammed",
            "confidence": 0.62,
        },
        {
            "id": "url-2",
            "name": "Nabeel Mohammed",
            "organization": "North South University",
            "profile_url": "https://another.example.edu/staff/nabeel",
            "confidence": 0.71,
        },
    ],
    max_candidates=5,
)
check("dedup collapses same person by name+org fingerprint", len(ranked_person) == 1)

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
