# Cognitive Enterprise Engine

A complete starter kit for running an AI automation consulting practice targeting traditional SMBs — built around a production-grade multi-agent autonomous back-office system as the technical core.

This repository contains three things:

1. **A working software product** — a multi-agent Python system that ingests chaotic business documents (invoices, receipts, HR forms) and produces structured, verified, ledger-ready output.
2. **Cross-platform prompts** — a Make.com / Zapier / n8n cognitive inference prompt that does a lighter-weight version of the same work inside no-code automation platforms.
3. **A business operating kit** — strategic proposal template, cold outreach scripts, discovery call framework, pricing structure, and case study template.

The intended user is a one-person consulting practice landing $2,500 – $9,500 deals with traditional Boston-area service businesses (contractors, logistics, professional services).

---

## Directory layout

```
cognitive-enterprise-engine/
├── README.md                      ← you are here
├── backend/                       ← the Python multi-agent system
│   ├── src/
│   │   ├── main.py                ← FastAPI app (webhook + upload endpoints)
│   │   ├── config.py              ← settings via pydantic-settings
│   │   ├── logging_setup.py       ← structured logging with trace IDs
│   │   ├── models/schemas.py      ← Pydantic v2 schemas (the contract)
│   │   ├── agents/
│   │   │   ├── orchestrator.py    ← pipeline coordinator
│   │   │   ├── extraction.py      ← Claude tool-use extraction agent
│   │   │   ├── verification.py    ← self-healing validator (recursive)
│   │   │   ├── intelligence.py    ← fuzzy match + COA classification
│   │   │   └── communications.py  ← drafts vendor reply emails
│   │   ├── services/
│   │   │   ├── anthropic_client.py    ← async Claude client w/ caching
│   │   │   └── document_parser.py     ← PDF / XLSX / CSV / text ingestion
│   │   └── data/
│   │       ├── chart_of_accounts.json
│   │       └── vendors.json
│   ├── tests/mock_webhook.py      ← end-to-end smoke test
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
# edit .env and add your ANTHROPIC_API_KEY

uvicorn src.main:app --reload
```

In a second terminal:

```sh
cd backend
python -m tests.mock_webhook
```

You should see a structured `ProcessedDocument` come back with `math_is_valid: true` and `entity.matched_vendor_id: "V001"`.

---

## Architecture in 60 seconds

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

---

## Using the business kit

Run the practice on this loop:

1. **Find a candidate.** Pull 50 Boston-area SMBs (Yelp, BBB, local chamber, industry directories) in one sitting.
2. **Send outreach.** Use the variant in `business/outreach_email.md` that matches their industry. Personalize the company name and one specific detail.
3. **Hold a discovery call.** Follow `business/discovery_call_script.md`. Take notes. Capture the operational baseline.
4. **Send a same-day proposal.** Fill in `business/proposal_template.md` with the numbers from discovery. Send within 4 hours of hanging up.
5. **Close.** Follow up at 48 hours. If they sign, deploy in two weeks using the backend in this repo as the foundation.
6. **Document.** Once the engagement hits day 30 of live operation, fill in `business/case_study_template.md` with their permission and publish.

---

## What this repo deliberately is not

- **A SaaS product.** Each deployment is a one-off custom install per client. That is a feature — it is what justifies the price and creates the moat.
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

Estimated per-document cost at Opus extraction prices: $0.02–$0.08 depending on document size. For a client processing 500 docs/month, that's $10–$40 in API costs against $450–$750 in retainer — a healthy margin.

---

## Security posture

- API key in environment, never hardcoded.
- Structured logging captures trace IDs but never logs raw document content at INFO level.
- All Claude calls go through one wrapper (`services/anthropic_client.py`) — single place to enforce Zero Data Retention org settings.
- Pydantic v2 with `extra="forbid"` on all schemas prevents stray fields from polluting downstream systems.

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

Build these as billable add-ons, not as core platform features.
