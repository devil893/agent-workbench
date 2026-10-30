# Local validation

Verified during initial implementation on Windows with Python 3.12:

- 29 tests passed, including the optional pinned SafeLabs adapter test.
- All 30 ASI05 prompts passed through the unmodified SafeLabs 0.11.2 runner using the offline demo transport, with no adapter errors.
- Separate per-prompt tool-event entries and immutable baseline serialization were checked.
- Tenant boundaries, approval expiry/rejection/replay/concurrent claims, SQL restrictions, network refusal, document retrieval, reminder delivery, signed webhook rejection/deduplication, and manager/specialist tool protocol were exercised.
- The local FastAPI server returned an `ok` health response.

There was one dependency deprecation warning: Starlette's installed test client recommends `httpx2` for a future transition. It did not cause a test failure.

No live Anthropic, Google, Twilio or booking-service call was made. The model protocol tests use scripted model responses. Docker and Linux CI configuration are supplied but were not run locally. The smoke test is not a valid LLM safety evaluation and does not substantiate any claim that the agent passed ASI05.
