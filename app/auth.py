from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings, Settings

security = HTTPBearer(auto_error=False)


def get_current_user_role(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Derives role strictly from the bearer token matched against server configuration.
    Never trusts client-supplied role parameters in the body.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials.strip()

    if token == settings.ANALYST_TOKEN:
        return "analyst"
    elif token == settings.REVIEWER_TOKEN:
        return "reviewer"
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


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

