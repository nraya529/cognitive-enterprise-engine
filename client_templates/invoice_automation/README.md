# Client Template — Invoice Automation

Starting point for invoice-only Tier A engagements.

**Scope to quote:**
- Forwarded email ingestion
- Extract invoices only (skip receipts, POs for first deployment)
- Post directly to client's accounting platform (QBO, Xero, etc.)
- Slack escalation for any document with `requires_human_review: true`

**Setup checklist:**
1. Export client's vendor list → `backend/src/data/vendors.json`
2. Export client's chart of accounts → `backend/src/data/chart_of_accounts.json`
3. Get a forwarding address set up (e.g. `ap@theirdomain.com` → your webhook)
4. Add accounting platform integration after `communications.draft_email` in `orchestrator.py`
5. Add Slack webhook for escalations
6. Deploy to a small cloud VM (Fly.io, Railway, Hetzner — $10–20/mo absorbed in retainer)

**Pricing:** $5,000 setup, $450/month (Tier A baseline).

**Two-week deployment plan:**
- Week 1: Discovery, data import, extraction agent tuning against 20 real past invoices
- Week 2: Integration plumbing, escalation routing, client UAT, go-live
