# tests/test_scraper.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.scraper import (
    build_page_url,
    load_manifest,
    save_manifest,
    download_page,
)


def test_build_page_url():
    """Page URL is constructed from volume config and page number."""
    # NOTE: Update this test after API discovery in Task 3
    url = build_page_url("GALE_DOC_ID", page_num=5)
    assert "GALE_DOC_ID" in url
    assert "5" in url


def test_load_manifest_new(tmp_path):
    """Loading a non-existent manifest returns empty dict."""
    manifest = load_manifest(tmp_path / "manifest.json")
    assert manifest == {"downloaded": [], "failed": [], "total": 0}


def test_save_and_load_manifest(tmp_path):
    """Manifest round-trips through save and load."""
    manifest_path = tmp_path / "manifest.json"
    data = {"downloaded": [1, 2, 3], "failed": [4], "total": 10}
    save_manifest(manifest_path, data)
    loaded = load_manifest(manifest_path)
    assert loaded == data


def test_download_page_success(tmp_path):
    """Successful page download saves file and returns True."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"fake image data"
    mock_response.headers = {"Content-Type": "image/jpeg"}
    mock_session.get.return_value = mock_response

    result = download_page(
        session=mock_session,
        gale_id="GALE_DOC_ID",
        page_num=1,
        output_dir=tmp_path,
    )
    assert result is True
    saved_files = list(tmp_path.glob("page_*"))
    assert len(saved_files) == 1


def test_download_page_failure(tmp_path):
    """Failed download returns False."""
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.raise_for_status.side_effect = Exception("Forbidden")
    mock_session.get.return_value = mock_response

    result = download_page(
        session=mock_session,
        gale_id="GALE_DOC_ID",
        page_num=1,
        output_dir=tmp_path,
    )
    assert result is False
