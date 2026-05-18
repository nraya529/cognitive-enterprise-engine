# Interview Study Notes — Cognitive Enterprise Engine

Plain-English explanations of every non-obvious pattern in this codebase. If an interviewer asks about your project, talk in terms of these concepts, not raw syntax.

---

## 1. What `async`/`await` actually does

Python normally runs one thing at a time. When the program asks the operating system for something slow — a network response, a database row — it just sits there waiting. That's wasted time.

`async def` marks a function as **suspendable**. When such a function hits `await some_io_call()`, it tells the event loop "I'm waiting on I/O, do something else useful for now, wake me up when the result arrives." The event loop (managed by `asyncio` or `uvicorn`) keeps a list of suspended tasks and rotates between them.

In this project, `process_document` calls four agents in sequence. Each agent makes an HTTP call to Anthropic. While one document is waiting for Claude's response, FastAPI can handle a different incoming request. That's why the server can handle many concurrent documents without spawning threads.

**Interview line:** "Async lets a single Python process handle many concurrent I/O-bound operations without the overhead of threads. The event loop multiplexes between suspended tasks while they wait on network calls."

---

## 2. The `async with get_sessionmaker()() as session:` pattern

Three things are happening in that one line:

1. `get_sessionmaker()` returns a **factory** — a function that creates database sessions. It's a singleton; we set it up once at startup.
2. The trailing `()` actually **invokes the factory** to produce a new session.
3. `async with ... as session:` opens the session in a managed scope. When the `with` block exits — even via exception — the session is closed automatically. If we made changes and committed, they're persisted; if an exception bubbled out, the transaction rolls back implicitly.

**Why this matters:** every database operation is wrapped in its own session. We don't leak connections, we don't accidentally share state across requests, and we don't need to remember to call `session.close()`.

**Interview line:** "Each unit of work gets its own session via the context manager. The async context manager guarantees connection cleanup and transaction boundary even when something throws."

---

## 3. Why the verification agent is "recursive self-healing"

The extraction agent reads chaotic text and emits structured JSON. Sometimes it gets the math wrong, hallucinates a missing tax ID, or fumbles a date format.

Instead of failing the whole pipeline, the verification agent:

1. Tries to load the extracted data into Pydantic schemas. Pydantic enforces strict rules (math must reconcile, dates must be ordered correctly, tax IDs must have 9–10 digits).
2. If validation fails, Pydantic returns a list of specific errors — like "ledger.line_items.0.total: line item total 95 != quantity*unit_price 100".
3. Those errors are reformatted and **fed back into the extraction agent** as part of a new prompt: "Here's the document. Here are the errors you made last time. Try again."
4. This loop runs up to `MAX_SELF_HEAL_ATTEMPTS` times before giving up.

The agent literally learns from its own mistakes within a single request. The result is much higher accuracy on messy real-world documents than a single-shot extraction would produce.

**Interview line:** "We use a validator-driven feedback loop. Pydantic's structured error output gets fed back to the LLM as natural language correction, which gives us self-healing on parse failures without the operational cost of human review."

---

## 4. Forced tool use vs free-form output

When you ask Claude "extract this invoice as JSON," it might give you JSON, or it might give you "Here's the JSON you requested:" followed by JSON wrapped in markdown fences. Inconsistent. Hard to parse.

Forced tool use solves this. We tell Claude:

> "Here's a tool called `submit_extracted_document` with this exact schema. You MUST call this tool exactly once."

Via the `tool_choice: {"type": "tool", "name": "submit_extracted_document"}` parameter, Claude is guaranteed to return a tool-use block with a JSON object that already conforms to our schema. No parsing of unstructured text. No markdown fences.

**Interview line:** "We use Anthropic's tool use feature in 'forced' mode. By defining a JSON schema and constraining the model to invoke that one tool, we get structured output guaranteed at the API level rather than relying on prompt engineering to enforce format."

---

## 5. The approval gate (and why permission errors don't kill drafts)

Before a generated email is sent through Resend, we check several things:

