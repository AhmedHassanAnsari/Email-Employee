"""Ad-hoc: print authorized users in google_tokens. Run: uv run python -m scripts.check_tokens"""

import asyncio

from dotenv import load_dotenv

load_dotenv("../.env")

from db.repository import list_token_user_ids  # noqa: E402
from db.session import module_sessionmaker  # noqa: E402


async def main() -> None:
    sm = module_sessionmaker()
    async with sm() as session:
        users = await list_token_user_ids(session)
    print("authorized users:", users)


if __name__ == "__main__":
    asyncio.run(main())
