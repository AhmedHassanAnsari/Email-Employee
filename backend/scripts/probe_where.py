import asyncio
from dotenv import load_dotenv
load_dotenv("../.env")
from agent_service.auth_client import AuthClient
from agent_service.gmail_mcp import gmail_server_for_token
from email_monitor import _tool_text, _extract_search_ids, _parse_content_batch

QUERIES = [
    "in:spam newer_than:5d",
    "in:sent newer_than:5d",
    "in:anywhere newer_than:5d",
    "category:primary newer_than:5d",
    "in:inbox is:unread -label:Processed newer_than:30d",
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
            print(f"\n=== {q!r} -> {len(ids)} | {txt.splitlines()[0] if txt else '(empty)'}")
            for mid, tid in ids[:15]:
                print(f"    msg={mid} thread={tid}")
        # Identify the mystery recent message
        c = await g.call_tool("get_gmail_messages_content_batch",
                              {"message_ids": ["19f7b8bda9ae6122"], "format": "full"})
        parsed = _parse_content_batch(_tool_text(c))
        print("\n=== content 19f7b8bda9ae6122:", parsed.get("19f7b8bda9ae6122"))

asyncio.run(main())
