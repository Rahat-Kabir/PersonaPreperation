#!/usr/bin/env python3
"""
PersonaPreparation Agent with Tool Use - AI-powered meeting preparation assistant.
Uses Anthropic SDK with real-time web search and scraping capabilities via:
- Tavily (AI-powered search)
- Firecrawl (web scraping)
- Brave Search API (privacy-focused search)
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from tavily import TavilyClient
from firecrawl import FirecrawlApp
import requests


# Configuration
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_MAX_TOKENS = 8192
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 2.0
MAX_TOOL_ITERATIONS = 15  # Prevent infinite loops
OUTPUT_DIR = Path(os.getenv("PERSONA_BRIEF_DIR", Path.home() / "PersonaPreparationBriefs"))
MAX_PERSON_NAME_LENGTH = 200

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are PersonaPreparation, an AI meeting preparation strategist with real-time research capabilities.

Your mission: Help users prepare for meetings by researching people and providing actionable strategies, clear recommendations, and specific guidance on what to do and what to avoid.

You have access to these tools:
- tavily_search: AI-powered web search optimized for research (best for general queries)
- brave_search: Privacy-focused search engine (good for news and current events)
- firecrawl_scrape: Extract clean content from specific URLs (for detailed page analysis)

RESEARCH WORKFLOW:
1. Start with broad searches about the person (name + role/company)
2. Search for recent news, articles, publications (last 6-12 months)
3. Look for social media presence (LinkedIn, Twitter, professional profiles)
4. Scrape specific pages that seem valuable (LinkedIn, company bio, articles)
5. Search for awards, achievements, speaking engagements, interviews
6. Look for their opinions, statements, and positions on relevant topics
7. Synthesize findings with the meeting context to create strategic recommendations

When given a person's name and meeting purpose, provide a structured meeting brief with:

**Executive Summary** (2-3 sentences)
Brief overview of who they are, their current role, and why they're relevant to this meeting.

**Professional Background**
- Current position, company, and responsibilities
- Career trajectory and notable previous roles
- Education, credentials, and areas of expertise

**Recent Activity & Current Focus** (last 6-12 months)
- Recent news, announcements, or initiatives they're involved in
- Articles, publications, or content they've created
- Speaking engagements, interviews, or public appearances
- Current projects, priorities, and focus areas

**Their Interests & Preferences**
- Professional interests and passion areas
- Topics they frequently discuss or advocate for
- Known likes and dislikes (based on public statements, interviews)
- Communication style and preferred approach

**Meeting Strategy**

**DO's** (with reasoning):
- Specific topics to bring up and why they'll resonate
- Approaches that align with their values and interests
- Questions to ask that demonstrate research and genuine interest
- Ways to frame your proposal/discussion that match their priorities

**DON'Ts** (with reasoning):
- Topics to avoid based on their known positions or sensitivities
- Approaches that may conflict with their style or values
- Common mistakes or misunderstandings about them
- Red flags or controversial areas to steer clear of

**Conversation Openers** (3-5 specific suggestions)
Concrete opening lines or topics based on their recent work and interests.

**Key Talking Points**
- Main themes to emphasize during the meeting
- How to position your message for maximum impact
- Common ground or shared interests to build rapport

**Potential Concerns & How to Address Them**
Based on their background and the meeting context, anticipate their potential objections or concerns and how to proactively address them.

**Bottom Line Recommendation**
A clear, actionable summary: the one key thing to emphasize and the one thing to absolutely avoid in this meeting.

GUIDELINES:
- Use tools to gather CURRENT, REAL-TIME information
- Be thorough but efficient - don't make redundant searches
- Focus on professional relevance - avoid personal/private information
- Be honest about information gaps - don't speculate without data
- Cite sources when possible (URLs from search results)
- Ground all recommendations in actual research findings
- Tailor every insight to the specific meeting context provided
- Provide specific, actionable guidance - not generic advice
- Use reasoning: explain WHY each recommendation matters
- Be strategic: think about what will actually help the meeting succeed"""


# Tool definitions for Claude
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


def validate_person_name(name: str) -> tuple[bool, str]:
    """Validate person name input."""
    if not name or not name.strip():
        return False, "Name cannot be empty"
    if len(name) > MAX_PERSON_NAME_LENGTH:
        return False, f"Name exceeds maximum length of {MAX_PERSON_NAME_LENGTH} characters"
    if re.search(r'[<>{}[\]\\]', name):
        return False, "Name contains invalid characters"
    return True, ""


