# Phase 2: Enhanced OCR Pipeline — Strategic Plan

**Last Updated: 2026-02-28**

---

## Executive Summary

Build an async OCR pipeline that reads Phase 1's document PDFs from GCS/local storage, extracts page images, runs Gemini Vision OCR on each page, and writes enhanced text + JSON metadata back. This directly impacts the competition's OCR Quality score (25%). Gale's built-in OCR is insufficient for 19th-century colonial documents — Gemini Vision produces significantly better results on handwritten/degraded text.

---

## Current State Analysis

- **Phase 1**: Code complete (16 tests passing), GCP bucket ready, awaiting real download (Task 10)
- **Phase 1 output structure**: `{volume}/documents/*.pdf` + `{volume}/text/*.txt` (Gale OCR baseline)
- **GCP project**: `aihistory-488807`, bucket `aihistory-co273` in `asia-southeast1`
- **Volumes**: CO273_534 (26 docs), CO273_550 (20 docs), CO273_579 (6 docs) — 52 documents total
- **Estimated pages**: ~2,738 across all volumes
- **No Phase 2 code exists yet**

---

## Proposed Future State

A working CLI (`python -m scripts.run_ocr all`) that:
1. Extracts page images from document PDFs → `{volume}/images/page_NNNN.jpg`
2. Runs Gemini Vision OCR (20 concurrent workers) → `{volume}/ocr/page_NNNN.txt` + `.json`
3. Tracks progress via `ocr_manifest.json` for resume support
4. Completes ~2,738 pages in ~15 minutes at 20 concurrency

```
gs://aihistory-co273/
  CO273_534/
    documents/*.pdf          ← Phase 1
    text/*.txt               ← Phase 1 (Gale baseline)
    images/page_0001.jpg ... ← Phase 2 (extracted)
    ocr/page_0001.txt ...    ← Phase 2 (Gemini enhanced)
    ocr/page_0001.json ...   ← Phase 2 (metadata)
    ocr_manifest.json        ← Phase 2 (progress)
```

---

## Implementation Phases & Agent Team Strategy

### Overview: 3 Phases, 2 Agent Teams

```
Phase A (sequential)        Phase B (parallel agents)        Phase C (sequential)
────────────────────        ────────────────────────         ────────────────────
Team Lead:                  Team: ocr-modules                Team Lead:
  Task 1: Dependencies        Agent 1: extract + manifest      Task 7: CLI
  Task 2: OCR config          Agent 2: gemini_ocr + pipeline   Task 8: Smoke test
                                                                Task 9: GCS integration
```

---

### Phase A: Foundation (Sequential — Team Lead)

**Must complete before Phase B can start.**

#### Task 1: Add Phase 2 Dependencies [Effort: S]

| Item | Detail |
|------|--------|
| **Modifies** | `pyproject.toml`, `.env.example` |
| **Actions** | Add `google-generativeai>=0.8.0`, `pytest-asyncio>=0.23.0`, `GEMINI_API_KEY` env var |
| **Acceptance** | `pip install -e ".[dev]"` succeeds, `python -c "import google.generativeai"` works |
| **Dependencies** | None |

#### Task 2: Phase 2 Configuration Module [Effort: S]

| Item | Detail |
|------|--------|
| **Creates** | `src/ocr/__init__.py`, `src/ocr/config.py` |
| **Config values** | `GEMINI_API_KEY`, `GEMINI_MODEL`, `OCR_CONCURRENCY`, `OCR_PROMPT`, retry/timeout settings |
| **Acceptance** | `python -c "from src.ocr.config import OCR_PROMPT"` works |
| **Dependencies** | Task 1 |

---

### Phase B: Core Modules (Parallel Agents)

**Two agents work simultaneously after Task 2 completes.**

#### Agent 1: Extract + Manifest

##### Task 3: PDF Page Extraction Module [Effort: M]

| Item | Detail |
|------|--------|
| **Creates** | `src/ocr/extract.py`, `tests/test_extract.py` |
| **Functions** | `extract_pages_from_pdf()`, `extract_volume_pages()` |
| **Tests** | Page extraction from test PDF, continuous numbering, multi-doc volume extraction |
| **Acceptance** | `pytest tests/test_extract.py -v` passes (3 tests) |
| **Dependencies** | Task 2 |

##### Task 5: OCR Manifest Module [Effort: S]

| Item | Detail |
|------|--------|
| **Creates** | `src/ocr/manifest.py`, `tests/test_ocr_manifest.py` |
| **Functions** | `load_ocr_manifest()`, `save_ocr_manifest()`, `update_manifest_page()` |
| **Tests** | Empty manifest, round-trip, success/failure page tracking |
| **Acceptance** | `pytest tests/test_ocr_manifest.py -v` passes (4 tests) |
| **Dependencies** | Task 2 |

