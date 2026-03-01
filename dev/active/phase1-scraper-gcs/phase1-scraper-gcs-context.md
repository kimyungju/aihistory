# Phase 1: Scraper + GCS -- Key Context

**Last Updated: 2026-03-01 (session 9 -- CO273_534 scraped, GCS upload blocked on permissions)**

---

## BREAKTHROUGH: dviViewer/getDviDocument API

The old approach (POST to `/ps/pdfGenerator/html`) is a **confirmed dead end** -- always returns 2,479-byte disclaimer PDFs regardless of cookies/headers/form data.

### The Working API

```
GET /ps/dviViewer/getDviDocument
    ?docId=GALE|LBYSJJ528199212
    &ct=dvi
    &tabID=Manuscripts
    &prodId=SPOC
    &userGroupName=nuslib
```

Returns 311KB JSON with EVERYTHING needed:

1. **`imageList`** (53 pages): each has `pageNumber`, `recordId` (encrypted URL-encoded token), `sourceRecordId` (e.g. `SPOCF0001-C00040-M3001042-00010.jpg`), dimensions
2. **`originalDocument.pdfRecordIds`** (106 entries): source record IDs for PDF generation
3. **`originalDocument.formatPdfRecordIdsForDviDownload`**: pipe-delimited string of all record IDs, ready for BulkPDF form
4. **`originalDocument.pageOcrTextMap`** (51 pages): OCR text already extracted per page!
5. **`citation`**: bibliographic info

### Download Paths

**Option A: Page Images** (proven endpoint)
```
GET {IMAGE_DOWNLOAD_URL}/{recordId}?legacy=no&scale=1.0&format=jpeg
```
Where `recordId` = URL-encoded encrypted token from `imageList[n].recordId`

**Option B: BulkPDF** (from JS analysis, untested)
```
POST /ps/callisto/BulkPDF/UBER2
Form: recordIds={formatPdfRecordIdsForDviDownload}
```

**Option C: OCR Text** -- already in JSON response (`pageOcrTextMap`), no extra request needed!

### Key Finding: Works with requests library
The dviViewer API works from both Selenium XHR and Python `requests` with session cookies. No need for Selenium for data retrieval -- only for SSO auth.

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `data/volumes.json` | All 52 docIds by volume (data-driven) | Committed |
| `src/config.py` | `load_volumes()` reads JSON, endpoints, scraper constants | Committed |
| `src/scraper.py` | dviViewer API scraper (rewritten session 6) | Committed |
| `src/auth.py` | NUS SSO auth, polls for JSESSIONID11_omni | Committed |
| `scripts/run.py` | CLI with scrape/build/upload/test commands | Committed |
| `src/pdf_builder.py` | pypdf merge | Committed |
| `src/gcs_upload.py` | GCS upload | Committed |
| `pdfs/_test/documents/dvi_response_requests.json` | Sample 311KB API response | Local only |

---

## Session 9: CO273_534 Scraped + GCS Upload Blocked (2026-03-01)

### Scraper fixes (session 8-9)
- Added retry logic to `get_document_data()`: checks empty `response.content` before `.json()`, retries MAX_RETRIES times with exponential backoff (2^attempt seconds)
- Added retry to `_download_single_page()`: retry loop around HTTP GET with backoff
- Updated `scrape_volume()`: clears `failed_docs` on resume, tracks `consecutive_failures`, aborts after 3 consecutive failures
- Commit: `4eb3bdc`

### CO273_534: COMPLETE (26/26 docs)
- First run: 15/26 succeeded, 11 failed (session expiry -- empty HTTP 200 from Gale API)
- After retry fix + `--resume`: all 26/26 downloaded successfully
- Data at: `pdfs/CO273_534/images/` (26 per-doc subdirectories), `pdfs/CO273_534/text/`
- 28/28 scraper tests passing