def sanitize_filename(name: str) -> str:
    """Sanitize a person name for use as a filename."""
    safe_name = re.sub(r'[<>:"/\\|?*]', '', name)
    safe_name = safe_name.replace(' ', '_')
    safe_name = safe_name.strip('. ')
    safe_name = safe_name[:100]
    if not safe_name:
        safe_name = "unnamed"
    return safe_name.lower()


class ToolExecutor:
    """Handles execution of all research tools."""

    def __init__(self):
        """Initialize API clients."""
        self.tavily_client = None
        self.firecrawl_client = None
        self.brave_api_key = None

        # Initialize Tavily
        tavily_key = os.getenv('TAVILY_API_KEY')
        if tavily_key and not tavily_key.startswith('your-'):
            try:
                self.tavily_client = TavilyClient(api_key=tavily_key)
                logger.info("Tavily client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize Tavily: {e}")

        # Initialize Firecrawl
        firecrawl_key = os.getenv('FIRECRAWL_API_KEY')
        if firecrawl_key and not firecrawl_key.startswith('your-'):
            try:
                self.firecrawl_client = FirecrawlApp(api_key=firecrawl_key)
                logger.info("Firecrawl client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize Firecrawl: {e}")

        # Initialize Brave Search
        brave_key = os.getenv('BRAVE_SEARCH_API_KEY')
        if brave_key and not brave_key.startswith('your-'):
            self.brave_api_key = brave_key
            logger.info("Brave Search API key loaded")

    def tavily_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Execute Tavily search."""
        if not self.tavily_client:
            return {
                "error": "Tavily API key not configured. Please set TAVILY_API_KEY in .env file.",
                "available": False
            }

        try:
            logger.info("Executing Tavily search request.")
            response = self.tavily_client.search(
                query=query,
                max_results=min(max_results, 10),
                search_depth="advanced"
            )

            # Format results
            results = []
            for result in response.get('results', []):
                results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', ''),
                    'score': result.get('score', 0)
                })

            return {
                "query": query,
                "results": results,
                "count": len(results)
            }

        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return {"error": f"Tavily search failed: {str(e)}"}

    def brave_search(self, query: str, count: int = 5, freshness: Optional[str] = None) -> Dict[str, Any]:
        """Execute Brave Search."""
        if not self.brave_api_key:
            return {
                "error": "Brave Search API key not configured. Please set BRAVE_SEARCH_API_KEY in .env file.",
                "available": False
            }

        try:
            logger.info("Executing Brave search request.")

            # Build request
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.brave_api_key
            }

            params = {
                "q": query,
                "count": min(count, 20)
            }

            if freshness:
                params["freshness"] = freshness

            response = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            # Format results
            results = []
            for result in data.get('web', {}).get('results', []):
                results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'description': result.get('description', ''),
                    'age': result.get('age', '')
                })

            return {
                "query": query,
                "results": results,
                "count": len(results)
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Brave search error: {e}")
            return {"error": f"Brave search failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Brave search error: {e}")
            return {"error": f"Brave search failed: {str(e)}"}

    def firecrawl_scrape(self, url: str, formats: List[str] = None) -> Dict[str, Any]:
        """Execute Firecrawl scraping."""
        if not self.firecrawl_client:
            return {
                "error": "Firecrawl API key not configured. Please set FIRECRAWL_API_KEY in .env file.",
                "available": False
            }

        try:
            logger.info("Executing Firecrawl scrape request.")

            if formats is None:
                formats = ["markdown"]

            response = self.firecrawl_client.scrape_url(
                url=url,
                params={'formats': formats}
            )

            return {
                "url": url,
                "markdown": response.get('markdown', ''),
                "html": response.get('html', ''),
                "links": response.get('links', []),
                "success": True
            }

        except Exception as e:
            logger.error(f"Firecrawl scrape error: {e}")
            return {"error": f"Firecrawl scrape failed: {str(e)}"}

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name."""
        if tool_name == "tavily_search":
            return self.tavily_search(**tool_input)
        elif tool_name == "brave_search":
            return self.brave_search(**tool_input)
        elif tool_name == "firecrawl_scrape":
            return self.firecrawl_scrape(**tool_input)
        else:
            return {"error": f"Unknown tool: {tool_name}"}


