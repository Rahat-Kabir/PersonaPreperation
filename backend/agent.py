"""
Core agentic research loop for PersonaPreparation.

Provides a single _run_agent_loop() implementation used by both
the streaming (SSE) and non-streaming (REST) interfaces.
"""

import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime
from typing import Any, Callable, Coroutine, Dict, Optional
from urllib.parse import urlparse

from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError

import cache
import history
from config import (
    ANTHROPIC_TIMEOUT,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    MAX_CONSECUTIVE_LOW_VALUE_ITERATIONS,
    MIN_EVIDENCE_SOURCES,
    MAX_TOOL_ITERATIONS,
    SYSTEM_PROMPT,
    TOOLS,
)
from tools import ToolExecutor
from utils import validate_person_name


_PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12]


def _brief_cache_key(
    person_name: str,
    meeting_context: str,
    selected_identity: Optional[Dict[str, Any]],
    continue_anyway: bool,
) -> str:
    """Build a stable cache key for a final brief.

    Includes the selected identity (profile_url with title/org+name fallback)
    so distinct candidates can't collide. Includes the model name and a hash
    of the system prompt so a prompt or model change naturally invalidates
    every prior brief; bump cache.BRIEF_CACHE_VERSION for a manual reset.
    """
    identity_token = ""
    if selected_identity:
        identity_token = "|".join(
            (selected_identity.get(field) or "").strip().lower()
            for field in ("profile_url", "name", "title", "organization")
        )
    payload = {
        "v": cache.BRIEF_CACHE_VERSION,
        "model": DEFAULT_MODEL,
        "prompt": _PROMPT_HASH,
        "name": re.sub(r"\s+", " ", (person_name or "")).strip().lower(),
        "context": re.sub(r"\s+", " ", (meeting_context or "")).strip().lower(),
        "identity": identity_token,
        "continue_anyway": bool(continue_anyway),
    }
    return cache.build_key("brief", payload)

logger = logging.getLogger("persona_preparation")

# Type alias for the event callback
EventCallback = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


def _parse_name_and_hint(person_name: str) -> tuple[str, str]:
    """Split enriched name input into base name and optional hint.

    Example:
      'Rahat Kabir, Student of North South University'
      -> ('Rahat Kabir', 'Student of North South University')
    """
    raw = re.sub(r"\s+", " ", person_name or "").strip()
    if not raw:
        return "", ""

    parts = [p.strip() for p in re.split(r"\s*[,;|-]\s*", raw, maxsplit=1) if p.strip()]
    if len(parts) > 1:
        return parts[0], parts[1]

    # Handle natural phrasing in name field: "Name from X", "Name at X"
    phrased = re.match(
        r"^\s*([A-Za-z][A-Za-z .'-]{1,120}?)\s+(from|at|in)\s+(.+?)\s*$",
        raw,
        flags=re.IGNORECASE,
    )
    if phrased:
        base = phrased.group(1).strip()
        hint = f"{phrased.group(2).strip()} {phrased.group(3).strip()}"
        return base, hint

    return parts[0], ""


def _name_tokens(name: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z]{2,}", name.lower()) if t not in {"mr", "mrs", "ms", "dr"}]


def _matches_name_tokens(title: str, snippet: str, base_name: str) -> bool:
    """Fuzzy name matching to handle enriched input strings."""
    text = f"{title} {snippet}".lower()
    tokens = _name_tokens(base_name)
    if len(tokens) < 2:
        return bool(tokens and tokens[0] in text)

    # Require first+last token to reduce false positives.
    first = tokens[0]
    last = tokens[-1]
    if first in text and last in text:
        return True
    # Fallback for spelling variants/transliteration in noisy snippets.
    return (first[:4] and first[:4] in text and last in text) or (
        last[:4] and last[:4] in text and first in text
    )


def _extract_hint_tokens(hint_text: str) -> list[str]:
    """Extract meaningful hint tokens for strict disambiguation filtering."""
    if not hint_text:
        return []
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "your", "you",
        "meeting", "why", "are",
    }
    tokens = [t for t in re.findall(r"[a-zA-Z]{2,}", hint_text.lower()) if t not in stop]
    return list(dict.fromkeys(tokens))


