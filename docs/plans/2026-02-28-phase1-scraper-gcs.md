# Phase 1: Gale PDF Scraper + GCS Upload — Implementation Plan

**Status**: COMPLETE. Superseded by [dviViewer API rewrite](2026-02-28-fix-download-unblock-pipeline.md) + [concurrent downloads](2026-03-01-concurrent-downloads.md).

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python tool that authenticates to Gale Primary Sources via NUS SSO, downloads all page images for CO273/534 (1,436 pages) and CO273/550 (460 pages), assembles them into PDFs, and uploads to Google Cloud Storage.

**Architecture:** Hybrid Selenium + Requests approach. Selenium handles NUS SSO login in a visible browser, extracts session cookies, then `requests` uses those cookies to download page images from Gale's internal API. Pages are saved locally, assembled into PDFs, and uploaded to a GCS bucket. A JSON manifest tracks progress for resume support.

**Tech Stack:** Python 3.11+, Selenium, requests, pypdf, Pillow, google-cloud-storage, python-dotenv

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `src/__init__.py`
- Create: `src/config.py`

**Step 1: Initialize git repository**

Run:
```bash
cd "C:/Users/yjkim/OneDrive - National University of Singapore/NUS/Projects/aihistory"
git init
```
Expected: `Initialized empty Git repository`

**Step 2: Create pyproject.toml**

```toml
[project]
name = "aihistory"
version = "0.1.0"
description = "Colonial records scraper and RAG pipeline for CO 273 Straits Settlements"
requires-python = ">=3.11"
dependencies = [
    "selenium>=4.15.0",
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "pypdf>=3.17.0",
    "Pillow>=10.0.0",
    "google-cloud-storage>=2.14.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
]

[project.scripts]
aihistory = "scripts.run:main"
```

**Step 3: Create .gitignore**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
env/

# Environment
.env

# Downloads
pdfs/

# GCS credentials
*.json
!.env.example

# IDE
.vscode/
.idea/
```

**Step 4: Create .env.example**

```
# Google Cloud Storage
GCS_BUCKET=aihistory-co273
GCS_KEY_PATH=path/to/service-account-key.json
GCS_REGION=asia-southeast1

# Gale (filled after network inspection)
GALE_BASE_URL=https://go-gale-com.libproxy1.nus.edu.sg
```

**Step 5: Create src/__init__.py**

```python
```

(empty file)

**Step 6: Create src/config.py**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "pdfs"

# Gale settings
GALE_BASE_URL = os.getenv(
    "GALE_BASE_URL",
    "https://go-gale-com.libproxy1.nus.edu.sg",
)

# Target volumes: {volume_id: {"gale_id": str, "pages": int}}
# gale_id will be filled after inspecting the Gale viewer URLs
VOLUMES = {
    "CO273_534": {"gale_id": "", "pages": 1436},
    "CO273_550": {"gale_id": "", "pages": 460},
    "CO273_579": {"gale_id": "", "pages": 842},
}

# Scraper settings
DOWNLOAD_DELAY = 1.5  # seconds between requests
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30  # seconds

# GCS settings
GCS_BUCKET = os.getenv("GCS_BUCKET", "aihistory-co273")
GCS_KEY_PATH = os.getenv("GCS_KEY_PATH", "")
GCS_REGION = os.getenv("GCS_REGION", "asia-southeast1")
```

**Step 7: Create directories**

Run:
```bash
mkdir -p src pdfs scripts tests
```

**Step 8: Commit**

```bash
git add pyproject.toml .gitignore .env.example src/__init__.py src/config.py
git commit -m "chore: scaffold project with config, dependencies, and gitignore"
```

---

### Task 2: Authentication Module

**Files:**
- Create: `src/auth.py`
- Create: `tests/test_auth.py`

**Step 1: Write the test**

```python
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
```

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_auth.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.auth'`

**Step 3: Write the auth module**

