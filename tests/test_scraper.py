# tests/test_scraper.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from src.scraper import (
    sanitize_doc_id,
    extract_csrf_token,
    discover_doc_ids,
    download_document_pdf,
    download_document_text,
    load_manifest,
    save_manifest,
)


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

SAMPLE_SEARCH_HTML = '''
<html><body>
<input type="hidden" name="_csrf" value="test-csrf-token">
<div class="search-results-list">
  <div class="resultItem">
    <a href="/ps/retrieve.do?tabID=Manuscripts&amp;resultListType=RESULT_LIST&amp;docId=GALE%7CLBYSJJ528199212&amp;prodId=SPOC">Document 1</a>
  </div>
  <div class="resultItem">
    <a href="/ps/retrieve.do?tabID=Manuscripts&amp;resultListType=RESULT_LIST&amp;docId=GALE%7CLBYSJJ528199213&amp;prodId=SPOC">Document 2</a>
  </div>
</div>
<div class="pagination">
  <span class="resultCount">Results 1 - 2 of 3</span>
</div>
</body></html>
'''

SAMPLE_SEARCH_HTML_PAGE2 = '''
<html><body>
<input type="hidden" name="_csrf" value="test-csrf-token">
<div class="search-results-list">
  <div class="resultItem">
    <a href="/ps/retrieve.do?tabID=Manuscripts&amp;resultListType=RESULT_LIST&amp;docId=GALE%7CLBYSJJ528199214&amp;prodId=SPOC">Document 3</a>
  </div>
</div>
<div class="pagination">
  <span class="resultCount">Results 3 - 3 of 3</span>
</div>
</body></html>
'''

SAMPLE_HTML_NO_CSRF = '''
<html><body>
<div class="search-results-list">
  <div class="resultItem">
    <a href="/ps/retrieve.do?docId=GALE%7CLBYSJJ528199212">Document 1</a>
  </div>
</div>
</body></html>
'''

SAMPLE_SMALL_SEARCH_HTML = '''
<html><body>
<input type="hidden" name="_csrf" value="small-csrf">
<div class="search-results-list">
  <div class="resultItem">
    <a href="/ps/retrieve.do?docId=GALE%7CABC123&amp;prodId=SPOC">Doc A</a>
  </div>
  <div class="resultItem">
    <a href="/ps/retrieve.do?docId=GALE%7CDEF456&amp;prodId=SPOC">Doc B</a>
  </div>
</div>
<div class="pagination">
  <span class="resultCount">Results 1 - 2 of 2</span>
</div>
</body></html>
'''


# ---------------------------------------------------------------------------
# 1. test_sanitize_doc_id
# ---------------------------------------------------------------------------

def test_sanitize_doc_id():
    """Pipe character is replaced with underscore for safe filenames."""
    assert sanitize_doc_id("GALE|LBYSJJ528199212") == "GALE_LBYSJJ528199212"
    assert sanitize_doc_id("GALE|ABC") == "GALE_ABC"
    # No pipe — unchanged
    assert sanitize_doc_id("NOPIPE") == "NOPIPE"


# ---------------------------------------------------------------------------
# 2. test_extract_csrf_token_from_html
# ---------------------------------------------------------------------------

def test_extract_csrf_token_from_html():
    """CSRF token is extracted from a hidden _csrf input field."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = SAMPLE_SEARCH_HTML
    session.get.return_value = response

    token = extract_csrf_token(session, "https://example.com/search")
    assert token == "test-csrf-token"


# ---------------------------------------------------------------------------
# 3. test_extract_csrf_token_from_cookie
# ---------------------------------------------------------------------------

def test_extract_csrf_token_from_cookie():
    """Falls back to XSRF-TOKEN cookie when no hidden input is present."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = SAMPLE_HTML_NO_CSRF  # no hidden _csrf field

    # Simulate XSRF-TOKEN cookie
    cookie = MagicMock()
    cookie.value = "cookie-csrf-value"
    jar = {
        "XSRF-TOKEN": "cookie-csrf-value",
    }
    session.cookies.get.side_effect = lambda name, default=None: jar.get(name, default)
    session.get.return_value = response

    token = extract_csrf_token(session, "https://example.com/search")
    assert token == "cookie-csrf-value"


# ---------------------------------------------------------------------------
# 4. test_extract_csrf_token_missing
# ---------------------------------------------------------------------------

def test_extract_csrf_token_missing():
    """Raises ValueError when neither hidden input nor cookie provides CSRF."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = SAMPLE_HTML_NO_CSRF  # no hidden _csrf field

    session.cookies.get.return_value = None
    session.get.return_value = response

    with pytest.raises(ValueError, match="CSRF"):
        extract_csrf_token(session, "https://example.com/search")


# ---------------------------------------------------------------------------
# 5. test_discover_doc_ids_single_page
# ---------------------------------------------------------------------------

def test_discover_doc_ids_single_page():
    """Extracts all docIds from a single page of search results."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = SAMPLE_SMALL_SEARCH_HTML
    session.get.return_value = response

    doc_ids = discover_doc_ids(session, "https://example.com/search?page=1")
    assert "GALE|ABC123" in doc_ids
    assert "GALE|DEF456" in doc_ids
    assert len(doc_ids) == 2


