"""
Test script for the PDF export endpoint.
Validates markdown-to-PDF conversion via WeasyPrint without a running server.
"""

import asyncio
import io
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


SAMPLE_BRIEF = """\
## Executive Summary
Jane Doe is the CEO of Acme Corp, a leading widget manufacturer.
She joined in 2018 and has driven 3x revenue growth.

## Professional Background
- **Current role:** CEO, Acme Corp (2018–present)
- **Previous:** VP Product, WidgetWorld
- **Education:** MBA, Stanford GSB

## Recent Activity & Current Focus (Last 6-12 Months)
- Announced expansion into Southeast Asia markets
- Published op-ed on sustainable manufacturing in *Harvard Business Review*

## Meeting Strategy

## DO's (With Reasoning)
- Lead with sustainability angle — she has publicly championed green ops
- Reference her HBR article to show genuine preparation

## DON'Ts (With Reasoning)
- Avoid pricing discussions before establishing strategic value
- Don't bring up the 2021 supply-chain issues

## Bottom Line Recommendation
Open with shared sustainability goals. Avoid cost-first framing.

## Sources
- https://example.com/jane-doe-profile
"""


def test_markdown_to_html():
    """Markdown conversion should produce valid HTML."""
    import markdown as md_lib
    html = md_lib.markdown(SAMPLE_BRIEF, extensions=["extra"])
    assert "<h2>" in html, "Expected h2 headings in output"
    assert "<li>" in html, "Expected list items in output"
    assert "<strong>" in html, "Expected bold text in output"
    print("PASS  markdown_to_html")


def test_pdf_html_template():
    """Template substitution should produce a full HTML document."""
    from config import PDF_HTML_TEMPLATE
    import markdown as md_lib
    from datetime import datetime

    html_body = md_lib.markdown(SAMPLE_BRIEF, extensions=["extra"])
    html = PDF_HTML_TEMPLATE.format(
        person_name="Jane Doe",
        date=datetime.now().strftime("%B %d, %Y"),
        content=html_body,
    )
    assert "<!DOCTYPE html>" in html
    assert "Jane Doe" in html
    assert "<h2>" in html
    print("PASS  pdf_html_template")


def test_weasyprint_generates_pdf():
    """WeasyPrint should produce a non-empty PDF from the HTML template."""
    from config import PDF_HTML_TEMPLATE
    import markdown as md_lib
    from weasyprint import HTML as WeasyprintHTML
    from datetime import datetime

    html_body = md_lib.markdown(SAMPLE_BRIEF, extensions=["extra"])
    html = PDF_HTML_TEMPLATE.format(
        person_name="Jane Doe",
        date=datetime.now().strftime("%B %d, %Y"),
        content=html_body,
    )
    pdf_bytes = WeasyprintHTML(string=html).write_pdf()
    assert isinstance(pdf_bytes, bytes), "Expected bytes output"
    assert len(pdf_bytes) > 1000, f"PDF suspiciously small: {len(pdf_bytes)} bytes"
    # PDF magic bytes
    assert pdf_bytes[:4] == b"%PDF", "Output does not start with PDF magic bytes"
    print(f"PASS  weasyprint_generates_pdf  ({len(pdf_bytes):,} bytes)")


def test_export_pdf_model():
    """ExportPDFRequest model should validate correctly."""
    from models import ExportPDFRequest
    req = ExportPDFRequest(brief="## Hello\n- item", person_name="Test Person")
    assert req.brief == "## Hello\n- item"
    assert req.person_name == "Test Person"
    print("PASS  export_pdf_model")


def test_filename_sanitisation():
    """Person names with special chars should produce safe filenames."""
    import re
    names = [
        ("Jane Doe", "Jane-Doe-brief.pdf"),
        ("Dr. John Smith Jr.", "Dr-John-Smith-Jr-brief.pdf"),
        ("María García", "María-García-brief.pdf"),
    ]
    for name, expected in names:
        safe = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "-")
        result = f"{safe}-brief.pdf"
        assert result == expected, f"Got {result!r}, expected {expected!r}"
    print("PASS  filename_sanitisation")


if __name__ == "__main__":
    print("Running PDF export tests...\n")
    tests = [
        test_markdown_to_html,
        test_pdf_html_template,
        test_weasyprint_generates_pdf,
        test_export_pdf_model,
        test_filename_sanitisation,
    ]
    failures = []
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
            failures.append(t.__name__)

    print(f"\n{'All tests passed.' if not failures else f'{len(failures)} test(s) failed: {failures}'}")
    sys.exit(1 if failures else 0)