#### Agent 2: Gemini OCR + Pipeline

##### Task 4: Gemini Vision OCR Module [Effort: M]

| Item | Detail |
|------|--------|
| **Creates** | `src/ocr/gemini_ocr.py`, `tests/test_gemini_ocr.py` |
| **Functions** | `build_page_metadata()`, `ocr_single_page()` (async) |
| **Tests** | Metadata building, illegible count, mock Gemini OCR success |
| **Acceptance** | `pytest tests/test_gemini_ocr.py -v` passes (3 tests) |
| **Dependencies** | Task 2 |

##### Task 6: Async Pipeline Orchestrator [Effort: L]

| Item | Detail |
|------|--------|
| **Creates** | `src/ocr/pipeline.py`, `tests/test_pipeline.py` |
| **Functions** | `get_gemini_model()`, `_ocr_with_retry()`, `run_ocr_pipeline()` |
| **Tests** | Full pipeline run with mock Gemini, resume skipping completed pages |
| **Acceptance** | `pytest tests/test_pipeline.py -v` passes (2 tests) |
| **Dependencies** | Tasks 4, 5 |

---

### Phase C: Integration (Sequential — Team Lead)

**After Phase B agents complete.**

#### Task 7: CLI Entry Point [Effort: S]

| Item | Detail |
|------|--------|
| **Creates** | `scripts/run_ocr.py` |
| **Commands** | `extract [--volume]`, `ocr [--volume] [--concurrency]`, `all [--volume]` |
| **Acceptance** | `python -m scripts.run_ocr --help` displays all commands |
| **Dependencies** | Tasks 3, 4, 5, 6 |

#### Task 8: Full Test Suite + Smoke Test [Effort: S]

| Item | Detail |
|------|--------|
| **Actions** | Run all tests (Phase 1 + Phase 2), verify CLI help |
| **Acceptance** | `pytest tests/ -v` passes all tests, CLI help works for all subcommands |
| **Dependencies** | Task 7 |

#### Task 9: GCS Integration [Effort: M] [DEFERRED]

| Item | Detail |
|------|--------|
| **Modifies** | `src/ocr/pipeline.py`, `scripts/run_ocr.py` |
| **Actions** | Add GCS read/write, `--local` flag for dev mode |
| **Acceptance** | Pipeline reads from GCS bucket, writes OCR results back |
| **Dependencies** | Phase 1 Task 10 (real data in bucket) |
| **Note** | Deferred until Phase 1 has uploaded real data to GCS |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Gemini rate limiting at 20 concurrency | Medium | Low | Configurable concurrency, exponential backoff |
| Poor OCR on handwritten colonial text | Medium | High | Prompt tuning, compare with Gale baseline |
| pypdf can't extract images from Gale PDFs | Low | Medium | Fallback to pdf2image (poppler) |
| Gemini API key quota exceeded | Low | Low | Flash model is cheap (~$0.27 total), monitor usage |
| Async manifest corruption from concurrent writes | Medium | Medium | Write after each page, atomic-style save |

---

## Success Metrics

1. All ~2,738 page images extracted from document PDFs
2. Gemini Vision OCR text produced for every page
3. OCR quality visibly better than Gale baseline on sample inspection
4. Resume works — interrupt and restart without re-processing
5. All unit tests pass (12+ new tests)
6. Processing completes in under 30 minutes at default concurrency

---

## Cost Estimate

| Model | Cost per 1M tokens | Total tokens (~2,738 pages) | Total cost |
|-------|--------------------|-----------------------------|-----------|
| Gemini 2.0 Flash | ~$0.10 | ~2.7M | **~$0.27** |
| Gemini Pro | ~$1.00 | ~2.7M | **~$2.70** |

---

## Timeline (Agent-Parallel Execution)

| Step | What | Who | Depends On |
|------|------|-----|-----------|
| 1 | Tasks 1-2: Dependencies + Config | Team Lead | — |
| 2a | Tasks 3+5: Extract + Manifest | Agent 1 | Step 1 |
| 2b | Tasks 4+6: Gemini OCR + Pipeline | Agent 2 | Step 1 |
| 3 | Task 7: CLI | Team Lead | Steps 2a, 2b |
| 4 | Task 8: Smoke Test | Team Lead | Step 3 |
| 5 | Task 9: GCS Integration | Team Lead | Phase 1 Task 10 |