async def research_person_with_tools_stream(
    client: Anthropic,
    tool_executor: ToolExecutor,
    person_name: str,
    meeting_context: str = "",
    max_retries: int = DEFAULT_MAX_RETRIES
):
    """
    Research a person using Claude with tool use capabilities, yielding events for real-time updates.

    Yields AgentEvent dictionaries with event_type, data, timestamp, and iteration.

    Args:
        client: Anthropic client instance
        tool_executor: ToolExecutor instance for executing tools
        person_name: Name of the person to research
        meeting_context: Optional context about the meeting
        max_retries: Maximum number of retry attempts for API calls

    Yields:
        Dict containing event_type, data, timestamp, and iteration
    """
    # Validate input
    is_valid, error_msg = validate_person_name(person_name)
    if not is_valid:
        logger.error("Invalid person name supplied: %s", error_msg)
        yield {
            "event_type": "error",
            "data": {"error": error_msg},
            "timestamp": datetime.now().isoformat(),
            "iteration": None
        }
        return

    # Build the user prompt
    if meeting_context:
        user_prompt = f"""Please research {person_name} and create a comprehensive meeting brief.

Meeting context: {meeting_context}

Use your available tools to gather current, real-time information. Start with broad searches, then drill down into specific areas. Once you have enough information, synthesize it into the structured format specified in your system prompt."""
    else:
        user_prompt = f"""Please research {person_name} and create a comprehensive meeting brief.

Use your available tools to gather current, real-time information. Start with broad searches, then drill down into specific areas. Once you have enough information, synthesize it into the structured format specified in your system prompt."""

    logger.info("Starting tool-enabled research stream.")

    # Emit start event
    yield {
        "event_type": "start",
        "data": {"person_name": person_name, "context": meeting_context},
        "timestamp": datetime.now().isoformat(),
        "iteration": None
    }

    # Initialize conversation
    messages = [{"role": "user", "content": user_prompt}]

    # Agentic loop
    iteration = 0
    final_response = None

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        try:
            # Emit thinking event
            yield {
                "event_type": "thinking",
                "data": {"message": f"Processing iteration {iteration}..."},
                "timestamp": datetime.now().isoformat(),
                "iteration": iteration
            }

            # Call Claude with tools
            response = client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Claude finished - extract final text
                for block in response.content:
                    if block.type == "text":
                        final_response = block.text
                        logger.info(f"Research complete after {iteration} iteration(s)")
                break

            elif response.stop_reason == "tool_use":
                # Claude wants to use tools
                assistant_message = {"role": "assistant", "content": response.content}
                messages.append(assistant_message)

                # Execute all tool calls
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        # Emit tool call event
                        yield {
                            "event_type": "tool_call",
                            "data": {
                                "tool_name": tool_name,
                                "tool_input": tool_input
                            },
                            "timestamp": datetime.now().isoformat(),
                            "iteration": iteration
                        }

                        logger.info("Executing tool call: %s", tool_name)

                        # Execute the tool
                        result = tool_executor.execute_tool(tool_name, tool_input)

                        # Prepare result summary for event
                        result_summary = {}
                        if "error" in result:
                            result_summary["error"] = result["error"]
                            result_summary["success"] = False
                        elif tool_name == "firecrawl_scrape":
                            markdown_len = len(result.get('markdown', ''))
                            result_summary["success"] = True
                            result_summary["message"] = f"Scraped {markdown_len} characters"
                            result_summary["url"] = result.get('url')
                        else:
                            count = result.get('count', 0)
                            result_summary["success"] = True
                            result_summary["message"] = f"Found {count} results"
                            result_summary["count"] = count

                        # Emit tool result event
                        yield {
                            "event_type": "tool_result",
                            "data": {
                                "tool_name": tool_name,
                                "result_summary": result_summary
                            },
                            "timestamp": datetime.now().isoformat(),
                            "iteration": iteration
                        }

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })

                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                yield {
                    "event_type": "error",
                    "data": {"error": f"Unexpected stop reason: {response.stop_reason}"},
                    "timestamp": datetime.now().isoformat(),
                    "iteration": iteration
                }
                break

        except RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}")
            yield {
                "event_type": "error",
                "data": {"error": "Rate limit reached. Please try again later."},
                "timestamp": datetime.now().isoformat(),
                "iteration": iteration
            }
            return

        except APIConnectionError as e:
            logger.warning(f"Connection error: {e}")
            yield {
                "event_type": "error",
                "data": {"error": "Connection error. Please check your internet connection."},
                "timestamp": datetime.now().isoformat(),
                "iteration": iteration
            }
            return

        except APIError as e:
            logger.error(f"API error: {e}")
            yield {
                "event_type": "error",
                "data": {"error": f"API error: {str(e)}"},
                "timestamp": datetime.now().isoformat(),
                "iteration": iteration
            }
            return

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            yield {
                "event_type": "error",
                "data": {"error": f"Unexpected error: {str(e)}"},
                "timestamp": datetime.now().isoformat(),
                "iteration": iteration
            }
            return

    if iteration >= MAX_TOOL_ITERATIONS:
        logger.warning("Reached maximum iterations without completion.")
        yield {
            "event_type": "error",
            "data": {"error": f"Reached maximum iterations ({MAX_TOOL_ITERATIONS})"},
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration
        }

    if final_response:
        logger.info("Research completed successfully.")
        yield {
            "event_type": "complete",
            "data": {
                "brief": final_response,
                "person_name": person_name,
                "iteration_count": iteration
            },
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration
        }
    else:
        yield {
            "event_type": "error",
            "data": {"error": "Failed to generate brief"},
            "timestamp": datetime.now().isoformat(),
            "iteration": iteration
        }


