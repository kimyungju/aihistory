# tests/test_auth.py
import pytest
from unittest.mock import MagicMock, patch
from src.auth import extract_cookies_from_driver, create_session_with_cookies


def test_extract_cookies_from_driver():
    """Cookie extraction converts Selenium cookies to requests-compatible dict."""
    mock_driver = MagicMock()
    mock_driver.get_cookies.return_value = [
        {"name": "session_id", "value": "abc123", "domain": ".gale.com"},
        {"name": "auth_token", "value": "xyz789", "domain": ".gale.com"},
    ]
    cookies = extract_cookies_from_driver(mock_driver)
    assert cookies == {"session_id": "abc123", "auth_token": "xyz789"}


def test_create_session_with_cookies():
    """Session is created with cookies properly set."""
    cookies = {"session_id": "abc123", "auth_token": "xyz789"}
    session = create_session_with_cookies(cookies)
    assert session.cookies.get("session_id") == "abc123"
    assert session.cookies.get("auth_token") == "xyz789"
    assert "User-Agent" in session.headers
