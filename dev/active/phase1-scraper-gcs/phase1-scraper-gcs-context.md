# Phase 1: Scraper + GCS — Key Context

**Last Updated: 2026-02-28 (session 3 — real download test)**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `data/volumes.json` | All 52 docIds by volume (data-driven) | ✅ Committed |
| `src/config.py` | `load_volumes()` reads from JSON | ✅ Committed |
| `src/scraper.py` | `scrape_volume()` accepts `doc_ids` list | **UNCOMMITTED** — form data fix |
| `src/auth.py` | NUS SSO auth via Selenium | **UNCOMMITTED** — em dash fix |
| `scripts/run.py` | CLI: scrape/build/upload/all | ✅ Committed |
| `src/pdf_builder.py` | pypdf merge (unchanged) | ✅ |
| `src/gcs_upload.py` | GCS upload (unchanged) | ✅ |
| `.env` | GCS_KEY_PATH configured | ✅ |

**16/16 tests passing. 52 docIds across 3 volumes.**

---

## CRITICAL: PDF Download Returns Disclaimers Only

### What Happened
The scraper ran successfully for CO273_534 (26/26 docs downloaded, 0 failures), BUT:
- **Every PDF is exactly 2,479 bytes** (identical size)
- **Every PDF contains only a 1-page disclaimer** from Cengage/Gale, NOT the actual scanned document
- **All text files are 0 bytes** (empty)

### Root Cause
The POST to `/ps/pdfGenerator/html` returns a disclaimer PDF, not the real scanned document. The real download likely uses a **different endpoint or additional parameters**.

### What We Know From Form Inspection
On the document viewer page, there are 3 download-related forms:

1. **Form 4**: `POST /ps/pdfGenerator/html` — this is what we're using. Returns disclaimer only.
2. **Form 8**: `POST /ps/htmlGenerator/forText` — text extraction. Returns empty content.
3. **Form 9**: `POST /ps/callisto/BulkPDF/UBER2` — **this might be the real PDF download**. Has fields: `dl`, `u=nuslib`, `p=SPOC`, `_csrf`.

### Next Step: Investigate the Correct Download
User needs to:
1. Open a document in Gale viewer in their regular browser
2. Open Chrome DevTools → Network tab
3. Click the actual download/save button
4. Capture the URL, method, and form data of the real download request
5. Look especially at Form 9 (`/ps/callisto/BulkPDF/UBER2`) — this is likely the real endpoint

### Error Encountered
After the 26 downloads, user got: **"Inter-institutional access failure. Please contact your system administrator for assistance."** — likely rate limiting or session expiry from 52 rapid requests (26 PDF + 26 text).

---

## Uncommitted Changes (MUST COMMIT)

### `src/auth.py`
- Replaced em dash `—` with `-` in print statements (UnicodeEncodeError on Korean Windows cp949 console)

### `src/scraper.py`
- Added missing form fields to `download_document_pdf()`: `title`, `disclaimerDisabled`, `asid`, `accessLevel`, `deliveryType`, `productCode`
- Added missing form fields to `download_document_text()`: `text`, `userGroupName`, `prodId`, `fileName`, `downloadAction`, `_csrf`, `deliveryType`
- These fixed the HTTP 500 errors (was getting 500, now gets 200), but the response is still just a disclaimer PDF

---

## Architecture: Data-Driven DocIds

```
data/volumes.json → src/config.py:load_volumes() → VOLUMES dict
                                                      ↓
scripts/run.py → scrape_volume(doc_ids=vol["doc_ids"]) → download each
```

---

## Volume Summary

| Volume | Docs | Status |
|--------|------|--------|
| CO273_534 | 26 | Downloaded (disclaimers only — needs fix) |
| CO273_550 | 20 | Not started |
| CO273_579 | 6 | Not started |

Existing downloads in `pdfs/CO273_534/` should be deleted before re-running with correct endpoint.

---

## GCP Setup (Complete)

- Project: `aihistory-488807`
- Bucket: `aihistory-co273` in `asia-southeast1`
- Key: configured in `.env`

---

## Environment Notes

- Python: `/c/Users/yjkim/AppData/Local/Microsoft/WindowsApps/python3.exe` (3.14.3)
- Venv: `source .venv/Scripts/activate`
- Korean Windows (cp949) — avoid unicode em dashes in print statements
- Git remote: https://github.com/kimyungju/aihistory.git
- Auth captures only 3 cookies: `ezproxyn`, `ezproxyl`, `ezproxy` (EZProxy only)
