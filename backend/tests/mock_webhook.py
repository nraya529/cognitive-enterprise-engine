"""End-to-end smoke test that simulates an upstream automation platform
(Make.com / Zapier) firing a chaotic invoice payload at the engine.

Run the server in one terminal:

    cd backend
    uvicorn src.main:app --reload

Then in another:

    python -m tests.mock_webhook
"""

from __future__ import annotations

import asyncio
import json
import sys
from textwrap import dedent

import httpx

ENDPOINT = "http://localhost:8000/webhook"


CHAOTIC_INVOICE = dedent(
    """\
    Forwarded from: billing@acmeplumbing.com
    Sent: Mon, Mar 3 2026 9:14 AM
    Subject: INV-2025-0847 from Acme Plumbing

    ---------- Forwarded Message ----------

    Hi Eddy,

    Please find our invoice attached below for the materials we delivered to
    your Cambridge site last week. Net 30 as usual.

    INVOICE
    Acme Plumbing Supply  Co.    EIN: 12-3456789
    47 Industrial Way, Boston MA 02118
    billing@acmeplumbing.com    (617) 555-0142

    Bill To:  Eddy's Plumbing Services
    Invoice #: INV-2025-0847
    Issue Date: 03/01/2026
    Due Date:   03/31/2026

    Line items:
       6"  copper pipe (10 ft)      qty 12  @  $43.50  =   $522.00
       Pressure fittings, brass     qty 24  @  $ 8.75  =   $210.00
       Solder kit                   qty  1  @  $34.99  =   $ 34.99

    Subtotal:               $766.99
    MA Sales Tax (6.25%):   $ 47.94
    -----
    GRAND TOTAL DUE:        $814.93

    Thank you for your continued business.
    Pay via ACH to routing 011000138 acct 4445102837
    """
)


async def fire() -> None:
    payload = {
        "source": "make_com",
        "raw_text": CHAOTIC_INVOICE,
        "sender_email": "billing@acmeplumbing.com",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        print(f">>> POST {ENDPOINT}")
        r = await client.post(ENDPOINT, json=payload)
        print(f"<<< {r.status_code}")
        body = r.json()
        print(json.dumps(body, indent=2, default=str))
        if r.status_code != 200:
            sys.exit(1)
        assert body["doc_type"] == "invoice", f"expected invoice, got {body['doc_type']}"
        assert body["ledger"]["math_is_valid"], "math should validate"
        assert body["entity"]["matched_vendor_id"] == "V001", "should match Acme vendor"
        print("\n✓ smoke test passed")


if __name__ == "__main__":
    asyncio.run(fire())
