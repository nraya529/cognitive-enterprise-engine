# Cognitive Enterprise Engine

[![CI](https://github.com/nraya529/cognitive-enterprise-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/nraya529/cognitive-enterprise-engine/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An autonomous AI back-office and B2B outreach engine built with FastAPI, Anthropic, Tavily, Resend, SQLite, and async Python.

> See [results/](results/) for a real chaotic invoice and the structured output the engine produces from it.

This repository showcases a dual-loop AI business system:

1. **The product engine** — a multi-agent Python backend that ingests chaotic business documents, extracts structured data with Claude tool use, verifies financial integrity with Pydantic, and returns ledger-ready output.
2. **The growth engine** — an autonomous prospecting workflow that searches for target companies with Tavily, qualifies leads with Claude, drafts personalized outreach, stores everything in SQLite, and only sends through Resend after explicit approval.
3. **The operating kit** — proposal templates, discovery scripts, service tiers, outreach copy, study notes, and client-delivery templates for turning the technical system into a consulting portfolio project.

The intended user is a one-person AI automation consulting practice landing high-ticket workflow automation deals with traditional SMBs: contractors, logistics firms, clinics, professional services, and other document-heavy operators.

---

## Directory layout

```
cognitive-enterprise-engine/
├── README.md                      ← you are here
├── backend/                       ← the Python multi-agent system
│   ├── src/
│   │   ├── main.py                ← FastAPI app (document + prospecting routes)
│   │   ├── config.py              ← settings via pydantic-settings
│   │   ├── logging_setup.py       ← structured logging with trace IDs
│   │   ├── models/
│   │   │   ├── schemas.py         ← document-processing Pydantic contract
│   │   │   └── leads.py           ← prospecting ORM models + schemas
│   │   ├── agents/
│   │   │   ├── orchestrator.py    ← pipeline coordinator
│   │   │   ├── extraction.py      ← Claude tool-use extraction agent
│   │   │   ├── verification.py    ← self-healing validator (recursive)
│   │   │   ├── intelligence.py    ← fuzzy match + COA classification
│   │   │   ├── communications.py  ← drafts vendor reply emails
│   │   │   └── prospecting/       ← discovery, qualification, copywriting loop
│   │   ├── routes/
│   │   │   └── prospecting.py     ← approval-gated growth engine API
│   │   ├── services/
│   │   │   ├── anthropic_client.py    ← async Claude client w/ caching
│   │   │   ├── document_parser.py     ← PDF / XLSX / CSV / text ingestion
│   │   │   ├── storage.py             ← async SQLite persistence
│   │   │   ├── tavily_client.py       ← B2B discovery search client
│   │   │   └── email_sender.py        ← Resend sender with approval gates
│   │   └── data/
│   │       ├── chart_of_accounts.json
│   │       └── vendors.json
│   ├── tests/                     ← mocked pytest suite + smoke test
│   ├── requirements.txt
│   └── .env.example
├── prompts/
│   ├── cognitive_inference.md     ← ready-to-paste Make.com / Zapier prompt
│   └── extraction_tool_schema.md  ← reference tool-use schema
├── business/
│   ├── proposal_template.md       ← strategic proposal (Tier A / Tier B)
│   ├── outreach_email.md          ← cold outreach (3 industry variants)
│   ├── discovery_call_script.md   ← 25-minute discovery framework
│   ├── service_tiers.md           ← pricing structure and philosophy
│   └── case_study_template.md     ← post-engagement case study
└── client_templates/              ← starting points for client deliverables
    ├── invoice_automation/
    ├── email_to_quote/
    └── hr_onboarding/
```

---

## Quick start (technical)

```sh
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add keys for the features you want:
# ANTHROPIC_API_KEY for document processing and lead scoring
# TAVILY_API_KEY for prospecting discovery
# RESEND_API_KEY for approved outbound dispatch

uvicorn src.main:app --reload
```

In a second terminal:

```sh
cd backend
python -m tests.mock_webhook
```

You should see a structured `ProcessedDocument` come back with `math_is_valid: true` and `entity.matched_vendor_id: "V001"`.

Run the mocked test suite without live provider credentials:

```sh
cd backend
pytest
```

---

## Architecture in 60 seconds

### Loop 1: Autonomous Document Processing

```
Webhook  →  Extraction  →  Verification  →  Intelligence  →  Communications  →  Result
(POST)      Claude+tool     Pydantic+heal     fuzzy+COA       Claude+JSON       (ProcessedDocument)
            (Opus 4.7)      (recursive)       (rapidfuzz)     (Sonnet 4.6)
```

- **Extraction** uses forced tool use to guarantee a strictly typed JSON payload. Adaptive thinking on, effort=high.
- **Verification** runs the payload through Pydantic v2 schemas with cross-field validators (math, dates). On failure it loops back to extraction with the specific errors — up to `MAX_SELF_HEAL_ATTEMPTS` retries.
- **Intelligence** runs locally: rapidfuzz against the vendor list, keyword classification against the chart of accounts, additive risk scoring.
- **Communications** drafts a contextual email matched to one of three scenarios (clean / flag / escalate).

Prompt caching is enabled on every Claude call (system prompts are stable, so the cache hits constantly after the first request). Models are configurable via `.env`.

### Loop 2: Autonomous Growth Engine

```
Target Niche  →  Tavily Discovery  →  Claude Qualification  →  Draft Generation  →  Approval Gate  →  Resend Dispatch
                   query matrix        fit + pain scoring       personalized copy     human audit       idempotent send
```

- **Discovery** expands a broad niche and geography into a matrix of buying-signal search phrases, then deduplicates companies by domain.
- **Qualification** asks Claude to score operational fit, revenue/scale indicators, visible pain points, and whether the account is worth outreach.
- **Copywriting** generates short, specific outbound emails with an opt-out compliance line.
- **Approval gating** prevents automatic sends. Drafts must be explicitly approved before Resend dispatch.
- **Persistence** stores prospecting runs, leads, drafts, approval timestamps, suppression state, and delivery results in async SQLite.

Useful endpoints:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/webhook` | Process raw document text |
| `POST` | `/upload` | Process uploaded PDF/XLSX/CSV/TXT files |
| `POST` | `/prospecting/run` | Start an autonomous prospecting run |
| `GET` | `/prospecting/leads` | Review discovered and qualified leads |
| `GET` | `/prospecting/drafts` | Review generated outreach drafts |
| `POST` | `/prospecting/approve/{draft_id}` | Approve a draft for sending |
| `POST` | `/prospecting/dispatch/{draft_id}` | Send an approved draft through Resend |

---

## Using the business kit

Run the practice on this loop:

1. **Define a niche.** Pick a narrow market such as regional logistics firms, specialty clinics, or trade contractors.
2. **Run prospecting.** Use `/prospecting/run` to discover and qualify companies, then audit the generated drafts.
3. **Approve outreach.** Send only the drafts that pass human review.
4. **Hold discovery calls.** Follow `business/discovery_call_script.md`. Capture the operational baseline.
5. **Send a same-day proposal.** Fill in `business/proposal_template.md` with the numbers from discovery.
6. **Deploy the product engine.** Use the backend as the foundation for a document automation implementation.
7. **Document results.** Once the engagement hits day 30, fill in `business/case_study_template.md` with permission.

---

## What this repo deliberately is not

- **A finished SaaS product.** The architecture is SaaS-ready, but the repo is intentionally positioned as a portfolio-grade engine and consulting foundation.
- **A no-code workflow.** The Python backend is for engagements where the client wants a dedicated server. The Make.com prompt in `prompts/` is for lighter engagements where they're already on a no-code platform.
- **A general-purpose AI consulting kit.** It is narrow on purpose: traditional SMBs, back-office document automation, $2.5K–$10K price band. Narrow positioning sells.

---

## Models and cost

Configured in `backend/.env`:

| Stage | Model | Why |
|---|---|---|
| Extraction | `claude-opus-4-7` | Strict tool use on chaotic text; quality matters more than cost here. |
| Verification re-extraction | `claude-opus-4-7` | Self-healing reuses the extraction agent. |
| Communications | `claude-sonnet-4-6` | Email drafting is straightforward; Sonnet is faster and cheaper. |
| Prospecting qualification | `claude-sonnet-4-6` | Scores target-account fit and visible operational pain. |
| Outreach copywriting | `claude-sonnet-4-6` | Generates concise personalized sales copy for approved review. |

Estimated per-document cost at Opus extraction prices: $0.02–$0.08 depending on document size. For a client processing 500 docs/month, that's $10–$40 in API costs against $450–$750 in retainer — a healthy margin.

---

## Security posture

- API key in environment, never hardcoded.
- `.env`, local SQLite files, virtualenvs, and Python caches are ignored by Git.
- Structured logging captures trace IDs but never logs raw document content at INFO level.
- All Claude calls go through one wrapper (`services/anthropic_client.py`) — single place to enforce Zero Data Retention org settings.
- Pydantic v2 with `extra="forbid"` on all schemas prevents stray fields from polluting downstream systems.
- Outbound email is approval-gated and suppression-aware. The system can draft autonomously, but it cannot send without an explicit approval action.

Before deploying to a client, also:
- Rotate to client-specific API keys
- Configure ZDR in your Anthropic console
- Put the FastAPI app behind a reverse proxy with TLS
- Set up off-host log aggregation

---

## Roadmap

What this repo intentionally leaves out, to be added per-client:

- Direct QuickBooks Online / Xero API integration (each client has different fields they care about)
- Slack / Discord escalation webhooks (depends on where they live)
- Multi-tenant data isolation (single-tenant is the right architecture for one-off deployments)
- Dashboards (Tier B add-on)
- Durable background jobs with Redis/Celery for long-running prospecting campaigns
- Postgres migration for concurrent production workloads

Build these as billable add-ons, not as core platform features.
