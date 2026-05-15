# Progress

## 2026-05-15 - PDF export import regression fix

### Decisions and implementation

1. Fixed `backend/main.py` import syntax for the merged PDF export endpoint.
   - Split the accidental `from xhtml2pdf import pisaimport json` line into separate `pisa` and `json` imports.

2. Hardened `backend/scripts/test_pdf_export.py`.
   - Updated stale WeasyPrint wording to xhtml2pdf.
   - Added a regression check that imports `main.py` and verifies `/api/export/pdf` is registered, so future syntax/import issues fail the PDF test.
   - Added a handler-level check that `/api/export/pdf` returns JSON-safe base64 PDF data.

3. Changed PDF download transport to avoid IDM/local download-manager interception.
   - Backend now returns `filename`, `content_type`, and `pdf_base64` instead of a direct `application/pdf` binary response.
   - Frontend decodes the base64 payload into a local Blob and downloads from a `blob:` URL.

### Validation

1. Validation run:
   - `uv run python scripts/test_pdf_export.py`
   - backend regression scripts
   - frontend `npm run build`

## 2026-03-11 - README rewrite around actual product flow

### Decisions and implementation

1. Rewrote `README.md` to match the implemented user journey instead of leading with a long feature list.
   - Top of the README now states the real sequence: input -> identity check -> select person -> research -> final brief.
   - Added a short `How It Works` section near the top.
   - Added a `What You Get` section so output expectations are visible early.

2. Simplified setup and configuration guidance.
   - Separated required auth token setup from optional provider keys.
   - Clarified that `ANTHROPIC_API_KEY` on the backend is optional when the user supplies a key from the frontend.
   - Clarified that the current web UI requires meeting context even though the API treats it as optional.

3. Simplified API documentation in the README.
   - Documented the intended disambiguation-first API flow.
   - Kept the current endpoint list without adding extra architecture detail to the top of the file.

4. Added README regression coverage in `backend/scripts/test_readme_contract.py`.
   - Verifies the README keeps the real product flow, setup rules, and API usage pattern visible.

5. API structure review.
   - No endpoint changes in this session.
   - Current API remains:
     - `GET /`
     - `GET /api/health`
     - `POST /api/research/disambiguate`
     - `POST /api/research`
     - `POST /api/research/stream`

### Test coverage updates (`backend/scripts/`)

1. Added `test_readme_contract.py` for top-level documentation regression coverage.
2. Validation run for this change:
   - `uv run python scripts/test_readme_contract.py`

## 2026-03-09 - Full UI/UX redesign (dark editorial theme)

### Decisions and implementation

