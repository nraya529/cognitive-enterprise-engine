# Reference: Extraction Tool Schema

This is the JSON Schema the Python backend uses for `submit_extracted_document`. Reproduced here so you can wire equivalents into Make.com, Zapier, n8n, or any platform that supports Anthropic tool use.

```json
{
  "name": "submit_extracted_document",
  "description": "Submit the fully extracted business document as a strictly structured payload.",
  "input_schema": {
    "type": "object",
    "properties": {
      "doc_type": {
        "type": "string",
        "enum": ["invoice", "receipt", "purchase_order", "w9", "hr_onboarding", "expense_report", "unknown"]
      },
      "document_date": {"type": ["string", "null"]},
      "due_date":      {"type": ["string", "null"]},
      "invoice_number": {"type": ["string", "null"]},
      "entity": {
        "type": "object",
        "properties": {
          "legal_name": {"type": "string"},
          "tax_id":     {"type": ["string", "null"]},
          "email":      {"type": ["string", "null"]},
          "phone":      {"type": ["string", "null"]},
          "address":    {"type": ["string", "null"]}
        },
        "required": ["legal_name"]
      },
      "ledger": {
        "type": "object",
        "properties": {
          "currency": {"type": "string", "default": "USD"},
          "line_items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "description": {"type": "string"},
                "quantity":    {"type": "number", "minimum": 0},
                "unit_price":  {"type": "number", "minimum": 0},
                "total":       {"type": "number", "minimum": 0}
              },
              "required": ["description", "quantity", "unit_price", "total"]
            }
          },
          "subtotal":    {"type": "number", "minimum": 0},
          "tax_amount":  {"type": "number", "minimum": 0, "default": 0},
          "grand_total": {"type": "number", "minimum": 0}
        },
        "required": ["subtotal", "grand_total"]
      }
    },
    "required": ["doc_type", "entity", "ledger"]
  }
}
```

When invoking via Anthropic tool use, also set `tool_choice: {"type": "tool", "name": "submit_extracted_document"}` to force the model to emit the structured payload.
