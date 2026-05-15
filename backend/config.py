"""
Configuration constants, system prompt, and tool definitions for PersonaPreparation.
"""

import logging
import os
from pathlib import Path

# Model & agent loop
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0
MAX_TOOL_ITERATIONS = 15
MAX_PERSON_NAME_LENGTH = 200
MAX_SEARCH_RESULTS = 8
MAX_RESULTS_PER_DOMAIN = 2
MAX_SCRAPE_MARKDOWN_CHARS = 12000
MIN_EVIDENCE_SOURCES = 4
MAX_CONSECUTIVE_LOW_VALUE_ITERATIONS = 3

# Timeouts (seconds)
ANTHROPIC_TIMEOUT = 60.0
TAVILY_TIMEOUT = 15
FIRECRAWL_TIMEOUT = 30
BRAVE_TIMEOUT = 10

# File output
OUTPUT_DIR = Path(os.getenv("PERSONA_BRIEF_DIR", Path.home() / "PersonaPreparationBriefs"))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("persona_preparation")


PDF_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: Georgia, "Times New Roman", serif;
    font-size: 14px;
    line-height: 1.75;
    color: #1a1a1a;
    background: #ffffff;
    padding: 48px 56px;
    max-width: 860px;
    margin: 0 auto;
  }}
  h1 {{ font-size: 28px; color: #111111; margin-bottom: 6px; }}
  h2 {{
    font-size: 17px;
    color: #8B6914;
    margin-top: 28px;
    margin-bottom: 10px;
    border-bottom: 1px solid #e8e0cc;
    padding-bottom: 5px;
    font-style: italic;
  }}
  h3 {{ font-size: 15px; color: #333333; margin-top: 18px; margin-bottom: 8px; }}
  p {{ margin-bottom: 10px; }}
  ul, ol {{ margin: 6px 0 12px 22px; }}
  li {{ margin-bottom: 5px; line-height: 1.65; }}
  strong {{ color: #111111; font-weight: 600; }}
  a {{ color: #8B6914; text-decoration: none; word-break: break-all; }}
  hr {{ border: none; border-top: 1px solid #e0d8c8; margin: 20px 0; }}
  code {{
    font-family: "Courier New", Courier, monospace;
    font-size: 12px;
    background: #f5f2eb;
    padding: 1px 4px;
    border-radius: 3px;
  }}
  .doc-header {{
    border-bottom: 2px solid #B8860B;
    padding-bottom: 18px;
    margin-bottom: 28px;
  }}
  .doc-title {{ font-size: 30px; color: #111111; letter-spacing: -0.5px; }}
  .doc-meta {{
    font-size: 11px;
    color: #999999;
    font-family: "Courier New", Courier, monospace;
    margin-top: 6px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }}
</style>
</head>
<body>
  <div class="doc-header">
    <h1 class="doc-title">{person_name}</h1>
    <p class="doc-meta">Meeting Brief &middot; {date}</p>
  </div>
  {content}
</body>
</html>"""


SYSTEM_PROMPT = """You are PersonaPreparation, an AI meeting preparation strategist with real-time research capabilities.

Your mission: Help users prepare for meetings by researching people and providing actionable strategies, clear recommendations, and specific guidance on what to do and what to avoid.

You have access to these tools:
- tavily_search: AI-powered web search optimized for research (best for general queries)
- brave_search: Privacy-focused search engine (good for news and current events)
- firecrawl_scrape: Extract clean content from specific URLs (for detailed page analysis)

RESEARCH WORKFLOW:
1. Start with identity/background search (name + current role/company).
2. Run a recency search (freshness='py') focused on last 6-12 months.
3. Run a perspective search for interviews, talks, publications, and quotes.
4. Scrape only the highest-signal URLs and avoid low-value pages.
5. Synthesize findings with meeting context into tactical recommendations.

When given a person's name and meeting purpose, provide a structured meeting brief with EXACTLY these section headers:

## Executive Summary
2-3 sentences on who they are, current role, and why they matter for this meeting.

## Professional Background
- Current position, company, responsibilities
- Career trajectory and notable roles
- Credentials and expertise

## Recent Activity & Current Focus (Last 6-12 Months)
- Recent initiatives, announcements, projects
- Publications, interviews, talks
- Current priorities

## Their Interests & Preferences
- Topics they repeatedly emphasize
- Communication style and preferred approach

## Meeting Strategy

## DO's (With Reasoning)
- Specific topics to bring up and why they'll resonate
- Approaches that align with their values and interests
- Questions to ask that demonstrate research and genuine interest
- Ways to frame your proposal/discussion that match their priorities

## DON'Ts (With Reasoning)
- Topics to avoid based on their known positions or sensitivities
- Approaches that may conflict with their style or values
- Common mistakes or misunderstandings about them
- Red flags or controversial areas to steer clear of

## Conversation Openers (3-5)
Specific opening lines or topics tied to recent work.

## Key Talking Points
- Main themes to emphasize
- Message positioning for impact
- Common ground for rapport

## Potential Concerns & How to Address Them
Anticipate likely objections and proactive responses.

## Bottom Line Recommendation
One key thing to emphasize and one thing to avoid.

## Unknowns & Evidence Gaps
- Explicitly list important unknowns.
- Do not invent details.

## Sources
- List the most relevant URLs used.
- Every major claim should be supported by at least one source URL.

GUIDELINES:
- Use tools to gather CURRENT, REAL-TIME information.
- Avoid redundant or repeated tool calls.
- Focus on professional relevance; avoid private/personal speculation.
- Be explicit about uncertainty; never fabricate unknown facts.
- Ground recommendations in actual findings and cited URLs.
- Tailor every insight to the provided meeting context.
- Keep advice specific and tactical, not generic.
- Cap each major bullet section at 5 bullets."""


TOOLS = [
    {
        "name": "tavily_search",
        "description": "Search the web using Tavily AI-powered search. Best for comprehensive research queries. Returns relevant web pages with titles, URLs, and content snippets. Use this for general background research on people, companies, and topics.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g., 'Satya Nadella Microsoft CEO', 'Demis Hassabis recent news 2025')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5, max: 10)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "brave_search",
        "description": "Search the web using Brave Search API. Privacy-focused search engine, good for news and current events. Returns web results with titles, descriptions, and URLs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5, max: 20)",
                    "default": 5
                },
                "freshness": {
                    "type": "string",
                    "description": "Filter by time period: 'pd' (past day), 'pw' (past week), 'pm' (past month), 'py' (past year)",
                    "enum": ["pd", "pw", "pm", "py"]
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "firecrawl_scrape",
        "description": "Extract clean, formatted content from a specific URL using Firecrawl. Returns markdown-formatted text without ads or navigation. Best for extracting detailed information from LinkedIn profiles, company pages, articles, or personal websites.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to scrape (must be valid http/https URL)"
                },
                "formats": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["markdown", "html", "links"]
                    },
                    "description": "Output formats to include (default: ['markdown'])",
                    "default": ["markdown"]
                }
            },
            "required": ["url"]
        }
    }
]
