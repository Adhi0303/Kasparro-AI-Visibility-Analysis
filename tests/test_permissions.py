import pytest
from fastapi import HTTPException
from app.auth import get_current_user_role, require_analyst, require_reviewer
from app.config import Settings
from fastapi.security import HTTPAuthorizationCredentials


def test_auth_analyst_token():
    settings = Settings(ANALYST_TOKEN="test-analyst", REVIEWER_TOKEN="test-reviewer")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-analyst")
    role = get_current_user_role(credentials=creds, settings=settings)
    assert role == "analyst"
    assert require_analyst(role) == "analyst"

    with pytest.raises(HTTPException) as exc:
        require_reviewer(role)
    assert exc.value.status_code == 403


def test_auth_reviewer_token():
    settings = Settings(ANALYST_TOKEN="test-analyst", REVIEWER_TOKEN="test-reviewer")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-reviewer")
    role = get_current_user_role(credentials=creds, settings=settings)
    assert role == "reviewer"
    assert require_reviewer(role) == "reviewer"

    with pytest.raises(HTTPException) as exc:
        require_analyst(role)
    assert exc.value.status_code == 403


def test_auth_invalid_token():
    settings = Settings(ANALYST_TOKEN="test-analyst", REVIEWER_TOKEN="test-reviewer")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token")
    with pytest.raises(HTTPException) as exc:
        get_current_user_role(credentials=creds, settings=settings)
    assert exc.value.status_code == 401


def test_auth_missing_token():
    settings = Settings(ANALYST_TOKEN="test-analyst", REVIEWER_TOKEN="test-reviewer")
    with pytest.raises(HTTPException) as exc:
        get_current_user_role(credentials=None, settings=settings)
    assert exc.value.status_code == 401

