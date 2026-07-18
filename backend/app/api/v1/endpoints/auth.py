"""
Authentication endpoints — password + simulated MFA, token issuance/refresh/logout
(§ Enterprise Security & Governance — MFA, session expiration).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.config import settings
from app.core.database import get_db
from app.core.geo_policy import is_login_permitted
from app.core.request_context import client_ip_ctx
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.enums import Role
from app.models.security import RefreshTokenRecord
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services import mfa_service

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class CurrentUserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    badge_number: Optional[str]
    district_id: Optional[int]
    unit_id: Optional[int]

    model_config = {"from_attributes": True}


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    challenge_id: UUID
    expires_in_minutes: int
    simulated_code: Optional[str] = None
    """Present only when ALLOW_MOCK_MFA=True — dev/demo stand-in for real SMS/email delivery."""


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    badge_number: str | None = None
    role: Role = Role.CONSTABLE


class MfaVerifyRequest(BaseModel):
    challenge_id: UUID
    code: str


class MfaResendRequest(BaseModel):
    challenge_id: UUID


class RefreshRequest(BaseModel):
    refresh_token: str


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    db.add(
        RefreshTokenRecord(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=None,
            ip_address=client_ip_ctx.get(),
        )
    )
    user.last_login = datetime.now(timezone.utc)
    await db.flush()

    await log_audit_event(db, action="auth.login", resource_type="user", resource_id=str(user.id), user_id=user.id)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/token")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """
    Password step. Returns MfaRequiredResponse when the account has MFA enabled
    (the default) — the caller must then hit /auth/mfa/verify to get real tokens.
    Only when mfa_enabled is False does this return TokenResponse directly.
    """
    repo = UserRepository(db)
    user = await repo.get_by_email(form.username)
    if not user or not verify_password(form.password, user.hashed_password):
        await log_audit_event(db, action="auth.login_failed", resource_type="user", resource_id=form.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account inactive")
    if not is_login_permitted(client_ip_ctx.get()):
        await log_audit_event(db, action="auth.login_blocked_geo", resource_type="user", resource_id=str(user.id), user_id=user.id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Login not permitted from this location")

    if not user.mfa_enabled:
        return await _issue_tokens(db, user)

    try:
        challenge, code = await mfa_service.create_challenge(db, user)
    except mfa_service.MockMfaDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="MFA is required for this account but no real OTP delivery provider is configured",
        ) from exc
    await log_audit_event(
        db, action="auth.mfa_challenge_issued", resource_type="user", resource_id=str(user.id), user_id=user.id,
    )
    return MfaRequiredResponse(
        challenge_id=challenge.id,
        expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
        simulated_code=code,
    )


@router.get("/me", response_model=CurrentUserOut)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Lets the frontend identify who's logged in (and their role, for nav/route
    gating) from just the stored tokens — there's no other way to recover this
    after a page reload without re-authenticating.
    """
    return CurrentUserOut.model_validate(current_user)


@router.post("/mfa/verify", response_model=TokenResponse)
async def verify_mfa(payload: MfaVerifyRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await mfa_service.verify_challenge(db, payload.challenge_id, payload.code)
    except mfa_service.ChallengeExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except mfa_service.ChallengeInvalidError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return await _issue_tokens(db, user)


@router.post("/mfa/resend", response_model=MfaRequiredResponse)
async def resend_mfa(payload: MfaResendRequest, db: AsyncSession = Depends(get_db)):
    from app.models.security import OtpChallenge

    previous = await db.get(OtpChallenge, payload.challenge_id)
    if previous is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown challenge")
    if previous.consumed_at is None:
        previous.consumed_at = datetime.now(timezone.utc)  # invalidate — a resend supersedes it

    user = await db.get(User, previous.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User no longer exists")

    try:
        challenge, code = await mfa_service.create_challenge(db, user, purpose=previous.purpose)
    except mfa_service.MockMfaDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="No real OTP delivery provider is configured",
        ) from exc
    return MfaRequiredResponse(
        challenge_id=challenge.id,
        expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
        simulated_code=code,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Validates the refresh token's signature/expiry AND its server-side
    RefreshTokenRecord (revoked/expired) — the JWT alone isn't enough, since a
    logged-out or revoked token must stop working immediately, not just at its
    original expiry.
    """
    from jose import JWTError, jwt
    from sqlalchemy import select

    try:
        jwt_payload = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if jwt_payload.get("type") != "refresh":
            raise JWTError("wrong token type")
        user_id = jwt_payload["sub"]
    except (JWTError, KeyError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    token_hash = hash_token(payload.refresh_token)
    stmt = select(RefreshTokenRecord).where(RefreshTokenRecord.token_hash == token_hash)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if record is None or record.revoked_at is not None or record.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is no longer valid")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer active")

    # Rotate — the old refresh token is single-use once exchanged.
    record.revoked_at = now
    await db.flush()
    return await _issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    token_hash = hash_token(payload.refresh_token)
    stmt = select(RefreshTokenRecord).where(RefreshTokenRecord.token_hash == token_hash)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()
    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
        await db.flush()
        await log_audit_event(db, action="auth.logout", resource_type="user", resource_id=str(record.user_id), user_id=record.user_id)
    return {"status": "logged_out"}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    if await repo.get_by_email(payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        badge_number=payload.badge_number,
        role=payload.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return await _issue_tokens(db, user)