def _acronym_matches_text(acronym: str, text: str) -> bool:
    """Check if a short token is an acronym of consecutive words in the text.

    Example: 'mit' matches 'Massachusetts Institute of Technology'
             'nsu' matches 'North South University'
    Works for any abbreviation dynamically — no hardcoding needed.
    """
    if len(acronym) < 2 or len(acronym) > 6:
        return False
    words = [w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 1]
    for i in range(len(words) - len(acronym) + 1):
        initials = "".join(w[0] for w in words[i : i + len(acronym)])
        if initials == acronym:
            return True
    return False


def _candidate_hint_match_count(title: str, snippet: str, url: str, hint_tokens: list[str]) -> int:
    """Count hint token overlaps in candidate text/url.

    Uses dynamic acronym expansion so any abbreviation (nsu, mit, iit, etc.)
    matches its full form in the candidate text — no country-specific hardcoding.
    """
    if not hint_tokens:
        return 0
    hay = f"{title} {snippet} {url}".lower()
    count = 0
    for token in hint_tokens:
        if re.search(rf"\b{re.escape(token)}\b", hay):
            count += 1
        elif _acronym_matches_text(token, hay):
            # Short token is an acronym of words found in the candidate text
            count += 1
    return count


def _is_noise_candidate(title: str, url: str, snippet: str, person_name: str) -> bool:
    """Reject non-person pages that look like directories, posts, or contact dumps."""
    lowered_title = title.lower()
    lowered_url = url.lower()
    lowered_snippet = snippet.lower()
    escaped_name = re.escape(person_name.lower())

    noisy_title_patterns = [
        rf"\b\d+\+?\s*\"?{escaped_name}\"?\s*profiles\b",
        r"\bcontact\b",
        r"\bemail\b",
        r"\bphone\b",
        r"\bpeople search\b",
        r"\bbrowsing by author\b",
    ]
    for pattern in noisy_title_patterns:
        if re.search(pattern, lowered_title):
            return True

    noisy_url_tokens = [
        "/pub/dir/",
        "/posts/",
        "/search",
        "/directory",
        "/people-search",
        "/browse/author",
    ]
    if any(token in lowered_url for token in noisy_url_tokens):
        return True

    if "zoominfo.com" in lowered_url and ("email" in lowered_snippet or "phone" in lowered_snippet):
        return True

    return False