```python
# src/auth.py
"""
NUS SSO authentication via Selenium.

Opens a visible Chrome browser for the user to complete NUS SSO login,
then extracts session cookies for use with the requests library.
"""
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from src.config import GALE_BASE_URL


def extract_cookies_from_driver(driver) -> dict[str, str]:
    """Extract cookies from Selenium WebDriver as a name→value dict."""
    selenium_cookies = driver.get_cookies()
    return {c["name"]: c["value"] for c in selenium_cookies}


def create_session_with_cookies(cookies: dict[str, str]) -> requests.Session:
    """Create a requests.Session pre-loaded with cookies and headers."""
    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    })
    return session


def authenticate_gale() -> requests.Session:
    """
    Open browser for NUS SSO login, wait for success, return authenticated session.

    The browser is VISIBLE (not headless) so the user can complete
    NUS SSO login including any 2FA steps.
    """
    options = Options()
    # Not headless — user needs to see and interact with SSO
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=options)

    try:
        # Navigate to Gale — will redirect through NUS SSO
        print(f"Opening {GALE_BASE_URL} — please complete NUS SSO login...")
        driver.get(GALE_BASE_URL)

        # Wait for user to complete login and land on Gale
        # Detected by URL containing "gale" and not "login" or "auth"
        print("Waiting for login to complete...")
        WebDriverWait(driver, 300).until(
            lambda d: "gale" in d.current_url.lower()
            and "login" not in d.current_url.lower()
            and "auth" not in d.current_url.lower()
        )

        # Give a moment for all cookies to settle
        time.sleep(2)

        cookies = extract_cookies_from_driver(driver)
        print(f"Login successful. Captured {len(cookies)} cookies.")

        session = create_session_with_cookies(cookies)
        return session

    finally:
        driver.quit()
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_auth.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add src/auth.py tests/test_auth.py
git commit -m "feat: add NUS SSO authentication module with cookie extraction"
```

---

### Task 3: API Endpoint Discovery (Manual + Code)

**Files:**
- Create: `docs/gale-api-notes.md`
- Modify: `src/config.py`

This task involves **manual investigation** using Chrome DevTools to discover Gale's internal API endpoints.

**Step 1: Document the discovery process**

Create `docs/gale-api-notes.md`:

```markdown
# Gale API Endpoint Discovery Notes

## How to Discover Endpoints

1. Open Chrome, navigate to the Gale viewer for a CO 273 document
2. Open DevTools (F12) → Network tab
3. Filter by: Images, XHR/Fetch
4. Navigate between pages in the viewer
5. Look for requests that load page images

## What to Record

For each relevant request, note:
- **URL pattern**: e.g., `https://go-gale-com.../api/image?docId=X&pageNum=Y`
- **Method**: GET/POST
- **Headers**: any required (Referer, X-CSRF-Token, etc.)
- **Query parameters**: document ID format, page numbering (0-based or 1-based)
- **Response type**: image/jpeg, image/png, application/pdf

## Discovered Endpoints

<!-- Fill in after manual inspection -->

### Page Image Endpoint
- URL: `TODO`
- Method: `TODO`
- Parameters: `TODO`
- Response: `TODO`

### Document Metadata Endpoint (if found)
- URL: `TODO`
- Method: `TODO`

### Download Endpoint (if found)
- URL: `TODO`
- Method: `TODO`

## Volume IDs

| Volume | Gale Document ID |
|--------|-----------------|
| CO273/534 | `TODO` — find by navigating to this volume |
| CO273/550 | `TODO` — find by navigating to this volume |
```

**Step 2: Perform manual inspection**

Using Chrome DevTools:
1. Log into Gale via NUS proxy
2. Open a CO 273 document in the viewer
3. Open Network tab, navigate pages, record API patterns
4. Find the Gale document IDs for CO273/534 and CO273/550

**Step 3: Update config.py with discovered values**

After discovering the endpoint pattern and document IDs, update `src/config.py`:
- Fill in `gale_id` values in `VOLUMES`
- Add endpoint URL pattern constant

**Step 4: Commit**

```bash
git add docs/gale-api-notes.md src/config.py
git commit -m "docs: add Gale API endpoint discovery notes and volume IDs"
```

---

### Task 4: Scraper Module

**Files:**
- Create: `src/scraper.py`
- Create: `tests/test_scraper.py`

**Step 1: Write the tests**

```python
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
```

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_scraper.py -v
```
Expected: FAIL — module not found

