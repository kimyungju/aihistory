# Phase 2: Enhanced OCR Pipeline — Task Checklist

**Last Updated: 2026-02-28**

---

## Phase A: Foundation ⏳

### Task 1: Add Phase 2 Dependencies [S] ⏳
- [ ] Add `google-generativeai>=0.8.0` to `pyproject.toml` dependencies
- [ ] Add `pytest-asyncio>=0.23.0` to `pyproject.toml` dev dependencies
- [ ] Add `GEMINI_API_KEY` to `.env.example`
- [ ] Run `pip install -e ".[dev]"` successfully
- [ ] Commit

### Task 2: Phase 2 Configuration Module [S] ⏳
- [ ] Create `src/ocr/__init__.py` (empty)
- [ ] Create `src/ocr/config.py` with Gemini settings, OCR prompt, retry config
- [ ] Verify: `python -c "from src.ocr.config import OCR_PROMPT"` works
- [ ] Commit

## Phase B: Core Modules ⏳

### Task 3: PDF Page Extraction [M] ⏳ → Agent 1
- [ ] Write failing tests: `tests/test_extract.py` (3 tests)
- [ ] Run tests → verify they fail
- [ ] Write `src/ocr/extract.py` with `extract_pages_from_pdf()`, `extract_volume_pages()`
- [ ] Run tests → verify 3 pass
- [ ] Commit

### Task 4: Gemini Vision OCR Module [M] ⏳ → Agent 2
- [ ] Write failing tests: `tests/test_gemini_ocr.py` (3 tests)
- [ ] Run tests → verify they fail
- [ ] Write `src/ocr/gemini_ocr.py` with `build_page_metadata()`, `ocr_single_page()`
- [ ] Run tests → verify 3 pass
- [ ] Commit

### Task 5: OCR Manifest Module [S] ⏳ → Agent 1
- [ ] Write failing tests: `tests/test_ocr_manifest.py` (4 tests)
- [ ] Run tests → verify they fail
- [ ] Write `src/ocr/manifest.py` with load/save/update functions
- [ ] Run tests → verify 4 pass
- [ ] Commit

### Task 6: Async Pipeline Orchestrator [L] ⏳ → Agent 2
- [ ] Write failing tests: `tests/test_pipeline.py` (2 tests)
- [ ] Run tests → verify they fail
- [ ] Write `src/ocr/pipeline.py` with `run_ocr_pipeline()`, retry logic, resume
- [ ] Run tests → verify 2 pass
- [ ] Commit

## Phase C: Integration ⏳

### Task 7: CLI Entry Point [S] ⏳
- [ ] Write `scripts/run_ocr.py` with extract/ocr/all subcommands
- [ ] Verify: `python -m scripts.run_ocr --help` works
- [ ] Commit

### Task 8: Full Test Suite + Smoke Test [S] ⏳
- [ ] Run `python -m pytest tests/ -v` — all tests pass (Phase 1 + Phase 2)
- [ ] Verify all CLI subcommands show help
- [ ] Commit any fixes

### Task 9: GCS Integration [M] ⏳ DEFERRED
- [ ] Add GCS read/write to pipeline (download images, upload OCR results)
- [ ] Add `--local` flag to CLI for dev mode
- [ ] **Blocked by**: Phase 1 Task 10 (real data in bucket)

---

## Summary

| Task | Effort | Owner | Status | Depends On |
|------|--------|-------|--------|-----------|
| 1. Dependencies | S | Team Lead | ⏳ | — |
| 2. OCR Config | S | Team Lead | ⏳ | Task 1 |
| 3. PDF Extract | M | Agent 1 | ⏳ | Task 2 |
| 4. Gemini OCR | M | Agent 2 | ⏳ | Task 2 |
| 5. Manifest | S | Agent 1 | ⏳ | Task 2 |
| 6. Pipeline | L | Agent 2 | ⏳ | Tasks 4, 5 |
| 7. CLI | S | Team Lead | ⏳ | Tasks 3-6 |
| 8. Smoke Test | S | Team Lead | ⏳ | Task 7 |
| 9. GCS Integration | M | Team Lead | ⏳ DEFERRED | Phase 1 Task 10 |

**Total: 9 tasks. 0/9 complete.**
