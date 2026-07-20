"""Ad-hoc state dump: authorized users + emails rows. Run: uv run python -m scripts.check_state"""

import asyncio

from dotenv import load_dotenv

load_dotenv("../.env")

from sqlalchemy import select  # noqa: E402

from db.models import Email  # noqa: E402
from db.repository import list_token_user_ids  # noqa: E402
from db.session import module_sessionmaker  # noqa: E402


async def main() -> None:
    sm = module_sessionmaker()
    async with sm() as session:
        users = await list_token_user_ids(session)
        rows = (await session.execute(select(Email))).scalars().all()
    print("authorized users:", users)
    print("email rows:", len(rows))
    for e in rows:
        print(f"  id={e.id} status={e.status} from={e.from_addr!r} subject={e.subject!r} msg={e.gmail_message_id}")


if __name__ == "__main__":
    asyncio.run(main())