**Step 3: Write the scraper module**

```python
# src/scraper.py
"""
Download page images from Gale Primary Sources using authenticated requests.

Requires session cookies from auth.py. Tracks progress via manifest.json
to support resuming interrupted downloads.
"""
import json
import time
from pathlib import Path
import requests
from src.config import DOWNLOAD_DELAY, MAX_RETRIES, REQUEST_TIMEOUT


# NOTE: Update this after API endpoint discovery in Task 3.
# This is a placeholder pattern — replace with actual Gale endpoint.
PAGE_URL_TEMPLATE = (
    "https://go-gale-com.libproxy1.nus.edu.sg"
    "/ps/i.do?id={gale_id}&page={page_num}&action=PageImage"
)


def build_page_url(gale_id: str, page_num: int) -> str:
    """Build the URL for a specific page image."""
    return PAGE_URL_TEMPLATE.format(gale_id=gale_id, page_num=page_num)


def load_manifest(path: Path) -> dict:
    """Load download manifest from JSON, or return empty manifest."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"downloaded": [], "failed": [], "total": 0}


def save_manifest(path: Path, data: dict) -> None:
    """Save download manifest to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def download_page(
    session: requests.Session,
    gale_id: str,
    page_num: int,
    output_dir: Path,
) -> bool:
    """
    Download a single page image. Returns True on success, False on failure.
    """
    url = build_page_url(gale_id, page_num)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        # Determine file extension from content type
        content_type = response.headers.get("Content-Type", "image/jpeg")
        ext = "pdf" if "pdf" in content_type else "jpg"
        filename = f"page_{page_num:04d}.{ext}"

        filepath = output_dir / filename
        with open(filepath, "wb") as f:
            f.write(response.content)

        return True

    except Exception as e:
        print(f"  Failed to download page {page_num}: {e}")
        return False


def scrape_volume(
    session: requests.Session,
    volume_id: str,
    gale_id: str,
    total_pages: int,
    output_dir: Path,
    resume: bool = True,
) -> dict:
    """
    Download all pages for a volume. Supports resume via manifest.

    Returns the final manifest dict.
    """
    volume_dir = output_dir / volume_id
    volume_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = volume_dir / "manifest.json"

    manifest = load_manifest(manifest_path) if resume else {
        "downloaded": [], "failed": [], "total": total_pages,
    }
    manifest["total"] = total_pages

    already_downloaded = set(manifest["downloaded"])

    for page_num in range(1, total_pages + 1):
        if page_num in already_downloaded:
            continue

        print(f"  [{volume_id}] Downloading page {page_num}/{total_pages}...")

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            if download_page(session, gale_id, page_num, volume_dir / "pages"):
                success = True
                break
            print(f"    Retry {attempt}/{MAX_RETRIES}...")
            time.sleep(DOWNLOAD_DELAY)

        if success:
            manifest["downloaded"].append(page_num)
        else:
            manifest["failed"].append(page_num)

        # Save progress after each page
        save_manifest(manifest_path, manifest)
        time.sleep(DOWNLOAD_DELAY)

    downloaded = len(manifest["downloaded"])
    failed = len(manifest["failed"])
    print(f"  [{volume_id}] Done: {downloaded} downloaded, {failed} failed")
    return manifest
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_scraper.py -v
```
Expected: 5 passed

**Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "feat: add scraper module with page download and resume support"
```

---

### Task 5: PDF Builder Module

**Files:**
- Create: `src/pdf_builder.py`
- Create: `tests/test_pdf_builder.py`

**Step 1: Write the test**

```python
# tests/test_pdf_builder.py
import pytest
from pathlib import Path
from PIL import Image
from src.pdf_builder import build_pdf_from_images


