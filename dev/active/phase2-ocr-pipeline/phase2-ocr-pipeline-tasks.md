# Phase 2: Enhanced OCR Pipeline — Task Checklist

**Last Updated: 2026-03-01 (session 8)**

---

## Base Pipeline (9/9) ✅

### Phase A: Foundation ✅
- Task 1: Dependencies (257ee04) ✅
- Task 2: OCR Config (adae434) ✅

### Phase B: Core Modules ✅
- Task 3: PDF Extract (42deb96) ✅ Agent 1
- Task 4: Gemini OCR (5760de1) ✅ Agent 2
- Task 5: Manifest (300b30f) ✅ Agent 1
- Task 6: Pipeline (a99048a) ✅ Agent 2

### Phase C: Integration ✅
- Task 7: CLI (2da2d41) ✅
- Task 8: Smoke Test ✅ (12/12 tests)
- Task 9: GCS Integration (8767cd2, a651078) ✅

---

## OCR Enhancement (10/10) ✅

Plan: `docs/plans/2026-03-01-ocr-enhancement.md`

### Phase 1: Parallel tracks (Track A/B/C)
- Task 1: Path structure fix -- pipeline traverses per-doc subdirs (78813d5) ✅ Track A
- Task 2: Prompt variants -- general/tabular/handwritten in OCR_PROMPTS (78813d5) ✅ Track B
- Task 3: jiwer dependency added to pyproject.toml (78813d5) ✅ Track C
- Task 4: Evaluation script -- WER/CER via evaluate.py (78813d5) ✅ Track C
- Task 5: Evaluate CLI subcommand (78813d5) ✅ Track C
- Task 6: Post-correction module -- correct.py with .raw.txt backup (78813d5) ✅ Track B

### Phase 2: Integration
- Task 7: Wire --correct flag into pipeline (e90462a) ✅
- Task 8: --prompt CLI flag for variant selection (0cc833d) ✅
- Task 9: A/B testing script -- ab_test_prompts.py (6d717ff) ✅
- Task 10: Full verification -- 54/54 tests passing ✅

### Deferred
- Gold-standard test set curation (needs real data first)
- Automatic prompt detection per page type (printed/tabular/handwritten)

### Next
- Obtain GEMINI_API_KEY and add to .env
- Run scraper with NUS SSO to get real data
- Test OCR on real colonial documents

---

## Summary

| Phase | Tasks | Status |
|-------|-------|--------|
| Base Pipeline | 9/9 | ✅ DONE |
| OCR Enhancement | 10/10 | ✅ DONE |
| **Total** | **19/19** | **All complete** |

**54 tests passing (excluding test_gcs_upload.py due to Python 3.14 protobuf issue).**