def _extract_candidate_from_result(
    result: Dict[str, Any],
    person_name: str,
    base_name: str,
    meeting_context: str,
    hint_tokens: list[str],
) -> Optional[Dict[str, Any]]:
    """Extract a lightweight identity candidate from a search result."""
    title = (result.get("title") or "").strip()
    url = (result.get("url") or "").strip()
    snippet = (result.get("content") or result.get("description") or "").strip()

    if not title or not url:
        return None

    target = base_name.lower().strip()
    lowered_title = title.lower()
    lowered_snippet = snippet.lower()
    if not _matches_name_tokens(lowered_title, lowered_snippet, base_name):
        return None
    if _is_noise_candidate(title, url, snippet, person_name):
        return None

    name = base_name
    cleaned_title = re.sub(r"\s+", " ", title)
    leading = cleaned_title
    for sep in (" - ", " | ", " — ", " – "):
        if sep in leading:
            leading = leading.split(sep, 1)[0].strip()
            break
    if " at " in leading.lower():
        leading = re.split(r"\s+at\s+", leading, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if target.split()[0] in leading.lower() and len(leading.split()) <= 6:
        name = leading

    org = None
    role = None
    title_parts = [part.strip() for part in re.split(r"\s+\|\s+|\s+-\s+", cleaned_title) if part.strip()]
    for part in title_parts:
        if target in part.lower():
            continue
        if " at " in part.lower():
            segs = part.split(" at ", 1)
            role = segs[0].strip() or role
            org = segs[1].strip() or org
        elif not role:
            role = part
        elif not org:
            org = part

    reason = "Matched exact name in title/snippet."
    confidence = 0.65
    if target in lowered_title:
        confidence += 0.15
    if "linkedin.com/in/" in url.lower() or "/about" in url.lower():
        confidence += 0.1
    if meeting_context and any(token in lowered_snippet for token in meeting_context.lower().split()[:3]):
        confidence += 0.05
    hint_matches = _candidate_hint_match_count(title, snippet, url, hint_tokens)
    if hint_matches:
        confidence += min(0.2, 0.05 * hint_matches)
    confidence = min(confidence, 0.95)

    summary_bits = []
    if role:
        summary_bits.append(role)
    if org:
        summary_bits.append(f"at {org}")
    if not summary_bits and snippet:
        summary_bits.append(re.sub(r"\s+", " ", snippet)[:140])
    summary = " ".join(summary_bits).strip()[:180] if summary_bits else None

    candidate_key = f"{urlparse(url).netloc.lower()}|{urlparse(url).path.lower()}|{(org or '').lower()}"
    return {
        "id": candidate_key[:120] or url[:120],
        "name": name,
        "title": role,
        "organization": org,
        "location": None,
        "profile_url": url,
        "summary": summary,
        "reason": reason,
        "confidence": round(confidence, 2),
        "hint_match_count": hint_matches,
    }


def _extract_loose_candidate_from_result(
    result: Dict[str, Any],
    person_name: str,
    base_name: str,
    hint_tokens: list[str],
) -> Optional[Dict[str, Any]]:
    """Fallback extractor when strict matching finds nothing.

    Keeps precision guardrails (noise filters + name-token overlap) but
    avoids hard no-match for ambiguous common names.
    """
    title = (result.get("title") or "").strip()
    url = (result.get("url") or "").strip()
    snippet = (result.get("content") or result.get("description") or "").strip()
    if not title or not url:
        return None
    if _is_noise_candidate(title, url, snippet, person_name):
        return None

    tokens = _name_tokens(base_name)
    hay = f"{title} {snippet} {url}".lower()
    overlap = sum(1 for token in tokens if token in hay)
    if overlap == 0:
        return None

    cleaned_title = re.sub(r"\s+", " ", title)
    leading = cleaned_title
    for sep in (" - ", " | ", " â€” ", " â€“ "):
        if sep in leading:
            leading = leading.split(sep, 1)[0].strip()
            break
    name = leading if len(leading.split()) <= 7 else base_name

    hint_matches = _candidate_hint_match_count(title, snippet, url, hint_tokens)
    confidence = 0.45 + min(0.2, overlap * 0.05) + min(0.1, hint_matches * 0.03)
    confidence = min(confidence, 0.78)

    summary = re.sub(r"\s+", " ", snippet)[:160] if snippet else cleaned_title[:160]
    parsed = urlparse(url)
    candidate_key = f"{parsed.netloc.lower()}|{parsed.path.lower()}"
    return {
        "id": candidate_key[:120] or url[:120],
        "name": name,
        "title": None,
        "organization": None,
        "location": None,
        "profile_url": url,
        "summary": summary or None,
        "reason": "Loose match from public profile-like result.",
        "confidence": round(confidence, 2),
        "hint_match_count": hint_matches,
    }


def _extract_fallback_candidate_from_result(
    result: Dict[str, Any],
    person_name: str,
    base_name: str,
) -> Optional[Dict[str, Any]]:
    """Last-resort candidate extraction to avoid dead-end no-match UX."""
    title = (result.get("title") or "").strip()
    url = (result.get("url") or "").strip()
    snippet = (result.get("content") or result.get("description") or "").strip()
    if not title or not url:
        return None
    if _is_noise_candidate(title, url, snippet, person_name):
        return None

    base_tokens = _name_tokens(base_name)
    hay = f"{title} {snippet} {url}".lower()
    full_name = re.sub(r"\s+", " ", base_name).strip().lower()
    has_overlap = any(t in hay for t in base_tokens) or (full_name and full_name in hay)
    if not has_overlap:
        return None

    cleaned_title = re.sub(r"\s+", " ", title)
    leading = cleaned_title.split(" - ", 1)[0].split(" | ", 1)[0].strip()
    parsed = urlparse(url)
    candidate_key = f"{parsed.netloc.lower()}|{parsed.path.lower()}"
    return {
        "id": candidate_key[:120] or url[:120],
        "name": leading if 1 <= len(leading.split()) <= 7 else base_name,
        "title": None,
        "organization": None,
        "location": None,
        "profile_url": url,
        "summary": (re.sub(r"\s+", " ", snippet)[:140] if snippet else cleaned_title[:140]) or None,
        "reason": "Low-confidence fallback candidate.",
        "confidence": 0.38,
        "hint_match_count": 0,
    }


def _dedup_and_rank_candidates(candidates: list[Dict[str, Any]], max_candidates: int) -> list[Dict[str, Any]]:
    """Deduplicate and rank candidates by confidence."""
    best_by_key: dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        key = candidate.get("id", "") or ""
        name = re.sub(r"\s+", " ", (candidate.get("name") or "").strip().lower())
        org = re.sub(r"\s+", " ", (candidate.get("organization") or "").strip().lower())
        url = candidate.get("profile_url") or ""
        domain = urlparse(url).netloc.lower() if url else ""
        person_fingerprint = f"{name}|{org}" if name and org else ""
        canonical = person_fingerprint or key or f"{name}|{domain}"
        if not canonical:
            continue
        existing = best_by_key.get(canonical)
        if not existing or candidate.get("confidence", 0.0) > existing.get("confidence", 0.0):
            best_by_key[canonical] = candidate

    deduped = list(best_by_key.values())

    deduped.sort(
        key=lambda item: (item.get("hint_match_count", 0), item.get("confidence", 0.0)),
        reverse=True,
    )
    return deduped[:max_candidates]


def _classify_hint(hint_text: str, hint_tokens: list[str]) -> Dict[str, bool]:
    """Classify what kind of context the hint describes to drive smarter queries."""
    lowered = hint_text.lower()
    token_set = set(hint_tokens)

    academic_signals = {
        "student", "university", "college", "institute", "faculty", "professor",
        "phd", "researcher", "academia", "undergraduate", "graduate", "alumni",
        "school", "department", "engineering", "science", "technology",
    }
    professional_signals = {
        "ceo", "cto", "coo", "founder", "director", "manager", "engineer",
        "developer", "architect", "consultant", "analyst", "officer", "president",
        "vp", "head", "lead", "executive",
    }

    is_academic = bool(token_set & academic_signals) or any(s in lowered for s in academic_signals)
    is_professional = bool(token_set & professional_signals) or any(s in lowered for s in professional_signals)

    return {"academic": is_academic, "professional": is_professional}


async def disambiguate_person_name(
    tool_executor: ToolExecutor,
    person_name: str,
    meeting_context: str = "",
    max_candidates: int = 7,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Run a cheap, quick search pass to detect identity ambiguity.

    All search queries are executed in parallel for speed.
    Queries are adapted based on what the hint describes (academic, professional, etc.).
    """
    query = person_name.strip()
    base_name, inline_hint = _parse_name_and_hint(person_name)
    identity_subject = base_name or query
    merged_context = " ".join(part for part in [inline_hint, meeting_context.strip()] if part).strip()
    hint_tokens = _extract_hint_tokens(merged_context)
    hint_class = _classify_hint(merged_context, hint_tokens)

    # --- Build queries ---
    identity_query = f"{identity_subject} current role company linkedin profile"
    linkedin_query = f'"{identity_subject}" site:linkedin.com/in'
    public_profile_query = f'"{identity_subject}" biography profile'

    # Assemble the task list — always include the three base queries
    tasks = [
        tool_executor.execute_tool("tavily_search", {"query": identity_query, "max_results": 6}, cache_bypass=force_refresh),
        tool_executor.execute_tool("tavily_search", {"query": linkedin_query, "max_results": 4}, cache_bypass=force_refresh),
        tool_executor.execute_tool("tavily_search", {"query": public_profile_query, "max_results": 4}, cache_bypass=force_refresh),
    ]

    if merged_context:
        context_query = f'"{identity_subject}" {merged_context} linkedin profile'.strip()
        alternate_query = f'"{identity_subject}" {merged_context} portfolio website'.strip()

        tasks += [
            tool_executor.execute_tool("tavily_search", {"query": context_query, "max_results": 6}, cache_bypass=force_refresh),
            tool_executor.execute_tool("brave_search", {"query": context_query, "count": 6, "freshness": "py"}, cache_bypass=force_refresh),
            tool_executor.execute_tool("tavily_search", {"query": alternate_query, "max_results": 4}, cache_bypass=force_refresh),
        ]

        # Academic-specific queries: ResearchGate, university pages, etc.
        if hint_class["academic"]:
            academic_query = f'"{identity_subject}" {merged_context} researchgate academia profile'
            tasks.append(tool_executor.execute_tool("tavily_search", {"query": academic_query, "max_results": 4}, cache_bypass=force_refresh))

        # Professional-specific queries: company pages, Crunchbase, etc.
        if hint_class["professional"]:
            professional_query = f'"{identity_subject}" {merged_context} company executive profile'
            tasks.append(tool_executor.execute_tool("tavily_search", {"query": professional_query, "max_results": 4}, cache_bypass=force_refresh))

    # --- Run all queries in parallel ---
    search_results: list[Dict[str, Any]] = []
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in raw_results:
        if isinstance(result, Exception):
            continue
        if "error" not in result:
            search_results.extend(result.get("results", []))

    extracted: list[Dict[str, Any]] = []
    for result in search_results:
        candidate = _extract_candidate_from_result(
            result,
            person_name,
            identity_subject,
            merged_context,
            hint_tokens,
        )
        if candidate:
            extracted.append(candidate)

    if not extracted:
        loose_extracted: list[Dict[str, Any]] = []
        for result in search_results:
            candidate = _extract_loose_candidate_from_result(
                result,
                person_name,
                identity_subject,
                hint_tokens,
            )
            if candidate:
                loose_extracted.append(candidate)
        extracted = loose_extracted
    if not extracted:
        fallback_extracted: list[Dict[str, Any]] = []
        for result in search_results:
            candidate = _extract_fallback_candidate_from_result(
                result,
                person_name,
                identity_subject,
            )
            if candidate:
                fallback_extracted.append(candidate)
        extracted = fallback_extracted

    ranked = _dedup_and_rank_candidates(extracted, max_candidates=max_candidates * 2)
    if hint_tokens:
        strict = [c for c in ranked if c.get("hint_match_count", 0) > 0]
        if strict:
            candidates = strict[:max_candidates]
            strict_applied = True
        else:
            # Fallback: avoid hard no-match when hint terms fail exact overlap.
            candidates = ranked[:max_candidates]
            strict_applied = False
    else:
        candidates = ranked[:max_candidates]
        strict_applied = False

    if not candidates:
        # Last-resort: broaden search using only the base name (drop hints entirely)
        # to handle cases where the right result exists but didn't match hint tokens.
        broad_query = f'"{identity_subject}" profile'
        broad_result = await tool_executor.execute_tool("tavily_search", {"query": broad_query, "max_results": 6}, cache_bypass=force_refresh)
        if "error" not in broad_result:
            for result in broad_result.get("results", []):
                candidate = _extract_fallback_candidate_from_result(result, person_name, identity_subject)
                if candidate:
                    candidates.append(candidate)
            candidates = _dedup_and_rank_candidates(candidates, max_candidates=max_candidates)

    if not candidates:
        return {
            "needs_disambiguation": False,
            "status": "no_match",
            "query": person_name,
            "candidates": [],
            "recommendation": (
                "No confident match found. Try adding more details like role, company, location, or a profile URL."
            ),
        }

    if len(candidates) == 1 and candidates[0].get("confidence", 0.0) >= 0.7:
        return {
            "needs_disambiguation": False,
            "status": "direct",
            "query": person_name,
            "candidates": candidates,
            "recommendation": "Single strong candidate found. Deep research can continue directly.",
        }

    return {
        "needs_disambiguation": True,
        "status": "ambiguous",
        "query": person_name,
        "candidates": candidates,
        "recommendation": (
            "Multiple possible people found. Select one candidate before deep research."
            if strict_applied
            else "No exact hint match found, showing closest candidates. Select one or refine hints."
        ),
    }


def _build_query_plan(person_name: str, meeting_context: str) -> dict:
    """Create deterministic query scaffolding for better retrieval coverage."""
    context_hint = meeting_context.strip() if meeting_context.strip() else "professional priorities"
    return {
        "identity_query": f"{person_name} current role company bio",
        "recency_query": f"{person_name} recent news interviews initiatives 2025",
        "perspective_query": f"{person_name} talks interviews opinions {context_hint}",
    }


def _build_user_prompt(
    person_name: str,
    meeting_context: str,
    selected_identity: Optional[Dict[str, Any]] = None,
    continue_anyway: bool = False,
) -> str:
    """Build the initial user prompt for research."""
    query_plan = _build_query_plan(person_name, meeting_context)
    base = f"Please research {person_name} and create a comprehensive meeting brief."
    if meeting_context:
        base += f"\n\nMeeting context: {meeting_context}"
    if selected_identity:
        base += "\n\nSelected identity (treat this as the anchor person):"
        base += f"\n- Name: {selected_identity.get('name', person_name)}"
        if selected_identity.get("title"):
            base += f"\n- Title: {selected_identity['title']}"
        if selected_identity.get("organization"):
            base += f"\n- Organization: {selected_identity['organization']}"
        if selected_identity.get("profile_url"):
            base += f"\n- Profile URL: {selected_identity['profile_url']}"
    elif continue_anyway:
        base += (
            "\n\nDisambiguation confidence is low and user asked to continue anyway."
            "\nDo not assume identity-specific facts unless clearly source-backed."
            "\nInclude a clear low-confidence warning in Unknowns & Evidence Gaps."
        )
    base += (
        "\n\nUse your available tools to gather current, real-time information."
        "\nFollow this search plan first:"
        f"\n1) Identity query: {query_plan['identity_query']}"
        f"\n2) Recency query (use brave_search freshness='py'): {query_plan['recency_query']}"
        f"\n3) Perspective query: {query_plan['perspective_query']}"
        "\nThen scrape only high-signal URLs."
        "\nAvoid repeated tool calls with the same input."
        "\nWhen you have enough evidence, stop calling tools and synthesize."
    )
    return base


def _make_event(event_type: str, data: dict, iteration: Optional[int] = None) -> Dict[str, Any]:
    """Create a standardised event dict."""
    return {
        "event_type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "iteration": iteration,
    }


def _summarize_tool_result(tool_name: str, result: Dict[str, Any]) -> dict:
    """Create a short summary of a tool result for event emission."""
    if "error" in result:
        return {"error": result["error"], "success": False}
    if tool_name == "firecrawl_scrape":
        return {
            "success": True,
            "message": f"Scraped {len(result.get('markdown', ''))} characters",
            "url": result.get("url"),
        }
    return {
        "success": True,
        "message": f"Found {result.get('count', 0)} results",
        "count": result.get("count", 0),
    }


def _compact_tool_result_for_model(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Trim tool payloads before sending back to the model to reduce token load."""
    if "error" in result:
        return {"error": result["error"]}

    if tool_name in ("tavily_search", "brave_search"):
        compact_results = []
        for item in result.get("results", [])[:5]:
            compact_results.append(
                {
                    "title": item.get("title", "")[:200],
                    "url": item.get("url", ""),
                    "summary": (item.get("content") or item.get("description") or "")[:400],
                }
            )
        return {
            "query": result.get("query", ""),
            "count": result.get("count", len(compact_results)),
            "results": compact_results,
        }

    if tool_name == "firecrawl_scrape":
        return {
            "url": result.get("url", ""),
            "markdown_excerpt": (result.get("markdown", "") or "")[:1800],
            "success": result.get("success", False),
        }

    return result


async def _run_agent_loop(
    client: Anthropic,
    tool_executor: ToolExecutor,
    person_name: str,
    meeting_context: str,
    on_event: EventCallback,
    selected_identity: Optional[Dict[str, Any]] = None,
    continue_anyway: bool = False,
    force_refresh: bool = False,
) -> Optional[str]:
    """Core agentic loop shared by streaming and non-streaming callers.

    Args:
        client: Anthropic SDK client.
        tool_executor: Initialised ToolExecutor.
        person_name: Person to research.
        meeting_context: Optional meeting context.
        on_event: Async callback invoked for every agent event.
        selected_identity: Optional identity anchor selected by the user.
        continue_anyway: Run deep research even when disambiguation was unclear.
        force_refresh: Bypass both the brief cache and per-tool cache layers.

    Returns:
        The final brief text, or None on failure.
    """
    # Validate
    is_valid, error_msg = validate_person_name(person_name)
    if not is_valid:
        logger.error("Invalid person name supplied: %s", error_msg)
        await on_event(_make_event("error", {"error": error_msg}))
        return None

    brief_key = _brief_cache_key(person_name, meeting_context, selected_identity, continue_anyway)
    if not force_refresh:
        cached_brief = cache.get(brief_key)
        if isinstance(cached_brief, str) and cached_brief.strip():
            logger.info("Brief cache HIT for %s", person_name)
            await on_event(_make_event("start", {"person_name": person_name, "context": meeting_context}))
            await on_event(_make_event("complete", {
                "brief": cached_brief,
                "person_name": person_name,
                "iteration_count": 0,
                "from_cache": True,
            }))
            return cached_brief

    user_prompt = _build_user_prompt(person_name, meeting_context, selected_identity, continue_anyway)

    await on_event(_make_event("start", {"person_name": person_name, "context": meeting_context}))

    messages = [{"role": "user", "content": user_prompt}]
    iteration = 0
    final_response = None
    seen_tool_signatures: set[str] = set()
    evidence_urls: set[str] = set()
    consecutive_low_value_iterations = 0
    max_token_continuations = 0

    while iteration < MAX_TOOL_ITERATIONS:
        iteration += 1

        try:
            await on_event(_make_event("thinking", {"message": f"Processing iteration {iteration}..."}, iteration))

            response = await asyncio.to_thread(
                client.messages.create,
                model=DEFAULT_MODEL,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
                timeout=ANTHROPIC_TIMEOUT,
            )

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        final_response = block.text
                        logger.info(f"Research complete after {iteration} iteration(s)")
                break

            elif response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                tool_value_found = False
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        signature = f"{tool_name}:{json.dumps(tool_input, sort_keys=True)}"

                        if signature in seen_tool_signatures:
                            skip_result = {"error": "Skipped duplicate tool call with identical input"}
                            await on_event(_make_event(
                                "tool_result",
                                {"tool_name": tool_name, "result_summary": _summarize_tool_result(tool_name, skip_result)},
                                iteration,
                            ))
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(skip_result),
                            })
                            continue

                        seen_tool_signatures.add(signature)

                        await on_event(_make_event(
                            "tool_call",
                            {"tool_name": tool_name, "tool_input": tool_input},
                            iteration,
                        ))

                        logger.info("Executing tool call: %s", tool_name)
                        result = await tool_executor.execute_tool(tool_name, tool_input, cache_bypass=force_refresh)

                        if "error" not in result:
                            if tool_name in ("tavily_search", "brave_search"):
                                urls = [entry.get("url", "") for entry in result.get("results", []) if entry.get("url")]
                                if urls:
                                    evidence_urls.update(urls)
                                    tool_value_found = True
                            elif tool_name == "firecrawl_scrape":
                                markdown = result.get("markdown", "")
                                scrape_url = result.get("url", "")
                                if len(markdown) >= 500 and scrape_url:
                                    evidence_urls.add(scrape_url)
                                    tool_value_found = True

                        await on_event(_make_event(
                            "tool_result",
                            {"tool_name": tool_name, "result_summary": _summarize_tool_result(tool_name, result)},
                            iteration,
                        ))

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(_compact_tool_result_for_model(tool_name, result)),
                        })

                messages.append({"role": "user", "content": tool_results})

                if tool_value_found:
                    consecutive_low_value_iterations = 0
                else:
                    consecutive_low_value_iterations += 1

                if len(evidence_urls) >= MIN_EVIDENCE_SOURCES and iteration >= 3:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"You already have at least {len(evidence_urls)} distinct source URLs. "
                            "Only call another tool if a critical gap blocks recommendations; otherwise synthesize now."
                        ),
                    })

                if consecutive_low_value_iterations >= MAX_CONSECUTIVE_LOW_VALUE_ITERATIONS:
                    messages.append({
                        "role": "user",
                        "content": (
                            "Recent tool calls produced low-value or duplicate evidence. "
                            "Stop using tools and synthesize the final brief now. "
                            "Explicitly list unknowns and evidence gaps."
                        ),
                    })

            elif response.stop_reason == "max_tokens":
                logger.warning("Model hit max_tokens; requesting concise continuation.")
                messages.append({"role": "assistant", "content": response.content})
                max_token_continuations += 1
                if max_token_continuations > 2:
                    await on_event(_make_event("error", {"error": "Model exceeded token budget repeatedly."}, iteration))
                    break
                messages.append({
                    "role": "user",
                    "content": (
                        "Continue and finish the brief now. Do not call tools. "
                        "Be concise, keep required headers, include unknowns and sources."
                    ),
                })
                continue
            else:
                logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                await on_event(_make_event("error", {"error": f"Unexpected stop reason: {response.stop_reason}"}, iteration))
                break

        except RateLimitError as e:
            logger.warning(f"Rate limit hit: {e}")
            await on_event(_make_event("error", {"error": "Rate limit reached. Please try again later."}, iteration))
            return None

        except APIConnectionError as e:
            logger.warning(f"Connection error: {e}")
            await on_event(_make_event("error", {"error": "Connection error. Please check your internet connection."}, iteration))
            return None

        except APIError as e:
            logger.error(f"API error: {e}")
            await on_event(_make_event("error", {"error": f"API error: {str(e)}"}, iteration))
            return None

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            await on_event(_make_event("error", {"error": f"Unexpected error: {str(e)}"}, iteration))
            return None

    if iteration >= MAX_TOOL_ITERATIONS:
        logger.warning("Reached maximum iterations without completion.")
        await on_event(_make_event("error", {"error": f"Reached maximum iterations ({MAX_TOOL_ITERATIONS})"}, iteration))

    if final_response:
        logger.info("Research completed successfully.")
        cache.set(brief_key, final_response, cache.BRIEF_TTL)
        # Save to user-visible history (separate from invisible cache).
        # Only fresh briefs land here — cache hits return earlier and skip this.
        history.insert(
            person_name=person_name,
            meeting_context=meeting_context,
            selected_identity=selected_identity,
            brief=final_response,
        )
        await on_event(_make_event("complete", {
            "brief": final_response,
            "person_name": person_name,
            "iteration_count": iteration,
            "from_cache": False,
        }, iteration))
    else:
        await on_event(_make_event("error", {"error": "Failed to generate brief"}, iteration))

    return final_response


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def research_person_with_tools_stream(
    client: Anthropic,
    tool_executor: ToolExecutor,
    person_name: str,
    meeting_context: str = "",
    selected_identity: Optional[Dict[str, Any]] = None,
    continue_anyway: bool = False,
    force_refresh: bool = False,
):
    """Async generator that yields agent events for SSE streaming.

    Wraps _run_agent_loop with an asyncio.Queue so events can be yielded
    as they are produced.
    """
    queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

    async def _push_event(event: Dict[str, Any]) -> None:
        await queue.put(event)

    async def _run():
        try:
            await _run_agent_loop(
                client,
                tool_executor,
                person_name,
                meeting_context,
                _push_event,
                selected_identity=selected_identity,
                continue_anyway=continue_anyway,
                force_refresh=force_refresh,
            )
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(_run())

    while True:
        event = await queue.get()
        if event is None:
            break
        yield event

    await task  # propagate exceptions


async def research_person_with_tools(
    client: Anthropic,
    tool_executor: ToolExecutor,
    person_name: str,
    meeting_context: str = "",
    selected_identity: Optional[Dict[str, Any]] = None,
    continue_anyway: bool = False,
    force_refresh: bool = False,
) -> Optional[str]:
    """Non-streaming research — returns the final brief or None."""

    async def _noop(_event: Dict[str, Any]) -> None:
        pass

    return await _run_agent_loop(
        client,
        tool_executor,
        person_name,
        meeting_context,
        _noop,
        selected_identity=selected_identity,
        continue_anyway=continue_anyway,
        force_refresh=force_refresh,
    )
