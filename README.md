# AI Employee for Email Automation

An autonomous "AI Employee" that monitors a Gmail inbox 24/7, drafts replies with a multi-agent AI pipeline, and **requires human approval before anything is sent**. Every completed task is written to disk and to Postgres as a full audit trail, and the human is kept in the loop via WhatsApp notifications.

> Agents never touch the outside world directly. Email read/search/send/label and WhatsApp delivery are exposed exclusively through **MCP (Model Context Protocol)** tools — that indirection is a hard design principle of this project.

---

## How it works

```
Incoming Gmail  ──►  Email Monitor (poll loop)
                         │  search unread via Gmail MCP, label "Processed"
                         ▼
                     Inbox/  +  emails row (status: pending)
                         │  POST /emails/{id}/solve
                         ▼
                  Multi-Agent Pipeline
                  Writer ─► Structure           (draft grounded in owner profile)
                         │
                         ▼
                     Approval/  (status: drafted)
                         │  WhatsApp: "reply awaiting approval"
                         ▼
              ┌──────── Human Review (web UI) ────────┐
              │                                       │
          Approve                                  Reject + feedback
              │                                       │
   send in-thread via Gmail MCP              Reviewer agent refines
   summarize ─► Done/ (status: sent)         ─► back to Approval/
   WhatsApp: "reply sent"                       (repeat until approved)
```

### Pipeline agents (Gemini via the OpenAI Agents SDK)

Gemini cannot combine **structured output and tool calls in one agent**, so the draft path is split:

| Agent | Tools | Output | Role |
|-------|-------|--------|------|
| **Writer** | Gmail MCP | free text | Reads thread context, drafts a reply grounded in the owner knowledge base |
| **Structure** | — | `StructuredReply` | Turns the free-text draft into `{subject, body, in_reply_to}` |
| **Reviewer** | — | free text | Refines a rejected draft from the user's feedback (stateless, context in-memory) |
| **Summarizer** | — | `SummaryOutput` | Writes the 2-3 line audit summary for `Done/` |

The Writer is constructed **per request** bound to the caller's Gmail MCP server (per-user bearer token). All agents share a model-fallback chain that walks through Gemini models when one hits its free-tier quota.

---

## Architecture

Three long-running services plus Postgres and an external Gmail MCP server:

