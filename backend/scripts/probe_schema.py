"""Ad-hoc: list Gmail MCP tools and their input schemas (which args are accepted).

Run: uv run python -m scripts.probe_schema
"""

import asyncio
import json

from dotenv import load_dotenv

load_dotenv("../.env")

from agent_service.auth_client import AuthClient  # noqa: E402
from agent_service.gmail_mcp import gmail_server_for_token  # noqa: E402

TOOLS = {
    "search_gmail_messages",
    "get_gmail_messages_content_batch",
    "modify_gmail_message_labels",
    "list_gmail_labels",
    "manage_gmail_label",
    "send_gmail_message",
}


async def main() -> None:
    auth = AuthClient()
    user_id = (await auth.list_users())[0]
    token = await auth.get_access_token(user_id)
    async with gmail_server_for_token(token) as gmail:
        tools = await gmail.list_tools()
    for t in tools:
        name = getattr(t, "name", None)
        if name in TOOLS:
            schema = getattr(t, "inputSchema", None) or {}
            props = list((schema.get("properties") or {}).keys())
            required = schema.get("required") or []
            print(f"{name}: props={props} required={required}")


if __name__ == "__main__":
    asyncio.run(main())
