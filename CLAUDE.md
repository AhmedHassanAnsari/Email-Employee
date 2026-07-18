# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This repository is at an early, pre-implementation stage. The only runtime code is `main.py` (a Hello-World stub). The authoritative design is in `Agent.md` — read it before building anything, as it defines the intended architecture, workflow, and technology choices.

## What This Is

An autonomous "AI Employee" for email automation. A Python service continuously monitors an inbox, drafts replies via a multi-agent AI pipeline, requires human approval before anything is sent, and keeps a full audit trail. See `Agent.md` for the full spec.

## Commands

This project uses `uv` (Python 3.12+).

```bash
uv sync                 # install/sync dependencies from pyproject.toml + uv.lock
uv run python main.py   # run the entry point
uv add <package>        # add a dependency (updates pyproject.toml and uv.lock)
```

There is no test, lint, or build tooling configured yet. When adding it, prefer wiring it through `uv run` so commands stay consistent.

## Architecture (intended — from Agent.md)

The design centers on a **human-in-the-loop, folder-based state machine**. Understanding these two things is key to being productive:

1. **Emails flow through folders that represent workflow state**, not just storage:
   - `Inbox/` — newly fetched incoming emails, triggers the agent pipeline
   - `Approval/` — drafted responses awaiting human review (the loop lives here: reject → refine → back to `Approval/`)
   - `Done/` — completed tasks with full audit summary (original email, draft history, feedback, final response, timestamp, delivery status)

2. **Agents never call external APIs directly — only through MCP tools.** Email read/fetch/send/search, WhatsApp notifications (Twilio), and file management are all exposed as MCP server tools. This indirection is a hard design principle; preserve it when adding capabilities.

The core loop: Email Monitor detects mail → multi-agent pipeline (Coordinator → Writer → Reviewer → QA) drafts a response → draft lands in `Approval/` → user notified via WhatsApp → approve (send + summarize to `Done/`) or reject-with-feedback (Reviewer Agent refines, repeat).

## Intended Tech Stack (from Agent.md)

- Multi-agent framework: **OpenAI Agents SDK, running the Google Gemini model** (Gemini is the LLM; the SDK is just the agent runtime). Configured via `GEMINI_API_KEY`.
- Tooling: Model Context Protocol (MCP) — the only path agents use to touch the outside world
- Notifications: Twilio (WhatsApp)
- Persistence: PostgreSQL (`DATABASE_URL`), likely via async SQLAlchemy/SQLModel + Alembic migrations
- Observability/eval: Langfuse
- Deployment: Docker, images in GitHub Container Registry (GHCR)

## Reference Implementation

This project follows the same architecture as the sibling repo **`AhmedHassanAnsari/ai-native-student-assistant`** (a 24/7 human-in-the-loop assignment automation pipeline) — adapt its patterns rather than reinventing them. Shared patterns: event-driven monitor loop → multi-agent solve (OpenAI Agents SDK + Gemini) → `inbox/approval/Done` filesystem artefacts → human approval → WhatsApp notify → MCP-driven delivery, all backed by PostgreSQL and run through `uv`. This email project differs in domain (email vs. university portal) and is not a 1:1 copy — treat the reference as the base idea, not a spec.
