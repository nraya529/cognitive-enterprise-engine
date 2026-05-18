# Client Template — HR Onboarding

For SMBs that hire frequently and burn hours on paperwork chase.

**Scope to quote:**
- New hire email or form submission triggers the pipeline
- Extract personal info, role, start date, tax forms
- Validate Tax IDs (SSN format), I-9 eligibility documents
- Auto-draft welcome email with required documents checklist
- Chase missing documents on a 3-day cadence

**Adaptations needed:**
- Add new doc types to the extraction schema: `w4`, `i9`, `direct_deposit_form`, `nda`
- New risk reasons: `missing_i9`, `incomplete_direct_deposit`
- Communications agent gets a "follow-up chase" scenario that escalates politeness pressure over time

**Compliance note:** HR data has stronger privacy requirements than financial data. Before deploying:
- Confirm client has appropriate consent flows
- Enable Zero Data Retention on Anthropic org
- Add encryption at rest for any PII the system touches
- Confirm processor agreements are in place

**Pricing:** $5,000 setup, $450/month standalone — but most HR engagements upsell into Tier B because once you're handling personnel data, the client wants you covering more.
