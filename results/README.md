# Sample Run Artifacts

End-to-end illustration of what the engine produces for one chaotic real-world input.

| File | What it is |
|---|---|
| [`sample_input.txt`](sample_input.txt) | A forwarded-email invoice as it lands in the AP inbox — header noise, inconsistent whitespace, mixed date formats, free-text addressing. |
| [`sample_output.json`](sample_output.json) | The `ProcessedDocument` the engine emits after extraction → verification → intelligence enrichment → email drafting. |

The output here was produced by the `tests/mock_webhook.py` smoke test against a deployed instance. Reproduce locally with:

```sh
cd backend
uvicorn src.main:app --reload
python -m tests.mock_webhook
```

## What to notice in the output

- **`ledger.math_is_valid: true`** — subtotal, tax, and grand total reconcile to the cent. The verification agent ran zero self-healing cycles (`self_heal_attempts: 0`) because the extraction agent got the math right on the first pass.
- **`entity.matched_vendor_id: "V001"`** — rapidfuzz matched "Acme Plumbing Supply  Co." (note the double space) against the canonical vendor list with confidence 0.97.
- **`line_items[*].ledger_account: "5600"`** — every line item was auto-classified into the *Materials & Inventory* GL account because the matched vendor's preferred account took precedence over keyword classification.
- **`risk_score: 0.0`** + **`requires_human_review: false`** — no risk signals tripped. The document is safe to auto-post.
- **`actions.draft_email_body`** — the communications agent drafted a confirmation email in the "clean confirmation" scenario, referencing the invoice number and net-30 terms specifically.

## Trace ID

Every processed document carries a 12-character `trace_id`. Searching the structured logs for that ID reconstructs every agent decision and downstream operation that touched the document.
