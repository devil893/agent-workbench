# Agent Workbench

A personal assistant with a browser workspace, persistent notes and tasks, searchable text documents, local reminders, and optional Claude-powered chat. Data is stored in SQLite and separated by user.

The architecture has a manager and 12 specialist groups: email, calendar, tasks, drive, documents, notes, reminders, memory, data, images, browser, and research. A real Claude backend can select and delegate tool calls. A deterministic offline backend provides a reproducible demonstration without an API key.

**Status:** working local application. Notes, tasks, documents and reminders work without paid APIs. External account services are separately labelled simulations; see the feature table below.

## Quick start

Python 3.11+ is required. Commands below run from this directory.

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m workbench init
python -m workbench serve
```

Open **http://127.0.0.1:8000** and enter the private access token printed by `init`. The browser keeps it in session storage for that tab. The generated configuration and database live in the Git-ignored `data/` directory. Run commands from the same project directory to keep using the same database. `init` never overwrites an existing account.

Use the tabs to save notes, create and complete tasks, paste and search text documents, and schedule reminders. Reminder times use your browser's timezone and appear in the Reminders inbox while the server is running; overdue reminders are delivered after restart. Deletion requests appear under Approvals before they execute.

Local chat supports `remember buy coffee`, `list notes`, `add task prepare a release`, and `list tasks`. This mode is deterministic. Enable the Claude backend below for open-ended language requests.

Run `python -m pytest -q` for automated tests or `python -m workbench demo` for an isolated command-line demonstration.

## Run the API

The browser uses the same authenticated API. For multiple users or environment-based configuration, generate a token with `python -m workbench token`. `WORKBENCH_TOKENS` overrides the local configuration and maps tokens to tenant IDs. There are no default API credentials. For example, in PowerShell:

```powershell
$token = python -m workbench token
$env:WORKBENCH_TOKENS = @{ $token = 'demo-user' } | ConvertTo-Json -Compress
python -m workbench serve
```

The local server listens at `http://127.0.0.1:8000`. Interactive API documentation is at `/docs`. Send `Authorization: Bearer YOUR_TOKEN` for every data endpoint. The tenant is derived from the token; callers cannot choose someone else's tenant in a request body.

```sh
curl http://127.0.0.1:8000/chat \
  -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" \
  -d '{"message":"remember prepare the review"}'
```

Offline demo commands include `remember ...`, `list notes`, and `/tool TOOL_NAME JSON_ARGUMENTS`. `/tools` lists every tool and its effect classification. Demo command parsing is deliberately simple and is **not an LLM**.

## Use a real Claude model

Set `WORKBENCH_BACKEND=anthropic`, `ANTHROPIC_API_KEY`, and an `ANTHROPIC_MODEL` available in your account, then restart. No model ID is invented or hard-coded. This uses the Anthropic Messages API with custom tools, not the Claude Agent SDK. The manager delegates to specialists; each specialist receives only its registered capabilities. The total model-step budget is bounded.

The model service receives the user's prompt, bounded conversation history and tool results. External action tools remain simulated even when the model is live. The live model path requires your credentials and incurs provider charges; it has not been live-tested as part of repository preparation.

## Approvals

External writes and destructive local actions create an immutable proposal. Nothing executes until the authenticated human sends `POST /approvals/ID` with `{"approve":true}`. `GET /approvals` shows the exact payload. Proposals expire after ten minutes and can be consumed only once. A model cannot grant itself approval: there is no approval tool.

`POST /chat` returns a run ID and trace. `GET /runs/ID` returns the same tenant's action events. Outcomes distinguish `blocked`, `approval_required`, `executed` (local), `simulated`, and `error`. A simulated email is a database record, never a sent email.

## What works, and what is simulated

| Surface | Implementation |
|---|---|
| Notes, preferences, text documents | Real, persistent SQLite records scoped to a tenant |
| Browser workspace and local tasks | Real create/list/complete/delete operations, persistent across restarts; `todo_*` tools |
| Document retrieval | Real keyword search with bounded excerpts; no vector embeddings |
| Reminders | Real scheduling into a durable local inbox, checked every five seconds |
| Data queries | Real read-only SQLite queries on a separate tenant-only snapshot |
| Charts | Real deterministic local SVG generation from numeric values |
| Manager/specialists | Real bounded model tool loop when Anthropic is configured; scripted protocol tests included |
| Email, calendar, Google-style tasks, drive | Synthetic account simulation; no Google OAuth or live Google writes. `tasks_*` is the simulation; `todo_*` is real local task management |
| Browser booking | Synthetic form/draft/approval/receipt state machine; no Playwright browser |
| Research | Tiny synthetic corpus; all network URLs blocked |
| Image generation | Explicitly unavailable; no image returned or success claimed |
| WhatsApp | Optional signed inbound text webhook and TwiML response; no unsolicited delivery |
| Voice, image input, contacts, Google Docs/Sheets | Not implemented in this release |

## WhatsApp text channel

Set `TWILIO_AUTH_TOKEN`, `TWILIO_WEBHOOK_URL` to the exact public HTTPS URL ending in `/whatsapp`, and `TWILIO_ALLOWED_PHONES` to a JSON list of enabled E.164 senders. Configure Twilio's incoming-message webhook to that URL. Unconfigured channels, invalid signatures and non-allowlisted senders are rejected. Message IDs are deduplicated. Send `approve ID` or `reject ID` to decide an action.

The synchronous TwiML path is suitable for short demo turns. Multi-call model turns can exceed Twilio's response deadline; reliable production delivery needs a queue and asynchronous outbound adapter. Voice/media receives an explicit unsupported response. Reminders are delivered to `/inbox`, not to WhatsApp.

## Evaluation

See [the evaluation guide](docs/EVALUATION.md). The optional runner uses SafeLabs-Eval **0.11.2**, prompt content **1.13.0**, schema **1.1.0**, and verifies the ASI05 set contains 30 prompts. Framework output is saved unchanged in a separate file from action telemetry. Results directories are ignored by Git.

This optional adapter is separate from the application. A deterministic smoke run is a transport check, not evidence of model safety.

## Deployment and limits

Use an isolated database and synthetic identities for evaluation. For local development, SQLite needs no service setup. Docker builds are provided but have not been exercised here. Mount `/app/data` for persistence. Set tokens through environment variables. The `.env.example` file is documentation; the application does not implicitly load `.env` files.

This release is designed for a single application process. In-memory turn locks are not distributed. The local DB and telemetry are plaintext and must be protected at the filesystem level. There is no user registration, token rotation UI, automatic retention policy, rate limiter, production queue, or general internet browser. Approval claims are at-most-once: a process crash after claiming can require a new proposal. Logs redact common credential patterns but are not a comprehensive data-loss-prevention system.

See [architecture](docs/ARCHITECTURE.md) and [security boundaries](docs/SECURITY.md).
