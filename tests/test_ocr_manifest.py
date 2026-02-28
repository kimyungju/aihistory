# tests/test_ocr_manifest.py
import json
import pytest
from pathlib import Path

from src.ocr.manifest import load_ocr_manifest, save_ocr_manifest, update_manifest_page


def test_load_ocr_manifest_new(tmp_path):
    """Loading non-existent manifest returns empty structure."""
    manifest = load_ocr_manifest(tmp_path / "ocr_manifest.json")
    assert manifest["completed_pages"] == []
    assert manifest["failed_pages"] == []
    assert manifest["total_pages"] == 0


def test_save_and_load_manifest(tmp_path):
    """Manifest round-trips through save and load."""
    path = tmp_path / "ocr_manifest.json"
    data = {
        "volume_id": "CO273_534",
        "total_pages": 100,
        "completed_pages": [1, 2, 3],
        "failed_pages": [{"page": 4, "error": "timeout"}],
        "doc_page_map": {},
    }
    save_ocr_manifest(path, data)
    loaded = load_ocr_manifest(path)
    assert loaded == data


def test_update_manifest_page_success():
    """Successful page is added to completed list."""
    manifest = {
        "completed_pages": [1, 2],
        "failed_pages": [],
        "total_pages": 10,
    }
    update_manifest_page(manifest, page_num=3, success=True)
    assert 3 in manifest["completed_pages"]


def test_update_manifest_page_failure():
    """Failed page is added to failed list with error."""
    manifest = {
        "completed_pages": [],
        "failed_pages": [],
        "total_pages": 10,
    }
    update_manifest_page(manifest, page_num=5, success=False, error="timeout")
    assert len(manifest["failed_pages"]) == 1
    assert manifest["failed_pages"][0]["page"] == 5
    assert manifest["failed_pages"][0]["error"] == "timeout"
