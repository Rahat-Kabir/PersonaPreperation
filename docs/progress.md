# Progress

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
