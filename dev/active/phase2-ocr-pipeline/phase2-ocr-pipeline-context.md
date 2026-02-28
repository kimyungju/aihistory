# Phase 2: Enhanced OCR Pipeline — Key Context

**Last Updated: 2026-02-28 (session 4 — implementation complete)**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `docs/plans/2026-02-28-phase2-ocr-pipeline-design.md` | Design doc | ✅ Written |
| `docs/plans/2026-02-28-phase2-ocr-pipeline.md` | Implementation plan (full code) | ✅ Written |
| `src/ocr/__init__.py` | Package init | ✅ Created (adae434) |
| `src/ocr/config.py` | Gemini model, concurrency, prompt settings | ✅ Created (adae434) |
| `src/ocr/extract.py` | PDF → page images | ✅ Created (42deb96) |
| `src/ocr/gemini_ocr.py` | Gemini Vision OCR per page | ✅ Created (5760de1) |
| `src/ocr/manifest.py` | OCR progress tracking | ✅ Created (300b30f) |
| `src/ocr/pipeline.py` | Async orchestrator | ✅ Created (a99048a) |
| `scripts/run_ocr.py` | CLI entry point | ✅ Created (2da2d41) |
| `tests/test_extract.py` | Extract tests (3) | ✅ Created (42deb96) |
| `tests/test_gemini_ocr.py` | OCR tests (3) | ✅ Created (5760de1) |
| `tests/test_ocr_manifest.py` | Manifest tests (4) | ✅ Created (300b30f) |
| `tests/test_pipeline.py` | Pipeline tests (2) | ✅ Created (a99048a) |

**All 12 Phase 2 tests pass. All code committed and pushed.**

---

## Architecture: Phase 1 → Phase 2 Handoff

```
Phase 1 output:                    Phase 2 reads:
pdfs/{vol}/documents/*.pdf    →    extract.py extracts page images
pdfs/{vol}/text/*.txt         →    kept as Gale OCR baseline for comparison
pdfs/{vol}/manifest.json      →    not used by Phase 2

Phase 2 produces:
pdfs/{vol}/images/page_NNNN.jpg    ← extracted page images
pdfs/{vol}/ocr/page_NNNN.txt      ← Gemini enhanced OCR text
pdfs/{vol}/ocr/page_NNNN.json     ← metadata (page_num, volume, model, illegible_count)
pdfs/{vol}/ocr_manifest.json       ← progress tracking
```

---

## Dependencies (New for Phase 2)

| Package | Purpose | Added to |
|---------|---------|----------|
| `google-generativeai>=0.8.0` | Gemini Vision API | `pyproject.toml` dependencies |
| `pytest-asyncio>=0.23.0` | Async test support | `pyproject.toml` dev dependencies |

Existing deps reused: `pypdf`, `Pillow`, `google-cloud-storage`, `python-dotenv`

---

## Environment Variables (New)

| Variable | Value | File |
|----------|-------|------|
| `GEMINI_API_KEY` | Your Gemini API key | `.env` |
| `GEMINI_MODEL` | `gemini-2.0-flash` (default) | `.env` (optional) |
| `OCR_CONCURRENCY` | `20` (default) | `.env` (optional) |

Get a Gemini API key at: https://aistudio.google.com/apikey

---

## GCP Setup

- **Project**: `aihistory-488807`
- **Bucket**: `aihistory-co273` in `asia-southeast1`
- **Auth**: Service account key at path in `GCS_KEY_PATH` env var
- **Public read**: Bucket is publicly readable (allUsers = Storage Object Viewer)

---

## Known Issues

### Python 3.14 + protobuf incompatibility
- `google-cloud-storage` triggers `ImportError: cannot import name 'duration_pb2' from 'google.protobuf'` on Python 3.14.3
- This blocks `test_gcs_upload.py` from being collected by pytest
- **Workaround**: Run Phase 2 tests only: `python -m pytest tests/test_extract.py tests/test_ocr_manifest.py tests/test_gemini_ocr.py tests/test_pipeline.py -v`
- Or exclude Phase 1 GCS test: `python -m pytest tests/ -v --ignore=tests/test_gcs_upload.py`
- Agent 2 used lazy import of `google.generativeai` in `pipeline.py:get_gemini_model()` to avoid import-time crash

### Python executable path
- Not on PATH in git bash shell
- Full path: `/c/Users/yjkim/AppData/Local/Microsoft/WindowsApps/python3.exe`

---

## Agent Team Execution Summary

Two parallel agents executed Tasks 3-6 successfully:

- **Agent 1** (extract + manifest): Tasks 3+5 — 7 tests, 2 commits (42deb96, 300b30f)
- **Agent 2** (gemini_ocr + pipeline): Tasks 4+6 — 5 tests, 2 commits (5760de1, a99048a)
- **Team Lead**: Tasks 1-2 (foundation), Task 7 (CLI), Task 8 (smoke test)

---

## Blockers

| Blocker | Status | Impact |
|---------|--------|--------|
| Phase 1 real data not yet downloaded | Waiting on scraper fix | Can't test OCR on real data, but unit tests pass |
| Gemini API key needed | User must create at aistudio.google.com | Blocks real OCR runs |
| protobuf/Python 3.14 incompatibility | Known issue | Phase 1 GCS tests can't run alongside Phase 2 tests |

---

## Next Steps

1. **Phase 1 scraper fix**: User needs to capture real Gale download endpoint via Chrome DevTools
2. **Get Gemini API key**: Create at https://aistudio.google.com/apikey, add to `.env`
3. **Task 9 (GCS integration)**: Blocked until Phase 1 uploads real PDFs to GCS bucket
4. **Phase 3**: Index generation from OCR output (after Phase 2 runs on real data)