def test_build_pdf_from_images(tmp_path):
    """Images are combined into a single PDF in page order."""
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()

    # Create 3 small test images
    for i in range(1, 4):
        img = Image.new("RGB", (100, 100), color=(i * 50, i * 50, i * 50))
        img.save(pages_dir / f"page_{i:04d}.jpg")

    output_pdf = tmp_path / "output.pdf"
    build_pdf_from_images(pages_dir, output_pdf)

    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0

    # Verify page count
    from pypdf import PdfReader
    reader = PdfReader(str(output_pdf))
    assert len(reader.pages) == 3
```

**Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/test_pdf_builder.py -v
```
Expected: FAIL

**Step 3: Write the PDF builder**

```python
# src/pdf_builder.py
"""
Combine downloaded page images into a single PDF per volume.
"""
from pathlib import Path
from PIL import Image


def build_pdf_from_images(pages_dir: Path, output_path: Path) -> None:
    """
    Combine all page images in a directory into a single PDF.

    Images are sorted by filename to preserve page order.
    Supports .jpg, .jpeg, .png, .tiff files.
    """
    image_extensions = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}
    image_files = sorted(
        f for f in pages_dir.iterdir()
        if f.suffix.lower() in image_extensions
    )

    if not image_files:
        print(f"No images found in {pages_dir}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert all images to RGB (required for PDF)
    images = []
    for img_path in image_files:
        img = Image.open(img_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        images.append(img)

    # Save first image as PDF, append the rest
    first_image = images[0]
    remaining = images[1:]

    first_image.save(
        str(output_path),
        "PDF",
        save_all=True,
        append_images=remaining,
        resolution=150.0,
    )

    print(f"Built PDF: {output_path} ({len(images)} pages)")
```

**Step 4: Run test to verify it passes**

Run:
```bash
python -m pytest tests/test_pdf_builder.py -v
```
Expected: 1 passed

**Step 5: Commit**

```bash
git add src/pdf_builder.py tests/test_pdf_builder.py
git commit -m "feat: add PDF builder to combine page images into per-volume PDFs"
```

---

### Task 6: GCS Upload Module

**Files:**
- Create: `src/gcs_upload.py`
- Create: `tests/test_gcs_upload.py`

**Step 1: Write the test**

```python
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
```

**Step 2: Run test to verify it fails**

Run:
```bash
python -m pytest tests/test_gcs_upload.py -v
```
Expected: FAIL

**Step 3: Write the GCS upload module**

```python
# src/gcs_upload.py
"""
Upload downloaded volumes to Google Cloud Storage.
"""
from pathlib import Path
from google.cloud import storage
from src.config import GCS_BUCKET, GCS_KEY_PATH


def get_gcs_client() -> storage.Client:
    """Create authenticated GCS client."""
    if GCS_KEY_PATH:
        return storage.Client.from_service_account_json(GCS_KEY_PATH)
    return storage.Client()


def get_bucket(client: storage.Client = None) -> storage.bucket.Bucket:
    """Get the project's GCS bucket."""
    if client is None:
        client = get_gcs_client()
    return client.bucket(GCS_BUCKET)


def upload_file(bucket, local_path: Path, gcs_path: str) -> None:
    """Upload a single file to GCS."""
    blob = bucket.blob(gcs_path)
    blob.upload_from_filename(str(local_path))


def upload_volume(bucket, volume_dir: Path, volume_id: str) -> int:
    """
    Upload all files in a volume directory to GCS.

    Uploads:
    - pages/*.jpg → {volume_id}/pages/
    - manifest.json → {volume_id}/
    - *_full.pdf → {volume_id}/

    Returns count of files uploaded.
    """
    count = 0

    for file_path in sorted(volume_dir.rglob("*")):
        if not file_path.is_file():
            continue

        # Build GCS path preserving directory structure
        relative = file_path.relative_to(volume_dir)
        gcs_path = f"{volume_id}/{relative.as_posix()}"

        print(f"  Uploading {gcs_path}...")
        upload_file(bucket, file_path, gcs_path)
        count += 1

    print(f"  [{volume_id}] Uploaded {count} files")
    return count


def upload_all_volumes(download_dir: Path) -> None:
    """Upload all downloaded volumes to GCS."""
    bucket = get_bucket()

    for volume_dir in sorted(download_dir.iterdir()):
        if not volume_dir.is_dir():
            continue

        volume_id = volume_dir.name
        print(f"Uploading volume {volume_id}...")
        upload_volume(bucket, volume_dir, volume_id)

    print("All uploads complete.")


def list_bucket_contents() -> list[str]:
    """List all objects in the bucket (for verification)."""
    bucket = get_bucket()
    return [blob.name for blob in bucket.list_blobs()]
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_gcs_upload.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add src/gcs_upload.py tests/test_gcs_upload.py
git commit -m "feat: add GCS upload module for volume files"
```