async def research_person_with_tools(
    client: Anthropic,
    tool_executor: ToolExecutor,
    person_name: str,
    meeting_context: str = "",
    max_retries: int = DEFAULT_MAX_RETRIES
) -> Optional[str]:
    """
    Research a person using Claude with tool use capabilities.

    Args:
        client: Anthropic client instance
        tool_executor: ToolExecutor instance for executing tools
        person_name: Name of the person to research
        meeting_context: Optional context about the meeting
        max_retries: Maximum number of retry attempts for API calls

    Returns:
        The generated meeting brief as a string, or None if failed
    """
    # Validate input
    is_valid, error_msg = validate_person_name(person_name)
    if not is_valid:
        logger.error("Invalid person name supplied: %s", error_msg)
        print(f"\nError: {error_msg}\n")
        return None

    # Build the user prompt
    if meeting_context:
        user_prompt = f"""Please research {person_name} and create a comprehensive meeting brief.

Meeting context: {meeting_context}

Use your available tools to gather current, real-time information. Start with broad searches, then drill down into specific areas. Once you have enough information, synthesize it into the structured format specified in your system prompt."""
    else:
        user_prompt = f"""Please research {person_name} and create a comprehensive meeting brief.

Use your available tools to gather current, real-time information. Start with broad searches, then drill down into specific areas. Once you have enough information, synthesize it into the structured format specified in your system prompt."""

    logger.info("Starting tool-enabled research run.")
    print("\n" + "=" * 70)
    print(f"Researching {person_name} with real-time web tools...")
    print("=" * 70 + "\n")

    # Initialize conversation
    messages = [{"role": "user", "content": user_prompt}]

    # Agentic loop
    iteration = 0
    final_response = None

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        try:
            # Call Claude with tools
            response = client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Claude finished - extract final text
                for block in response.content:
                    if block.type == "text":
                        final_response = block.text
                        print(f"\n[Research complete after {iteration} iteration(s)]")
                break

            elif response.stop_reason == "tool_use":
                # Claude wants to use tools
                assistant_message = {"role": "assistant", "content": response.content}
                messages.append(assistant_message)

                # Execute all tool calls
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        print(f"\n[Tool: {tool_name}]")
                        print(f"Input: {json.dumps(tool_input, indent=2)}")

                        # Execute the tool
                        result = tool_executor.execute_tool(tool_name, tool_input)

                        # Show result summary
                        if "error" in result:
                            print(f"Error: {result['error']}")
                        elif tool_name == "firecrawl_scrape":
                            markdown_len = len(result.get('markdown', ''))
                            print(f"Scraped {markdown_len} characters from {result.get('url')}")
                        else:
                            print(f"Found {result.get('count', 0)} results")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result)
                        })

                # Add tool results to messages
                messages.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                break

        except RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}")
            print(f"\nRate limit reached. Please try again later.\n")
            return None

        except APIConnectionError as e:
            logger.warning(f"Connection error: {e}")
            print(f"\nConnection error. Please check your internet connection.\n")
            return None

        except APIError as e:
            logger.error(f"API error: {e}")
            print(f"\nAPI error: {e}\n")
            return None

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            print(f"\nUnexpected error: {e}\n")
            return None

    if iteration >= MAX_TOOL_ITERATIONS:
        print(f"\n[Warning: Reached maximum iterations ({MAX_TOOL_ITERATIONS})]")
        logger.warning("Reached maximum iterations without completion.")

    if final_response:
        print("\n" + "=" * 70)
        print("MEETING BRIEF")
        print("=" * 70 + "\n")
        print(final_response)
        print("\n" + "=" * 70)
        logger.info("Research completed successfully.")
        return final_response
    else:
        print("\nFailed to generate brief.\n")
        return None


