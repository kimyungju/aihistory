# tests/test_gcs_upload.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.gcs_upload import upload_file, upload_volume


def test_upload_file():
    """Single file is uploaded to correct GCS path."""
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    upload_file(mock_bucket, Path("/tmp/test.pdf"), "CO273_534/test.pdf")

    mock_bucket.blob.assert_called_once_with("CO273_534/test.pdf")
    mock_blob.upload_from_filename.assert_called_once_with(str(Path("/tmp/test.pdf")))


def test_upload_volume(tmp_path):
    """All files in volume directory are uploaded with correct prefixes."""
    # Create mock volume structure
    pages_dir = tmp_path / "CO273_534" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "page_0001.jpg").write_bytes(b"fake")
    (pages_dir / "page_0002.jpg").write_bytes(b"fake")
    (tmp_path / "CO273_534" / "manifest.json").write_text("{}")
    (tmp_path / "CO273_534" / "CO273_534_full.pdf").write_bytes(b"fake pdf")

    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    mock_bucket.blob.return_value = mock_blob

    count = upload_volume(mock_bucket, tmp_path / "CO273_534", "CO273_534")
    assert count == 4  # 2 pages + manifest + full pdf