---

### Task 7: CLI Entry Point

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/run.py`

**Step 1: Create the CLI script**

```python
# scripts/__init__.py
```

(empty file)

```python
# scripts/run.py
"""
CLI entry point for aihistory scraper pipeline.

Usage:
    python -m scripts.run scrape [--resume]    # Auth + download pages
    python -m scripts.run build                 # Combine pages into PDFs
    python -m scripts.run upload                # Upload to GCS
    python -m scripts.run all [--resume]        # Full pipeline
"""
import argparse
from pathlib import Path
from src.config import VOLUMES, DOWNLOAD_DIR
from src.auth import authenticate_gale
from src.scraper import scrape_volume
from src.pdf_builder import build_pdf_from_images
from src.gcs_upload import upload_all_volumes, list_bucket_contents


def cmd_scrape(args):
    """Authenticate and download all volume pages."""
    print("=== Step 1: NUS SSO Authentication ===")
    session = authenticate_gale()

    print("\n=== Step 2: Downloading pages ===")
    for volume_id, vol_config in VOLUMES.items():
        print(f"\nStarting {volume_id} ({vol_config['pages']} pages)...")
        scrape_volume(
            session=session,
            volume_id=volume_id,
            gale_id=vol_config["gale_id"],
            total_pages=vol_config["pages"],
            output_dir=DOWNLOAD_DIR,
            resume=args.resume,
        )

    print("\n=== Scraping complete ===")


def cmd_build(args):
    """Combine downloaded page images into PDFs."""
    print("=== Building PDFs ===")
    for volume_id in VOLUMES:
        pages_dir = DOWNLOAD_DIR / volume_id / "pages"
        output_pdf = DOWNLOAD_DIR / volume_id / f"{volume_id}_full.pdf"

        if not pages_dir.exists():
            print(f"Skipping {volume_id}: no pages directory found")
            continue

        print(f"\nBuilding {volume_id}...")
        build_pdf_from_images(pages_dir, output_pdf)

    print("\n=== PDF build complete ===")


def cmd_upload(args):
    """Upload all volumes to GCS."""
    print("=== Uploading to GCS ===")
    upload_all_volumes(DOWNLOAD_DIR)

    print("\n=== Verifying uploads ===")
    contents = list_bucket_contents()
    print(f"Bucket contains {len(contents)} objects")
    for name in contents[:20]:
        print(f"  {name}")
    if len(contents) > 20:
        print(f"  ... and {len(contents) - 20} more")


def cmd_all(args):
    """Run full pipeline: scrape → build → upload."""
    cmd_scrape(args)
    cmd_build(args)
    cmd_upload(args)


