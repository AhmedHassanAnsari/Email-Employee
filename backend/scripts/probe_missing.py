import asyncio, re
from dotenv import load_dotenv
load_dotenv("../.env")
from agent_service.auth_client import AuthClient
from agent_service.gmail_mcp import gmail_server_for_token
from email_monitor import _tool_text, _extract_search_ids

QUERIES = [
    "is:unread in:inbox -label:Processed",   # what the poller actually runs
    "is:unread in:inbox",                     # unread, ignoring Processed
    "in:inbox newer_than:3d",                 # anything recent in inbox
    "newer_than:3d",                          # anything recent anywhere (tabs/spam)
    "label:Processed newer_than:3d",          # recently-labeled Processed
]

async def main():
    a = AuthClient()
    users = await a.list_users()
    print("users:", users)
    for u in users:
        t = await a.get_access_token(u)
        async with gmail_server_for_token(t) as g:
            for q in QUERIES:
                r = await g.call_tool("search_gmail_messages", {"query": q, "page_size": 30})
                txt = _tool_text(r)
                ids = _extract_search_ids(txt)
                header = txt.splitlines()[0] if txt else "(empty)"
                print(f"\n=== {q!r}  -> {len(ids)} ids | {header}")
                for mid, tid in ids[:12]:
                    print(f"    msg={mid} thread={tid}")

asyncio.run(main())
