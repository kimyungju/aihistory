# Fix Download & Unblock Pipeline Implementation Plan

**Status**: COMPLETE. dviViewer API approach is the production path.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the Gale document download (disclaimers → real PDFs) by capturing the JSESSIONID11_omni cookie, clean up form data, add download validation, and add direct image download as an alternative path.

**Architecture:** The root cause of disclaimer-only PDFs is the missing `JSESSIONID11_omni` session cookie — Gale's application cookie distinct from the EZProxy cookies. Fix auth.py to wait for and capture this cookie. Also add `download_page_image()` as an alternative download path that fetches page images directly from Gale's image server (`luna-gale-com`), which feeds directly into Phase 2 OCR (skipping PDF extraction).

**Tech Stack:** Python 3.14, requests, selenium, BeautifulSoup

---

## Background

### The Problem
- `POST /ps/pdfGenerator/html` returns 2,479-byte disclaimer PDFs (not real documents)
- `POST /ps/htmlGenerator/forText` returns empty text (0 bytes)
- Auth only captures 3 EZProxy cookies: `ezproxy`, `ezproxyl`, `ezproxyn`
- Missing: `JSESSIONID11_omni` (Gale's actual session cookie)

### User-Captured Endpoints (Chrome DevTools)

**PDF Download:**
```
POST https://go-gale-com.libproxy1.nus.edu.sg/ps/pdfGenerator/html
Form: prodId=SPOC, userGroupName=nuslib, downloadAction=DO_DOWNLOAD_DOCUMENT,
      retrieveFormat=PDF, deliveryType=DownLoad, disclaimerDisabled=false,
      docId=GALE|..., _csrf=TOKEN
```

**Text Download:**
```
POST https://go-gale-com.libproxy1.nus.edu.sg/ps/htmlGenerator/forText
Form: prodId=SPOC, userGroupName=nuslib, downloadAction=DO_DOWNLOAD_DOCUMENT,
      retrieveFormat=PLAIN_TEXT, deliveryType=DownLoad, productCode=SPOC-3,
      accessLevel=FULLTEXT, docId=GALE|..., _csrf=TOKEN
```

**Image Download (NEW):**
```
GET https://luna-gale-com.libproxy1.nus.edu.sg/imgsrv/FastFetch/UBER2/{encoded_id}
    ?legacy=no&scale=1.0&format=jpeg
```

**Auth Cookies Required:**
- `ezproxy`, `ezproxyl`, `ezproxyn` (proxy)
- `JSESSIONID11_omni` (Gale session — MISSING from current capture)
- `XSRF-TOKEN` (CSRF)

---

### Task 1: Fix Auth Cookie Capture

**Files:**
- Modify: `src/auth.py:39-79`
- Test: `tests/test_auth.py`

**Step 1: Write the failing test**

Add a test that verifies `JSESSIONID11_omni` would be captured. We can't test real SSO, but we can test that `extract_cookies_from_driver` captures all cookies including ones with "JSESSIONID" in the name.

```python
# In tests/test_auth.py — add this test

def test_extract_cookies_captures_all():
    """All cookies from driver are captured, including JSESSIONID11_omni."""
    driver = MagicMock()
    driver.get_cookies.return_value = [
        {"name": "ezproxy", "value": "abc"},
        {"name": "ezproxyl", "value": "def"},
        {"name": "ezproxyn", "value": "ghi"},
        {"name": "JSESSIONID11_omni", "value": "sess123"},
        {"name": "XSRF-TOKEN", "value": "csrf456"},
    ]
    cookies = extract_cookies_from_driver(driver)
    assert "JSESSIONID11_omni" in cookies
    assert cookies["JSESSIONID11_omni"] == "sess123"
    assert len(cookies) == 5
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_auth.py::test_extract_cookies_captures_all -v`
Expected: PASS (extract_cookies_from_driver already captures all, so this confirms the function works)

**Step 3: Update authenticate_gale() to wait for JSESSIONID11_omni**

The real issue is that `authenticate_gale()` returns too early — before Gale sets its session cookie. Update it to:
1. After SSO completes, navigate to a Gale document page to trigger session cookie creation
2. Wait for `JSESSIONID11_omni` to appear in cookies
3. Capture all cookies including the new ones

```python
# In src/auth.py — replace authenticate_gale() function

def authenticate_gale() -> requests.Session:
    """
    Open browser for NUS SSO login, wait for success, return authenticated session.

    The browser is VISIBLE (not headless) so the user can complete
    NUS SSO login including any 2FA steps.
    """
    options = Options()
    # Not headless - user needs to see and interact with SSO
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=options)

    try:
        # Navigate to Gale - will redirect through NUS SSO
        print(f"Opening {GALE_BASE_URL} - please complete NUS SSO login...")
        driver.get(GALE_BASE_URL)

        # Wait for user to complete login and land on Gale
        print("Waiting for login to complete...")
        WebDriverWait(driver, 300).until(
            lambda d: "gale" in d.current_url.lower()
            and "login" not in d.current_url.lower()
            and "auth" not in d.current_url.lower()
        )

        # Navigate to a document page to establish full session cookies
        # (JSESSIONID11_omni is set when visiting document viewer)
        print("Establishing Gale session cookies...")
        doc_url = f"{GALE_BASE_URL}/ps/start.do?prodId=SPOC&userGroupName=nuslib"
        driver.get(doc_url)
        time.sleep(3)

        # Wait for session cookie to appear (up to 15 seconds)
        for _ in range(15):
            cookies = extract_cookies_from_driver(driver)
            if "JSESSIONID11_omni" in cookies:
                break
            time.sleep(1)

        cookies = extract_cookies_from_driver(driver)
        print(f"Login successful. Captured {len(cookies)} cookies.")

        # Log cookie names for debugging
        print(f"  Cookies: {', '.join(sorted(cookies.keys()))}")

        if "JSESSIONID11_omni" not in cookies:
            print("  WARNING: JSESSIONID11_omni not found - downloads may return disclaimers")

        session = create_session_with_cookies(cookies)
        return session

    finally:
        driver.quit()
```

**Step 4: Run tests to verify existing tests still pass**

Run: `python -m pytest tests/test_auth.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/auth.py tests/test_auth.py
git commit -m "fix auth: wait for JSESSIONID11_omni session cookie"
```

---

### Task 2: Clean Up PDF Download Form Data

**Files:**
- Modify: `src/scraper.py:121-169`
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test**

Add a test that checks the exact form fields sent in the POST:

```python
# In tests/test_scraper.py — add this test

def test_download_pdf_form_data(tmp_path):
    """PDF download sends exactly the correct form fields."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"%PDF-1.4 real content"
    response.headers = {"Content-Type": "application/pdf"}
    response.ok = True
    session.post.return_value = response

    download_document_pdf(session, "GALE|TEST123", "csrf-tok", tmp_path)

    # Check the form data sent
    call_args = session.post.call_args
    data = call_args.kwargs.get("data") or call_args[1].get("data") or call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs["data"]

    expected_keys = {
        "prodId", "userGroupName", "downloadAction",
        "retrieveFormat", "deliveryType", "disclaimerDisabled",
        "docId", "_csrf",
    }
    assert set(data.keys()) == expected_keys
    assert data["prodId"] == "SPOC"
    assert data["userGroupName"] == "nuslib"
    assert data["deliveryType"] == "DownLoad"
    assert data["disclaimerDisabled"] == "false"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scraper.py::test_download_pdf_form_data -v`
Expected: FAIL (our data dict has extra keys: title, asid, accessLevel, productCode)

**Step 3: Update download_document_pdf form data**

```python
# In src/scraper.py — replace the data dict in download_document_pdf (lines 134-147)

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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scraper.py::test_download_pdf_form_data -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "clean up PDF download form data to match captured endpoint"
```

---

### Task 3: Clean Up Text Download Form Data

**Files:**
- Modify: `src/scraper.py:172-212`
- Test: `tests/test_scraper.py`

**Step 1: Write the failing test**

```python
# In tests/test_scraper.py — add this test

def test_download_text_form_data(tmp_path):
    """Text download sends exactly the correct form fields."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "Some OCR text content"
    response.ok = True
    session.post.return_value = response

    download_document_text(session, "GALE|TEST123", "csrf-tok", tmp_path)

    call_args = session.post.call_args
    data = call_args.kwargs.get("data") or call_args[1].get("data") or call_args[0][1] if len(call_args[0]) > 1 else call_args.kwargs["data"]

    expected_keys = {
        "prodId", "userGroupName", "downloadAction",
        "retrieveFormat", "deliveryType", "productCode",
        "accessLevel", "docId", "_csrf",
    }
    assert set(data.keys()) == expected_keys
    assert data["prodId"] == "SPOC"
    assert data["productCode"] == "SPOC-3"
    assert data["accessLevel"] == "FULLTEXT"
    assert data["deliveryType"] == "DownLoad"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scraper.py::test_download_text_form_data -v`
Expected: FAIL (extra keys: text, fileName)

**Step 3: Update download_document_text form data**

```python
# In src/scraper.py — replace the data dict in download_document_text (lines 186-197)

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
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_scraper.py::test_download_text_form_data -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "clean up text download form data to match captured endpoint"
```

---

### Task 4: Add Download Validation

**Files:**
- Modify: `src/scraper.py:121-169`
- Test: `tests/test_scraper.py`

The current code only checks Content-Type. Add size validation to catch disclaimer PDFs (always ~2,479 bytes).

**Step 1: Write the failing test**

```python
# In tests/test_scraper.py — add this test

def test_download_pdf_rejects_disclaimer(tmp_path):
    """PDFs under 5KB are rejected as likely disclaimers."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    # Simulate a 2,479-byte disclaimer PDF
    response.content = b"%PDF-1.4 " + b"x" * 2470
    response.headers = {"Content-Type": "application/pdf"}
    response.ok = True
    session.post.return_value = response

    result = download_document_pdf(session, "GALE|TEST123", "csrf-tok", tmp_path)
    assert result is False  # Should reject small disclaimer PDFs
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scraper.py::test_download_pdf_rejects_disclaimer -v`
Expected: FAIL (currently saves any PDF regardless of size)

**Step 3: Add size validation to download_document_pdf**

```python
# In src/scraper.py — in download_document_pdf, after response.raise_for_status()
# Add this check before writing the file:

        # Reject suspiciously small PDFs (disclaimer PDFs are ~2,479 bytes)
        MIN_PDF_SIZE = 5000  # 5KB - real multi-page docs are much larger
        if len(response.content) < MIN_PDF_SIZE:
            print(f"  Warning: PDF for {doc_id} is only {len(response.content)} bytes (likely disclaimer)")
            return False
```

Full updated function:

```python
def download_document_pdf(
    session: requests.Session,
    doc_id: str,
    csrf_token: str,
    output_dir: Path,
) -> bool:
    """Download a document as PDF via Gale's PDF generator endpoint.

    POSTs to PDF_DOWNLOAD_URL with required form data.
    Saves as output_dir/{sanitized_doc_id}.pdf.
    Returns True on success, False on failure.
    Rejects PDFs under 5KB as likely disclaimers.
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

    try:
        response = session.post(
            PDF_DOWNLOAD_URL, data=data, timeout=PDF_DOWNLOAD_TIMEOUT
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "pdf" not in content_type and not response.content[:5] == b"%PDF-":
            print(f"  Warning: unexpected Content-Type for {doc_id}: {content_type}")
            return False

        # Reject suspiciously small PDFs (disclaimer PDFs are ~2,479 bytes)
        MIN_PDF_SIZE = 5000
        if len(response.content) < MIN_PDF_SIZE:
            print(f"  Warning: PDF for {doc_id} is only {len(response.content)} bytes (likely disclaimer)")
            return False

        filename = f"{sanitize_doc_id(doc_id)}.pdf"
        filepath = output_dir / filename
        with open(filepath, "wb") as f:
            f.write(response.content)

        return True

    except Exception as e:
        print(f"  Failed to download PDF for {doc_id}: {e}")
        return False
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: All PASS. Note: `test_download_document_pdf_success` uses a small fake PDF — update it to be >5KB:

```python
# Update existing test_download_document_pdf_success:
def test_download_document_pdf_success(tmp_path):
    """Successful PDF download saves file and returns True."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"%PDF-1.4 " + b"x" * 10000  # >5KB = real PDF
    response.headers = {"Content-Type": "application/pdf"}
    response.ok = True
    session.post.return_value = response

    result = download_document_pdf(
        session, "GALE|LBYSJJ528199212", "csrf-tok", tmp_path
    )
    assert result is True
    saved = tmp_path / "GALE_LBYSJJ528199212.pdf"
    assert saved.exists()
```

**Step 5: Commit**

```bash
git add src/scraper.py tests/test_scraper.py
git commit -m "add PDF size validation to reject disclaimer downloads"
```

---

### Task 5: Add Direct Page Image Download

**Files:**
- Modify: `src/config.py`
- Modify: `src/scraper.py`
- Test: `tests/test_scraper.py`

This adds the ability to download individual page images via Gale's image server. This is an alternative to PDF download that feeds directly into Phase 2 OCR.

**Step 1: Add image endpoint to config**

```python
# In src/config.py — add after TEXT_DOWNLOAD_URL (line 20):

# Gale image server (different subdomain)
IMAGE_BASE_URL = "https://luna-gale-com.libproxy1.nus.edu.sg"
IMAGE_DOWNLOAD_URL = f"{IMAGE_BASE_URL}/imgsrv/FastFetch/UBER2"
```

**Step 2: Write the failing test**

```python
# In tests/test_scraper.py — add this test and import

from src.scraper import download_page_image

def test_download_page_image_success(tmp_path):
    """Downloads a JPEG page image and saves it."""
    session = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"\xff\xd8\xff" + b"x" * 5000  # JPEG header + data
    response.headers = {"Content-Type": "image/jpeg"}
    response.ok = True
    session.get.return_value = response

    result = download_page_image(
        session, "ENCODED_ID_123", tmp_path, page_num=1
    )
    assert result is True
    saved = tmp_path / "page_0001.jpg"
    assert saved.exists()
```

**Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_scraper.py::test_download_page_image_success -v`
Expected: FAIL (function doesn't exist yet)

**Step 4: Implement download_page_image**

```python
# In src/scraper.py — add import at top:
from src.config import IMAGE_DOWNLOAD_URL

# Add new function after download_document_text:

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

        return True

    except Exception as e:
        print(f"  Failed to download page image {page_num}: {e}")
        return False
```

**Step 5: Run tests**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/config.py src/scraper.py tests/test_scraper.py
git commit -m "add direct page image download from Gale image server"
```

---

### Task 6: Manual Integration Test — Single Document

**This task requires NUS SSO login — cannot be automated in tests.**

**Step 1: Delete old disclaimer downloads**

```bash
rm -rf pdfs/CO273_534/
```

**Step 2: Test single document download**

```bash
python -m scripts.run scrape --volume CO273_534 --resume
```

After SSO login completes, watch for:
- Cookie count should be >3 (should include JSESSIONID11_omni)
- PDF sizes should be >>5KB (not 2,479 bytes)
- Text files should have content (not 0 bytes)

**Step 3: If PDFs still show disclaimers**

The fallback approach: skip PDF download entirely and use the image endpoint. This requires knowing the encoded_id per page, which may need to be extracted from the document viewer page HTML. In that case:

1. Visit each document's viewer page
2. Extract image URLs from the page HTML (look for FastFetch/UBER2 URLs)
3. Download each page image directly
4. Skip PDF download + extraction entirely

**Step 4: Commit results**

```bash
git add -A
git commit -m "test: verify real document downloads work"
```

---

### Task 7: Download All Volumes & Upload to GCS

**Depends on:** Task 6 success (real downloads, not disclaimers)

**Step 1: Download all 3 volumes**

```bash
python -m scripts.run scrape --resume
```

Expected: 52 documents across 3 volumes (26 + 20 + 6)

**Step 2: Build merged PDFs**

```bash
python -m scripts.run build
```

**Step 3: Upload to GCS**

```bash
python -m scripts.run upload
```

**Step 4: Verify in GCS**

Check that the bucket has real content (not disclaimers).

**Step 5: Commit manifest**

```bash
git add pdfs/*/manifest.json
git commit -m "add download manifests for all 3 volumes"
```

---

### Task 8: Unblock Phase 2 Task 9 — GCS Integration

**Depends on:** Task 7 (real data in GCS bucket)

**Files:**
- Modify: `src/ocr/pipeline.py`
- Modify: `scripts/run_ocr.py`
- Test: `tests/test_pipeline.py`

This wires Phase 2's OCR pipeline to read images from GCS and write OCR results back.

**Step 1: Add --local flag to CLI**

```python
# In scripts/run_ocr.py — add to ocr and all subparsers:
sp_ocr.add_argument("--local", action="store_true", help="Use local files instead of GCS")
sp_all.add_argument("--local", action="store_true", help="Use local files instead of GCS")
```

**Step 2: Add GCS read/write to pipeline**

```python
# In src/ocr/pipeline.py — add GCS download/upload functions:

def download_images_from_gcs(volume_id: str, local_dir: Path) -> None:
    """Download page images from GCS to local directory."""
    from src.gcs_upload import get_bucket
    bucket = get_bucket()
    prefix = f"{volume_id}/images/"

    local_dir.mkdir(parents=True, exist_ok=True)
    for blob in bucket.list_blobs(prefix=prefix):
        filename = blob.name.split("/")[-1]
        local_path = local_dir / filename
        if not local_path.exists():
            blob.download_to_filename(str(local_path))

def upload_ocr_to_gcs(volume_id: str, local_dir: Path) -> None:
    """Upload OCR results to GCS."""
    from src.gcs_upload import get_bucket, upload_file
    bucket = get_bucket()

    for file_path in sorted(local_dir.rglob("*")):
        if file_path.is_file():
            relative = file_path.relative_to(local_dir.parent)
            gcs_path = f"{volume_id}/{relative.as_posix()}"
            upload_file(bucket, file_path, gcs_path)
```

**Step 3: Update CLI to use GCS when --local is not set**

```python
# In scripts/run_ocr.py — update cmd_ocr:

def cmd_ocr(args):
    """Run Gemini Vision OCR on extracted page images."""
    print("=== Running Gemini Vision OCR ===")

    for volume_id in get_volume_ids(args):
        volume_dir = DOWNLOAD_DIR / volume_id

        if not getattr(args, 'local', False):
            # Download images from GCS
            print(f"[{volume_id}] Downloading images from GCS...")
            from src.ocr.pipeline import download_images_from_gcs
            download_images_from_gcs(volume_id, volume_dir / "images")

        if not (volume_dir / "images").exists():
            print(f"Skipping {volume_id}: no images/ directory")
            continue

        print(f"\n[{volume_id}] Starting OCR...")
        asyncio.run(run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id=volume_id,
            concurrency=args.concurrency,
        ))

        if not getattr(args, 'local', False):
            # Upload OCR results to GCS
            print(f"[{volume_id}] Uploading OCR results to GCS...")
            from src.ocr.pipeline import upload_ocr_to_gcs
            upload_ocr_to_gcs(volume_id, volume_dir / "ocr")

    print("\n=== OCR complete ===")
```

**Step 4: Run Phase 2 tests**

Run: `python -m pytest tests/test_pipeline.py tests/test_extract.py tests/test_ocr_manifest.py tests/test_gemini_ocr.py -v`
Expected: All 12 PASS (existing tests unaffected — they don't use GCS)

**Step 5: Commit**

```bash
git add src/ocr/pipeline.py scripts/run_ocr.py
git commit -m "add GCS integration to OCR pipeline with --local flag"
```

---

## Summary

| Task | What | Effort | Depends On |
|------|------|--------|-----------|
| 1 | Fix auth cookie capture | S | — |
| 2 | Clean up PDF form data | S | — |
| 3 | Clean up text form data | S | — |
| 4 | Add download validation | S | — |
| 5 | Add image download | M | — |
| 6 | Manual integration test | M | Tasks 1-4 |
| 7 | Download all + upload | L | Task 6 |
| 8 | Phase 2 GCS integration | M | Task 7 |

Tasks 1-5 can be done in parallel (no dependencies between them).
Task 6 requires manual NUS SSO login.
Tasks 7-8 are sequential after Task 6.
