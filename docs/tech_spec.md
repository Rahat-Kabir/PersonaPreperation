# Technical Specification

## Documentation Decisions

- `README.md` now starts with the implemented product flow instead of a long features-first introduction.
- The README now explains the end-user sequence clearly:
  1. enter person name and meeting context
  2. run identity disambiguation
  3. select the right person or continue anyway
  4. run deep research with live progress
  5. return the final meeting brief
- The README now separates required configuration from optional provider keys.
- The README now states that the current web UI requires meeting context, while the API still treats `meeting_context` as optional.
- The README now documents the intended API path: disambiguate first, then call deep research with `selected_identity` or `continue_anyway=true`.
- Added `backend/scripts/test_readme_contract.py` to keep the README aligned with the implemented product flow and setup rules.

### API Structure Review

- No API endpoints changed in this session.
- Current API remains:
  - `GET /`
  - `GET /api/health`
  - `POST /api/research/disambiguate`
  - `POST /api/research`
  - `POST /api/research/stream`

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
- `ResearchRequest.anthropic_api_key` (optional user-provided Anthropic API key; overrides server default)
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
|   |-- page.tsx     # 4-state app (input, disambiguation, researching, result)
|   |-- globals.css  # Dark theme, CSS variables, animations, prose-dossier styles
|   `-- layout.tsx
|-- components/ui/
|   |-- button.tsx   # CVA button (default/gold, ghost, outline, danger variants)
|   |-- input.tsx    # Dark-themed input
|   |-- textarea.tsx # Dark-themed textarea
|   `-- label.tsx    # Uppercase tracking label
`-- lib/
    |-- api.ts       # API client for disambiguation + streamed research
    `-- utils.ts
```

### Design System (Dark Editorial Theme)

- **Typography**: Instrument Serif (headings), Geist (body), Geist Mono (activity feed)
- **Color palette**: Near-black backgrounds (#0C0C0E), warm white text (#F0EDE6), gold accent (#E8C872)
- **Layout**: 4-state single-page app with crossfade transitions between states
- **Prose rendering**: Custom `prose-dossier` class for dark-themed markdown briefs

### 4-State App Architecture

1. **Input** - centered form with hero text, person name + context inputs
2. **Disambiguation** - radio-select candidate list with confirm/skip actions
3. **Researching** - SVG progress ring (iteration/15) + live monospace activity feed
4. **Result** - full-viewport markdown dossier with copy/new-research actions

### Frontend Regression Checks

- `backend/scripts/test_frontend_research_flow.py` verifies the 4-state UI contract, progress ring, disambiguation actions, result actions, dark theme stylesheet, and dark root layout.

### Markdown Rendering

Briefs are rendered with `react-markdown` and custom `prose-dossier` styles (dark theme, gold headings, styled lists).

### Frontend Disambiguation Flow

1. Submit form triggers `/api/research/disambiguate`.
2. If status is `ambiguous`, app transitions to disambiguation state with radio-select candidate list.
3. If status is `no_match`, disambiguation state shows guidance and "Skip" button.
4. Selecting a candidate and clicking "Confirm & Research" passes `selected_identity` to `/api/research/stream`.
5. "Skip" passes `continue_anyway=true` to `/api/research/stream`.
6. Candidates show name, title, organization, summary, and profile URL in a stacked list.

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

### Frontend Build Maintenance

- Added a direct frontend devDependency on `baseline-browser-mapping` so Next.js/Browserslist uses refreshed Baseline browser support data during compilation.
- API structure is unchanged in this session:
  - `GET /`
  - `GET /api/health`
  - `POST /api/research/disambiguate`
  - `POST /api/research`
  - `POST /api/research/stream`

### Frontend Runtime Safety

- `frontend/src/lib/api.ts` now resolves `NEXT_PUBLIC_API_URL` lazily inside request functions instead of at module load time.
- This keeps configuration failures explicit while reducing client-module side effects during Fast Refresh and dev recompiles.

### User-Provided Anthropic API Key

- Backend: `get_anthropic_client(user_api_key)` creates a per-request Anthropic client. Falls back to `ANTHROPIC_API_KEY` env var if no user key is provided. Returns HTTP 400 if neither is available.
- Backend: `ANTHROPIC_API_KEY` is no longer required at startup - the server can boot without it and rely on user-supplied keys.
- Frontend: API key settings panel in the header (key icon). Key is stored in `localStorage` and passed in all API request bodies as `anthropic_api_key`.
- Frontend: Settings copy explicitly states the key is stored locally and sent only to the PersonaPreparation backend when research is triggered.
- Frontend: `api.ts` functions accept an optional `anthropicApiKey` parameter and include it in request payloads.
- Security: The user key is stored only in the browser's `localStorage`, never sent to any third-party server. It is sent to the backend only as part of the research request body.
