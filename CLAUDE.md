# PersonaPreparation — Agent Guide

## What This Project Is

Web app that researches a public person and produces a meeting brief.

Two stages, in order:
1. **Disambiguation** — fast, search-only pass (Tavily + Brave). No Claude. Returns candidates.
2. **Deep Research** — agent loop (Claude tool-use) over Tavily/Brave/Firecrawl. Streams progress via SSE.

Stack: FastAPI backend + Next.js frontend. Single-page UI with 4 states (input → disambiguation → researching → result).

## Architecture At A Glance

Backend ([backend/](backend/)) — one job per file:

| File | Role |
|---|---|
| [main.py](backend/main.py) | FastAPI app, endpoints, auth, rate limiting, SSE |
| [agent.py](backend/agent.py) | Agent loop (`_run_agent_loop`) + `disambiguate_person_name` |
| [tools.py](backend/tools.py) | `ToolExecutor` — Tavily, Brave, Firecrawl wrappers |
| [config.py](backend/config.py) | System prompt, tool JSON schemas, timeouts, guardrails |
| [models.py](backend/models.py) | Pydantic request/response models |
| [utils.py](backend/utils.py) | Name validation, filename sanitizing, brief saving |
| [cli.py](backend/cli.py) | Terminal entry point (same agent, no HTTP) |

Frontend ([frontend/src/](frontend/src/)):

| File | Role |
|---|---|
| [app/page.tsx](frontend/src/app/page.tsx) | 4-state SPA (input / disambiguation / researching / result) |
| [lib/api.ts](frontend/src/lib/api.ts) | `disambiguatePerson()` + streamed research client |
| [components/ui/](frontend/src/components/ui/) | CVA-styled button/input/textarea/label |

Endpoints: `GET /`, `GET /api/health`, `POST /api/research/disambiguate`, `POST /api/research`, `POST /api/research/stream`.

## Which External API Runs When

| API | Disambiguation | Deep Research |
|---|---|---|
| Tavily search | yes (3–8 parallel queries, plus possible fallback broad query) | yes |
| Brave search | yes (only when hint/context present) | yes |
| Firecrawl scrape | **no** | yes |
| Anthropic / Claude | **no** | yes (per-request client) |

## Extension Points

- **New search/scrape tool** → add method on `ToolExecutor` ([tools.py](backend/tools.py)) + tool JSON schema in [config.py](backend/config.py) + dispatch branch in the agent loop ([agent.py](backend/agent.py)) + tool summaries/compaction in `_summarize_tool_result()` and `_compact_tool_result_for_model()` ([agent.py](backend/agent.py)). If it appears in streamed UI, add labels/icons in [page.tsx](frontend/src/app/page.tsx).
- **New brief section** → edit the system prompt in [config.py](backend/config.py). Markdown rendering on the frontend picks it up automatically.
- **New endpoint** → route in [main.py](backend/main.py) + model in [models.py](backend/models.py) + client function in [lib/api.ts](frontend/src/lib/api.ts).
- **New UI state** → extend the state union and transition switch in [page.tsx](frontend/src/app/page.tsx).
- **Tune disambiguation** → ranking in `_dedup_and_rank_candidates`, noise filter `_is_noise_candidate`, auto-`direct` threshold (currently 0.7) — all in [agent.py](backend/agent.py).

## Dev Commands

```powershell
# Backend (from backend/)
uv sync
uv run uvicorn main:app --reload

# Frontend (from frontend/)
npm install
npm run dev

# Backend script tests (from backend/)
uv run python scripts/test_<name>.py

# Frontend validation (from frontend/, for frontend changes)
npm run build
```

## Environment

- Platform: Windows + PowerShell. Default to PS syntax (`$env:VAR`, `;` not `&&`).
- Backend required: `API_AUTH_TOKEN`.
- Frontend required: `NEXT_PUBLIC_API_ACCESS_TOKEN` (must match backend `API_AUTH_TOKEN`) and `NEXT_PUBLIC_API_URL`.
- Anthropic key: either `ANTHROPIC_API_KEY` env var **or** user-supplied via frontend settings panel (stored in `localStorage`, sent in request body as `anthropic_api_key`). Server boots without it.
- Optional: `TAVILY_API_KEY`, `BRAVE_SEARCH_API_KEY`, `FIRECRAWL_API_KEY`. Research degrades gracefully without them.

## Non-Obvious Behavior

- API treats `meeting_context` as optional; the web UI requires it. Intentional.
- Anthropic client is built **per-request** via `get_anthropic_client(user_api_key)`, not globally.
- Disambiguation auto-skips to deep research only when there's a single candidate with confidence ≥ 0.7.
- One `_run_agent_loop()` powers both streaming and non-streaming endpoints.
- Sync SDK calls run via `asyncio.to_thread()` + `asyncio.wait_for()` for timeouts.

## Rules

- **Think before coding.** State assumptions; if uncertain, ask. Don't guess.
- **Simplicity first.** No overengineering, no unrequested "flexibility". Before writing, ask: would a senior engineer delete this?
- **Surgical changes.** Touch only what the task requires. Don't reformat adjacent code.
- **Fail fast.** Don't swallow exceptions. Crash with a clear stack trace unless you have a specific recovery plan.
- **Clean up orphans.** Remove unused imports/deps when you remove a function or variable.
- **Tests are mandatory.** After any code change, add or update a script in `backend/scripts/` and run it green before declaring done.
- **Update docs.** After code changes, update [docs/tech_spec.md](docs/tech_spec.md) and [docs/progress.md](docs/progress.md) with the decisions made.
- **Visual debugging.** For complex UI issues, ask for a screenshot.
- **Keep guides synced.** [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) should stay identical unless there is an intentional, documented reason to diverge.

## Pointers

- Current design state → [docs/tech_spec.md](docs/tech_spec.md)
- Session-by-session decision history → [docs/progress.md](docs/progress.md)
- Test scripts (one per module) → [backend/scripts/](backend/scripts/)
