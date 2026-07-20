"""
Simulated multi-factor authentication (§ Enterprise Security & Governance — MFA).
Delivery is simulated — the plaintext code is logged and, only when
settings.ALLOW_MOCK_MFA is True, handed back in the API response under a clearly
named field. When ALLOW_MOCK_MFA is False this raises rather than silently
no-op'ing, because there is no real delivery channel wired in yet.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.models.security import OtpChallenge
from app.models.user import User

log = structlog.get_logger(__name__)

MAX_ATTEMPTS = 5


class MfaError(Exception):
    """Base class — auth.py maps these to specific HTTP status codes."""


class ChallengeExpiredError(MfaError):
    pass


class ChallengeInvalidError(MfaError):
    pass


class MockMfaDisabledError(MfaError):
    """ALLOW_MOCK_MFA=False and no real delivery provider is configured yet."""


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def create_challenge(
    db: AsyncSession, user: User, purpose: str = "login"
) -> Tuple[OtpChallenge, Optional[str]]:
    if not settings.ALLOW_MOCK_MFA:
        raise MockMfaDisabledError(
            "No real OTP delivery provider is configured and ALLOW_MOCK_MFA is False"
        )

    code = _generate_code()
    challenge = OtpChallenge(
        user_id=user.id,
        code_hash=hash_password(code),
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(challenge)
    await db.flush()
    await db.refresh(challenge)

    log.info(
        "Simulated OTP issued — no real delivery channel configured",
        user_id=str(user.id), challenge_id=str(challenge.id), code=code,
    )
    return challenge, code


async def verify_challenge(db: AsyncSession, challenge_id: UUID, code: str) -> User:
    challenge = await db.get(OtpChallenge, challenge_id)
    if challenge is None:
        raise ChallengeInvalidError("Unknown or expired challenge")
    if challenge.consumed_at is not None:
        raise ChallengeInvalidError("Challenge already used")
    if challenge.expires_at < datetime.now(timezone.utc):
        raise ChallengeExpiredError("Code expired — request a new one")
    if challenge.attempt_count >= MAX_ATTEMPTS:
        raise ChallengeInvalidError("Too many incorrect attempts — request a new code")

    challenge.attempt_count += 1
    if not verify_password(code, challenge.code_hash):
        await db.flush()
        raise ChallengeInvalidError("Incorrect code")

    challenge.consumed_at = datetime.now(timezone.utc)
    await db.flush()

    user = await db.get(User, challenge.user_id)
    if user is None:
        raise ChallengeInvalidError("User no longer exists")
    return user
