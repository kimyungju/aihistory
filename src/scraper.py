# src/scraper.py
"""
Download documents from Gale Primary Sources using the dviViewer API.

The dviViewer/getDviDocument endpoint returns JSON with:
- Page image tokens (recordId) for downloading page images
- OCR text per page (pageOcrTextMap)
- PDF record IDs for bulk PDF download

This replaces the old pdfGenerator/html approach which always returned disclaimers.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote

import requests
from bs4 import BeautifulSoup

from src.config import (
    GALE_BASE_URL,
    DVI_DOCUMENT_URL,
    IMAGE_DOWNLOAD_URL,
    PDF_DOWNLOAD_URL,
    TEXT_DOWNLOAD_URL,
    GALE_PROD_ID,
    GALE_PRODUCT_CODE,
    GALE_USER_GROUP,
    DOWNLOAD_DELAY,
    MAX_RETRIES,
    MAX_WORKERS,
    PDF_DOWNLOAD_TIMEOUT,
    REQUEST_TIMEOUT,
    SEARCH_RESULTS_PER_PAGE,
)


def sanitize_doc_id(doc_id: str) -> str:
    """Convert 'GALE|LBYSJJ528199212' to 'GALE_LBYSJJ528199212' for filenames."""
    return doc_id.replace("|", "_")


def extract_csrf_token(session: requests.Session, url: str) -> str:
    """Fetch a Gale page and extract the CSRF token.

    Looks first for a hidden <input name="_csrf"> field in the HTML,
    then falls back to the XSRF-TOKEN cookie.

    Raises ValueError if neither source provides a token.
    """
    response = session.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Try hidden input first
    csrf_input = soup.find("input", {"name": "_csrf"})
    if csrf_input and csrf_input.get("value"):
        return csrf_input["value"]

    # Fallback to XSRF-TOKEN cookie
    cookie_token = session.cookies.get("XSRF-TOKEN")
    if cookie_token:
        return cookie_token

    raise ValueError("CSRF token not found in HTML or cookies")


def _extract_doc_ids_from_html(html: str) -> list[str]:
    """Parse search results HTML and return decoded docIds."""
    soup = BeautifulSoup(html, "html.parser")
    doc_ids = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.search(r"docId=(GALE%7C[^&]+)", href)
        if match:
            doc_id = unquote(match.group(1))
            if doc_id not in doc_ids:
                doc_ids.append(doc_id)

    return doc_ids


def _extract_total_results(html: str) -> int:
    """Extract total result count from pagination text like 'Results 1 - 25 of 50'."""
    match = re.search(r"of\s+(\d+)", html)
    if match:
        return int(match.group(1))
    return 0


def discover_doc_ids(session: requests.Session, search_url: str) -> list[str]:
    """Paginate Gale search results and extract all docIds from document links."""
    all_doc_ids: list[str] = []
    current_url = search_url

    while True:
        response = session.get(current_url)
        html = response.text

        page_doc_ids = _extract_doc_ids_from_html(html)
        all_doc_ids.extend(
            did for did in page_doc_ids if did not in all_doc_ids
        )

        total = _extract_total_results(html)
        if total == 0 or len(all_doc_ids) >= total:
            break

        if "page=" in current_url:
            current_page = int(re.search(r"page=(\d+)", current_url).group(1))
            current_url = re.sub(
                r"page=\d+", f"page={current_page + 1}", current_url
            )
        else:
            sep = "&" if "?" in current_url else "?"
            current_url = f"{current_url}{sep}page=2"

    return all_doc_ids


# ---------------------------------------------------------------------------
# dviViewer API-based download (new approach)
# ---------------------------------------------------------------------------


def get_document_data(session: requests.Session, doc_id: str) -> dict:
    """Call dviViewer/getDviDocument API to get document metadata and page tokens.

    Returns parsed JSON with:
    - imageList: list of pages with recordId tokens for image download
    - originalDocument.pageOcrTextMap: OCR text per page
    - originalDocument.formatPdfRecordIdsForDviDownload: for BulkPDF
    """
    params = {
        "docId": doc_id,
        "ct": "dvi",
        "tabID": "Manuscripts",
        "prodId": GALE_PROD_ID,
        "userGroupName": GALE_USER_GROUP,
    }
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    response = session.get(
        DVI_DOCUMENT_URL, params=params, headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _download_single_page(
    session: requests.Session,
    page_info: dict,
    output_dir: Path,
) -> bool:
    """Download a single page image. Returns True on success or skip."""
    page_num = int(page_info["pageNumber"])
    record_id = page_info["recordId"]
    filename = f"page_{page_num:04d}.jpg"
    filepath = output_dir / filename

    # Skip if already downloaded
    if filepath.exists() and filepath.stat().st_size > 1000:
        return True

    try:
        url = f"{IMAGE_DOWNLOAD_URL}/{record_id}"
        params = {"legacy": "no", "scale": "1.0", "format": "jpeg"}
        response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        if len(response.content) < 1000:
            print(f"    Warning: page {page_num} too small ({len(response.content)} bytes)")
            return False

        with open(filepath, "wb") as f:
            f.write(response.content)
        return True

    except Exception as e:
        print(f"    Failed page {page_num}: {e}")
        return False


def download_document_pages(
    session: requests.Session,
    doc_data: dict,
    output_dir: Path,
    max_workers: int | None = None,
) -> int:
    """Download all page images concurrently using recordId tokens.

    Uses ThreadPoolExecutor for parallel downloads. requests.Session is
    thread-safe so the same session is shared across workers.

    Returns the number of pages successfully downloaded or skipped.
    """
    if max_workers is None:
        max_workers = MAX_WORKERS

    image_list = doc_data.get("imageList", [])
    if not image_list:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_download_single_page, session, page_info, output_dir)
            for page_info in image_list
        ]
        results = [f.result() for f in futures]

    return sum(1 for r in results if r)


def save_ocr_text(doc_data: dict, output_dir: Path, doc_id: str) -> int:
    """Extract OCR text from dviViewer JSON and save as a text file.

    The pageOcrTextMap in the JSON response contains OCR text per page.
    Saves combined text as {sanitized_doc_id}.txt with page markers.

    Returns number of pages with OCR text.
    """
    original_doc = doc_data.get("originalDocument", {})
    ocr_map = original_doc.get("pageOcrTextMap", {})

    if not ocr_map:
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_id = sanitize_doc_id(doc_id)

    # Combine all pages with page markers
    combined = []
    for page_num in sorted(ocr_map.keys(), key=lambda x: int(x)):
        text = ocr_map[page_num]
        if text.strip():
            combined.append(f"--- Page {page_num} ---\n{text}")

    if not combined:
        return 0

    combined_path = output_dir / f"{safe_id}.txt"
    with open(combined_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(combined))

    return len(combined)


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def load_manifest(path: Path) -> dict:
    """Load download manifest from JSON, or return empty manifest."""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "volume_id": "",
        "total_documents": 0,
        "doc_ids": [],
        "downloaded_docs": [],
        "failed_docs": [],
    }


def save_manifest(path: Path, data: dict) -> None:
    """Save download manifest to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Volume orchestration