1. Redesigned entire frontend from warm/earthy light theme to dark editorial "intelligence briefing" aesthetic.
   - Near-black backgrounds, warm white text, gold (#E8C872) accent color.
   - Typography: Instrument Serif for headings, Geist for body, Geist Mono for activity feed.
   - Noise grain overlay, gradient mesh backgrounds, custom scrollbar.

2. Implemented 4-state app architecture in `frontend/src/app/page.tsx`.
   - **Input**: Centered form with animated hero, floating labels, gold CTA button.
   - **Disambiguation**: Radio-select candidate list (replaces card-per-candidate layout), confirm/skip flow.
   - **Researching**: SVG progress ring showing iteration/15, live monospace activity feed with tool-specific icons.
   - **Result**: Full-viewport markdown dossier with custom `prose-dossier` dark-theme rendering, copy-to-clipboard and new-research actions.
   - CSS crossfade transitions between all states (translate + opacity + scale).

3. Updated all UI primitives for dark theme.
   - `button.tsx`: gold default variant, ghost, outline, danger variants.
   - `input.tsx`, `textarea.tsx`: dark bg (#222226), gold focus ring.
   - `label.tsx`: muted uppercase tracking.

4. Updated `globals.css` with CSS custom properties, dark prose overrides, animations (slide-in-right, fade-up, pulse-glow, stagger-children).

5. Updated `tailwind.config.ts` with new font families, dark color system, updated shadows.

6. No API changes — all endpoints and request/response schemas unchanged.

7. Added direct regression coverage for the redesigned frontend flow.
   - `backend/scripts/test_frontend_research_flow.py` verifies the 4-state app contract, research progress UI, result actions, dark theme styles, and forced dark layout mode.

### Test coverage

1. All existing frontend regression tests pass:
   - `test_frontend_api_key_copy.py` (3/3)
   - `test_frontend_lock.py` (4/4)
   - `test_frontend_api_config.py` (4/4)
   - `test_frontend_research_flow.py` (6/6)
2. `npm run build` passes clean.

## 2026-03-09 - API key UI copy correction

### Decisions and implementation

1. Corrected the frontend API key settings copy in `frontend/src/app/page.tsx`.
   - Previous copy incorrectly claimed the key was "Never sent to our servers."
   - Updated copy now states the key is stored locally in the browser and sent only to the PersonaPreparation backend when research runs.

2. Added regression coverage in `backend/scripts/test_frontend_api_key_copy.py`.
   - Verifies the copy still mentions local browser storage.
   - Verifies the copy states the key is sent only to the backend for research.
   - Verifies the incorrect "Never sent to our servers" wording does not return.

3. API structure review.
   - No endpoint changes in this session.
   - Current API remains:
     - `GET /`
     - `GET /api/health`
     - `POST /api/research/disambiguate`
     - `POST /api/research`
     - `POST /api/research/stream`

### Test coverage updates (`backend/scripts/`)

1. Added `test_frontend_api_key_copy.py` for UI copy regression coverage.
2. Validation to run for this change:
   - `python backend/scripts/test_frontend_api_key_copy.py`

## 2026-03-09 - User-provided Anthropic API key from frontend

### Decisions and implementation

1. Added `anthropic_api_key` optional field to `ResearchRequest` in `backend/models.py`.
   - Users can now supply their own Anthropic API key per request.

2. Added `get_anthropic_client()` helper in `backend/main.py`.
   - Creates per-request Anthropic client using user key or env fallback.
   - Raises HTTP 400 if no key is available from either source.

3. Made `ANTHROPIC_API_KEY` env var optional at server startup.
   - Server can boot without it; users supply their own key via the frontend.

4. Updated all three research endpoints (`/api/research`, `/api/research/stream`, `/api/research/disambiguate`) to use per-request client.

5. Updated `frontend/src/lib/api.ts`:
   - All API functions (`generateBrief`, `disambiguatePerson`, `generateBriefStream`) accept optional `anthropicApiKey` and pass it in request body.
   - Extracted shared `buildHeaders()` helper.

6. Built API key settings UI in `frontend/src/app/page.tsx`:
   - Key icon button in header with green dot indicator when key is saved.
   - Collapsible settings panel with password input, show/hide toggle, save/clear actions.
   - Key persisted in `localStorage` (`persona_anthropic_api_key`).
   - Masked key display after saving.

### Test coverage updates (`backend/scripts/`)

1. Added `test_user_api_key.py`:
   - ResearchRequest accepts anthropic_api_key field
   - Key defaults to None
   - get_anthropic_client uses user-provided key
   - get_anthropic_client falls back to env
   - get_anthropic_client raises 400 when no key available
2. All 5 tests passed.

## 2026-03-09 - Frontend Baseline browser data refresh

### Decisions and implementation

1. Refreshed the frontend Baseline browser dataset.
   - Added direct devDependency: `baseline-browser-mapping` in `frontend/package.json`
   - Updated `frontend/package-lock.json` to `baseline-browser-mapping@2.10.0`
   - Goal: remove the stale-data warning emitted during `next dev` / frontend compilation.

2. Added a repository regression script in `backend/scripts/test_frontend_lock.py`.
   - Verifies `frontend/package.json` keeps the explicit devDependency.
   - Verifies `frontend/package-lock.json` contains the matching installed package entry.

3. API structure review.
   - No API endpoint changes in this session.
   - Current API remains:
     - `GET /`
     - `GET /api/health`
     - `POST /api/research/disambiguate`
     - `POST /api/research`
     - `POST /api/research/stream`

### Test coverage updates (`backend/scripts/`)

1. Added `test_frontend_lock.py` for frontend lockfile regression coverage.
2. Validation to run for this change:
   - `python backend/scripts/test_frontend_lock.py`
   - `npm run build`

## 2026-03-09 - Frontend Fast Refresh hardening

### Decisions and implementation

1. Reduced client module side effects in `frontend/src/lib/api.ts`.
   - Removed module-scope `NEXT_PUBLIC_API_URL` validation.
   - Added `getApiBaseUrl()` so the env check runs only when an API request is actually made.
   - Goal: keep config failures explicit without forcing the whole page module to fail during dev reload/HMR evaluation.

2. API structure review.
   - No API endpoint changes in this session.
   - Current API remains:
     - `GET /`
     - `GET /api/health`
     - `POST /api/research/disambiguate`
     - `POST /api/research`
     - `POST /api/research/stream`

### Test coverage updates (`backend/scripts/`)

1. Added `test_frontend_api_config.py` for frontend API config-loading behavior.
2. Validation to run for this change:
   - `python backend/scripts/test_frontend_api_config.py`
   - `npm run build`

## 2026-02-22 - Explicit name disambiguation gate before deep research

### Decisions and implementation

1. Added explicit quick disambiguation flow for common or ambiguous names.
   - New endpoint: `POST /api/research/disambiguate`
   - Statuses: `direct`, `ambiguous`, `no_match`

2. Added identity-aware request/response schema in `backend/models.py`.
   - `ResearchRequest.selected_identity`
   - `ResearchRequest.continue_anyway`
   - `ResearchResponse.disambiguation_status`
   - `ResearchResponse.selected_identity_name`
   - New models: `SelectedIdentity`, `IdentityCandidate`, `DisambiguationResponse`

3. Implemented cheap candidate extraction/ranking in `backend/agent.py`.
   - `disambiguate_person_name()` performs quick search-only candidate pass.
   - No deep scrape during disambiguation.
   - Dedup + confidence-based ranking.

4. Added deep-research gating in `backend/main.py`.
   - If status is `ambiguous` or `no_match` and `continue_anyway=false`, API returns guidance and avoids expensive deep research.
   - If `continue_anyway=true`, research proceeds with low-confidence caution.
   - If status is `direct`, system auto-anchors to best candidate.

5. Anchored prompt when user selects identity.
   - Selected identity is injected into research prompt as the target person anchor.

6. Wired frontend disambiguation UX in `frontend/src/app/page.tsx` and `frontend/src/lib/api.ts`.
   - Calls `/api/research/disambiguate` before deep research.
   - Shows candidate picker when status is `ambiguous`.
   - Shows "Continue anyway" when status is `no_match` or user wants to bypass.
   - Sends `selected_identity` / `continue_anyway` to streaming endpoint.
   - Parses backend error details so 409 guidance is visible in UI.

7. Refined disambiguation candidate quality for better UX.
   - Filtered noisy candidates (profile directories, contact dumps, generic post pages).
   - Added per-candidate short summary so user can pick the right person quickly.
   - Removed name+link-only candidate experience.
   - Added enriched name parsing + fuzzy token matching so input like
     `"Rahat Kabir, Student of North South University"` resolves using base name.
   - Increased candidate list ceiling to 7 for better manual selection.
   - Added strict hint-aware search/ranking:
     - extra quick searches using `name + hint + linkedin/portfolio`
     - hint token scoring and strict filtering when hints are present
     - better prioritization for location/org-specific identity hints.
   - Added natural phrasing parser in name field (`from/at/in`) so inputs like
     `"Nabeel Mohammed from NSU"` split correctly into base name + hint.
   - Improved candidate display-name extraction to avoid echoing full enriched input as candidate name.

### Test coverage updates (`backend/scripts/`)

1. Added `test_models.py` for new request/response schemas.
2. Added `test_disambiguation.py` for candidate extraction and ranking.
3. Updated `test_agent.py` for:
   - selected-identity prompt anchoring
   - disambiguation statuses (`no_match`, `direct`, `ambiguous`)
4. Ran all script tests successfully:
   - `test_config.py`
   - `test_utils.py`
   - `test_tools.py`
   - `test_agent.py`
   - `test_cli.py`
   - `test_prompt_contract.py`
   - `test_models.py`
   - `test_disambiguation.py`

5. Frontend production build passed:
   - `npm run build`

6. Quality filter and summary tests passed:
   - `test_disambiguation.py`
   - `test_models.py`
   - `test_agent.py`

## 2026-02-22 - Retrieval/prompt quality hardening (simplified, no overengineering)

### Summary

- Added retrieval guardrails, prompt contract hardening, and loop reliability improvements.
- Added script-based test coverage for prompt contract and guardrail behavior.
- Ran cost-controlled live eval successfully.

## 2026-02-22 - Disambiguation fallback hardening for real user names

### Decisions and implementation

1. Reduced dead-end `no_match` outcomes in `backend/agent.py`.
   - Added tiered extraction fallback:
     - strict candidate extraction
     - loose token-overlap extraction
     - low-confidence fallback extraction (still noise-filtered)
   - Goal: show plausible candidates instead of empty state when search snippets are weak.

2. Improved duplicate-person collapsing.
   - Candidate dedup now also fingerprints by `name + organization` when available, reducing repeated cards for the same person across multiple URLs.

3. Prevented unsafe auto-selection.
   - `direct` status now only when there is exactly one **strong** candidate (`confidence >= 0.7`).
   - Single weak candidate remains `ambiguous` and requires explicit user confirmation.

4. Expanded quick query coverage in disambiguation.
   - Added additional low-cost profile-oriented queries (`site:linkedin.com/in`, biography/profile query) before deep research.

### Test coverage updates (`backend/scripts/`)

1. Updated `test_disambiguation.py`:
   - Added loose extractor test.
   - Added low-confidence fallback extractor test.
   - Added stronger dedup fingerprint assertion.

2. Updated `test_agent.py`:
   - Added assertion that a single weak candidate does **not** become `direct`.

3. Re-ran full script suite successfully:
   - `test_config.py`
   - `test_utils.py`
   - `test_tools.py`
   - `test_agent.py`
   - `test_cli.py`
   - `test_prompt_contract.py`
   - `test_models.py`
   - `test_disambiguation.py`