- **`backend` (agent service)** — FastAPI app (`agent_service.main:app`) exposing the email lifecycle (`/solve`, `/approve`, `/reject`), our Google OAuth flow (`/oauth/google/*`), and the `GET /emails` view for the UI. Port `8001`.
- **`email-monitor`** — standalone poll loop (`email_monitor.py`). For each authorized user it searches Gmail for unread inbox mail, writes an `Inbox/{id}.json` artefact, applies a `Processed` label (restart-safe dedup), upserts an `emails` row, and triggers `/solve`.
- **`frontend`** — React + Vite + Tailwind dashboard with Inbox / Approval / Done views and an approve/reject-with-feedback flow. Served on `5173`.
- **`postgres`** — two app-owned tables: `emails` (the per-email state machine) and `google_tokens` (per-user Google refresh token, Fernet-encrypted at rest).
- **Gmail MCP** — [`taylorwilsdon/google_workspace_mcp`](https://github.com/taylorwilsdon/google_workspace_mcp) run in **external-provider mode** over streamable-http. It is a pure resource server: it validates the `ya29.*` access tokens we mint and routes by the email in the token. **We own the OAuth consent flow and refresh tokens**, not the MCP server.

### Folder-based state machine

Emails flow through folders that represent workflow state (mirrored by the `emails.status` column):

```
Inbox/      newly fetched incoming emails       (status: pending)
Approval/   drafted replies awaiting review      (status: drafted)
Done/       sent replies + audit summary         (status: sent)
```

### Auth model

We run Google OAuth ourselves (`access_type=offline`, `prompt=consent`) and store each user's **refresh token** encrypted in Postgres. Per task we mint a fresh access token from it and hand that to the Gmail MCP as a per-request bearer. This survives MCP-server restarts and needs no re-consent.

---

## Tech stack

| Concern | Choice |
|---|---|
| Language / tooling | Python 3.12, [`uv`](https://docs.astral.sh/uv/) |
| Agent framework | OpenAI Agents SDK (`openai-agents`) |
| LLM | Google Gemini (via the OpenAI-compatible endpoint) |
| Tooling boundary | Model Context Protocol (MCP) |
| Backend API | FastAPI + Uvicorn |
| Database | PostgreSQL, async SQLAlchemy / SQLModel, Alembic migrations |
| Notifications | Twilio WhatsApp (own MCP server) |
| Frontend | React 18, Vite, Tailwind CSS, React Router |
| Deployment | Docker / Docker Compose |

---

## Getting started

### Prerequisites

- Docker + Docker Compose (easiest path), or Python 3.12 + `uv` and Node 18+ for local dev
- A Google Cloud OAuth client (Web application) with `http://localhost:8001/oauth/google/callback` as an authorized redirect URI
- A Gemini API key
- (Optional) Twilio WhatsApp sandbox credentials for notifications
- `uvx` available to run the Gmail MCP server (`taylorwilsdon/google_workspace_mcp`)

### 1. Configure environment

```bash
cp .env.example .env
```

Fill in `.env`:

- `GEMINI_API_KEY`, `GEMINI_MODEL`
- `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`
- `TOKEN_ENCRYPTION_KEY` — generate a Fernet key:
  ```bash
  uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `DATABASE_URL` (note the `+asyncpg` scheme)
- `GMAIL_MCP_URL` (default `http://127.0.0.1:8000/mcp`)
- Twilio `account_sid` / `auth_token` / `from` / `to` (optional — notifications no-op if absent)

### 2. Start the Gmail MCP server

This runs separately from the compose stack (it needs `uvx`):

```bash
cd backend
bash scripts/run_workspace_mcp.sh   # streamable-http on :8000, external-provider mode
```

### 3a. Run with Docker Compose

```bash
docker compose up --build
```

This starts Postgres, the agent service (runs `alembic upgrade head` on boot), the email monitor, and the frontend.

- Frontend: http://localhost:5173
- Agent API: http://localhost:8001 (`GET /health`)

### 3b. Run locally without Docker

```bash
# Backend deps
cd backend
uv sync
uv run alembic upgrade head

# Agent service
uv run uvicorn agent_service.main:app --host 0.0.0.0 --port 8001

# Email monitor (separate shell)
uv run python email_monitor.py

# Frontend (separate shell)
cd ../frontend
npm install
npm run dev
```

### 4. Connect a Gmail account

Open the frontend, sign in, and complete the Google consent flow (the backend redirects through `/oauth/google/start`). Once authorized, the monitor begins polling that inbox.

---

## Project layout

```
backend/
  agent_service/
    main.py            FastAPI app + CORS + lifespan
    agent.py           multi-agent pipeline (Writer/Structure/Reviewer/Summarizer) + owner profile
    routers/
      lifecycle.py     /emails, /solve, /approve, /reject
      oauth.py         /oauth/google/start, /oauth/google/callback
    gmail_mcp.py       per-user Gmail MCP connection (bearer-scoped)
    auth_client.py     mints Google access tokens from stored refresh tokens
    crypto.py          Fernet encrypt/decrypt for refresh tokens
    notify.py          WhatsApp notifier agent (approval / done events)
    models.py          Pydantic models for agent I/O
  notify_service/
    whatsapp_mcp.py    Twilio WhatsApp MCP server (send_whatsapp tool)
  db/
    models.py          SQLModel schema (emails, google_tokens)
    repository.py      queries
    session.py         async engine / session helpers
    migrations/        Alembic
  email_monitor.py     poll loop (search -> label -> upsert -> trigger /solve)
  scripts/             MCP launcher + probe/debug utilities
frontend/
  src/
    pages/             Inbox, Approval, Done
    components/        Dashboard, SignIn, EventCard, RejectModal
    context/           AuthContext, EventContext
    api/client.ts      axios client for the agent API
Inbox/ Approval/ Done/  on-disk workflow artefacts
docker-compose.yml
Agent.md                 original design spec
```

---

## Key design principles

- **Human approval before every outgoing email** — nothing sends without an explicit approve action.
- **All external I/O through MCP tools** — agents never call Gmail or Twilio APIs directly.
- **We own auth** — Google refresh tokens are ours, encrypted in Postgres; the Gmail MCP is a stateless resource server.
- **Restart-safe** — the `Processed` Gmail label and Postgres dedup mean nothing is reprocessed across restarts.
- **Full auditability** — original email, draft history, feedback, final response, and delivery status are preserved in `Done/` and the database.