# ---------------------------------------------------------------------------


def scrape_volume(
    session: requests.Session,
    volume_id: str,
    doc_ids: list[str],
    output_dir: Path,
    resume: bool = True,
    max_workers: int | None = None,
) -> dict:
    """Download all documents for a volume using the dviViewer API.

    For each document:
    1. Call dviViewer/getDviDocument to get JSON with page tokens + OCR
    2. Download page images using recordId tokens
    3. Extract OCR text from the JSON response
    4. Track progress in manifest for resume support

    Saves images to output_dir/{volume_id}/images/{safe_doc_id}/page_NNNN.jpg
    Saves text to output_dir/{volume_id}/text/{safe_doc_id}.txt
    """
    volume_dir = output_dir / volume_id
    images_dir = volume_dir / "images"
    text_dir = volume_dir / "text"
    manifest_path = volume_dir / "manifest.json"

    # Load or create manifest
    if resume:
        manifest = load_manifest(manifest_path)
    else:
        manifest = load_manifest(Path("/nonexistent"))

    manifest["volume_id"] = volume_id

    if resume and manifest["doc_ids"]:
        doc_ids = manifest["doc_ids"]
        print(f"[{volume_id}] Resuming with {len(doc_ids)} known documents")
    else:
        manifest["doc_ids"] = doc_ids

    manifest["total_documents"] = len(doc_ids)
    save_manifest(manifest_path, manifest)
    print(f"[{volume_id}] {len(doc_ids)} documents to process")

    downloaded_docs = set(manifest.get("downloaded_docs", []))

    for i, doc_id in enumerate(doc_ids, 1):
        if doc_id in downloaded_docs:
            continue

        safe_id = sanitize_doc_id(doc_id)
        print(f"  [{volume_id}] {i}/{len(doc_ids)}: {doc_id}")

        try:
            # Step 1: Get document data from dviViewer API
            doc_data = get_document_data(session, doc_id)
            image_list = doc_data.get("imageList", [])
            print(f"    {len(image_list)} pages found")

            # Step 2: Download page images
            doc_images_dir = images_dir / safe_id
            pages = download_document_pages(session, doc_data, doc_images_dir, max_workers=max_workers)
            print(f"    {pages}/{len(image_list)} page images downloaded")

            # Step 3: Extract OCR text
            ocr_pages = save_ocr_text(doc_data, text_dir, doc_id)
            if ocr_pages:
                print(f"    {ocr_pages} pages of OCR text saved")

            # Mark as complete
            manifest.setdefault("downloaded_docs", []).append(doc_id)
            downloaded_docs.add(doc_id)

        except Exception as e:
            print(f"    FAILED: {e}")
            manifest.setdefault("failed_docs", [])
            if doc_id not in manifest["failed_docs"]:
                manifest["failed_docs"].append(doc_id)

        save_manifest(manifest_path, manifest)
        time.sleep(DOWNLOAD_DELAY)

    done = len(manifest.get("downloaded_docs", []))
    failed = len(manifest.get("failed_docs", []))
    print(f"[{volume_id}] Done: {done} downloaded, {failed} failed")
    return manifest


