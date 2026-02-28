# Phase 1: Scraper + GCS — Key Context

**Last Updated: 2026-02-28 (session 4 — download fixes applied)**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `data/volumes.json` | All 52 docIds by volume (data-driven) | ✅ Committed |
| `src/config.py` | `load_volumes()` reads JSON, `IMAGE_DOWNLOAD_URL` added | ✅ Committed (c59d6c4) |
| `src/scraper.py` | `scrape_volume()`, `download_page_image()`, disclaimer rejection | ✅ Committed (c59d6c4) |
| `src/auth.py` | NUS SSO auth, polls for JSESSIONID11_omni | ✅ Committed (67dfbf3) |
| `scripts/run.py` | CLI: scrape/build/upload/test/all + debug page analysis | ✅ Committed (f18e611) |
| `src/pdf_builder.py` | pypdf merge (unchanged) | ✅ |
| `src/gcs_upload.py` | GCS upload (unchanged) | ✅ |
| `.env` | GCS_KEY_PATH configured | ✅ |

**28/28 tests passing. All code committed and pushed. No uncommitted changes.**

---

## Session 4 Changes (This Session)

### Fixes Applied to Download Problem

1. **Auth: JSESSIONID11_omni polling** (67dfbf3)
   - `authenticate_gale()` now polls up to 15 seconds for `JSESSIONID11_omni` cookie
   - This was likely the root cause of disclaimers — Gale needs its session cookie, not just ezproxy

2. **Form data cleaned** (e2c8e02, dab05ff)
   - PDF form data: removed 4 extra fields (`title`, `asid`, `accessLevel`, `productCode`)
   - Text form data: removed 2 extra fields (`text`, `fileName`)
   - Now matches exactly what user captured from Chrome DevTools

3. **Image download added** (c59d6c4)
   - New `download_page_image()` function in `src/scraper.py`
   - New `IMAGE_BASE_URL` and `IMAGE_DOWNLOAD_URL` in `src/config.py`
   - Fetches page images directly from `luna-gale-com.libproxy1.nus.edu.sg/imgsrv/FastFetch/UBER2/`
   - Fallback path that bypasses PDF download entirely

4. **Debug page analysis enhanced** (f18e611)
   - `scripts/run.py` `cmd_test` with `--debug` searches for image IDs, API endpoints, recordIds
   - Tests image endpoint with different ID formats

### User-Captured Endpoints (Chrome DevTools)

**PDF:** `POST /ps/pdfGenerator/html` — form: prodId, userGroupName, downloadAction, retrieveFormat, deliveryType, disclaimerDisabled, docId, _csrf

**Text:** `POST /ps/htmlGenerator/forText` — form: prodId, userGroupName, downloadAction, retrieveFormat, deliveryType, productCode, accessLevel, docId, _csrf

**Image:** `GET luna-gale-com.libproxy1.nus.edu.sg/imgsrv/FastFetch/UBER2/{encoded_id}?legacy=no&scale=1.0&format=jpeg`

**Auth cookies needed:** ezproxy, ezproxyl, ezproxyn, JSESSIONID11_omni, XSRF-TOKEN

---

## Architecture: Data-Driven DocIds

```
data/volumes.json → src/config.py:load_volumes() → VOLUMES dict
                                                      ↓
scripts/run.py → scrape_volume(doc_ids=vol["doc_ids"]) → download each
                                                      ↓
                    _visit_document_page() → download_document_pdf() → save
                                          → download_document_text() → save
```

Alternative path (image download):
```
download_page_image(session, encoded_id, output_dir, page_num) → page_NNNN.jpg
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
- Korean Windows (cp949) — no em dashes in print statements
- Git remote: https://github.com/kimyungju/aihistory.git
- Test command: `python -m pytest tests/ --ignore=tests/test_gcs_upload.py -v`

---

## Next Step

Test a real download with NUS SSO to see if the JSESSIONID11_omni fix resolves the disclaimer issue:
```
python -m scripts.run test --doc-id "GALE|LBYSJJ528199212"
```
If still disclaimers, use `--debug` flag to analyze the page and find the correct image endpoint encoded_id format.
