# Phase 1: Scraper + GCS -- Key Context

**Last Updated: 2026-02-28 (session 5 -- dviViewer API breakthrough)**

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
| `src/scraper.py` | Old scraper (pdfGenerator -- dead end) | Needs rewrite |
| `src/auth.py` | NUS SSO auth, polls for JSESSIONID11_omni | Committed |
| `scripts/run.py` | CLI (has debug cmd_test from session 5) | Uncommitted changes |
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

- Python: `/c/Users/yjkim/AppData/Local/Microsoft/WindowsApps/python3.exe` (3.14.3)
- Venv: `source .venv/Scripts/activate`
- Korean Windows (cp949) -- no em dashes in print, use `encoding='utf-8'` for file I/O
- Git remote: https://github.com/kimyungju/aihistory.git
- Test command: `python -m pytest tests/ --ignore=tests/test_gcs_upload.py -v`

---

## Next Steps

1. Rewrite `src/scraper.py` to use dviViewer API (fetch JSON -> download page images -> extract OCR text)
2. Update `src/config.py` with new endpoint constants
3. Update `scripts/run.py` to use new scraper
4. Update tests for new approach
5. Delete old pdfs/CO273_534/ disclaimers, download all 3 volumes
6. Build + upload to GCS
