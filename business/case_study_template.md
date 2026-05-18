# Case Study Template

You don't have case studies yet. That's fine — write the first one as soon as your first client hits day 30 of live operation. Get their permission, anonymize where they're sensitive, but publish it.

The template below is the structure that converts prospects best in the SMB market: concrete numbers, low jargon, the client's own words.

---

# How {{CLIENT_INDUSTRY}} Operator {{CLIENT_PSEUDONYM}} Reclaimed {{HOURS_RECLAIMED}} Hours/Week Without Adding Headcount

**Industry:** {{INDUSTRY}}
**Size:** {{EMPLOYEE_COUNT}} employees, ${{ANNUAL_REVENUE}} annual revenue
**Engagement:** Tier {{A_OR_B}} · Deployed {{DEPLOY_DATE}} · Reporting period: {{REPORT_START}}–{{REPORT_END}}

---

## The problem

{{CLIENT_PSEUDONYM}} runs a {{INDUSTRY}} operation in {{REGION}}. Like most operators at that scale, they had a single bookkeeper handling vendor invoices, customer receipts, and ledger reconciliation across a QuickBooks Online instance.

By volume, that bookkeeper was processing about {{DOCS_PER_WEEK}} documents per week — emails, PDFs, scanned paper. Average handling time: {{MIN_PER_DOC}} minutes per document. That comes to roughly {{HOURS_LOST_PER_WEEK}} hours per week spent on what is, fundamentally, retyping.

> "{{CLIENT_PULL_QUOTE_PROBLEM}}"
> — {{CLIENT_TITLE}}, {{CLIENT_PSEUDONYM}}

---

## What we built

We deployed a Cognitive Enterprise Engine configured for {{CLIENT_PSEUDONYM}}'s exact stack:

- **Ingestion:** dedicated forwarding address tied to their accounts-payable inbox
- **Extraction:** invoices and receipts
- **Verification:** every math check enforced; failed extractions auto-retry up to 3 times
- **Posting:** direct integration with their existing QuickBooks Online instance, posting to their existing chart of accounts
- **Escalation:** anything failing verification or scoring above 0.5 risk routed to a dedicated Slack channel

Deployment took **{{DEPLOY_DAYS}} business days**. No accounting platform changes. No new logins for the bookkeeper.

---

## The numbers, 90 days in

| Metric | Before | After 90 days |
|---|---|---|
| Docs processed per week | {{DOCS_BEFORE}} | {{DOCS_AFTER}} |
| Avg. handling time per doc | {{TIME_BEFORE}} min | {{TIME_AFTER}} min |
| Hours/week on data entry | {{HRS_BEFORE}} | {{HRS_AFTER}} |
| Data-entry errors caught at month-end | {{ERR_BEFORE}}/month | {{ERR_AFTER}}/month |
| Cash flow visibility horizon | {{CF_BEFORE}} days | {{CF_AFTER}} days |

The bookkeeper now spends the reclaimed time on vendor relationship management and proactive collections — work that directly affects the company's cash position.

> "{{CLIENT_PULL_QUOTE_RESULT}}"
> — {{CLIENT_TITLE}}, {{CLIENT_PSEUDONYM}}

---

## What's next

{{CLIENT_PSEUDONYM}} upgraded to Tier B in month {{UPGRADE_MONTH}} to add purchase order processing and a quarterly cash flow forecasting dashboard. The Tier B engagement has been running cleanly for {{TIER_B_MONTHS}} months.

---

*Want to see what this would look like for your operation? [Book a 20-minute call →]({{BOOKING_URL}})*
