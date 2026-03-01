# Phase 1: Scraper + GCS -- Key Context

**Last Updated: 2026-03-01 (session 7 -- concurrent downloads plan written)**

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

## Session 7: Concurrent Downloads Plan (2026-03-01)

### Problem
Sequential page downloads take ~60 minutes for 2,738 pages:
- 0.3s sleep per page = 14 min of sleeping
- ~1s network per page = 46 min of I/O
- 1.5s between 52 documents = 78s

### Solution: Plan Written
**Plan file: `docs/plans/2026-03-01-concurrent-downloads.md`**

5 tasks:
1. Add `MAX_WORKERS=5` to config, reduce `DOWNLOAD_DELAY` from 1.5s to 0.5s
2. Extract `_download_single_page()` helper from `download_document_pages()`
3. Rewrite `download_document_pages()` with `ThreadPoolExecutor(max_workers=5)`
4. Remove per-page `time.sleep(0.3)` (concurrency provides natural throttling)
5. Add `--workers` CLI flag to `scripts/run.py`

Expected speedup: ~60 min -> ~10 min (6x faster)

### User chose: Subagent-driven execution (multi-agent team)
The plan has NOT been implemented yet. User requested multi-agent team execution.

### Key design decisions
- `requests.Session` is thread-safe -- safe to share across ThreadPoolExecutor workers
- `_download_single_page()` returns bool (True=success/skip, False=fail) -- composable with futures
- `max_workers` parameter defaults to `MAX_WORKERS` from config but can be overridden via CLI `--workers`
- No async rewrite needed -- ThreadPoolExecutor is sufficient for I/O-bound downloads

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
| CO273_534 | 26 | Downloaded disclaimers only (delete and retry) |
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

1. **Implement concurrent downloads**: Execute `docs/plans/2026-03-01-concurrent-downloads.md` (5 tasks, multi-agent team)
2. **Test the scraper**: `python -m scripts.run test` (downloads 3 pages from one doc via NUS SSO)
3. If test passes, run full scrape: `python -m scripts.run scrape --resume --workers 5`
4. Build PDFs: `python -m scripts.run build`
5. Upload to GCS: `python -m scripts.run upload`
6. Get Gemini API key for Phase 2 OCR
