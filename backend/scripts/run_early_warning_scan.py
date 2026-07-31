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
            print("Scan Results:", res)
    finally:
        await graph_db.close()

if __name__ == "__main__":
    asyncio.run(main())
