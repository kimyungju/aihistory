# Phase 2: Enhanced OCR Pipeline — Key Context

**Last Updated: 2026-02-28**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `docs/plans/2026-02-28-phase2-ocr-pipeline-design.md` | Design doc | ✅ Written |
| `docs/plans/2026-02-28-phase2-ocr-pipeline.md` | Implementation plan (full code) | ✅ Written |
| `src/ocr/__init__.py` | Package init | ❌ Not created |
| `src/ocr/config.py` | Gemini model, concurrency, prompt settings | ❌ Not created |
| `src/ocr/extract.py` | PDF → page images | ❌ Not created |
| `src/ocr/gemini_ocr.py` | Gemini Vision OCR per page | ❌ Not created |
| `src/ocr/manifest.py` | OCR progress tracking | ❌ Not created |
| `src/ocr/pipeline.py` | Async orchestrator | ❌ Not created |
| `scripts/run_ocr.py` | CLI entry point | ❌ Not created |
| `tests/test_extract.py` | Extract tests (3) | ❌ Not created |
| `tests/test_gemini_ocr.py` | OCR tests (3) | ❌ Not created |
| `tests/test_ocr_manifest.py` | Manifest tests (4) | ❌ Not created |
| `tests/test_pipeline.py` | Pipeline tests (2) | ❌ Not created |

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

## Agent Team Strategy

Two parallel agents after foundation tasks:

- **Agent 1** (extract + manifest): Independent modules, no Gemini API dependency
- **Agent 2** (gemini_ocr + pipeline): Depends on Agent 1's manifest module for Task 6

Task 6 (pipeline) depends on both Tasks 4 and 5. Agent 2 should do Task 4 first, then wait for Agent 1 to finish Task 5 before starting Task 6.

---

## Blockers

| Blocker | Status | Impact |
|---------|--------|--------|
| Phase 1 real data not yet downloaded | Waiting on Task 10 | Can't test on real data, but unit tests work |
| Gemini API key needed | User must create at aistudio.google.com | Blocks real OCR runs |
| Volume search_url values empty | Being filled by another session | Blocks Phase 1 Task 10 |

---

## Next Step

Run Phase 2 implementation using agent team:
1. Team Lead does Tasks 1-2 (dependencies + config)
2. Spawn Agent 1 (Tasks 3+5) and Agent 2 (Tasks 4+6) in parallel
3. Team Lead does Tasks 7-8 (CLI + smoke test)
