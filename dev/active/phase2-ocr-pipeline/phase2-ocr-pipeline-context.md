# Phase 2: Enhanced OCR Pipeline — Key Context

**Last Updated: 2026-02-28 (session 4 — GCS integration added)**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `docs/plans/2026-02-28-phase2-ocr-pipeline-design.md` | Design doc | ✅ Written |
| `docs/plans/2026-02-28-phase2-ocr-pipeline.md` | Implementation plan | ✅ Written |
| `src/ocr/__init__.py` | Package init | ✅ Created (adae434) |
| `src/ocr/config.py` | Gemini model, concurrency, prompt settings | ✅ Created (adae434) |
| `src/ocr/extract.py` | PDF → page images | ✅ Created (42deb96) |
| `src/ocr/gemini_ocr.py` | Gemini Vision OCR per page | ✅ Created (5760de1) |
| `src/ocr/manifest.py` | OCR progress tracking | ✅ Created (300b30f) |
| `src/ocr/pipeline.py` | Async orchestrator + GCS functions | ✅ Updated (8767cd2) |
| `scripts/run_ocr.py` | CLI with --local flag | ✅ Updated (a651078) |
| `tests/test_extract.py` | Extract tests (3) | ✅ Created |
| `tests/test_gemini_ocr.py` | OCR tests (3) | ✅ Created |
| `tests/test_ocr_manifest.py` | Manifest tests (4) | ✅ Created |
| `tests/test_pipeline.py` | Pipeline tests (2) | ✅ Created |

**All 12 Phase 2 tests pass. All code committed and pushed.**

---

## Session 4: GCS Integration Added

- `download_images_from_gcs()` and `upload_ocr_to_gcs()` added to `src/ocr/pipeline.py` (8767cd2)
- `--local` flag added to `scripts/run_ocr.py` for `ocr` and `all` subparsers (a651078)
- Default behavior: download images from GCS, run OCR, upload results to GCS
- With `--local`: use local files only (for dev/testing)
- All GCS imports are lazy (inside function bodies) to avoid Python 3.14 protobuf crash

**Task 9 (GCS Integration) is now COMPLETE.** Phase 2 is fully implemented (9/9 tasks done).

---

## CLI Usage

```bash
# Local mode (dev): extract from local PDFs, run OCR locally
python -m scripts.run_ocr extract --volume CO273_534
python -m scripts.run_ocr ocr --volume CO273_534 --local --concurrency 20

# GCS mode (production): download images from GCS, OCR, upload results
python -m scripts.run_ocr ocr --volume CO273_534 --concurrency 20

# Full pipeline
python -m scripts.run_ocr all --volume CO273_534 --local
```

---

## Architecture: Phase 1 → Phase 2 Handoff

```
Phase 1 output:                    Phase 2 reads:
pdfs/{vol}/documents/*.pdf    →    extract.py extracts page images
pdfs/{vol}/text/*.txt         →    kept as Gale OCR baseline

Phase 2 produces:
pdfs/{vol}/images/page_NNNN.jpg    ← extracted page images
pdfs/{vol}/ocr/page_NNNN.txt      ← Gemini enhanced OCR text
pdfs/{vol}/ocr/page_NNNN.json     ← metadata
pdfs/{vol}/ocr_manifest.json       ← progress tracking

GCS mode:
gs://aihistory-co273/{vol}/images/ → download → OCR → upload → gs://aihistory-co273/{vol}/ocr/
```

---

## Known Issues

### Python 3.14 + protobuf incompatibility
- `google-cloud-storage` crashes at import time on Python 3.14.3
- **Workaround**: All GCS imports are lazy (inside function bodies)
- Run tests: `python -m pytest tests/ --ignore=tests/test_gcs_upload.py -v`

### Python executable path
- Not on PATH in git bash: `/c/Users/yjkim/AppData/Local/Microsoft/WindowsApps/python3.exe`

---

## Blockers

| Blocker | Status | Impact |
|---------|--------|--------|
| Phase 1 real data not downloaded | Fixes applied, needs SSO test | Can't run OCR on real data |
| Gemini API key needed | User creates at aistudio.google.com | Blocks real OCR runs |

---

## Next Steps

1. **Phase 1 SSO test**: Verify download fixes work with real NUS SSO session
2. **Get Gemini API key**: Add to `.env` as `GEMINI_API_KEY`
3. **Run OCR on real data**: After Phase 1 downloads succeed
4. **Phase 3**: Index generation from OCR output