- Is the draft approved? (`status == APPROVED`, `is_approved == True`)
- Is the recipient domain on the blocked list? (gmail.com, yahoo.com, etc.)
- Is the recipient on the suppression list? (opted out previously)
- Have we already sent to this address?
- Are we under the per-run send limit?
- Are we under the daily send limit?

If any of these fail, we raise `PermissionError`. The route handler catches it and returns HTTP 409 Conflict — **but does NOT mark the draft as `FAILED`**. This is deliberate: a permission failure is a *state mismatch*, not a delivery error. If you later remove the recipient from the suppression list, the same approved draft can be re-tried.

Compare to `Exception`: if Resend itself returns an error, that *is* a delivery failure. The draft is marked failed, the error is persisted, and the operator has to re-approve before another attempt.

**Interview line:** "We distinguish recoverable state violations from real delivery failures. State violations return 409 without mutating draft state; only genuine provider errors persist as failed and require re-approval."

---

## 6. Why we use Pydantic at the API boundary

Pydantic is doing three jobs at once:

1. **Type enforcement on input** — the FastAPI route declares `request: ProspectingRunRequest`. If the JSON body doesn't match, FastAPI returns a 422 with a specific error before our code runs.
2. **Cross-field validation** — our `LineItem` schema has a `@model_validator` that checks `quantity * unit_price == total` at construction time. This catches LLM math errors at the schema boundary.
3. **Serialization on output** — when we return a `ProspectingRunRead` object, FastAPI serializes it to JSON with the exact field types declared. No accidental leaking of internal database fields.

We use `ConfigDict(extra="forbid")` on every schema, which means any unexpected field in the input causes a validation error. That's how we catch the kind of "the LLM hallucinated an extra field" bugs that would otherwise silently propagate.

**Interview line:** "Pydantic v2 gives us a single layer that handles request validation, business invariant checking, and response serialization. The `extra='forbid'` configuration makes our API contracts strict — clients can't drift the schema without us noticing."

---

## 7. The BackgroundTasks pattern and its limit

`POST /prospecting/runs` returns 202 Accepted immediately, and the actual work happens *after* the response is sent. We do that via FastAPI's `BackgroundTasks`:

```python
background_tasks.add_task(run_prospecting, run.id)
```

This works because FastAPI runs the task on the same event loop, in the same process, after flushing the response.

**The limit:** if the process is killed mid-run, the work is lost. No automatic recovery, no persistence of in-flight state beyond what the orchestrator has already committed to the database.

**Honest framing for interviews:** "For a single-worker MVP this is fine because runs complete in under a minute. For production I'd swap in a proper task queue — Celery or RQ on Redis — so workers are decoupled from the request process and runs survive a restart."

---

## 8. Idempotency keys and retry-with-backoff

When sending via Resend:

1. We pick an idempotency key (`f"draft-{draft.id}-{draft.send_attempts}"`). This includes the attempt counter, so a retry after a real failure gets a *new* key — Resend won't dedupe a legitimate retry.
2. We pass the key in the `Idempotency-Key` header.
3. If Resend returns 429 (rate limit) or 5xx, we retry with exponential backoff (1s, 2s, 4s).
4. If we exhaust retries, we raise; the route handler persists the failure.

**Why this matters:** without idempotency, a network blip during retry could send the same email twice. Without backoff, hitting a rate limit just creates more rate-limit errors. Both patterns are non-negotiable for production outbound systems.

**Interview line:** "Outbound email needs idempotency keys to make retries safe, and exponential backoff to coexist politely with provider rate limits. We include the attempt counter in the idempotency key so genuine retries aren't deduped."

---

## 9. Fuzzy matching for vendor identification

Real-world data is messy. An invoice might say "Acme Plumbing Supply Co." but your vendor list has "Acme Plumbing Supply Company" or "Acme Plumbing." Exact string matching misses all of these.

We use `rapidfuzz.process.extractOne(name, choices, scorer=fuzz.WRatio)`. WRatio (weighted ratio) is a composite scorer that handles:

