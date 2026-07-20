"""Ad-hoc: mint a token and dump the raw search_gmail_messages text + parsed ids.

Run: uv run python -m scripts.probe_search
"""

import asyncio

from dotenv import load_dotenv

load_dotenv("../.env")

from agent_service.auth_client import AuthClient  # noqa: E402
from agent_service.gmail_mcp import gmail_server_for_token  # noqa: E402
from email_monitor import SEARCH_QUERY, _extract_search_ids, _tool_text  # noqa: E402


async def main() -> None:
    auth = AuthClient()
    users = await auth.list_users()
    print("users:", users)
    for user_id in users:
        token = await auth.get_access_token(user_id)
        async with gmail_server_for_token(token) as gmail:
            for q in (SEARCH_QUERY, "in:inbox", "is:unread"):
                res = await gmail.call_tool(
                    "search_gmail_messages",
                    {"query": q},
                )
                text = _tool_text(res)
                print(f"\n===== query={q!r} =====")
                print(text[:1200])
                print("--- parsed ids:", _extract_search_ids(text))


if __name__ == "__main__":
    asyncio.run(main())
