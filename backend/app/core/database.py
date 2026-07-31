"""
Async SQLAlchemy engine + session factory.
Uses pgvector extension for vector similarity search.

Two engines exist on purpose:
  - `engine` (settings.DATABASE_URL, POSTGRES_APP_USER) is what every request
    actually queries through.
  - The admin engine built inside init_db() (settings.DATABASE_URL_ADMIN,
    POSTGRES_USER) exists only for one-time startup DDL: create_all, numbered
    schema_upgrades steps, and the app_runtime role/grants/RLS policy setup.
A Postgres superuser or table owner bypasses Row-Level Security entirely, so the
district-isolation policies in _setup_runtime_role_and_rls() would be silent
no-ops if `engine` connected as the same role that owns the tables — that's the
whole reason these are two separate credentials.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# A second, long-lived admin-connected session factory for the handful of
# request paths whose authorization model isn't the logged-in user's RBAC
# district scope at all — e.g. GET /reports/shared/{token}, which is
# deliberately unauthenticated (the token itself is the authorization) and so
# never runs get_current_user, meaning the RLS session variables never get
# set. Using the ordinary get_db() session there doesn't "fail safe", it fails
# *wrong*: RLS blocks the report's own already-authorized data lookup outright
# (caught live — a valid share link 404'd because its case_master read
# returned zero rows). This is intentionally narrow — only for read paths
# whose authorization already happened via a mechanism other than the
# session's RBAC context.
_admin_engine = create_async_engine(settings.DATABASE_URL_ADMIN, pool_pre_ping=True)
AdminSessionFactory = async_sessionmaker(
    _admin_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# Mirrors app.repositories.case_repository._DISTRICT_UNRESTRICTED_ROLES. Kept as
# a plain string list here rather than importing the Role enum because this SQL
# runs in a separate execution context (raw DDL against Postgres, not the ORM) —
# both lists trace back to the same design-approved role set and must be kept
# in sync by hand if that set ever changes.
_DISTRICT_UNRESTRICTED_ROLE_NAMES = ("DSP", "SP", "DGP", "CRIME_ANALYST", "POLICY_MAKER")


async def _setup_runtime_role_and_rls(admin_engine) -> None:
    role_list_sql = ", ".join(f"'{r}'" for r in _DISTRICT_UNRESTRICTED_ROLE_NAMES)
    app_user = settings.POSTGRES_APP_USER

    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{app_user}') THEN
                        -- EXECUTE format(...) lets Postgres quote the password with %L
                        -- (its own string-literal escaper) rather than relying on a
                        -- Python f-string, which would break or enable SQL injection if
                        -- POSTGRES_APP_PASSWORD contained a single quote.
                        EXECUTE format(
                            'CREATE ROLE %I LOGIN PASSWORD %L
                             NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS',
                            '{app_user}',
                            '{settings.POSTGRES_APP_PASSWORD.replace("'", "''")}'  -- belt-and-suspenders escape for the format() arg itself
                        );
                    END IF;
                END
                $$;
                """
            )
        )
        await conn.execute(text(f"GRANT CONNECT ON DATABASE {settings.POSTGRES_DB} TO {app_user}"))
        await conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {app_user}"))
        await conn.execute(
            text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {app_user}")
        )
        await conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {app_user}"))
        await conn.execute(
            text(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {app_user}"
            )
        )

        # district_id = NULLIF(current_setting(...), '')::integer fails safe: if
        # get_current_user hasn't SET LOCAL'd the session variables (or a raw
        # query bypasses the app entirely), the comparison is NULL = NULL, which
        # SQL treats as unknown/false — zero rows, not every row.
        await conn.execute(text("ALTER TABLE case_master ENABLE ROW LEVEL SECURITY"))
        await conn.execute(text("DROP POLICY IF EXISTS case_master_district_isolation ON case_master"))
        await conn.execute(
            text(
                f"""
                CREATE POLICY case_master_district_isolation ON case_master
                USING (
                    current_setting('app.current_role', true) IN ({role_list_sql})
                    OR district_id = NULLIF(current_setting('app.current_district_id', true), '')::integer
                )
                """
            )
        )

        await conn.execute(text("ALTER TABLE person_case_role ENABLE ROW LEVEL SECURITY"))
        await conn.execute(
            text("DROP POLICY IF EXISTS person_case_role_district_isolation ON person_case_role")
        )
        await conn.execute(
            text(
                f"""
                CREATE POLICY person_case_role_district_isolation ON person_case_role
                USING (
                    current_setting('app.current_role', true) IN ({role_list_sql})
                    OR case_id IN (
                        SELECT id FROM case_master
                        WHERE district_id = NULLIF(current_setting('app.current_district_id', true), '')::integer
                    )
                )
                """
            )
        )


async def init_db() -> None:
    """
    Startup DDL, run once via the admin (table-owning) connection:
      1. pgvector extension + create_all (new tables/columns only).
      2. Any pending numbered schema_upgrades.py steps.
      3. The restricted app_runtime role + grants + RLS policies.
    """
    import app.models  # noqa: F401 — import side effect: registers every model with Base.metadata

    # Deferred rather than a module-level import: change_tracking imports the
    # model classes, which import Base from this module — a module-level import
    # here would be a circular import (this module wouldn't have finished
    # defining Base yet). By init_db() time this module is fully loaded, so the
    # cycle doesn't exist.
    import app.core.change_tracking  # noqa: F401

    admin_engine = create_async_engine(settings.DATABASE_URL_ADMIN, pool_pre_ping=True)
    try:
        async with admin_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)

        from app.core import schema_upgrades

        await schema_upgrades.run_pending_upgrades(admin_engine)
        await _setup_runtime_role_and_rls(admin_engine)
    finally:
        await admin_engine.dispose()


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields an AsyncSession per request, connected as the
    RLS-restricted app_runtime role."""
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_admin_db() -> AsyncSession:
    """
    FastAPI dependency for the narrow set of routes whose authorization is a
    token/link, not the caller's logged-in RBAC session — see the module
    docstring on AdminSessionFactory above for why get_db() is actively wrong
    there, not just stricter than needed.
    """
    async with AdminSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