- Slight typos ("Plummbing" → "Plumbing")
- Word reordering ("Supply Co. Acme" → "Acme Supply Co.")
- Partial matches (alias vs full legal name)

It returns a similarity score 0–100. We only accept matches above a configurable threshold (default 85). Below that, we fall back to "unknown vendor" and flag for review.

**Interview line:** "We use rapidfuzz's WRatio for entity resolution because it composes multiple Levenshtein-derived scorers — it handles typos, word reordering, and alias variants without us having to engineer features manually."

---

## 10. Why `from __future__ import annotations` is everywhere

It postpones evaluation of type annotations. Without it, `def foo(x: ProcessedDocument)` would be evaluated when the function is *defined*, which can cause circular imports or errors with not-yet-defined types.

With `from __future__ import annotations`, all annotations become strings until something explicitly resolves them. This means we can use modern syntax like `dict[str, int]` even on older Python versions, and we can forward-reference classes that haven't been defined yet.

**The exception:** SQLAlchemy's `Mapped[X]` annotations are read at class-creation time to figure out column nullability. For those specifically, we use `Optional[X]` instead of `X | None`, because PEP 604 syntax requires Python 3.10+ for runtime resolution. The Pydantic schemas can stay on the modern syntax.

**Interview line:** "We use PEP 563 deferred evaluation for forward references and clean modern syntax. The exception is SQLAlchemy ORM mapped types, which need runtime type access — there we use `Optional` for cross-version compatibility."

---

## 11. The Tavily query matrix

A single search like `"regional logistics New England"` returns generic listings. Real B2B prospecting needs angle — different facets of the same target market.

So discovery generates 5 different queries from one niche/geography:

- `... operations manager contact email`
- `... invoice processing accounting operations`
- `... logistics back office document workflow`
- `... company directory leadership email`
- `... multi location service business operations`

Each query surfaces a different slice of the web. Results are deduplicated by domain (a company that shows up in 3 queries is still one lead). The orchestrator only proceeds with companies that surface unique domains.

**Interview line:** "We fan out a single market query into a matrix of buying-signal-specific phrases, then deduplicate by domain. This catches companies whose web presence emphasizes one facet (operations vs leadership vs procurement) over another."

---

## 12. Trace IDs

Every request gets a `trace_id` — a short random hex string — set as a context variable when the request arrives. Every log line emitted during that request's processing automatically includes the trace ID via structlog's contextvars processor.

This means when something goes wrong, you can grep the logs for one trace ID and see every step: which agent ran, what it returned, what the database did, whether the email was sent. You don't need correlation IDs scattered through application code.

**Interview line:** "We use structlog with contextvars to propagate trace IDs across async boundaries automatically. Every log line is correlated to its originating request without manual plumbing."

---

## Things you should be ready to defend or improve

**If asked "what would you change":**

- Replace SQLite with Postgres for concurrent writes
- Replace BackgroundTasks with Celery/RQ for durable job processing
- Add OpenTelemetry tracing — currently we only have logs
- Add API key per tenant and a multi-tenant data isolation layer
- Add a webhook dead-letter queue for failed Tavily/Anthropic calls

**If asked "what's risky in this design":**

- The agent self-healing loop is unbounded by token budget — a pathological document could burn API credits before hitting `MAX_SELF_HEAL_ATTEMPTS`. We mitigate via per-call `max_tokens`.
- The TOCTOU race on send rate limits is real but acceptable at low scale; would need a row-level lock for high throughput.
- We trust Claude's tool-use output structurally but still verify mathematically. Without the verification layer, hallucinated totals would corrupt the ledger.

**If asked "why not use LangChain or LlamaIndex":**

Be honest: those frameworks add abstraction that doesn't help for a focused, four-agent pipeline. We're using the Anthropic SDK directly because every layer of indirection between our prompt and the model is a layer where intent can drift. For a more open-ended agent or a RAG pipeline, the answer would be different.
