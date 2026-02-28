# Phase 1: Scraper + GCS — Task Checklist

**Last Updated: 2026-02-28 (session 3)**

---

## Phase A: Foundation (Sequential — Team Lead)

### Task 1: Project Scaffolding [S] ✅
- [x] `git init`
- [x] Create `pyproject.toml` with all dependencies
- [x] Create `.gitignore` (pdfs/, .env, __pycache__, *.json creds)
- [x] Create `.env.example`
- [x] Create `src/__init__.py`
- [x] Create `src/config.py` with VOLUMES, paths, settings
- [x] Create directories: `src/`, `pdfs/`, `scripts/`, `tests/`
- [x] `pip install -e ".[dev]"` succeeds
- [x] Commit: `chore: scaffold project with config, dependencies, and gitignore`

---

## Phase B: Core Modules (Parallel Agents) ✅

### Agent 1: auth-scraper ✅

#### Task 2: Authentication Module [M] ✅
- [x] Write `tests/test_auth.py` (2 tests)
- [x] Write `src/auth.py` (extract_cookies_from_driver, create_session_with_cookies, authenticate_gale)
- [x] 2 tests passing
- [x] Committed

#### Task 4: Scraper Module [L] ✅ (then rewritten — see Task 3)
- [x] Original: page-by-page scraper with 5 tests
- [x] REWRITTEN after API discovery: document-level PDF download with 10 tests
- [x] Commit: `feat: rewrite scraper for Gale document-level PDF download API`

### Agent 2: pdf-gcs ✅

#### Task 5: PDF Builder Module [S] ✅ (then rewritten)
- [x] Original: Pillow image→PDF
- [x] REWRITTEN: pypdf merge_pdfs() for combining document PDFs
- [x] 2 tests passing

#### Task 6: GCS Upload Module [M] ✅
- [x] Write `tests/test_gcs_upload.py` (2 tests)
- [x] Write `src/gcs_upload.py` (get_gcs_client, get_bucket, upload_file, upload_volume, upload_all_volumes, list_bucket_contents)
- [x] 2 tests passing
- [x] Committed

---

## Manual Tasks (User)

### Task 3: Gale API Endpoint Discovery [M] [MANUAL] ✅
- [x] Log into Gale, use Chrome DevTools to find API endpoints
- [x] Discovered: POST /ps/pdfGenerator/html (PDF download)
- [x] Discovered: POST /ps/htmlGenerator/forText (OCR text)
- [x] CSRF token in hidden form field + XSRF-TOKEN cookie
- [x] Each volume has many sub-documents with GALE|... docIds
- [x] Scraper completely rewritten based on findings
- [x] Commit: `feat: rewrite scraper for Gale document-level PDF download API`

### Task 9: GCP Project & Bucket Setup [M] [MANUAL] 🔄 IN PROGRESS
- [ ] Create GCP project named `aihistory` at console.cloud.google.com
- [ ] Enable Cloud Storage API
- [ ] Create bucket `aihistory-co273` in `asia-southeast1`
- [ ] Create service account `aihistory-uploader` with Storage Object Creator + Viewer roles
- [ ] Download JSON key file → `credentials/gcs-key.json`
- [ ] Create `.env` from `.env.example`, fill in GCS_KEY_PATH
- [ ] (Optional) Create viewer service account for collaborators
- **Status**: User has Google account, no GCP project yet. Walkthrough provided — waiting for user to complete Steps 1-4 in GCP Console.

---

## Phase C: Integration (Sequential — Team Lead)

### Task 7: CLI Entry Point [S] ✅
- [x] Create `scripts/__init__.py`
- [x] Create `scripts/run.py` with scrape/build/upload/all commands
- [x] `python -m scripts.run --help` works
- [x] Commit: `feat: add CLI entry point with scrape/build/upload/all commands`

### Task 8: End-to-End Smoke Test [S] ✅
- [x] All 16 tests passing (`pytest tests/ -v`)
- [x] CLI works: `python -m scripts.run --help`
- [x] All subcommands work: scrape --help, build --help, upload

### Task 10: Real Download & Full Integration [XL] ⏳ BLOCKED
- [ ] Fill `search_url` values in `src/config.py` from Gale volume facet filter URLs
- [ ] Verify Task 9 complete (GCS bucket ready)
- [ ] Test: `python -m scripts.run scrape --volume CO273_534` (verify docId discovery + PDF download)
- [ ] Full run: `python -m scripts.run scrape --resume` (all 3 volumes)
- [ ] Build: `python -m scripts.run build`
- [ ] Upload: `python -m scripts.run upload`
- [ ] Verify bucket contents in Cloud Console
- **Blocked by**: Task 9 (GCP bucket) + empty search_url values in config.py

---

## Summary

| Phase | Tasks | Agent | Status |
|-------|-------|-------|--------|
| A | 1 (Scaffold) | Team Lead | ✅ Done |
| B | 2, 4 (Auth + Scraper) | Agent 1 | ✅ Done (scraper rewritten) |
| B | 5, 6 (PDF + GCS) | Agent 2 | ✅ Done (pdf_builder rewritten) |
| Manual | 3 (API Discovery) | User | ✅ Done |
| Manual | 9 (GCP Setup) | User | 🔄 In Progress |
| C | 7, 8 (CLI + Smoke) | Team Lead | ✅ Done |
| C | 10 (Integration) | Team Lead | ⏳ Blocked |

**Completed: 8/10 tasks. Remaining: Task 9 (GCP setup) → Task 10 (real download test)**
