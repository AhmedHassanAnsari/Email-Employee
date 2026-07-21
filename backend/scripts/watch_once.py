import asyncio, sys
from dotenv import load_dotenv
load_dotenv("../.env")
from agent_service.auth_client import AuthClient
from agent_service.gmail_mcp import gmail_server_for_token
from email_monitor import _tool_text, _extract_search_ids

async def main():
    a = AuthClient()
    u = (await a.list_users())[0]
    t = await a.get_access_token(u)
    async with gmail_server_for_token(t) as g:
        for q in ("from:ahassanai512@gmail.com", "newer_than:1h", "is:unread in:inbox -label:Processed"):
            r = await g.call_tool("search_gmail_messages", {"query": q, "page_size": 15})
            ids = _extract_search_ids(_tool_text(r))
            print(f"{q!r} -> {len(ids)}", flush=True)
            if q == "from:ahassanai512@gmail.com" and ids:
                print("FOUND:", ids[0][0], flush=True)

asyncio.run(main())