### GCS Upload: BLOCKED on permissions
- `.env` file created with `GCS_KEY_PATH=C:\NUS\Projects\aihistory-488807-34cea8f4bde7.json`
- Client authenticates OK (service account: `aihistory-uploader@aihistory-488807.iam.gserviceaccount.com`)
- **403 error**: service account has Storage Object Creator + Viewer roles only
- Needs **Storage Admin** or **Storage Legacy Bucket Reader** on the bucket
- **Bucket name might be wrong**: user said "I created the separate bucket" -- may not be `aihistory-co273`
- User must fix in GCP Console: Cloud Storage > Buckets > [bucket] > Permissions > Grant Access

### To unblock GCS upload:
1. User confirms bucket name (might not be `aihistory-co273`)
2. User adds Storage Admin role to service account on that bucket
3. Update `.env` `GCS_BUCKET=` if bucket name differs
4. Run: `python -m scripts.run upload`

---

## Session 7: Concurrent Downloads (2026-03-01)

Concurrent downloads were implemented in session 7-8:
- `MAX_WORKERS=5` in config, `DOWNLOAD_DELAY` reduced to 0.5s
- `_download_single_page()` helper extracted
- `ThreadPoolExecutor(max_workers=5)` in `download_document_pages()`
- `--workers` CLI flag in `scripts/run.py`

---

## Dead Ends (Confirmed in Session 5)

1. **POST /ps/pdfGenerator/html** -- always returns disclaimer PDFs (2,479 bytes)
2. **POST /ps/htmlGenerator/forText** -- returns empty
3. **retrieve.do page rendering** -- server returns `<head>` but NO `<body>`, JSP template crashes silently
4. **Selenium page interaction** -- 0 buttons, 0 forms, 0 interactive elements (blank page)
5. **Most /ps/ API endpoints** -- eToc.do, documentDetailAction.do, callistoSearch.do all return 500

---

## Architecture

```
NUS SSO (Selenium) -> extract cookies -> requests.Session
    -> GET /ps/dviViewer/getDviDocument?docId=...  (JSON with page tokens)
    -> ThreadPoolExecutor(max_workers=5):
         for each page in imageList:
           GET {IMAGE_DOWNLOAD_URL}/{recordId}  -> page_NNNN.jpg
    -> Extract OCR text from pageOcrTextMap  -> save as .txt
    -> manifest.json tracks progress per volume
```

---

## Volume Summary

| Volume | Docs | Status |
|--------|------|--------|
| CO273_534 | 26 | COMPLETE (26/26, ~1.2GB locally) |
| CO273_550 | 20 | Not started |
| CO273_579 | 6 | Not started |

---

## GCP Setup (Complete)

- Project: `aihistory-488807`
- Bucket: `aihistory-co273` in `asia-southeast1`
- Key: configured in `.env`

---

## Environment Notes

- Python 3.14.3 installed from python.org (Microsoft Store version removed)
- Python NOT on PATH in Git Bash by default; added to `~/.bashrc`
- Cursor terminal (PowerShell): Python PATH injected via `terminal.integrated.env.windows` in Cursor settings
- PowerShell profile at OneDrive Documents (Windows redirected): `C:\Users\yjkim\OneDrive - National University of Singapore\Documents\WindowsPowerShell\`
- Venv: `.venv\Scripts\Activate.ps1` (PowerShell) or `source .venv/Scripts/activate` (Git Bash)
- Venv created with Python 3.14.3, all deps installed via `pip install -e ".[dev]"`
- Korean Windows (cp949) -- no em dashes in print, use `encoding='utf-8'` for file I/O
- Git remote: https://github.com/kimyungju/aihistory.git
- Test command: `python -m pytest tests/ --ignore=tests/test_gcs_upload.py -v`

---

## Next Steps

1. **Unblock GCS upload**: User fixes bucket permissions + confirms bucket name
2. **Upload CO273_534**: `python -m scripts.run upload`
3. **Scrape remaining volumes**: `python -m scripts.run scrape --volume CO273_550` and CO273_579 (need NUS SSO)
4. **Build PDFs**: `python -m scripts.run build`
5. **Get Gemini API key** for Phase 2 OCR