# ---------------------------------------------------------------------------
# 6. test_discover_doc_ids_pagination
# ---------------------------------------------------------------------------

def test_discover_doc_ids_pagination():
    """Follows pagination to collect docIds across multiple pages."""
    session = MagicMock()
    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.text = SAMPLE_SEARCH_HTML  # 2 docs, total 50

    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.text = SAMPLE_SEARCH_HTML_PAGE2  # 1 doc, page 2

    # First call returns page 1, subsequent calls return page 2
    session.get.side_effect = [resp1, resp2]

    doc_ids = discover_doc_ids(session, "https://example.com/search?page=1")
    assert "GALE|LBYSJJ528199212" in doc_ids
    assert "GALE|LBYSJJ528199213" in doc_ids
    assert "GALE|LBYSJJ528199214" in doc_ids
    assert len(doc_ids) >= 3


# ---------------------------------------------------------------------------
# 7. test_download_document_pdf_success
# ---------------------------------------------------------------------------

def test_download_document_pdf_success(tmp_path):
    """Successful PDF download saves file and returns True."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    # Must be >5000 bytes to pass disclaimer size check
    response.content = b"%PDF-1.4 " + b"x" * 6000
    response.headers = {"Content-Type": "application/pdf"}
    response.ok = True
    session.post.return_value = response

    result = download_document_pdf(
        session, "GALE|LBYSJJ528199212", "csrf-tok", tmp_path
    )
    assert result is True
    saved = tmp_path / "GALE_LBYSJJ528199212.pdf"
    assert saved.exists()

    # Verify essential fields in POST data
    call_kwargs = session.post.call_args
    post_data = call_kwargs.kwargs.get("data", {})
    assert post_data["docId"] == "GALE|LBYSJJ528199212"
    assert post_data["retrieveFormat"] == "PDF"
    assert post_data["_csrf"] == "csrf-tok"


# ---------------------------------------------------------------------------
# 8. test_download_document_pdf_failure
# ---------------------------------------------------------------------------

def test_download_document_pdf_failure(tmp_path):
    """Failed PDF download returns False."""
    session = MagicMock()
    session.post.side_effect = Exception("Connection error")

    result = download_document_pdf(
        session, "GALE|LBYSJJ528199212", "csrf-tok", tmp_path
    )
    assert result is False


# ---------------------------------------------------------------------------
# 8b. test_download_document_pdf_rejects_disclaimer
# ---------------------------------------------------------------------------

def test_download_document_pdf_rejects_disclaimer(tmp_path):
    """Small PDF (<5KB) is rejected as likely disclaimer."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"%PDF-1.4 small disclaimer"  # ~25 bytes, way under 5KB
    response.headers = {"Content-Type": "application/pdf"}
    response.ok = True
    session.post.return_value = response

    result = download_document_pdf(
        session, "GALE|LBYSJJ528199212", "csrf-tok", tmp_path
    )
    assert result is False
    # Should NOT save the disclaimer file
    saved = tmp_path / "GALE_LBYSJJ528199212.pdf"
    assert not saved.exists()


# ---------------------------------------------------------------------------
# 9. test_download_document_text_success
# ---------------------------------------------------------------------------

def test_download_document_text_success(tmp_path):
    """Successful text download saves .txt file and returns True."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "This is the OCR text content of the document."
    response.ok = True
    session.post.return_value = response

    result = download_document_text(
        session, "GALE|LBYSJJ528199212", "csrf-tok", tmp_path
    )
    assert result is True
    saved = tmp_path / "GALE_LBYSJJ528199212.txt"
    assert saved.exists()
    assert "OCR text content" in saved.read_text()


# ---------------------------------------------------------------------------
# 10. test_manifest_roundtrip
# ---------------------------------------------------------------------------

def test_manifest_roundtrip(tmp_path):
    """Manifest saves and loads with the new schema."""
    manifest_path = tmp_path / "manifest.json"
    data = {
        "volume_id": "CO273_534",
        "total_documents": 42,
        "doc_ids": ["GALE|ABC", "GALE|DEF"],
        "downloaded_pdfs": ["GALE|ABC"],
        "downloaded_texts": ["GALE|ABC"],
        "failed_pdfs": [],
        "failed_texts": ["GALE|DEF"],
    }
    save_manifest(manifest_path, data)
    loaded = load_manifest(manifest_path)
    assert loaded == data

    # Loading non-existent path returns empty manifest with correct keys
    empty = load_manifest(tmp_path / "nonexistent.json")
    assert "volume_id" in empty
    assert "doc_ids" in empty
    assert "downloaded_pdfs" in empty
    assert "downloaded_texts" in empty
    assert "failed_pdfs" in empty
    assert "failed_texts" in empty
    assert empty["total_documents"] == 0
