import asyncio
from app.core.database import AsyncSessionFactory
from app.services.analytics.early_warning import EarlyWarningService

async def main():
    from app.core.graph_db import graph_db
    await graph_db.connect()
    try:
        async with AsyncSessionFactory() as session:
            print("Running Early Warning Scan...")
            res = await EarlyWarningService(session).scan()
            # AsyncSessionFactory() alone doesn't commit on clean exit — the
            # real app dependency (get_db(), database.py) does this explicitly
            # after a successful request, but a standalone script isn't a
            # request. Without this, the alerts inserted by scan() roll back
            # silently when the session closes, and this "Scan Results" line
            # prints as if it succeeded while nothing was actually persisted.
            await session.commit()
            print("Scan Results:", res)
    finally:
        await graph_db.close()

if __name__ == "__main__":
    asyncio.run(main())
