# PersonaPreparation

PersonaPreparation helps you prepare for a meeting with a public person.

You enter a person's name and your meeting context. The app first checks who the person likely is, asks you to confirm if the name is ambiguous, then researches that person using public web sources and generates a structured meeting brief.

## How It Works

1. Enter a person's name and meeting context.
2. PersonaPreparation runs a quick identity check.
3. If multiple matches are found, you select the correct person.
4. The agent searches public sources and streams live progress.
5. The app returns a meeting brief with recommendations, conversation starters, do's and don'ts, and source links.

## What You Get

Each brief includes:

- Executive summary
- Professional background
- Recent activity and current focus
- Interests and preferences
- Meeting strategy
- Do's with reasoning
- Don'ts with reasoning
- Conversation openers
- Key talking points
- Potential concerns and how to address them
- Bottom-line recommendation
- Unknowns and evidence gaps
- Source URLs

You can copy the brief to clipboard or download it as a PDF.

## Demo

![PersonaPreparation Interface](demo/homepage1.png)
_Real-time research progress with live tool execution tracking_

## Quick Start

### Prerequisites

- Python 3.10+
- `uv`
- Node.js 18+
- A shared backend/frontend auth token
- An Anthropic API key, either:
  - configured on the backend, or
  - provided by the user in the frontend settings

### 1. Backend

```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

Create `backend/.env` with:

```env
API_AUTH_TOKEN=your_shared_token
ANTHROPIC_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
FIRECRAWL_API_KEY=your_key_here
BRAVE_SEARCH_API_KEY=your_key_here
PERSONA_BRIEF_DIR=/abs/path/outside/repo
API_RATE_LIMIT=30
API_RATE_WINDOW_SECONDS=60
```

Notes:

- `API_AUTH_TOKEN` is required.
- `ANTHROPIC_API_KEY` is optional if users provide their own key in the frontend.
- Tavily, Firecrawl, and Brave keys are optional, but research quality and coverage will drop without them.
- `API_RATE_LIMIT` and `API_RATE_WINDOW_SECONDS` control per-IP rate limiting (defaults: 30 requests per 60 seconds).

Backend runs at `http://localhost:8000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local` with:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_API_ACCESS_TOKEN=your_shared_token
```

Frontend runs at `http://localhost:3000`.

## Configuration

### Required

- `API_AUTH_TOKEN` in `backend/.env`
- `NEXT_PUBLIC_API_ACCESS_TOKEN` in `frontend/.env.local`
- Both values must match
- `NEXT_PUBLIC_API_URL` must point to the backend

### Anthropic API Key

You can use either:

1. `ANTHROPIC_API_KEY` on the backend
2. A user-provided API key entered in the frontend settings panel

### Optional Search and Scraping Keys

- `TAVILY_API_KEY`
- `FIRECRAWL_API_KEY`
- `BRAVE_SEARCH_API_KEY`

## Usage

### Web App

1. Open `http://localhost:3000`
2. Enter the person's name
3. Enter the meeting context
4. Submit the form
5. If needed, select the correct person from the identity check step
6. Wait while research runs and live progress is streamed
7. Review the final brief
8. Copy the brief to clipboard or click **PDF** to download it as a formatted document

Notes:

- In the current web UI, meeting context is required.
- The API allows `meeting_context` to be optional.

### CLI

```bash
cd backend
uv run cli.py
```

The CLI allows optional meeting context and can save the generated brief to `PERSONA_BRIEF_DIR` or `~/PersonaPreparationBriefs`.

## API

### Endpoints

- `GET /`
- `GET /api/health`
- `POST /api/research/disambiguate`
- `POST /api/research`
- `POST /api/research/stream`
- `POST /api/export/pdf`

### Typical Flow

1. Call `/api/research/disambiguate`
2. If the name is ambiguous, let the user choose a candidate
3. Call `/api/research/stream` with either:
   - `selected_identity`, or
   - `continue_anyway=true`

Swagger docs are available at `http://localhost:8000/docs`.

### Request Notes

- All `POST` endpoints accept `person_name`
- `meeting_context` is optional at the API level
- `anthropic_api_key` is optional and overrides the backend default key
- `POST /api/export/pdf` accepts `{ "brief": "<markdown>", "person_name": "<name>" }` and returns JSON with `filename`, `content_type`, and `pdf_base64`; the frontend decodes it into a local PDF download

## Development

### Backend

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Script Tests

Run script-based checks from `backend/`:

```bash
uv run python scripts/test_config.py
uv run python scripts/test_utils.py
uv run python scripts/test_tools.py
uv run python scripts/test_agent.py
uv run python scripts/test_cli.py
uv run python scripts/test_prompt_contract.py
uv run python scripts/test_models.py
uv run python scripts/test_disambiguation.py
uv run python scripts/test_readme_contract.py
uv run python scripts/test_pdf_export.py
```

### Frontend

```bash
cd frontend
npm run build
```

## Limitations

- Research depends on public web data quality
- External APIs may be slow, incomplete, or rate-limited
- Identity disambiguation is heuristic, not guaranteed
- Some pages may not scrape cleanly
- Research sessions are stateless

## Privacy

PersonaPreparation works only from public web sources.

It does not:

- access private accounts or inboxes
- maintain long-term memory for a research session
- claim certainty when identity or evidence is weak

You should still verify important claims before acting on them.

## Project Structure

```text
PersonaPreparation/
|-- backend/
|   |-- main.py
|   |-- agent.py
|   |-- tools.py
|   |-- models.py
|   |-- config.py
|   |-- utils.py
|   |-- cli.py
|   `-- scripts/
|-- frontend/
|   |-- src/app/
|   |-- src/components/ui/
|   `-- src/lib/
|-- docs/
|   |-- tech_spec.md
|   `-- progress.md
|-- demo/
`-- README.md
```

## License

This project is licensed under the [MIT License](LICENSE).

## Author

Rahat Kabir — [Website](https://rahatkabir.me) · [GitHub](https://github.com/Rahat-Kabir) · [Email](mailto:rahatkabir0101@gmail.com)