def main():
    parser = argparse.ArgumentParser(description="aihistory scraper pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scrape
    sp_scrape = subparsers.add_parser("scrape", help="Auth + download pages")
    sp_scrape.add_argument("--resume", action="store_true", help="Resume interrupted download")
    sp_scrape.set_defaults(func=cmd_scrape)

    # build
    sp_build = subparsers.add_parser("build", help="Combine pages into PDFs")
    sp_build.set_defaults(func=cmd_build)

    # upload
    sp_upload = subparsers.add_parser("upload", help="Upload to GCS")
    sp_upload.set_defaults(func=cmd_upload)

    # all
    sp_all = subparsers.add_parser("all", help="Full pipeline")
    sp_all.add_argument("--resume", action="store_true", help="Resume interrupted download")
    sp_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

**Step 2: Test CLI runs without errors**

Run:
```bash
python -m scripts.run --help
```
Expected: Shows usage/help text with scrape, build, upload, all commands

**Step 3: Commit**

```bash
git add scripts/__init__.py scripts/run.py
git commit -m "feat: add CLI entry point with scrape/build/upload/all commands"
```

---

### Task 8: Install Dependencies & End-to-End Smoke Test

**Step 1: Create virtual environment and install**

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
pip install -e ".[dev]"
```

**Step 2: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: All tests pass (8 tests)

**Step 3: Verify CLI**

```bash
python -m scripts.run --help
python -m scripts.run scrape --help
```
Expected: Help text displays correctly

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore: verify all tests pass and CLI works"
```

---

### Task 9: GCP Project & Bucket Setup (Manual)

This task is done in the Google Cloud Console, not in code.

**Step 1: Create GCP project**

1. Go to https://console.cloud.google.com
2. Create new project: name `aihistory`
3. Note the project ID

**Step 2: Enable Cloud Storage API**

1. Navigate to APIs & Services → Enable APIs
2. Search "Cloud Storage" → Enable

**Step 3: Create service account**

1. IAM & Admin → Service Accounts → Create
2. Name: `aihistory-uploader`
3. Grant roles: `Storage Object Creator` + `Storage Object Viewer`
4. Create key → JSON → download
5. Save JSON key file (NOT in git repo)

**Step 4: Create bucket**

1. Cloud Storage → Create Bucket
2. Name: `aihistory-co273`
3. Region: `asia-southeast1` (Singapore)
4. Default storage class: Standard
5. Access control: Uniform

**Step 5: Configure .env**

Copy `.env.example` → `.env` and fill in:
```
GCS_BUCKET=aihistory-co273
GCS_KEY_PATH=/path/to/aihistory-service-account-key.json
```

**Step 6: Grant downstream access**

For collaborators/demo consumers, create a separate service account with `Storage Object Viewer` role. Share its key with team members who need to read from the bucket (for OCR pipeline, chatbot, etc.).

---

### Task 10: Gale API Discovery & First Real Download Test

**Step 1: Manual API inspection**

1. Log into Gale via NUS proxy in Chrome
2. Navigate to CO273/534 in the viewer
3. Open DevTools → Network tab
4. Navigate pages, examine requests
5. Document findings in `docs/gale-api-notes.md`

**Step 2: Update config with real values**

Update `src/config.py` with discovered:
- Gale document IDs
- Update `PAGE_URL_TEMPLATE` in `src/scraper.py` with real endpoint pattern

**Step 3: Test with 5 pages**

Temporarily set a small page range and run:
```bash
python -m scripts.run scrape
```
Verify 5 page images download correctly to `pdfs/CO273_534/pages/`

**Step 4: Run full download**

Once the 5-page test succeeds, run full download for all three volumes:
```bash
python -m scripts.run scrape --resume
```

**Step 5: Build PDFs and upload**

```bash
python -m scripts.run build
python -m scripts.run upload
```

**Step 6: Verify in GCS Console**

Check bucket contents in Cloud Console. Confirm:
- `CO273_534/pages/` has 1,436 images
- `CO273_550/pages/` has 460 images
- `CO273_579/pages/` has 842 images
- All three `*_full.pdf` files exist

**Step 7: Final commit**

```bash
git add src/config.py src/scraper.py docs/gale-api-notes.md
git commit -m "feat: configure real Gale API endpoints and verify download"
```

---

## Verification Checklist

- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] `python -m scripts.run scrape` — authenticates and downloads pages
- [ ] `python -m scripts.run build` — creates per-volume PDFs
- [ ] `python -m scripts.run upload` — uploads to GCS
- [ ] GCS bucket contains all page images + PDFs for all three volumes
- [ ] A non-NUS collaborator can read from the bucket using a viewer service account
