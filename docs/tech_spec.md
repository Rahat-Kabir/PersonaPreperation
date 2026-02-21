# Technical Specification

## Backend Architecture

### Module Structure

```text
backend/
|-- main.py        # FastAPI server, endpoints, auth, rate limiting
|-- cli.py         # Standalone CLI for terminal-based research
|-- agent.py       # Core agent loop + disambiguation helpers
|-- tools.py       # ToolExecutor class (Tavily, Brave, Firecrawl)
|-- utils.py       # validate_person_name, sanitize_filename, save_brief_to_file
|-- config.py      # Constants, system prompt, tool definitions, timeout values
|-- models.py      # Pydantic request/response models
`-- pyproject.toml # Dependencies
```

### Key Design Decisions

- Deduplicated agent loop: one `_run_agent_loop()` powers streaming and non-streaming flows.
- Async tool execution with timeouts: sync SDK calls run via `asyncio.to_thread()` and `asyncio.wait_for()`.
- Deterministic retrieval controls: URL filtering, dedup, domain caps, ranking.
- Loop guardrails: duplicate tool-call skip, low-value iteration nudge, evidence-threshold nudge.
- Token pressure control: compact tool payloads and reduced `DEFAULT_MAX_TOKENS`.
- Explicit disambiguation gate: quick candidate pass before deep research for ambiguous names.

### Timeout Configuration (`config.py`)

| Constant          | Value | Purpose |
|-------------------|-------|---------|
| ANTHROPIC_TIMEOUT | 60s   | Claude API call timeout |
| TAVILY_TIMEOUT    | 15s   | Tavily search timeout |
| FIRECRAWL_TIMEOUT | 30s   | Firecrawl scrape timeout |
| BRAVE_TIMEOUT     | 10s   | Brave search HTTP timeout |

### Quality Guardrail Configuration (`config.py`)

| Constant                             | Value | Purpose |
|--------------------------------------|-------|---------|
| DEFAULT_MAX_TOKENS                   | 4096  | Lower output token budget |
| MAX_SEARCH_RESULTS                   | 8     | Upper cap for refined search results |
| MAX_RESULTS_PER_DOMAIN               | 2     | Source diversity |
| MAX_SCRAPE_MARKDOWN_CHARS            | 12000 | Bound scrape payload size |
| MIN_EVIDENCE_SOURCES                 | 4     | Synthesis nudge threshold |
| MAX_CONSECUTIVE_LOW_VALUE_ITERATIONS | 3     | Stop low-signal churn |

### API Endpoints

- `GET /` - API info
- `GET /api/health` - Health check
- `POST /api/research/disambiguate` - quick low-cost identity disambiguation
- `POST /api/research` - non-streaming research
- `POST /api/research/stream` - SSE streaming research

### Request/Response Structure Changes

- `ResearchRequest.selected_identity` (optional identity anchor selected by user)
- `ResearchRequest.continue_anyway` (allow deep research despite ambiguity/no-match)
- `ResearchResponse.disambiguation_status` (`direct | ambiguous | no_match`)
- `ResearchResponse.selected_identity_name` (identity used in deep research)
- New response model: `DisambiguationResponse` with candidate list and recommendation

### Retrieval Flow (Current)

1. Client may call `/api/research/disambiguate` first.
2. Disambiguation returns status:
   - `direct`: one strong candidate.
   - `ambiguous`: multiple candidates.
   - `no_match`: no confident candidate.
3. Deep research gate:
   - if `ambiguous/no_match` and `continue_anyway=false`, API returns clear guidance instead of running deep search.
   - if `continue_anyway=true`, deep research proceeds with low-confidence caution.
   - if `selected_identity` is present, prompt is anchored to that identity.
4. Agent runs identity/recency/perspective retrieval, tool filtering/ranking, then synthesis.

## Frontend Architecture

```text
frontend/src/
|-- app/
|   |-- page.tsx     # Form + disambiguation picker + streamed brief output
|   `-- layout.tsx
|-- components/ui/
`-- lib/
    |-- api.ts       # API client for disambiguation + streamed research
    `-- utils.ts
```

### Markdown Rendering

Briefs are rendered with `react-markdown` and `@tailwindcss/typography` classes.

### Frontend Disambiguation Flow

1. Submit form triggers `/api/research/disambiguate`.
2. If status is `ambiguous`, UI renders candidate cards with "Select this person".
3. If status is `no_match`, UI shows guidance and exposes "Continue anyway".
4. Selecting a candidate passes `selected_identity` to `/api/research/stream`.
5. "Continue anyway" passes `continue_anyway=true` to `/api/research/stream`.
6. Candidate cards now show a short summary per person (role/company or snippet-derived summary) instead of name+link only.

### Disambiguation Candidate Quality Filters

- Directory/listing pages are filtered out (for example "60+ ... profiles").
- Contact dump pages are filtered out (email/phone scraping pages).
- Generic social post pages are filtered out from identity selection.
- Only likely person-specific profiles with usable context are shown.
- Enriched name inputs are parsed (`"Name, role/company hint"`), and matching uses base-name tokens (first+last) instead of strict literal full-string match.
- Natural phrasing in name field is parsed too (for example: `"Name from X"`, `"Name at X"`, `"Name in X"`).
- Disambiguation now returns up to 7 candidates and applies strict hint-aware ranking/filtering when hints are provided.
- Hint-aware strict mode runs extra quick searches (`name + hint + linkedin/portfolio`) and prioritizes candidates with hint-token matches.
- Candidate extraction now runs in tiers: strict -> loose -> low-confidence fallback, to avoid dead-end `no_match` when profile snippets are imperfect.
- Auto-`direct` now requires a single strong candidate (confidence >= 0.7). Single weak hits stay in `ambiguous` for user confirmation.
