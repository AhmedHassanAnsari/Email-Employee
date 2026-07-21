"""WhatsApp notification via the notify_service MCP server.

Two events only: ``approval`` (draft awaiting review) and ``done`` (email sent).
No inbox notification. Gracefully no-ops if Twilio credentials are absent.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Literal

from agents import Agent, RunConfig, Runner, RunContextWrapper
from agents.mcp import MCPServerStdio
from pydantic import BaseModel

from .agent import config as _run_config

logger = logging.getLogger("notify")

EventType = Literal["approval", "done"]


class NotificationEvent(BaseModel):
    event_type: EventType
    email_id: int
    subject: str | None = None
    summary: str | None = None


def _credentials_present() -> bool:
    return all(os.getenv(v) for v in ("account_sid", "auth_token", "from", "to"))


def _notify_instructions(
    wrapper: RunContextWrapper[NotificationEvent], agent: Agent
) -> str:
    ev = wrapper.context

    role = (
        "# ROLE\n"
        "You are the WhatsApp Notifier for an autonomous email-automation "
        "system. You are a machine relay, not a conversational assistant. Your "
        "sole function is to deliver one WhatsApp message about the event below "
        "by calling the send_whatsapp tool.\n\n"
        "# GOAL\n"
        "Convert the EVENT DATA into a single concise plain-text WhatsApp "
        "message and deliver it by calling send_whatsapp.\n\n"
        "# ABSOLUTE RULES\n"
        "1. Your FIRST and ONLY action MUST be a call to the send_whatsapp "
        "tool. Do not emit any assistant text before the tool call.\n"
        "2. Call send_whatsapp EXACTLY ONCE. Never zero times, never twice.\n"
        "3. Calling the tool is MANDATORY and unconditional. Never decide the "
        "message is unnecessary, never ask the user for confirmation, never "
        "explain what you are about to do instead of doing it.\n"
        "4. Put the entire notification text in the tool's `body` argument. "
        "The message is only 'sent' if the tool is called — text you write "
        "outside the tool call is discarded and the user never sees it.\n"
        "5. After the tool returns, reply with exactly one short confirmation "
        "line (e.g. 'Notification sent.'). Add nothing else.\n\n"
        "# TOOL INPUT CONTRACT (send_whatsapp)\n"
        "- body (string, REQUIRED): the plain-text WhatsApp message. Plain text "
        "only \u2014 no markdown, no code fences, no emojis. Maximum 350 "
        "characters. Recipient and sender are configured server-side; you "
        "provide ONLY the body.\n\n"
        "# MESSAGE BODY REQUIREMENTS\n"
    )

    if ev.event_type == "approval":
        spec = (
            "Compose the body from this EVENT DATA, event type = APPROVAL "
            "(a drafted reply is waiting for the user to review and approve):\n"
            f"- Email ID: {ev.email_id}\n"
            f"- Subject: {ev.subject or '(no subject)'}\n\n"
            "The body MUST tell the user that a drafted email reply is awaiting "
            "their review and approval, and MUST include the Email ID and the "
            "Subject so they can identify it."
        )
    elif ev.event_type == "done":
        spec = (
            "Compose the body from this EVENT DATA, event type = DONE "
            "(the approved reply has been sent):\n"
            f"- Email ID: {ev.email_id}\n"
            f"- Subject: {ev.subject or '(no subject)'}\n"
            f"- Summary: {ev.summary or '(no summary)'}\n\n"
            "The body MUST tell the user the reply was sent, MUST include the "
            "Email ID and Subject, and MUST embed the Summary text verbatim."
        )
    else:
        spec = (
            "EVENT DATA is malformed (unknown event type). Call send_whatsapp "
            "once with body exactly: 'Email automation: unrecognized event.'"
        )
    return role + spec


_notify_agent: Agent | None = None
_notify_server: MCPServerStdio | None = None


async def _get_agent() -> Agent | None:
    global _notify_agent, _notify_server
    if not _credentials_present():
        return None
    if _notify_agent is not None:
        return _notify_agent

    backend_root = Path(__file__).parent.parent
    server = MCPServerStdio(
        params={
            "command": sys.executable,
            "args": ["-m", "notify_service.whatsapp_mcp"],
            "cwd": str(backend_root),
            "env": dict(os.environ),
        },
        cache_tools_list=True,
        name="whatsapp-notify",
        client_session_timeout_seconds=30.0,
    )
    await server.connect()
    _notify_server = server
    _notify_agent = Agent(
        name="WhatsApp Notifier",
        instructions=_notify_instructions,
        mcp_servers=[server],
    )
    return _notify_agent


def _unwrap_mcp_content(raw):
    """Unwrap the MCP tool-output envelope into the tool's own dict.

    The openai-agents MCP layer delivers a send_whatsapp result as a content
    block ({"type": "text", "text": "<json>"}), or a list of such blocks, not
    the raw dict the tool returned. Peel that off and parse the inner JSON.
    """
    if isinstance(raw, list):
        for block in raw:
            unwrapped = _unwrap_mcp_content(block)
            if unwrapped is not None:
                return unwrapped
        return None
    if isinstance(raw, dict):
        if raw.get("type") == "text" and isinstance(raw.get("text"), str):
            try:
                return json.loads(raw["text"])
            except Exception:
                return {"status": "unknown", "raw": raw["text"]}
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {"status": "unknown", "raw": raw}
    return None


def _extract_tool_outcome(result) -> dict | None:
    from agents.items import ToolCallOutputItem

    for item in reversed(getattr(result, "new_items", []) or []):
        if isinstance(item, ToolCallOutputItem):
            return _unwrap_mcp_content(item.output)
    return None


async def notify(event: NotificationEvent) -> bool:
    """Run the notify agent for an event. Returns True on delivery success."""
    if not _credentials_present():
        logger.info("WhatsApp disabled: notify event %s skipped", event.event_type)
        return False
    try:
        agent = await _get_agent()
        if agent is None:
            return False
        trigger = f"Process the {event.event_type} event for email {event.email_id}."
        result = await Runner.run(agent, trigger, context=event, run_config=_run_config)
        outcome = _extract_tool_outcome(result)
        if not outcome:
            logger.warning("notify %s: agent did not call send_whatsapp", event.event_type)
            return False
        if outcome.get("status") == "sent":
            logger.info("notify %s sent (sid=%s)", event.event_type, outcome.get("sid", ""))
            return True
        reason = outcome.get("reason") or outcome.get("error") or "unknown"
        logger.warning("notify %s failed: %s", event.event_type, reason)
        return False
    except Exception as exc:
        logger.warning("notify %s error: %s: %s", event.event_type, type(exc).__name__, exc)
        return False
