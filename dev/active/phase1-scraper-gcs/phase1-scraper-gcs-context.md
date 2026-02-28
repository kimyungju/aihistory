# Phase 1: Scraper + GCS -- Key Context

**Last Updated: 2026-02-28 (session 6 -- environment setup + scraper rewrite DONE)**

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
| `src/config.py` | `load_volumes()` reads JSON, endpoints | Committed |
| `src/scraper.py` | dviViewer API scraper (rewritten session 6) | Committed |
| `src/auth.py` | NUS SSO auth, polls for JSESSIONID11_omni | Committed |
| `scripts/run.py` | CLI with scrape/build/upload/test commands | Committed |
| `src/pdf_builder.py` | pypdf merge | Committed |
| `src/gcs_upload.py` | GCS upload | Committed |
| `pdfs/_test/documents/dvi_response_requests.json` | Sample 311KB API response | Local only |

---

## Dead Ends (Confirmed in Session 5)

1. **POST /ps/pdfGenerator/html** -- always returns disclaimer PDFs (2,479 bytes)
2. **POST /ps/htmlGenerator/forText** -- returns empty
3. **retrieve.do page rendering** -- server returns `<head>` but NO `<body>`, JSP template crashes silently
4. **Selenium page interaction** -- 0 buttons, 0 forms, 0 interactive elements (blank page)
5. **Most /ps/ API endpoints** -- eToc.do, documentDetailAction.do, callistoSearch.do all return 500

---

## New Architecture (To Implement)

```
NUS SSO (Selenium) -> extract cookies -> requests.Session
    -> GET /ps/dviViewer/getDviDocument?docId=...  (JSON with page tokens)
    -> for each page in imageList:
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

## Session 6 Changes (This Session)

1. **Python environment fixed**: Installed Python 3.14.3 from python.org, removed broken Microsoft Store version
2. **PATH issues resolved**: Added Python to Git Bash `~/.bashrc` and Cursor `settings.json` (`terminal.integrated.env.windows`)
3. **Venv created**: `.venv` with all project dependencies installed
4. **CLAUDE.md updated**: Added PowerShell activation command for Cursor terminal
5. **Scraper rewrite already done** (prior sessions): `src/scraper.py` has `get_document_data()`, `download_document_pages()`, `save_ocr_text()`, `scrape_volume()`

## Next Steps

1. **Test the scraper**: `python -m scripts.run test` (downloads 3 pages from one doc via NUS SSO)
2. If test passes, run full scrape: `python -m scripts.run scrape --resume`
3. Build PDFs: `python -m scripts.run build`
4. Upload to GCS: `python -m scripts.run upload`
5. Get Gemini API key for Phase 2 OCR
