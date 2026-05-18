# Client Template — Email-to-Quote

For service businesses (contractors, mobile services) where customer inquiry emails should auto-generate a draft quote.

**Different from invoice automation** — this is outbound communication automation, not back-office data entry. Reuse the extraction + communications agents, skip verification/intelligence.

**Scope to quote:**
- Customer email arrives → extract location, scope of work, urgency, contact info
- Look up client's pricing rules (one-time setup of pricing config)
- Draft a quote email matching client's voice
- Send to a human review queue OR auto-send below a threshold (client preference)

**Adaptations needed:**
- Replace `chart_of_accounts.json` with a `pricing_rules.json` — service codes, base rates, modifiers
- Add a `quote_drafter.py` agent that combines extraction output with pricing rules
- Rewire orchestrator: extraction → quote drafter → communications (no verification, no fuzzy match)

**Pricing:** $5,000 setup, $450/month standalone. Bundle with invoice automation for $7,500 / $650.

This is a higher-emotion sale than invoice automation — owners feel the pain of lost leads in their gut.
