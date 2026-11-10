import secrets
from dataclasses import dataclass
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings, Settings

security = HTTPBearer(auto_error=False)

_DEV_DEFAULT_TOKENS = {"dev-analyst-token-2026", "dev-reviewer-token-2026"}
_DEV_ENVS = {"development", "dev", "test", "testing"}


@dataclass(frozen=True)
class AuthenticatedActor:
    role: str
    user_id: str


def _safe_token_match(provided: str, expected: Optional[str]) -> bool:
    if not provided or not expected:
        return False
    return secrets.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def get_current_actor(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedActor:
    """
    Derives authenticated role and identity strictly from server-configured Bearer tokens
    using constant-time comparison. Never trusts client-supplied role or owner headers/bodies.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()
    is_non_dev = settings.APP_ENV.lower() not in _DEV_ENVS

    candidates = [
        (settings.ANALYST_TOKEN, "analyst", "analyst-1"),
        (settings.SECONDARY_ANALYST_TOKEN, "analyst", "analyst-2"),
        (settings.REVIEWER_TOKEN, "reviewer", "reviewer-1"),
        (settings.ADMIN_TOKEN, "admin", "admin-1"),
    ]

    for configured, role, user_id in candidates:
        if _safe_token_match(token, configured):
            if is_non_dev and configured in _DEV_DEFAULT_TOKENS:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Default development credentials are disabled in non-development environments",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return AuthenticatedActor(role=role, user_id=user_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_role(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    settings: Settings = Depends(get_settings),
) -> str:
    return get_current_actor(credentials=credentials, settings=settings).role


def require_analyst(role: str = Depends(get_current_user_role)) -> str:
    if role != "analyst":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires analyst privileges",
        )
    return role


def require_reviewer(role: str = Depends(get_current_user_role)) -> str:
    if role != "reviewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires reviewer privileges",
        )
    return role


def require_analyst_or_reviewer(role: str = Depends(get_current_user_role)) -> str:
    if role not in ("analyst", "reviewer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires analyst or reviewer privileges",
        )
    return role


def require_analyst_actor(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    if actor.role != "analyst":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires analyst privileges",
        )
    return actor


def require_reviewer_actor(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    if actor.role != "reviewer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires reviewer privileges",
        )
    return actor


def require_admin_actor(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    if actor.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Requires admin privileges",
        )
    return actor


def require_authenticated_actor(
    actor: AuthenticatedActor = Depends(get_current_actor),
) -> AuthenticatedActor:
    return actor
