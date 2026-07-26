import asyncio
from sqlalchemy import delete, select
from app.core.database import init_db
from app.models.case import CaseMaster, CaseStageEvent, ActSectionAssociation
from app.models.financial import FinancialTransaction
from app.models.person import Person, PersonCaseRole
from app.models.offender import CriminalHistory, RiskScore
from app.models.document import Document
from app.core.graph_db import graph_db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
from scripts.seed_demo_data import seed

async def main():
    await init_db()
    await graph_db.connect()
    
    admin_engine = create_async_engine(settings.DATABASE_URL_ADMIN)
    session_factory = async_sessionmaker(admin_engine, expire_on_commit=False)
    
    # 1. Clean Neo4j
    print("Cleaning Neo4j stale demo nodes...")
    await graph_db.execute_query("MATCH (p:Person) WHERE p.name IN ['Naveen Reddy', 'Manjunath Gowda', 'Ashwin Rao'] DETACH DELETE p", {})
    await graph_db.execute_query("MATCH (i:Incident) WHERE i.crime_no = 'THEFT-BLR-INDR-2025-0142' DETACH DELETE i", {})
    await graph_db.execute_query("MATCH (a:Account) WHERE a.account_no IN ['ACCT-4471-0093-7712', 'ACCT-9931-2200-4821', 'ACCT-1187-5502-6634', 'ACCT-8825-5533-6621'] DETACH DELETE a", {})
    
    # 2. Clean Postgres
    async with session_factory() as session:
        # Find old case
        res = await session.execute(select(CaseMaster).where(CaseMaster.crime_no == "THEFT-BLR-INDR-2025-0142"))
        case = res.scalar_one_or_none()
        if case:
            print(f"Deleting Postgres old demo case {case.crime_no}...")
            await session.execute(delete(FinancialTransaction).where(FinancialTransaction.linked_incident_id == case.id))
            await session.execute(delete(PersonCaseRole).where(PersonCaseRole.case_id == case.id))
            await session.execute(delete(CaseStageEvent).where(CaseStageEvent.case_id == case.id))
            await session.execute(delete(ActSectionAssociation).where(ActSectionAssociation.case_id == case.id))
            await session.execute(delete(Document).where(Document.linked_incident_id == case.id))
            await session.execute(delete(CaseMaster).where(CaseMaster.id == case.id))
            
        # Delete old people
        res_p = await session.execute(select(Person).where(Person.full_name.in_(["Naveen Reddy", "Manjunath Gowda", "Ashwin Rao"])))
        persons = res_p.scalars().all()
        for p in persons:
            print(f"Deleting Postgres person {p.full_name}...")
            res_ch = await session.execute(select(CriminalHistory).where(CriminalHistory.person_id == p.id))
            ch_objs = res_ch.scalars().all()
            for ch in ch_objs:
                await session.execute(delete(RiskScore).where(RiskScore.criminal_history_id == ch.id))
                await session.execute(delete(CriminalHistory).where(CriminalHistory.id == ch.id))
            await session.execute(delete(Person).where(Person.id == p.id))
            
        await session.commit()
        print("Deleted old demo case and suspects from Postgres.")
        
    await graph_db.close()
    
    # 3. Re-run Seeder
    print("Re-running demo data seeder...")
    await seed()
    print("Demo case successfully re-seeded!")

if __name__ == "__main__":
    asyncio.run(main())
