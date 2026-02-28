# Phase 2: Enhanced OCR Pipeline — Task Checklist

**Last Updated: 2026-02-28**

---

## Phase A: Foundation ✅

### Task 1: Add Phase 2 Dependencies [S] ✅
- [x] Add `google-generativeai>=0.8.0` to `pyproject.toml` dependencies
- [x] Add `pytest-asyncio>=0.23.0` to `pyproject.toml` dev dependencies
- [x] Add `GEMINI_API_KEY` to `.env.example`
- [x] Run `pip install -e ".[dev]"` successfully
- [x] Commit (257ee04)

### Task 2: Phase 2 Configuration Module [S] ✅
- [x] Create `src/ocr/__init__.py` (empty)
- [x] Create `src/ocr/config.py` with Gemini settings, OCR prompt, retry config
- [x] Verify: `python -c "from src.ocr.config import OCR_PROMPT"` works
- [x] Commit (adae434)

## Phase B: Core Modules ✅

### Task 3: PDF Page Extraction [M] ✅ → Agent 1
- [x] Write failing tests: `tests/test_extract.py` (3 tests)
- [x] Run tests → verify they fail
- [x] Write `src/ocr/extract.py` with `extract_pages_from_pdf()`, `extract_volume_pages()`
- [x] Run tests → verify 3 pass
- [x] Commit (42deb96)

### Task 4: Gemini Vision OCR Module [M] ✅ → Agent 2
- [x] Write failing tests: `tests/test_gemini_ocr.py` (3 tests)
- [x] Run tests → verify they fail
- [x] Write `src/ocr/gemini_ocr.py` with `build_page_metadata()`, `ocr_single_page()`
- [x] Run tests → verify 3 pass
- [x] Commit (5760de1)

### Task 5: OCR Manifest Module [S] ✅ → Agent 1
- [x] Write failing tests: `tests/test_ocr_manifest.py` (4 tests)
- [x] Run tests → verify they fail
- [x] Write `src/ocr/manifest.py` with load/save/update functions
- [x] Run tests → verify 4 pass
- [x] Commit (300b30f)

### Task 6: Async Pipeline Orchestrator [L] ✅ → Agent 2
- [x] Write failing tests: `tests/test_pipeline.py` (2 tests)
- [x] Run tests → verify they fail
- [x] Write `src/ocr/pipeline.py` with `run_ocr_pipeline()`, retry logic, resume
- [x] Run tests → verify 2 pass
- [x] Commit (a99048a)

## Phase C: Integration ✅ (except Task 9)

### Task 7: CLI Entry Point [S] ✅
- [x] Write `scripts/run_ocr.py` with extract/ocr/all subcommands
- [x] Verify: `python -m scripts.run_ocr --help` works
- [x] Commit (2da2d41)

### Task 8: Full Test Suite + Smoke Test [S] ✅
- [x] Run Phase 2 tests: 12/12 pass
- [x] Verify CLI help works
- [x] Note: Phase 1 tests (test_gcs_upload, test_auth, test_scraper) excluded — protobuf/Python 3.14 incompatibility

### Task 9: GCS Integration [M] ⏳ DEFERRED
- [ ] Add GCS read/write to pipeline (download images, upload OCR results)
- [ ] Add `--local` flag to CLI for dev mode
- [ ] **Blocked by**: Phase 1 Task 10 (real data in bucket)

---

## Summary

| Task | Effort | Owner | Status | Depends On |
|------|--------|-------|--------|-----------|
| 1. Dependencies | S | Team Lead | ✅ | — |
| 2. OCR Config | S | Team Lead | ✅ | Task 1 |
| 3. PDF Extract | M | Agent 1 | ✅ | Task 2 |
| 4. Gemini OCR | M | Agent 2 | ✅ | Task 2 |
| 5. Manifest | S | Agent 1 | ✅ | Task 2 |
| 6. Pipeline | L | Agent 2 | ✅ | Tasks 4, 5 |
| 7. CLI | S | Team Lead | ✅ | Tasks 3-6 |
| 8. Smoke Test | S | Team Lead | ✅ | Task 7 |
| 9. GCS Integration | M | Team Lead | ⏳ DEFERRED | Phase 1 Task 10 |

**Total: 9 tasks. 8/9 complete. Task 9 deferred (blocked by Phase 1).**
