# Phase 1: Scraper + GCS — Task Checklist

**Last Updated: 2026-02-28 (session 3)**

---

## Phase A: Foundation ✅

### Task 1: Project Scaffolding [S] ✅
- [x] git init, pyproject.toml, .gitignore, .env.example, src/, scripts/, tests/

## Phase B: Core Modules ✅

### Task 2: Authentication Module [M] ✅
- [x] src/auth.py + tests/test_auth.py (2 tests)

### Task 4: Scraper Module [L] ✅ (rewritten twice)
- [x] Original: page-by-page → Rewritten: document-level API → Updated: data-driven docIds
- [x] src/scraper.py + tests/test_scraper.py (10 tests)

### Task 5: PDF Builder [S] ✅ (rewritten)
- [x] src/pdf_builder.py: pypdf merge + tests/test_pdf_builder.py (2 tests)

### Task 6: GCS Upload [M] ✅
- [x] src/gcs_upload.py + tests/test_gcs_upload.py (2 tests)

## Manual Tasks

### Task 3: Gale API Endpoint Discovery [M] ✅
- [x] PDF download: POST /ps/pdfGenerator/html
- [x] Text download: POST /ps/htmlGenerator/forText
- [x] CSRF token extraction
- [x] 52 docIds extracted from user-provided URLs → data/volumes.json

### Task 9: GCP Project & Bucket Setup [M] ✅
- [x] GCP project created (aihistory-488807)
- [x] Bucket aihistory-co273 created
- [x] Service account key downloaded
- [x] .env configured with GCS_KEY_PATH

## Phase C: Integration

### Task 7: CLI Entry Point [S] ✅
- [x] scripts/run.py with scrape/build/upload/all commands

### Task 8: End-to-End Smoke Test [S] ✅
- [x] 16/16 tests passing, CLI works

### Task 10: Real Download & Full Integration [XL] ⏳ READY
- [ ] Test: `python -m scripts.run scrape --volume CO273_534`
- [ ] Full run: `python -m scripts.run scrape --resume` (all 3 volumes)
- [ ] Build: `python -m scripts.run build`
- [ ] Upload: `python -m scripts.run upload`
- [ ] Verify bucket contents in Cloud Console
- **No longer blocked** — docIds configured, GCP ready

---

## Summary

| Task | Status |
|------|--------|
| 1-8 (Code + Tests) | ✅ Done |
| 3 (API Discovery) | ✅ Done |
| 9 (GCP Setup) | ✅ Done |
| 10 (Real Download) | ⏳ Ready to run |

**Completed: 9/10 tasks. Remaining: Task 10 (real download test)**
