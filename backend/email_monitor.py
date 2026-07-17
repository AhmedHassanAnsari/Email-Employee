"""Email monitor — poll loop over authorized users.

For each Google-linked user (from the auth service), search their Gmail for
unread inbox mail we haven't processed, and for each new message:

1. Write an ``inbox/{message_id}.json`` artefact (debuggable on-disk payload).
2. Apply the ``Processed`` Gmail label so it's skipped on re-detection (restart-safe).
3. Upsert an ``emails`` row (status ``pending``).
4. POST ``/emails/{id}/solve`` to the agent service.

No inbox WhatsApp notification — the first notification the user sees is the
approval request emitted by ``/solve``.

Detection and labelling go through the Gmail MCP (per-user bearer), keeping the
"touch the outside world only through MCP" principle intact.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.request
from dataclasses import dataclass

from dotenv import load_dotenv

from agent_service.auth_client import AuthClient
from agent_service.gmail_mcp import gmail_server_for_token
from agent_service.storage import ensure_dirs, inbox_payload_path
from db.repository import get_by_message_id, upsert_incoming
from db.session import module_sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_POLL_SECONDS = 30
DEFAULT_AGENT_API_BASE = "http://127.0.0.1:8001"
PROCESSED_LABEL = "Processed"
SEARCH_QUERY = "is:unread in:inbox -label:Processed"


@dataclass
class MonitorConfig:
    poll_seconds: int
    agent_api_base: str

    @classmethod
    def from_env(cls) -> "MonitorConfig":
        return cls(
            poll_seconds=int(os.getenv("MONITOR_POLL_SECONDS", str(DEFAULT_POLL_SECONDS))),
            agent_api_base=os.getenv("AGENT_API_BASE", DEFAULT_AGENT_API_BASE),
        )


def _tool_json(result) -> object:
    """Best-effort parse of an MCP CallToolResult into Python data.

    workspace-mcp returns JSON as text content; fall back to structuredContent
    when present.
    """
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
    return None


def _extract_messages(parsed: object) -> list[dict]:
    """Normalise a search result into a list of message dicts."""
    if isinstance(parsed, dict):
        for key in ("messages", "results", "items"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        return []
    if isinstance(parsed, list):
        return [m for m in parsed if isinstance(m, dict)]
    return []


class EmailMonitor:
    def __init__(self, config: MonitorConfig, sessionmaker, auth: AuthClient) -> None:
        self.config = config
        self.sessionmaker = sessionmaker
        self.auth = auth
        self.is_running = False
        ensure_dirs()

    async def poll_user(self, user_id: str) -> None:
        token = await self.auth.get_access_token(user_id)
        async with gmail_server_for_token(token) as gmail:
            search = await gmail.call_tool(
                "search_gmail_messages", {"query": SEARCH_QUERY}
            )
            messages = _extract_messages(_tool_json(search))
            if not messages:
                return
            logger.info("User %s: %d candidate message(s)", user_id, len(messages))
            for msg in messages:
                await self._handle_message(user_id, gmail, msg)

    async def _handle_message(self, user_id: str, gmail, msg: dict) -> None:
        message_id = str(msg.get("id") or msg.get("message_id") or "").strip()
        if not message_id:
            return

        async with self.sessionmaker() as session:
            if await get_by_message_id(session, message_id) is not None:
                return  # already ingested — DB guard on top of the label filter

        thread_id = msg.get("threadId") or msg.get("thread_id")
        from_addr = msg.get("from") or msg.get("sender")
        subject = msg.get("subject")
        snippet = msg.get("snippet") or msg.get("body") or ""

        inbox_payload_path(message_id).write_text(
            json.dumps(
                {
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "from": from_addr,
                    "subject": subject,
                    "snippet": snippet,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        # Label first so a crash mid-processing still skips it next round.
        try:
            await gmail.call_tool(
                "modify_gmail_message_labels",
                {"message_id": message_id, "add_label_names": [PROCESSED_LABEL]},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to label %s: %s", message_id, exc)

        async with self.sessionmaker() as session:
            email = await upsert_incoming(
                session,
                user_id=user_id,
                gmail_message_id=message_id,
                gmail_thread_id=thread_id,
                from_addr=from_addr,
                subject=subject,
                snippet=snippet,
            )
        logger.info("Ingested email id=%s (msg=%s)", email.id, message_id)
        await self._trigger_solve(email.id)

    async def _trigger_solve(self, email_id: int) -> None:
        url = f"{self.config.agent_api_base.rstrip('/')}/emails/{email_id}/solve"
        try:
            req = urllib.request.Request(url, method="POST")
            await asyncio.to_thread(urllib.request.urlopen, req, None, 120)
            logger.info("Triggered /solve for email %s", email_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to trigger /solve for %s: %s", email_id, exc)

    async def start(self) -> None:
        self.is_running = True
        logger.info("Starting email monitor (poll interval=%ds)", self.config.poll_seconds)
        while self.is_running:
            try:
                users = await self.auth.list_users()
                for user_id in users:
                    try:
                        await self.poll_user(user_id)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Error polling user %s: %s", user_id, exc)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Error during monitor cycle: %s", exc)
            await asyncio.sleep(self.config.poll_seconds)

    async def stop(self) -> None:
        self.is_running = False


def main() -> None:
    config = MonitorConfig.from_env()
    monitor = EmailMonitor(config, module_sessionmaker(), AuthClient())
    try:
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        logger.info("Stopping email monitor")


if __name__ == "__main__":
    main()
