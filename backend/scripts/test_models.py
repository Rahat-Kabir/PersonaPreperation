#!/usr/bin/env python3
"""Test script for backend/models.py disambiguation and research models."""

import sys

sys.path.insert(0, sys.path[0] + "/..")

from models import (
    ResearchRequest,
    ResearchResponse,
    IdentityCandidate,
    DisambiguationResponse,
    ExportPDFResponse,
    SelectedIdentity,
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


print("=== test_models.py ===\n")

req = ResearchRequest(person_name="Jane Smith", meeting_context="sales call")
check("research request basic fields", req.person_name == "Jane Smith")
check("continue_anyway default false", req.continue_anyway is False)

sel = SelectedIdentity(name="Jane Smith", organization="Acme", profile_url="https://example.com")
req_sel = ResearchRequest(person_name="Jane Smith", selected_identity=sel, continue_anyway=True)
check("request accepts selected_identity", req_sel.selected_identity is not None)
check("request keeps continue_anyway", req_sel.continue_anyway is True)

candidate = IdentityCandidate(
    id="c1",
    name="Jane Smith",
    title="VP Sales",
    organization="Acme",
    profile_url="https://example.com/jane",
    reason="Matched exact name",
    confidence=0.9,
)
check("candidate confidence range accepted", candidate.confidence == 0.9)

dis = DisambiguationResponse(
    needs_disambiguation=True,
    status="ambiguous",
    query="Jane Smith",
    candidates=[candidate],
    recommendation="Select a candidate",
)
check("disambiguation response stores candidates", len(dis.candidates) == 1)

res = ResearchResponse(
    success=False,
    brief=None,
    person_name="Jane Smith",
    timestamp="2026-02-22T00:00:00",
    error_message="Ambiguous identity",
    disambiguation_status="ambiguous",
)
check("research response stores disambiguation status", res.disambiguation_status == "ambiguous")

pdf_res = ExportPDFResponse(
    filename="Jane-Smith-brief.pdf",
    content_type="application/pdf",
    pdf_base64="JVBERi0=",
)
check("pdf export response stores base64 payload", pdf_res.pdf_base64 == "JVBERi0=")
check("pdf export response stores filename", pdf_res.filename.endswith(".pdf"))

print(f"\n{'=' * 40}")
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
print("All tests passed!")
