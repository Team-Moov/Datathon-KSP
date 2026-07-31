"""
JWT-based authentication helpers.
Roles: CONSTABLE, INSPECTOR, DSP, SP, DGP, CRIME_ANALYST, POLICY_MAKER — see
app/core/permissions.py for the capability matrix these grant.
Sensitive columns (PersonCaseRole.religion_id, PersonCaseRole.caste_id) are
access-controlled at the service layer (app/core/masking.py).
"""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.request_context import current_user_id_ctx
from app.models.user import User
from app.repositories.user_repository import UserRepository

log = structlog.get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/token")


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token helpers ──────────────────────────────────────────────────────────────

def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "role": role, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def hash_token(token: str) -> str:
    """
    SHA-256 for refresh-token storage lookups — unlike a user password, a JWT
    refresh token is already high-entropy, so a fast deterministic hash (indexed
    equality lookup in RefreshTokenRecord) is the right tool; bcrypt is reserved
    for low-entropy user-supplied secrets.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ── FastAPI dependencies ───────────────────────────────────────────────────────

async def get_user_from_token(token: str, db: AsyncSession) -> User:
    """
    Shared JWT-validation core, factored out of get_current_user() so
    WebSocket routes (which can't carry a normal Authorization header from a
    browser client, and so read the token from elsewhere — e.g. a query
    param — instead of via the oauth2_scheme Depends) can reuse the exact
    same validation instead of re-implementing it.
    """
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exc
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_exc

    current_user_id_ctx.set(user.id)
    await _apply_rls_session_context(db, user)
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await get_user_from_token(token, db)


async def _apply_rls_session_context(db: AsyncSession, user: User) -> None:
    """
    Sets the two Postgres session variables the RLS district-isolation policies
    read (app/core/database.py's _setup_runtime_role_and_rls). set_config(...,
    true) is the parameterized equivalent of SET LOCAL — scoped to this request's
    transaction — and, unlike a raw `SET LOCAL x = value` string, takes its value
    as a normal bound parameter rather than needing to be interpolated into SQL.
    """
    await db.execute(text("SELECT set_config('app.current_role', :role, true)"), {"role": user.role.value})
    await db.execute(
        text("SELECT set_config('app.current_district_id', :district_id, true)"),
        {"district_id": str(user.district_id) if user.district_id is not None else ""},
    )
