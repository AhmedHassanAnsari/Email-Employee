import asyncio
from dotenv import load_dotenv
load_dotenv("../.env")
from agent_service.auth_client import AuthClient
from agent_service.gmail_mcp import gmail_server_for_token
from email_monitor import _tool_text, _extract_search_ids

QUERIES = [
    'subject:"project status update"',
    'subject:project status update',
    '"request for project status update"',
    'in:inbox is:unread',           # sanity: what raw unread inbox returns now
    'is:unread',                    # all unread anywhere
]

async def main():
    a = AuthClient()
    u = (await a.list_users())[0]
    print("ACCOUNT (from token owner):", u)
    t = await a.get_access_token(u)
    async with gmail_server_for_token(t) as g:
        # confirm which mailbox the bearer resolves to
        prof = await g.call_tool("list_gmail_labels", {})
        first = _tool_text(prof).splitlines()[0] if _tool_text(prof) else "(no labels)"
        print("labels header:", first)
        for q in QUERIES:
            r = await g.call_tool("search_gmail_messages", {"query": q, "page_size": 30})
            txt = _tool_text(r)
            ids = _extract_search_ids(txt)
            print(f"\n=== {q!r} -> {len(ids)} | {txt.splitlines()[0] if txt else '(empty)'}")
            for mid, tid in ids[:15]:
                print(f"    msg={mid} thread={tid}")

asyncio.run(main())