# ---------------------------------------------------------------------------
# Legacy functions (kept for backward compatibility with tests)
# ---------------------------------------------------------------------------


def _visit_document_page(session: requests.Session, doc_id: str) -> None:
    """Visit the document viewer page to establish server-side session context."""
    encoded_id = doc_id.replace("|", "%7C")
    url = (
        f"{GALE_BASE_URL}/ps/retrieve.do"
        f"?tabID=Manuscripts&prodId={GALE_PROD_ID}"
        f"&userGroupName={GALE_USER_GROUP}"
        f"&docId={encoded_id}"
    )
    response = session.get(url, headers={"Accept": "text/html"})
    if response.status_code != 200:
        print(f"  Warning: visiting doc page returned {response.status_code}")


def download_document_pdf(
    session: requests.Session,
    doc_id: str,
    csrf_token: str,
    output_dir: Path,
) -> bool:
    """Download a document as PDF via Gale's PDF generator endpoint.

    NOTE: This endpoint always returns disclaimers. Use get_document_data()
    + download_document_pages() instead. Kept for backward compatibility.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "prodId": GALE_PROD_ID,
        "userGroupName": GALE_USER_GROUP,
        "downloadAction": "DO_DOWNLOAD_DOCUMENT",
        "retrieveFormat": "PDF",
        "deliveryType": "DownLoad",
        "disclaimerDisabled": "false",
        "docId": doc_id,
        "_csrf": csrf_token,
    }

    encoded_id = doc_id.replace("|", "%7C")
    headers = {
        "Referer": (
            f"{GALE_BASE_URL}/ps/retrieve.do"
            f"?tabID=Manuscripts&prodId={GALE_PROD_ID}"
            f"&userGroupName={GALE_USER_GROUP}"
            f"&docId={encoded_id}"
        ),
        "Accept": "application/pdf",
    }

    try:
        response = session.post(
            PDF_DOWNLOAD_URL, data=data, headers=headers,
            timeout=PDF_DOWNLOAD_TIMEOUT,
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "pdf" not in content_type and response.content[:5] != b"%PDF-":
            print(f"  Warning: unexpected Content-Type for {doc_id}: {content_type}")
            return False

        if len(response.content) < 5000:
            print(
                f"  Warning: PDF too small for {doc_id} "
                f"({len(response.content)} bytes) - likely a disclaimer"
            )
            return False

        filename = f"{sanitize_doc_id(doc_id)}.pdf"
        filepath = output_dir / filename
        with open(filepath, "wb") as f:
            f.write(response.content)

        size_kb = len(response.content) / 1024
        print(f"  Saved {filename} ({size_kb:.1f} KB)")
        return True

    except Exception as e:
        print(f"  Failed to download PDF for {doc_id}: {e}")
        return False


def download_document_text(
    session: requests.Session,
    doc_id: str,
    csrf_token: str,
    output_dir: Path,
) -> bool:
    """Download OCR text via Gale's text extraction endpoint.

    NOTE: This endpoint returns empty. Use save_ocr_text() with dviViewer
    JSON response instead. Kept for backward compatibility.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "prodId": GALE_PROD_ID,
        "userGroupName": GALE_USER_GROUP,
        "downloadAction": "DO_DOWNLOAD_DOCUMENT",
        "retrieveFormat": "PLAIN_TEXT",
        "deliveryType": "DownLoad",
        "productCode": GALE_PRODUCT_CODE,
        "accessLevel": "FULLTEXT",
        "docId": doc_id,
        "_csrf": csrf_token,
    }

    encoded_id = doc_id.replace("|", "%7C")
    headers = {
        "Referer": (
            f"{GALE_BASE_URL}/ps/retrieve.do"
            f"?tabID=Manuscripts&prodId={GALE_PROD_ID}"
            f"&userGroupName={GALE_USER_GROUP}"
            f"&docId={encoded_id}"
        ),
        "Accept": "text/plain, text/html, */*",
    }

    try:
        response = session.post(
            TEXT_DOWNLOAD_URL, data=data, headers=headers,
        )
        response.raise_for_status()

        text_content = response.text.strip()
        if not text_content:
            print(f"  Warning: empty text for {doc_id}")
            return False

        filename = f"{sanitize_doc_id(doc_id)}.txt"
        filepath = output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(text_content)

        print(f"  Saved {filename} ({len(text_content)} chars)")
        return True

    except Exception as e:
        print(f"  Failed to download text for {doc_id}: {e}")
        return False


def download_page_image(
    session: requests.Session,
    encoded_id: str,
    output_dir: Path,
    page_num: int,
) -> bool:
    """Download a single page image from Gale's image server.

    NOTE: Prefer download_document_pages() which handles all pages from
    dviViewer JSON. Kept for backward compatibility.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    url = f"{IMAGE_DOWNLOAD_URL}/{encoded_id}"
    params = {
        "legacy": "no",
        "scale": "1.0",
        "format": "jpeg",
    }

    try:
        response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        if len(response.content) < 1000:
            print(f"  Warning: page image {page_num} is only {len(response.content)} bytes")
            return False

        filename = f"page_{page_num:04d}.jpg"
        filepath = output_dir / filename
        with open(filepath, "wb") as f:
            f.write(response.content)

        size_kb = len(response.content) / 1024
        print(f"  Saved {filename} ({size_kb:.1f} KB)")
        return True

    except Exception as e:
        print(f"  Failed to download page image {page_num}: {e}")
        return False
