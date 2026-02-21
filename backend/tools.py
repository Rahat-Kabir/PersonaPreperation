"""
ToolExecutor — handles execution of all research tools (Tavily, Brave, Firecrawl).
"""

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import requests
from tavily import TavilyClient
from firecrawl import FirecrawlApp

from config import (
    BRAVE_TIMEOUT,
    DEFAULT_RETRY_DELAY,
    FIRECRAWL_TIMEOUT,
    MAX_RESULTS_PER_DOMAIN,
    MAX_SCRAPE_MARKDOWN_CHARS,
    MAX_SEARCH_RESULTS,
    TAVILY_TIMEOUT,
)

logger = logging.getLogger("persona_preparation")


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

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for stable deduplication."""
        if not url:
            return ""
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return ""
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        normalized = parsed._replace(fragment="", query="", path=path.rstrip("/") or "/")
        return urlunparse(normalized)

    @staticmethod
    def _domain(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc.lower()

    @staticmethod
    def _is_low_value_url(url: str) -> bool:
        lowered = url.lower()
        blocked_tokens = [
            "/search",
            "/tag/",
            "/tags/",
            "/category/",
            "/login",
            "/signin",
            "/signup",
            "/register",
            "/privacy",
            "/terms",
            "utm_",
        ]
        return any(token in lowered for token in blocked_tokens)

    @staticmethod
    def _score_result(query: str, result: Dict[str, Any]) -> float:
        title = (result.get("title") or "").lower()
        content = (result.get("content") or result.get("description") or "").lower()
        query_terms = [term for term in re.findall(r"[a-z0-9]+", query.lower()) if len(term) > 2]

        term_hits = sum(1 for term in query_terms if term in title or term in content)
        base = float(result.get("score") or 0)
        recency_hint = 1.0 if re.search(r"\b(202[4-9]|recent|announced|launch|interview)\b", title + " " + content) else 0.0
        return base + float(term_hits) + recency_hint

    def _refine_search_results(self, query: str, raw_results: List[Dict[str, Any]], max_results: int) -> List[Dict[str, Any]]:
        """Filter noisy URLs, deduplicate, and keep domain-diverse high-signal results."""
        scored: List[Dict[str, Any]] = []
        for result in raw_results:
            normalized_url = self._normalize_url(result.get("url", ""))
            if not normalized_url or self._is_low_value_url(normalized_url):
                continue
            enriched = dict(result)
            enriched["url"] = normalized_url
            enriched["_score"] = self._score_result(query, enriched)
            scored.append(enriched)

        scored.sort(key=lambda item: item.get("_score", 0), reverse=True)

        selected: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        per_domain: dict[str, int] = {}
        capped = min(max_results, MAX_SEARCH_RESULTS)

        for item in scored:
            url = item.get("url", "")
            domain = self._domain(url)
            if not domain or url in seen_urls:
                continue
            if per_domain.get(domain, 0) >= MAX_RESULTS_PER_DOMAIN:
                continue

            seen_urls.add(url)
            per_domain[domain] = per_domain.get(domain, 0) + 1
            item.pop("_score", None)
            selected.append(item)
            if len(selected) >= capped:
                break

        return selected

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

            raw_results = []
            for result in response.get('results', []):
                raw_results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', ''),
                    'score': result.get('score', 0)
                })
            results = self._refine_search_results(query, raw_results, max_results)

            return {
                "query": query,
                "results": results,
                "count": len(results),
                "selected_urls": [r.get("url", "") for r in results[:5]],
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
                timeout=BRAVE_TIMEOUT
            )
            response.raise_for_status()

            data = response.json()

            raw_results = []
            for result in data.get('web', {}).get('results', []):
                raw_results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'description': result.get('description', ''),
                    'age': result.get('age', '')
                })
            results = self._refine_search_results(query, raw_results, count)

            return {
                "query": query,
                "results": results,
                "count": len(results),
                "selected_urls": [r.get("url", "") for r in results[:5]],
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Brave search error: {e}")
            return {"error": f"Brave search failed: {str(e)}"}
        except Exception as e:
            logger.error(f"Brave search error: {e}")
            return {"error": f"Brave search failed: {str(e)}"}

    def firecrawl_scrape(self, url: str, formats: List[str] = None) -> Dict[str, Any]:
        """Execute Firecrawl scraping."""
        normalized_url = self._normalize_url(url)
        if not normalized_url:
            return {"error": "Invalid URL provided for scraping"}
        if self._is_low_value_url(normalized_url):
            return {"error": "URL skipped because it appears low-value for research"}

        if not self.firecrawl_client:
            return {
                "error": "Firecrawl API key not configured. Please set FIRECRAWL_API_KEY in .env file.",
                "available": False
            }

        try:
            logger.info("Executing Firecrawl scrape request.")

            if formats is None:
                formats = ["markdown"]

            if hasattr(self.firecrawl_client, "scrape_url"):
                response = self.firecrawl_client.scrape_url(
                    url=normalized_url,
                    params={'formats': formats}
                )
            elif hasattr(self.firecrawl_client, "scrape"):
                response = self.firecrawl_client.scrape(
                    normalized_url,
                    formats=formats
                )
            else:
                return {"error": "Firecrawl client does not support scrape_url/scrape methods"}

            if isinstance(response, dict):
                markdown = response.get("markdown", "") or ""
                html = response.get("html", "") or ""
                links = response.get("links", []) or []
            else:
                markdown = getattr(response, "markdown", "") or ""
                html = getattr(response, "html", "") or ""
                links = getattr(response, "links", []) or []

            markdown = re.sub(r"(?im)^\s*(cookie|privacy|terms|sign in|log in).*$", "", markdown)
            markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
            if len(markdown) > MAX_SCRAPE_MARKDOWN_CHARS:
                markdown = markdown[:MAX_SCRAPE_MARKDOWN_CHARS]

            return {
                "url": normalized_url,
                "markdown": markdown,
                "html": html,
                "links": links,
                "success": True
            }

        except Exception as e:
            logger.error(f"Firecrawl scrape error: {e}")
            return {"error": f"Firecrawl scrape failed: {str(e)}"}

    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with timeout protection.

        Runs sync tool calls in a thread to avoid blocking the event loop,
        and applies per-tool timeouts.
        """
        for attempt in range(2):
            try:
                if tool_name == "tavily_search":
                    return await asyncio.wait_for(
                        asyncio.to_thread(self.tavily_search, **tool_input),
                        timeout=TAVILY_TIMEOUT
                    )
                elif tool_name == "brave_search":
                    return await asyncio.wait_for(
                        asyncio.to_thread(self.brave_search, **tool_input),
                        timeout=BRAVE_TIMEOUT
                    )
                elif tool_name == "firecrawl_scrape":
                    return await asyncio.wait_for(
                        asyncio.to_thread(self.firecrawl_scrape, **tool_input),
                        timeout=FIRECRAWL_TIMEOUT
                    )
                else:
                    return {"error": f"Unknown tool: {tool_name}"}
            except asyncio.TimeoutError:
                logger.error("Tool %s timed out (attempt %s)", tool_name, attempt + 1)
                if attempt == 0:
                    await asyncio.sleep(DEFAULT_RETRY_DELAY)
                    continue
                return {"error": f"{tool_name} timed out"}
            except requests.exceptions.RequestException as e:
                logger.error("Tool %s network error (attempt %s): %s", tool_name, attempt + 1, e)
                if attempt == 0:
                    await asyncio.sleep(DEFAULT_RETRY_DELAY)
                    continue
                return {"error": f"{tool_name} network error: {str(e)}"}
