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
    return all(
        os.getenv(v)
        for v in (
            "TWILIO_ACCOUNT_SID",
            "TWILIO_AUTH_TOKEN",
            "TWILIO_WHATSAPP_FROM",
            "USER_WHATSAPP_TO",
        )
    )


def _notify_instructions(
    wrapper: RunContextWrapper[NotificationEvent], agent: Agent
) -> str:
    ev = wrapper.context
    base = (
        "You are a concise WhatsApp notifier for an email-automation system. "
        "You MUST call the send_whatsapp tool exactly once with a well-formatted "
        "plain-text body for the event below. Keep it under 350 characters. "
        "After the tool call, reply with one short confirmation line.\n\n"
    )
    if ev.event_type == "approval":
        body = (
            f"Event: DRAFT AWAITING APPROVAL.\n"
            f"Email ID: {ev.email_id}\n"
            f"Subject: {ev.subject or '(no subject)'}\n\n"
            "Tell the user a drafted reply is awaiting their review and approval."
        )
    elif ev.event_type == "done":
        body = (
            f"Event: EMAIL SENT.\n"
            f"Email ID: {ev.email_id}\n"
            f"Subject: {ev.subject or '(no subject)'}\n"
            f"Summary: {ev.summary or '(no summary)'}\n\n"
            "Tell the user the reply was sent. Embed the summary verbatim."
        )
    else:
        body = "Unknown event. Do not call the tool."
    return base + body


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


def _extract_tool_outcome(result) -> dict | None:
    from agents.items import ToolCallOutputItem

    for item in reversed(getattr(result, "new_items", []) or []):
        if isinstance(item, ToolCallOutputItem):
            raw = item.output
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except Exception:
                    return {"status": "unknown", "raw": raw}
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