def save_brief_to_file(
    person_name: str,
    brief_content: str,
    meeting_context: str = "",
    output_dir: Path = OUTPUT_DIR
) -> Optional[Path]:
    """Save a meeting brief to a markdown file."""
    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_name = sanitize_filename(person_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"brief_{safe_name}_{timestamp}.md"

        generated_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Meeting Brief: {person_name}\n\n")
            if meeting_context:
                f.write(f"**Meeting Context:** {meeting_context}\n\n")
            f.write(f"**Generated:** {generated_time}\n")
            f.write(f"**Generated with:** Real-time web research (Tavily, Brave Search, Firecrawl)\n\n")
            f.write("-" * 70 + "\n\n")
            f.write(brief_content)

        logger.info("Brief saved to disk.")
        print(f"\nBrief saved to: {filename}")
        return filename

    except Exception as e:
        logger.error(f"Error saving file: {e}", exc_info=True)
        print(f"\nError: Could not save file - {e}")
        return None


async def main() -> None:
    """Main entry point for the PersonaPreparation agent with tools."""
    # Load environment variables
    load_dotenv()

    # Check Anthropic API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key or api_key.startswith('your-'):
        logger.error("Missing or invalid ANTHROPIC_API_KEY")
        print("\n" + "=" * 70)
        print("ERROR: Missing Anthropic API Key")
        print("=" * 70)
        print("Please set your ANTHROPIC_API_KEY in the .env file")
        print("Get your API key from: https://console.anthropic.com/")
        print("=" * 70 + "\n")
        return

    # Create Anthropic client
    try:
        client = Anthropic(api_key=api_key)
        logger.info("Anthropic client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Anthropic client: {e}")
        print(f"\nError: Could not initialize API client - {e}\n")
        return

    # Create tool executor
    tool_executor = ToolExecutor()

    # Check which tools are available
    available_tools = []
    if tool_executor.tavily_client:
        available_tools.append("Tavily Search")
    if tool_executor.firecrawl_client:
        available_tools.append("Firecrawl")
    if tool_executor.brave_api_key:
        available_tools.append("Brave Search")

    # Display banner
    print("\n" + "=" * 70)
    print("PersonaPreparation - AI Meeting Prep Assistant with Real-Time Research")
    print("=" * 70)
    print("Research people before meetings with AI-powered briefs using live web data.")
    print("=" * 70)

    if available_tools:
        print(f"\nAvailable tools: {', '.join(available_tools)}")
    else:
        print("\nWARNING: No research tools configured!")
        print("Please add API keys to .env file:")
        print("  - TAVILY_API_KEY (https://tavily.com/)")
        print("  - FIRECRAWL_API_KEY (https://firecrawl.dev/)")
        print("  - BRAVE_SEARCH_API_KEY (https://brave.com/search/api/)")
        print("\nThe agent will still work but with limited capabilities.")

    print("\nHow to use:")
    print("1. Enter a person's name to research")
    print("2. Optionally provide meeting context (e.g., 'job interview', 'sales call')")
    print("3. The AI will use real-time web tools to gather current information")
    print(f"4. Briefs are saved to the '{OUTPUT_DIR}/' directory")
    print("5. Type 'quit' to exit\n")

    logger.info("Interactive session started")

    # Interactive loop
    while True:
        try:
            print("\n" + "-" * 70)
            person_name = input("\nPerson to research (or 'quit'): ").strip()

            if not person_name:
                continue

            if person_name.lower() in ['quit', 'exit', 'q']:
                logger.info("User exited application")
                print("\nThank you for using PersonaPreparation!\n")
                break

            # Optional context
            meeting_context = input("Meeting context (optional, press Enter to skip): ").strip()

            # Research the person with tools
            brief_content = await research_person_with_tools(
                client,
                tool_executor,
                person_name,
                meeting_context
            )

            if brief_content:
                # Offer to save the brief
                save_choice = input("\nSave this brief to a file? (y/n): ").strip().lower()
                if save_choice == 'y':
                    save_brief_to_file(person_name, brief_content, meeting_context)
                else:
                    logger.info("User skipped saving the generated brief.")

        except KeyboardInterrupt:
            logger.info("User interrupted application (Ctrl+C)")
            print("\n\nThank you for using PersonaPreparation!\n")
            break

        except EOFError:
            logger.info("EOF received, exiting application")
            print("\n\nThank you for using PersonaPreparation!\n")
            break

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            print(f"\nUnexpected error: {e}\n")
            print("Please try again or type 'quit' to exit.")


if __name__ == "__main__":
    asyncio.run(main())
