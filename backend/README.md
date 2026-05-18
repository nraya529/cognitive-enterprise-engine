# Backend — Cognitive Enterprise Engine

Asynchronous, multi-agent document processing engine. Built with FastAPI, Anthropic SDK, Pydantic v2, and rapidfuzz.

## Run locally

```sh
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add your ANTHROPIC_API_KEY

uvicorn src.main:app --reload
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `POST` | `/webhook` | JSON payload: `{ "raw_text": "...", "source": "make_com", ... }` |
| `POST` | `/upload` | Multipart file upload (PDF / XLSX / CSV / TXT) |
| `POST` | `/prospecting/runs` | Queue an autonomous Tavily-backed prospecting run |
| `GET`  | `/prospecting/runs` | List prospecting runs |
| `GET`  | `/prospecting/runs/{run_id}` | Get one run |
| `POST` | `/prospecting/runs/{run_id}/execute` | Execute a run synchronously for tests/admin use |
| `GET`  | `/prospecting/leads` | List discovered/qualified/rejected leads |
| `GET`  | `/prospecting/drafts` | List generated outreach drafts |
| `POST` | `/prospecting/drafts/{draft_id}/approve` | Approve a generated draft for sending |
| `POST` | `/prospecting/drafts/{draft_id}/send` | Send an approved draft through Resend |

Both processing endpoints return a `ProcessedDocument` (see `src/models/schemas.py`).

## Configuration

All via `.env` — see `.env.example`.

| Var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | |
| `EXTRACTION_MODEL` | `claude-opus-4-7` | Used for chaotic-text extraction with forced tool use |
| `VERIFICATION_MODEL` | `claude-sonnet-4-6` | (currently unused — extraction agent handles self-heal) |
| `COMMUNICATIONS_MODEL` | `claude-sonnet-4-6` | Drafts vendor reply emails |
| `PROSPECTING_MODEL` | `claude-sonnet-4-6` | Qualifies leads and writes outreach drafts |
| `MAX_SELF_HEAL_ATTEMPTS` | `3` | How many times verification can recurse |
| `FUZZY_MATCH_THRESHOLD` | `85` | rapidfuzz WRatio threshold for vendor matching (0–100) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./nexus_growth.db` | Async SQLAlchemy database URL for growth-engine state |
| `TAVILY_API_KEY` | *(required for prospecting)* | Tavily Search API key |
| `TAVILY_BASE_URL` | `https://api.tavily.com` | Tavily API base URL |
| `RESEND_API_KEY` | *(required for sending)* | Resend API key |
| `RESEND_BASE_URL` | `https://api.resend.com` | Resend API base URL |
| `OUTBOUND_FROM_EMAIL` | `Project Nexus <outreach@example.com>` | Sender identity for approved outreach |
| `OUTBOUND_REPLY_TO_EMAIL` | *(optional)* | Reply-to mailbox |
| `OUTBOUND_DAILY_SEND_LIMIT` | `25` | Global daily cap for approved sends |
| `OUTBOUND_RUN_SEND_LIMIT` | `10` | Per-run cap for approved sends |
| `OUTBOUND_BLOCKED_DOMAINS` | consumer mail domains | Comma-separated suppression list |
| `DEFAULT_PROSPECTING_NICHE` | `regional logistics companies` | Default run niche when no body is provided |
| `DEFAULT_PROSPECTING_GEOGRAPHY` | `New England` | Default run geography when no body is provided |
| `DEFAULT_PROSPECTING_MAX_RESULTS` | `10` | Default Tavily result limit |
| `MINIMUM_QUALIFICATION_SCORE` | `0.68` | Minimum score for a lead to be drafted |

## Autonomous growth flow

Queue a run:

```sh
curl -X POST http://localhost:8000/prospecting/runs \
  -H 'Content-Type: application/json' \
  -d '{"niche":"regional logistics firms","geography":"New England","max_results":10,"qualification_threshold":0.68}'
```

The run searches Tavily, asks the prospecting LLM to qualify each result, stores every lead in SQLite, and creates outreach drafts only for qualified leads with corporate contact emails.

Outbound is approval-gated. Generated emails are drafts until explicitly approved:

```sh
curl -X POST http://localhost:8000/prospecting/drafts/1/approve \
  -H 'Content-Type: application/json' \
  -d '{"approved_by":"Niketh"}'

curl -X POST http://localhost:8000/prospecting/drafts/1/send
```

The send endpoint refuses unapproved drafts, blocked recipient domains, duplicate sent drafts, and sends over the configured run/day limits.

## Smoke test

With the server running:

```sh
python -m tests.mock_webhook
```

This fires a deliberately-chaotic forwarded-email invoice at the engine and asserts:

- `doc_type` resolves to `invoice`
- Math reconciles (`math_is_valid: true`)
- Vendor matches `V001` (Acme Plumbing) via fuzzy match
- Risk score is reasonable
- A draft email is generated

The growth-engine tests mock external provider behavior and can run without live Tavily, Anthropic, or Resend calls:

```sh
pytest
```

## Adapting per-client

1. Replace `src/data/vendors.json` with the client's vendor list (export from their accounting platform).
2. Replace `src/data/chart_of_accounts.json` with the client's chart of accounts (export from their accounting platform).
3. Add a downstream integration in `src/agents/orchestrator.py` after the `communications.draft_email` call — push the `ProcessedDocument` into QuickBooks API / Xero API / Slack webhook / etc.
4. Adjust risk scoring thresholds in `src/agents/intelligence.py::_compute_risk_score` to match client tolerance.

The contract for downstream integrations is the `ProcessedDocument` schema. Treat it as the stable interface — change everything else above and below it, but keep that schema steady.
