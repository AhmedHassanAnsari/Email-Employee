import asyncio
from dotenv import load_dotenv
load_dotenv("../.env")
from agent_service.auth_client import AuthClient
from agent_service.gmail_mcp import gmail_server_for_token
from email_monitor import _tool_text, _extract_search_ids

QUERIES = [
    "from:ahassanai512@gmail.com",
    "from:ahassanai512@gmail.com is:unread in:inbox -label:Processed",
    "is:unread in:inbox -label:Processed",   # exact poller query
    "newer_than:1h",
]
async def main():
    a = AuthClient()
    u = (await a.list_users())[0]
    t = await a.get_access_token(u)
    async with gmail_server_for_token(t) as g:
        for q in QUERIES:
            r = await g.call_tool("search_gmail_messages", {"query": q, "page_size": 30})
            txt = _tool_text(r)
            ids = _extract_search_ids(txt)
            print(f"=== {q!r} -> {len(ids)} | {txt.splitlines()[0] if txt else '(empty)'}")
            for mid, tid in ids[:15]:
                print(f"    msg={mid} thread={tid}")
asyncio.run(main())
