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
import re
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

DEFAULT_POLL_SECONDS = 5
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


def _tool_text(result) -> str:
    """Extract the human-formatted text payload from an MCP CallToolResult.

    workspace-mcp's Gmail tools return a single formatted TEXT string (not JSON),
    optionally wrapped by fastmcp as ``{"result": "..."}`` in structuredContent.
    """
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        inner = structured.get("result")
        if isinstance(inner, str):
            return inner
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            # A fastmcp text block may itself be a JSON envelope {"result": "..."}.
            stripped = text.lstrip()
            if stripped.startswith("{"):
                try:
                    obj = json.loads(text)
                    if isinstance(obj, dict) and isinstance(obj.get("result"), str):
                        return obj["result"]
                except json.JSONDecodeError:
                    pass
            return text
    return ""


# search_gmail_messages emits blocks of "  N. Message ID: <id>\n ... Thread ID: <tid>".
_MESSAGE_ID_RE = re.compile(r"^\s*\d+\.\s*Message ID:\s*(\S+)", re.MULTILINE)
_THREAD_ID_RE = re.compile(r"^\s*Thread ID:\s*(\S+)", re.MULTILINE)


def _extract_search_ids(text: str) -> list[tuple[str, str | None]]:
    """Parse (message_id, thread_id) pairs from the search tool's text output.

    Message ID and Thread ID lines alternate per message block, so we zip them
    positionally. Entries whose id is ``unknown`` (the tool's null placeholder)
    are dropped.
    """
    message_ids = _MESSAGE_ID_RE.findall(text)
    thread_ids = _THREAD_ID_RE.findall(text)
    pairs: list[tuple[str, str | None]] = []
    for idx, mid in enumerate(message_ids):
        if mid == "unknown":
            continue
        tid = thread_ids[idx] if idx < len(thread_ids) else None
        pairs.append((mid, None if tid in (None, "unknown") else tid))
    return pairs


# get_gmail_messages_content_batch emits per-message blocks separated by "\n---\n\n",
# each starting "Message ID: <id>" then "Subject:"/"From:"/... header lines and a BODY.
_CONTENT_MSG_ID_RE = re.compile(r"^Message ID:\s*(\S+)", re.MULTILINE)


def _parse_content_batch(text: str) -> dict[str, dict]:
    """Map message_id -> {subject, from, snippet} from the batch-content text."""
    parsed: dict[str, dict] = {}
    for block in text.split("\n---\n\n"):
        m = _CONTENT_MSG_ID_RE.search(block)
        if not m:
            continue
        mid = m.group(1)
        subject = _header_value(block, "Subject")
        from_addr = _header_value(block, "From")
        snippet = _body_snippet(block)
        parsed[mid] = {
            "subject": subject,
            "from": from_addr,
            "snippet": snippet,
        }
    return parsed


def _header_value(block: str, name: str) -> str | None:
    m = re.search(rf"^{re.escape(name)}:\s*(.*)$", block, re.MULTILINE)
    return m.group(1).strip() if m else None


def _body_snippet(block: str, limit: int = 2000) -> str:
    """Text after the '--- BODY ---' marker, trimmed to a sane length."""
    marker = "--- BODY ---"
    idx = block.find(marker)
    if idx == -1:
        return ""
    body = block[idx + len(marker) :].strip()
    # Drop a trailing attachments section if present.
    att = body.find("--- ATTACHMENTS ---")
    if att != -1:
        body = body[:att].strip()
    return body[:limit]


class EmailMonitor:
    def __init__(self, config: MonitorConfig, sessionmaker, auth: AuthClient) -> None:
        self.config = config
        self.sessionmaker = sessionmaker
        self.auth = auth
        self.is_running = False
        # Resolved "Processed" label id per user (Gmail label ids are per-account).
        self._label_ids: dict[str, str] = {}
        ensure_dirs()

    async def _processed_label_id(self, user_id: str, gmail) -> str | None:
        """Resolve (creating if needed) the 'Processed' label id for a user."""
        cached = self._label_ids.get(user_id)
        if cached:
            return cached

        listing = _tool_text(await gmail.call_tool("list_gmail_labels", {}))
        m = re.search(
            rf"^\s*•\s*{re.escape(PROCESSED_LABEL)}\s*\(ID:\s*(\S+?)\)",
            listing,
            re.MULTILINE,
        )
        if m:
            self._label_ids[user_id] = m.group(1)
            return m.group(1)

        created = _tool_text(
            await gmail.call_tool(
                "manage_gmail_label",
                {"action": "create", "name": PROCESSED_LABEL},
            )
        )
        cm = re.search(r"ID:\s*(\S+)", created)
        if cm:
            self._label_ids[user_id] = cm.group(1)
            return cm.group(1)
        return None

    async def poll_user(self, user_id: str) -> None:
        token = await self.auth.get_access_token(user_id)
        async with gmail_server_for_token(token) as gmail:
            search = await gmail.call_tool(
                "search_gmail_messages",
                {"query": SEARCH_QUERY},
            )
            pairs = _extract_search_ids(_tool_text(search))
            if not pairs:
                return

            # Filter out ids we've already ingested before spending a content fetch.
            async with self.sessionmaker() as session:
                fresh = [
                    (mid, tid)
                    for mid, tid in pairs
                    if await get_by_message_id(session, mid) is None
                ]
            if not fresh:
                return
            logger.info("User %s: %d new message(s)", user_id, len(fresh))

            content = await gmail.call_tool(
                "get_gmail_messages_content_batch",
                {
                    "message_ids": [mid for mid, _ in fresh],
                    "format": "full",
                },
            )
            contents = _parse_content_batch(_tool_text(content))

            for message_id, thread_id in fresh:
                info = contents.get(message_id, {})
                await self._handle_message(
                    user_id,
                    gmail,
                    message_id=message_id,
                    thread_id=thread_id,
                    from_addr=info.get("from"),
                    subject=info.get("subject"),
                    snippet=info.get("snippet", ""),
                )

    async def _handle_message(
        self,
        user_id: str,
        gmail,
        *,
        message_id: str,
        thread_id: str | None,
        from_addr: str | None,
        subject: str | None,
        snippet: str,
    ) -> None:
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
            label_id = await self._processed_label_id(user_id, gmail)
            if label_id:
                await gmail.call_tool(
                    "modify_gmail_message_labels",
                    {
                        "message_id": message_id,
                        "add_label_ids": [label_id],
                    },
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
