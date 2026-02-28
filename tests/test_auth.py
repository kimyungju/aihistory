# tests/test_auth.py
import pytest
from unittest.mock import MagicMock, patch
from src.auth import extract_cookies_from_driver, create_session_with_cookies


def test_extract_cookies_from_driver():
    """Cookie extraction returns full cookie dicts with domain info."""
    mock_driver = MagicMock()
    mock_driver.get_cookies.return_value = [
        {"name": "session_id", "value": "abc123", "domain": ".gale.com", "path": "/"},
        {"name": "auth_token", "value": "xyz789", "domain": ".gale.com", "path": "/"},
    ]
    cookies = extract_cookies_from_driver(mock_driver)
    assert len(cookies) == 2
    assert cookies[0]["name"] == "session_id"
    assert cookies[0]["value"] == "abc123"
    assert cookies[1]["name"] == "auth_token"


def test_create_session_with_cookies():
    """Session is created with cookies and headers properly set."""
    cookies = [
        {"name": "session_id", "value": "abc123", "domain": ".gale.com", "path": "/"},
        {"name": "auth_token", "value": "xyz789", "domain": ".gale.com", "path": "/"},
    ]
    session = create_session_with_cookies(cookies)
    assert session.cookies.get("session_id") == "abc123"
    assert session.cookies.get("auth_token") == "xyz789"
    assert "User-Agent" in session.headers
    assert "Origin" in session.headers
