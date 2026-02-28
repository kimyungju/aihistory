# src/scraper.py
"""
Download documents from Gale Primary Sources using authenticated requests.

Uses Gale's PDF generator and text extraction endpoints to download
entire multi-page documents in single requests. Tracks progress via
manifest.json to support resuming interrupted downloads.
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup

from src.config import (
    GALE_BASE_URL,
    PDF_DOWNLOAD_URL,
    TEXT_DOWNLOAD_URL,
    IMAGE_DOWNLOAD_URL,
    GALE_PROD_ID,
    GALE_PRODUCT_CODE,
    GALE_USER_GROUP,
    DOWNLOAD_DELAY,
    MAX_RETRIES,
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
        # Look for docId=GALE%7C... in href
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
    """Paginate Gale search results and extract all docIds from document links.

    DocIds appear in href attributes containing 'docId=GALE%7C...'.
    Detects total results from page text and follows pagination.
    """
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

        # Build next page URL: increment page parameter
        if "page=" in current_url:
            current_page = int(re.search(r"page=(\d+)", current_url).group(1))
            current_url = re.sub(
                r"page=\d+", f"page={current_page + 1}", current_url
            )
        else:
            sep = "&" if "?" in current_url else "?"
            current_url = f"{current_url}{sep}page=2"

    return all_doc_ids


def _visit_document_page(session: requests.Session, doc_id: str) -> None:
    """Visit the document viewer page to establish server-side session context.

    Gale may require the user to have 'visited' the document before allowing
    PDF download (disclaimer acceptance, session binding, etc.).
    """
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

    POSTs to PDF_DOWNLOAD_URL with form data matching browser exactly.
    Saves as output_dir/{sanitized_doc_id}.pdf.
    Returns True on success, False on failure.
    Rejects suspiciously small PDFs (<5KB) as likely disclaimers.
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

    # Set Referer to the document viewer page
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

        # Reject suspiciously small PDFs (disclaimers are ~2.5KB)
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
    """Download OCR text for a document via Gale's text extraction endpoint.

    POSTs to TEXT_DOWNLOAD_URL with form data matching browser exactly.
    Saves as output_dir/{sanitized_doc_id}.txt.
    Returns True on success, False on failure.
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

    # Set Referer to the document viewer page
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

    GETs from IMAGE_DOWNLOAD_URL/{encoded_id} with format=jpeg.
    Saves as output_dir/page_NNNN.jpg.
    Returns True on success, False on failure.
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


def load_manifest(path: Path) -> dict:
    """Load download manifest from JSON, or return empty manifest with new schema."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "volume_id": "",
        "total_documents": 0,
        "doc_ids": [],
        "downloaded_pdfs": [],
        "downloaded_texts": [],
        "failed_pdfs": [],
        "failed_texts": [],
    }


def save_manifest(path: Path, data: dict) -> None:
    """Save download manifest to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def scrape_volume(
    session: requests.Session,
    volume_id: str,
    doc_ids: list[str],
    output_dir: Path,
    resume: bool = True,
    download_text: bool = True,
) -> dict:
    """Orchestrate the full download of a Gale volume.

    Steps:
    1. Extract CSRF token from a Gale page
    2. Use provided doc_ids (from data/volumes.json)
    3. Download each document as PDF (and optionally text)
    4. Track progress in manifest, saving after each download

    Saves PDFs to output_dir/{volume_id}/documents/
    Saves text to output_dir/{volume_id}/text/
    """
    volume_dir = output_dir / volume_id
    pdf_dir = volume_dir / "documents"
    text_dir = volume_dir / "text"
    manifest_path = volume_dir / "manifest.json"

    # Load or create manifest
    if resume:
        manifest = load_manifest(manifest_path)
    else:
        manifest = load_manifest(Path("/nonexistent"))  # fresh empty

    manifest["volume_id"] = volume_id

    # Step 1: extract CSRF from any Gale page
    print(f"[{volume_id}] Extracting CSRF token...")
    csrf_url = f"{GALE_BASE_URL}/ps/start.do?prodId={GALE_PROD_ID}&userGroupName={GALE_USER_GROUP}"
    csrf_token = extract_csrf_token(session, csrf_url)

    # Step 2: use provided doc_ids (or reuse from manifest if resuming)
    if resume and manifest["doc_ids"]:
        doc_ids = manifest["doc_ids"]
        print(f"[{volume_id}] Resuming with {len(doc_ids)} known documents")
    else:
        manifest["doc_ids"] = doc_ids

    manifest["total_documents"] = len(doc_ids)
    save_manifest(manifest_path, manifest)
    print(f"[{volume_id}] Found {len(doc_ids)} documents")

    # Step 3: download each document
    downloaded_pdfs = set(manifest["downloaded_pdfs"])
    downloaded_texts = set(manifest["downloaded_texts"])

    for i, doc_id in enumerate(doc_ids, 1):
        # Visit document page to establish session context before downloading
        if doc_id not in downloaded_pdfs or (download_text and doc_id not in downloaded_texts):
            _visit_document_page(session, doc_id)
            time.sleep(1)

        # PDF download
        if doc_id not in downloaded_pdfs:
            print(f"  [{volume_id}] PDF {i}/{len(doc_ids)}: {doc_id}")
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                if download_document_pdf(session, doc_id, csrf_token, pdf_dir):
                    success = True
                    break
                if attempt < MAX_RETRIES:
                    print(f"    Retry {attempt}/{MAX_RETRIES}...")
                    time.sleep(DOWNLOAD_DELAY)

            if success:
                manifest["downloaded_pdfs"].append(doc_id)
                downloaded_pdfs.add(doc_id)
            elif doc_id not in manifest["failed_pdfs"]:
                manifest["failed_pdfs"].append(doc_id)

            save_manifest(manifest_path, manifest)
            time.sleep(DOWNLOAD_DELAY)

        # Text download
        if download_text and doc_id not in downloaded_texts:
            print(f"  [{volume_id}] Text {i}/{len(doc_ids)}: {doc_id}")
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                if download_document_text(session, doc_id, csrf_token, text_dir):
                    success = True
                    break
                if attempt < MAX_RETRIES:
                    print(f"    Retry {attempt}/{MAX_RETRIES}...")
                    time.sleep(DOWNLOAD_DELAY)

            if success:
                manifest["downloaded_texts"].append(doc_id)
                downloaded_texts.add(doc_id)
            elif doc_id not in manifest["failed_texts"]:
                manifest["failed_texts"].append(doc_id)

            save_manifest(manifest_path, manifest)
            time.sleep(DOWNLOAD_DELAY)

    pdfs = len(manifest["downloaded_pdfs"])
    texts = len(manifest["downloaded_texts"])
    fpdf = len(manifest["failed_pdfs"])
    ftxt = len(manifest["failed_texts"])
    print(f"[{volume_id}] Done: {pdfs} PDFs, {texts} texts, {fpdf} failed PDFs, {ftxt} failed texts")
    return manifest
