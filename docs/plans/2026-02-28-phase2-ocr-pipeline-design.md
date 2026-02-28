# Phase 2 Design: Enhanced OCR Pipeline

**Date**: 2026-02-28
**Project**: aihistory — "New Kratoska Index" for CO 273 Colonial Records
**Phase**: 2 of 4 (Enhanced OCR)

## Context

Phase 1 scrapes document PDFs and Gale's built-in OCR text from Gale Primary Sources, uploading to GCS. However, Gale's automated OCR is likely poor on 19th-century colonial documents (handwriting, old typefaces, faded ink, stamps). Phase 2 enhances OCR quality using Gemini Vision, which is critical since OCR Quality accounts for 25% of the competition score.

## Approach

**GCS-native pipeline with Gemini Vision**:
- Read document PDFs directly from GCS
- Extract each page as a JPEG image
- Send page images to Gemini Vision API with a prompt tuned for colonial documents
- Write enhanced OCR text + metadata back to GCS
- Async workers (20-50 concurrent) for throughput
- Resume support via per-volume manifest

## Data Flow

```
Phase 1 output (GCS)              Phase 2                              Phase 2 output (GCS)
─────────────────────             ───────                              ────────────────────
{vol}/documents/doc_001.pdf  →  Extract page images  →  {vol}/images/page_0001.jpg
                                        ↓
{vol}/text/doc_001.txt       →  (kept as Gale baseline)
                                        ↓
                                 Gemini Vision API    →  {vol}/ocr/page_0001.txt
                                 (async, 20-50 workers)  {vol}/ocr/page_0001.json
                                        ↓
                                 manifest updated     → {vol}/ocr_manifest.json
```

## GCS Bucket Structure After Phase 2

```
gs://aihistory-co273/
  CO273_534/
    documents/doc_001.pdf ...     ← Phase 1
    text/doc_001.txt ...          ← Phase 1 (Gale OCR baseline)
    images/page_0001.jpg ...      ← Phase 2 (extracted from PDFs)
    ocr/page_0001.txt ...         ← Phase 2 (Gemini enhanced OCR)
    ocr/page_0001.json ...        ← Phase 2 (metadata per page)
    manifest.json                 ← Phase 1 (download tracking)
    ocr_manifest.json             ← Phase 2 (OCR progress tracking)
  CO273_550/
    ...same structure...
  CO273_579/
    ...same structure...
```

## Components

```
src/
  ocr/
    __init__.py
    extract.py        # PDF → page images (pypdf + Pillow)
    gemini_ocr.py     # Send image to Gemini Vision, get text back
    pipeline.py       # Async orchestrator: extract → OCR → save
    config.py         # Phase 2 settings (concurrency, model, prompts)
scripts/
  run_ocr.py          # CLI entry point
```

### extract.py — PDF Page Extraction

- Read document PDFs from GCS (`{vol}/documents/`)
- Extract each page as a JPEG image using `pypdf` + `Pillow`
- Upload to `{vol}/images/page_NNNN.jpg` in GCS
- Continuous page numbering across documents within a volume
- Track extraction progress in manifest

### gemini_ocr.py — Gemini Vision OCR

- Download page image from GCS
- Send to Gemini Vision API with colonial document prompt
- Parse response into structured result (text + confidence)
- Handle retries with exponential backoff on rate limit (429) errors
- Return plain text + JSON metadata

### pipeline.py — Async Orchestrator

For a given volume:
1. List all page images in `{vol}/images/`
2. Check `ocr_manifest.json` for already-completed pages (resume support)
3. Create async worker pool (configurable concurrency, default 20)
4. Each worker: download image → Gemini OCR → upload `.txt` + `.json` → update manifest
5. Progress logging with ETA

### config.py — Phase 2 Configuration

- Gemini model: Flash (default, cheapest) or Pro (higher quality)
- Concurrency limit (default 20)
- OCR prompt template
- Retry settings (max retries, backoff multiplier)
- Timeout per request (30s)

### scripts/run_ocr.py — CLI

```
python -m scripts.run_ocr extract [--volume CO273_534]     # Extract page images from PDFs
python -m scripts.run_ocr ocr [--volume CO273_534] [--concurrency 20]  # Run Gemini OCR
python -m scripts.run_ocr all [--volume CO273_534]          # Extract + OCR
python -m scripts.run_ocr compare [--volume CO273_534] [--sample 20]   # Compare Gemini vs Gale OCR
```

## OCR Prompt

```
Transcribe all text visible in this image of a 19th-century colonial document.
Preserve original spelling, punctuation, and line breaks.
If text is unclear, mark with [illegible].
Include any printed headers, stamps, or marginal notes.
```

## Output Format

**Per page `.txt`**: Raw transcribed text.

**Per page `.json`**:
```json
{
  "page_num": 1,
  "volume_id": "CO273_534",
  "source_document": "GALE|...",
  "model": "gemini-2.0-flash",
  "text": "transcribed text...",
  "illegible_count": 3,
  "timestamp": "2026-02-28T12:00:00Z"
}
```

## Error Handling & Resume

- **Resume**: `ocr_manifest.json` per volume tracks completed pages. Re-running skips them.
- **Rate limiting**: Exponential backoff on 429 errors. Auto-reduce concurrency if hitting limits.
- **Failed pages**: Logged in manifest `failed` list with error message. Can retry just failures.
- **Timeout**: 30s per Gemini request. Timed-out pages go to failed list.

## Testing

- Unit tests with mock Gemini responses (no real API calls)
- Integration test: extract pages from a small test PDF, verify image output
- Quality check: `compare` CLI command diffs Gemini OCR vs Gale OCR on a sample

## Cost Estimate

- Gemini 2.0 Flash: ~$0.10 per 1M input tokens
- ~2,738 pages × ~1,000 tokens per image ≈ 2.7M tokens ≈ **~$0.27**
- Gemini Pro: ~10x more ≈ **~$2.70**

## Dependencies (New)

```
google-generativeai       # Gemini API client
aiohttp                   # Async HTTP for parallel requests
```

## Risks

| Risk | Mitigation |
|------|------------|
| Gemini rate limiting | Configurable concurrency, exponential backoff |
| Poor OCR on handwritten text | Prompt tuning, compare with Gale baseline |
| Large number of pages | Async parallelism, per-volume processing |
| API cost overrun | Flash model by default, sample before full run |
