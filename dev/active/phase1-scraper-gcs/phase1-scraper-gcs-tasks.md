# Phase 1: Scraper + GCS -- Task Checklist

**Last Updated: 2026-03-01 (session 7)**

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

### 10c-perf: Concurrent downloads -- PLAN WRITTEN, NOT IMPLEMENTED
Plan: `docs/plans/2026-03-01-concurrent-downloads.md`
User chose: multi-agent team execution (subagent-driven)

- [ ] Task 1: Add `MAX_WORKERS=5` to config, reduce `DOWNLOAD_DELAY` to 0.5s
- [ ] Task 2: Extract `_download_single_page()` helper + tests
- [ ] Task 3: Rewrite `download_document_pages()` with `ThreadPoolExecutor`
- [ ] Task 4: Remove per-page `time.sleep(0.3)`, verify no stale sleeps
- [ ] Task 5: Add `--workers` CLI flag to `scripts/run.py`

### 10d: Test and download all volumes -- NEXT (after concurrent downloads)
- [ ] Run `python -m scripts.run test` to verify scraper works with NUS SSO
- [ ] Delete old pdfs/CO273_534/ disclaimer files
- [ ] Download CO273_534 (26 docs)
- [ ] Download CO273_550 (20 docs)
- [ ] Download CO273_579 (6 docs)

### 10e: Build + Upload
- [ ] Update `pdf_builder.py` if needed (now merging page images, not doc PDFs)
- [ ] `python -m scripts.run build` -- create per-volume PDFs from page images
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
| Concurrent Downloads | **Plan written** (session 7), not implemented |
| Test Scraper | Blocked by concurrent downloads impl |
| Download All Volumes | Blocked by test |
| Build + Upload | Blocked by download |
