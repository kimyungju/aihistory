# Phase 2: Enhanced OCR Pipeline — Key Context

**Last Updated: 2026-03-01 (session 9 — CO273_534 scraped, GCS blocked on perms)**

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `docs/plans/2026-02-28-phase2-ocr-pipeline-design.md` | Design doc | ✅ Written |
| `docs/plans/2026-02-28-phase2-ocr-pipeline.md` | Implementation plan | ✅ Written |
| `docs/plans/2026-03-01-ocr-enhancement.md` | OCR enhancement plan (10 tasks) | ✅ Written |
| `src/ocr/__init__.py` | Package init | ✅ Created (adae434) |
| `src/ocr/config.py` | Gemini model, concurrency, prompt variants | ✅ Updated (78813d5) |
| `src/ocr/extract.py` | PDF page images | ✅ Created (42deb96) |
| `src/ocr/gemini_ocr.py` | Gemini Vision OCR with prompt selection | ✅ Updated (78813d5) |
| `src/ocr/correct.py` | LLM post-correction module | ✅ Created (78813d5) |
| `src/ocr/evaluate.py` | WER/CER evaluation (jiwer) | ✅ Created (78813d5) |
| `src/ocr/manifest.py` | OCR progress tracking (per-doc subdirs) | ✅ Updated (78813d5) |
| `src/ocr/pipeline.py` | Async orchestrator + GCS + correction | ✅ Updated (e90462a) |
| `scripts/run_ocr.py` | CLI: ocr/extract/evaluate + flags | ✅ Updated (0cc833d) |
| `scripts/ab_test_prompts.py` | A/B testing for prompt variants | ✅ Created (6d717ff) |
| `tests/test_extract.py` | Extract tests (3) | ✅ Created |
| `tests/test_gemini_ocr.py` | OCR tests (3) | ✅ Created |
| `tests/test_ocr_manifest.py` | Manifest tests (4) | ✅ Created |
| `tests/test_pipeline.py` | Pipeline tests | ✅ Updated |
| `tests/test_correct.py` | Post-correction tests | ✅ Created |
| `tests/test_evaluate.py` | Evaluation tests | ✅ Created |

**All 54 tests pass (excluding test_gcs_upload.py). All code committed and pushed.**

---

## Session 8: OCR Enhancement (2026-03-01)

Plan: `docs/plans/2026-03-01-ocr-enhancement.md` (10 tasks, all complete)

Implemented in 3 parallel agent tracks + 1 integration pass:

**Track A -- Path structure fix (pipeline.py, manifest.py):**
- Pipeline now traverses per-document image subdirectories: `images/{doc_id}/page_NNNN.jpg`
- Manifest tracks `source_document` per page for traceability

**Track B -- Prompt variants + post-correction (config.py, gemini_ocr.py, correct.py):**
- `OCR_PROMPTS` dict in `config.py` with 3 variants: `general`, `tabular`, `handwritten`
- `gemini_ocr.py` accepts prompt variant selection
- `correct.py`: LLM post-correction module, saves `.raw.txt` backup before overwriting

**Track C -- Evaluation (evaluate.py, run_ocr.py, pyproject.toml):**
- `jiwer` dependency added for WER/CER metrics
- `evaluate.py`: compares Gemini OCR output vs Gale baseline text
- `evaluate` CLI subcommand added to `run_ocr.py`

**Integration pass:**
- `--correct` flag wired into pipeline (runs post-correction after OCR)
- `--prompt` CLI flag for selecting prompt variant (general/tabular/handwritten)
- `ab_test_prompts.py` script for comparing prompt variants on the same pages

**All 10 OCR enhancement tasks complete. 54/54 tests passing.**

---

## Session 4: GCS Integration Added

- `download_images_from_gcs()` and `upload_ocr_to_gcs()` added to `src/ocr/pipeline.py` (8767cd2)
- `--local` flag added to `scripts/run_ocr.py` for `ocr` and `all` subparsers (a651078)
- Default behavior: download images from GCS, run OCR, upload results to GCS
- With `--local`: use local files only (for dev/testing)
- All GCS imports are lazy (inside function bodies) to avoid Python 3.14 protobuf crash

---

## CLI Usage

```bash
# Local mode (dev): extract from local PDFs, run OCR locally
python -m scripts.run_ocr extract --volume CO273_534
python -m scripts.run_ocr ocr --volume CO273_534 --local --concurrency 20

# With prompt variant selection
python -m scripts.run_ocr ocr --volume CO273_534 --local --prompt tabular

# With post-correction pass
python -m scripts.run_ocr ocr --volume CO273_534 --local --correct

# Evaluate OCR quality (WER/CER vs Gale baseline)
python -m scripts.run_ocr evaluate --volume CO273_534

# A/B test prompt variants
python scripts/ab_test_prompts.py --volume CO273_534 --pages 10

# GCS mode (production): download images from GCS, OCR, upload results
python -m scripts.run_ocr ocr --volume CO273_534 --concurrency 20

# Full pipeline
python -m scripts.run_ocr all --volume CO273_534 --local
```

---

## Architecture: Phase 1 → Phase 2 Handoff

```
Phase 1 output:                         Phase 2 reads:
pdfs/{vol}/documents/*.pdf         →    extract.py extracts page images
pdfs/{vol}/text/{doc_id}.txt       →    Gale OCR baseline (for evaluation)

Phase 2 produces:
pdfs/{vol}/images/{doc_id}/page_NNNN.jpg  ← per-document page images
pdfs/{vol}/ocr/page_NNNN.txt             ← Gemini enhanced OCR text
pdfs/{vol}/ocr/page_NNNN.raw.txt         ← pre-correction backup (if --correct)
pdfs/{vol}/ocr/page_NNNN.json            ← metadata (includes source_document)
pdfs/{vol}/ocr_manifest.json              ← progress tracking

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
| Phase 1 CO273_534 data | DONE (26/26 docs scraped) | OCR can run on local data |
| CO273_550 + CO273_579 | Not started (need NUS SSO) | Partial data only |
| Gemini API key needed | User creates at aistudio.google.com | Blocks real OCR runs |
| GCS upload blocked | Service account permissions | Can't use GCS mode for OCR |

---

## Deferred / Future Work

- **Gold-standard test set curation**: Manual ground truth for evaluation (needs real data)
- **Automatic prompt detection**: Classify page type (printed/tabular/handwritten) and select prompt automatically

## Next Steps

1. **Get Gemini API key**: Add to `.env` as `GEMINI_API_KEY`
2. **Phase 1 SSO test**: Run scraper with NUS SSO to download real data
3. **Run OCR on real data**: Test all 3 prompt variants on real colonial documents
4. **Evaluate**: Compare Gemini vs Gale OCR using WER/CER metrics
5. **Phase 3**: Index generation from OCR output
