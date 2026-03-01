# Phase 1: Scraper + GCS -- Task Checklist

**Last Updated: 2026-03-01 (session 9)**

---

## Tasks 1-9: Done

All code, tests, GCP setup, and docId config complete.

## Task 10: Real Download & Integration

### 10a: Old approach (dead end) -- DONE
- [x] Scraper runs end-to-end (auth -> CSRF -> download loop -> manifest)
- [x] 26/26 docs downloaded for CO273_534 (disclaimers only)
- [x] User captured real endpoints via Chrome DevTools
- [x] Form data cleaned to match captured data
- [x] Auth polls for JSESSIONID11_omni cookie
- [x] Disclaimer size rejection added (<5KB)
- [x] Selenium download path attempted -- blank page, 0 interactive elements
- [x] **DEAD END CONFIRMED**: pdfGenerator/html always returns disclaimers
- [x] **DEAD END CONFIRMED**: retrieve.do returns no `<body>` (JSP crash)

### 10b: dviViewer API discovery -- DONE (session 5)
- [x] Investigated DOM, network requests, JS code in Selenium
- [x] Found `dviViewer/getDviDocument` API returns 311KB JSON with all data
- [x] Confirmed works with both Selenium XHR and requests library
- [x] Parsed JSON: 53 pages imageList, 106 pdfRecordIds, 51 pages OCR text
- [x] Saved sample response: `pdfs/_test/documents/dvi_response_requests.json`

### 10c: Rewrite scraper for dviViewer approach -- DONE
- [x] Add `DVI_DOCUMENT_URL` constant to `src/config.py`
- [x] Add `get_document_data()` to `src/scraper.py` -- calls dviViewer API, returns parsed JSON
- [x] Add `download_document_pages()` -- downloads all page images using recordId tokens
- [x] Add `save_ocr_text()` -- extracts OCR text from JSON response
- [x] Update `scrape_volume()` to use new functions
- [x] Update `scripts/run.py` cmd_test to verify new approach
- [x] Update unit tests for new functions

### 10c-env: Environment setup -- DONE (session 6)
- [x] Install Python 3.14.3 from python.org (removed MS Store version)
- [x] Fix PATH for Git Bash (~/.bashrc) and Cursor terminal (settings.json)
- [x] Create .venv and install all dependencies
- [x] Update CLAUDE.md with PowerShell activation command

### 10c-perf: Concurrent downloads -- DONE (session 7-8)
- [x] Task 1: `MAX_WORKERS=5` in config, `DOWNLOAD_DELAY` reduced to 0.5s
- [x] Task 2: `_download_single_page()` helper extracted + tests
- [x] Task 3: `download_document_pages()` rewritten with `ThreadPoolExecutor`
- [x] Task 4: Per-page `time.sleep(0.3)` removed
- [x] Task 5: `--workers` CLI flag added to `scripts/run.py`

### 10c-retry: Session expiry retry logic -- DONE (session 8-9, commit 4eb3bdc)
- [x] Retry + empty response detection in `get_document_data()` (exponential backoff)
- [x] Retry in `_download_single_page()` (connection errors + empty responses)
- [x] Clear `failed_docs` on `--resume` in `scrape_volume()`
- [x] Consecutive failure abort (3 in a row -> stop + suggest `--resume`)
- [x] 3 new tests added (28/28 total)

### 10d: Download all volumes -- IN PROGRESS
- [x] Scraper test passed with NUS SSO
- [x] Deleted old CO273_534 disclaimer files
- [x] Download CO273_534 (26/26 docs) ✅
- [ ] Download CO273_550 (20 docs) -- needs NUS SSO session
- [ ] Download CO273_579 (6 docs) -- needs NUS SSO session

### 10e: Build + Upload -- BLOCKED on GCS permissions
- [ ] `python -m scripts.run build` -- create per-volume PDFs from page images
- [ ] Fix GCS bucket permissions (service account needs Storage Admin role)
- [ ] Confirm bucket name (user may have created different name than `aihistory-co273`)
- [ ] Update `.env` GCS_BUCKET if needed
- [ ] `python -m scripts.run upload` -- upload to GCS
- [ ] Verify in Cloud Console

---

## Bugs Fixed (Sessions 3-5)

1. **UnicodeEncodeError** (cp949): Em dash -> ASCII dash
2. **HTTP 500 on PDF download**: Missing form fields
3. **`.gitignore` blocking volumes.json**: Added exception
4. **Disclaimer-only PDFs**: pdfGenerator/html is a dead end
5. **Blank Selenium page**: retrieve.do server-side rendering broken (no `<body>`)
6. **SPA never initializes**: All body content is missing from server response

---

## Summary

| Item | Status |
|------|--------|
| Code + Tests (28/28) | Done |
| GCP Setup | Done |
| DocId Config (52 docs) | Done |
| dviViewer API Discovery | Done (session 5) |
| Scraper Rewrite | Done |
| Environment Setup | Done (session 6) |
| Concurrent Downloads | Done (session 7-8) |
| Retry Logic | Done (session 8-9, commit 4eb3bdc) |
| CO273_534 Download | **Done** (26/26 docs, ~1.2GB) |
| CO273_550 + CO273_579 | Not started (need NUS SSO) |
| GCS Upload | **Blocked** (bucket permissions + name) |
