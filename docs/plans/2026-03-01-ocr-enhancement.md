# OCR Enhancement Implementation Plan

**Status**: COMPLETE (10/10 tasks, 2026-03-01). 54/54 tests passing.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance the existing Phase 2 OCR pipeline with per-document path alignment, tuned prompt variants for colonial documents, WER/CER evaluation against Gale baseline, and an optional post-correction pass.

**Architecture:** The Phase 1 scraper saves images per-document at `pdfs/{vol}/images/{doc_id}/page_NNNN.jpg` and Gale OCR text at `pdfs/{vol}/text/{doc_id}.txt`. The Phase 2 pipeline currently expects flat `images/page_*.jpg`. This plan fixes that mismatch, adds 3 prompt variants tuned for CO 273 Straits Settlements colonial correspondence (printed, tabular, handwritten), a WER/CER evaluation script comparing Gemini vs Gale OCR, and a flag-gated LLM post-correction pass. All changes modify existing modules; no new architectural layers.

**Tech Stack:** Python 3.14, google-generativeai, jiwer (WER/CER), existing async pipeline

---

### Task 1: Fix OCR pipeline to traverse per-document subdirectories

Phase 1 saves images at `images/{doc_id}/page_NNNN.jpg` (per-document subdirs), but `run_ocr_pipeline` globs `images/page_*.jpg` (flat). Fix the pipeline to walk subdirectories and populate `source_document` in metadata.

**Files:**
- Modify: `src/ocr/pipeline.py:82-104`
- Modify: `src/ocr/manifest.py:7-18`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
def _create_doc_images(images_dir: Path, doc_id: str, count: int) -> None:
    """Create test images in a per-document subdirectory."""
    doc_dir = images_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        img = Image.new("RGB", (100, 100), color=(i * 30, i * 30, i * 30))
        img.save(doc_dir / f"page_{i:04d}.jpg")


@pytest.mark.asyncio
async def test_run_ocr_pipeline_per_doc_subdirs(tmp_path):
    """Pipeline traverses per-document subdirectories under images/."""
    volume_dir = tmp_path / "CO273_534"
    images_dir = volume_dir / "images"

    _create_doc_images(images_dir, "GALE_AAA111", count=2)
    _create_doc_images(images_dir, "GALE_BBB222", count=3)

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Transcribed text"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    with patch("src.ocr.pipeline.get_gemini_model", return_value=mock_model):
        result = await run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id="CO273_534",
            concurrency=2,
        )

    # 5 total pages across 2 documents
    assert len(result["completed_pages"]) == 5

    # OCR output mirrors per-document structure
    ocr_dir = volume_dir / "ocr"
    assert (ocr_dir / "GALE_AAA111" / "page_0001.txt").exists()
    assert (ocr_dir / "GALE_BBB222" / "page_0003.txt").exists()

    # Metadata includes source_document
    import json
    meta = json.loads((ocr_dir / "GALE_AAA111" / "page_0001.json").read_text())
    assert meta["source_document"] == "GALE_AAA111"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py::test_run_ocr_pipeline_per_doc_subdirs -v`
Expected: FAIL (pipeline globs flat `images/page_*.jpg`, finds nothing in subdirs)

**Step 3: Update pipeline to walk per-document subdirectories**

In `src/ocr/pipeline.py`, replace the image discovery logic in `run_ocr_pipeline`:

```python
async def run_ocr_pipeline(
    volume_dir: Path,
    volume_id: str,
    concurrency: int = OCR_CONCURRENCY,
) -> dict:
    """Run OCR pipeline on all page images in a volume directory.

    Supports two image layouts:
    - Per-document: volume_dir/images/{doc_id}/page_NNNN.jpg (Phase 1 output)
    - Flat: volume_dir/images/page_NNNN.jpg (legacy)

    Writes output mirroring input structure:
    - Per-document: volume_dir/ocr/{doc_id}/page_NNNN.{txt,json}
    - Flat: volume_dir/ocr/page_NNNN.{txt,json}
    """
    images_dir = volume_dir / "images"
    ocr_dir = volume_dir / "ocr"
    manifest_path = volume_dir / "ocr_manifest.json"

    # Discover all page images (per-doc subdirs or flat)
    page_entries = _discover_pages(images_dir)
    if not page_entries:
        print(f"[{volume_id}] No images found in {images_dir}")
        return load_ocr_manifest(manifest_path)

    # Load or create manifest
    manifest = load_ocr_manifest(manifest_path)
    manifest["volume_id"] = volume_id
    manifest["total_pages"] = len(page_entries)

    # Determine which pages still need OCR
    completed = set(manifest["completed_pages"])
    pages_to_process = [
        entry for entry in page_entries
        if entry["page_key"] not in completed
    ]

    if not pages_to_process:
        print(f"[{volume_id}] All {len(page_entries)} pages already OCR'd")
        return manifest

    print(f"[{volume_id}] Processing {len(pages_to_process)} pages "
          f"({len(completed)} already done, concurrency={concurrency})")

    model = get_gemini_model()
    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        _ocr_with_retry(
            semaphore=semaphore,
            model=model,
            image_path=entry["image_path"],
            page_num=entry["page_num"],
            volume_id=volume_id,
            source_document=entry["doc_id"],
            output_dir=ocr_dir / entry["doc_id"] if entry["doc_id"] else ocr_dir,
            manifest=manifest,
            manifest_path=manifest_path,
            page_key=entry["page_key"],
        )
        for entry in pages_to_process
    ]

    await asyncio.gather(*tasks)

    save_ocr_manifest(manifest_path, manifest)
    completed = len(manifest["completed_pages"])
    failed = len(manifest["failed_pages"])
    print(f"[{volume_id}] OCR complete: {completed} done, {failed} failed")
    return manifest


def _discover_pages(images_dir: Path) -> list[dict]:
    """Discover page images in per-document subdirs or flat layout.

    Returns list of dicts: {image_path, page_num, doc_id, page_key}.
    page_key is a unique identifier for manifest tracking:
    - Per-doc: "GALE_AAA111/3" (doc_id + page_num)
    - Flat: "3" (just page_num, as string for consistency)
    """
    entries = []

    # Check for per-document subdirectories first
    subdirs = sorted(
        d for d in images_dir.iterdir()
        if d.is_dir() and list(d.glob("page_*.jpg"))
    ) if images_dir.exists() else []

    if subdirs:
        for doc_dir in subdirs:
            doc_id = doc_dir.name
            for img_path in sorted(doc_dir.glob("page_*.jpg")):
                page_num = int(img_path.stem.split("_")[1])
                entries.append({
                    "image_path": img_path,
                    "page_num": page_num,
                    "doc_id": doc_id,
                    "page_key": f"{doc_id}/{page_num}",
                })
    else:
        # Flat layout fallback
        for img_path in sorted(images_dir.glob("page_*.jpg")):
            page_num = int(img_path.stem.split("_")[1])
            entries.append({
                "image_path": img_path,
                "page_num": page_num,
                "doc_id": "",
                "page_key": str(page_num),
            })

    return entries
```

**Step 4: Update `_ocr_with_retry` to accept `source_document` and `page_key`**

```python
async def _ocr_with_retry(
    semaphore: asyncio.Semaphore,
    model,
    image_path: Path,
    page_num: int,
    volume_id: str,
    source_document: str,
    output_dir: Path,
    manifest: dict,
    manifest_path: Path,
    page_key: str = "",
) -> None:
    """OCR a single page with retries and concurrency control."""
    if not page_key:
        page_key = str(page_num)

    async with semaphore:
        last_error = ""
        for attempt in range(1, OCR_MAX_RETRIES + 1):
            success = await ocr_single_page(
                model=model,
                image_path=image_path,
                page_num=page_num,
                volume_id=volume_id,
                source_document=source_document,
                output_dir=output_dir,
            )
            if success:
                update_manifest_page(manifest, page_key, success=True)
                save_ocr_manifest(manifest_path, manifest)
                completed = len(manifest["completed_pages"])
                total = manifest["total_pages"]
                print(f"  [{volume_id}] {page_key} done ({completed}/{total})")
                return

            last_error = f"attempt {attempt} failed"
            if attempt < OCR_MAX_RETRIES:
                wait = OCR_RETRY_BACKOFF ** attempt
                await asyncio.sleep(wait)

        update_manifest_page(manifest, page_key, success=False, error=last_error)
        save_ocr_manifest(manifest_path, manifest)
        print(f"  [{volume_id}] {page_key} FAILED after {OCR_MAX_RETRIES} attempts")
```

**Step 5: Update manifest to use string page_keys instead of int page_nums**

In `src/ocr/manifest.py`, change `update_manifest_page` to accept string keys:

```python
def update_manifest_page(
    manifest: dict,
    page_key: str | int,
    success: bool,
    error: str = "",
) -> None:
    """Update manifest with result of a single page OCR.

    page_key is either an int (flat layout) or "doc_id/page_num" (per-doc).
    Modifies manifest dict in-place.
    """
    # Normalize to consistent type for comparison
    key = str(page_key) if not isinstance(page_key, int) else page_key

    if success:
        if key not in manifest["completed_pages"]:
            manifest["completed_pages"].append(key)
    else:
        manifest["failed_pages"].append({"page": key, "error": error})
```

**Step 6: Update existing tests for new page_key signature**

In `tests/test_ocr_manifest.py`, update `test_update_manifest_page_success`:

```python
def test_update_manifest_page_success():
    """Successful page is added to completed list."""
    manifest = {
        "completed_pages": ["1", "2"],
        "failed_pages": [],
        "total_pages": 10,
    }
    update_manifest_page(manifest, page_key="3", success=True)
    assert "3" in manifest["completed_pages"]


def test_update_manifest_page_per_doc_key():
    """Per-document page key format works."""
    manifest = {
        "completed_pages": [],
        "failed_pages": [],
        "total_pages": 10,
    }
    update_manifest_page(manifest, page_key="GALE_AAA111/1", success=True)
    assert "GALE_AAA111/1" in manifest["completed_pages"]


def test_update_manifest_page_failure():
    """Failed page is added to failed list with error."""
    manifest = {
        "completed_pages": [],
        "failed_pages": [],
        "total_pages": 10,
    }
    update_manifest_page(manifest, page_key="5", success=False, error="timeout")
    assert len(manifest["failed_pages"]) == 1
    assert manifest["failed_pages"][0]["page"] == "5"
```

Also update existing `test_run_ocr_pipeline` and `test_run_ocr_pipeline_resumes` to use per-doc structure or keep as flat layout regression tests.

**Step 7: Run all tests**

Run: `python -m pytest tests/test_pipeline.py tests/test_ocr_manifest.py -v`
Expected: ALL pass

**Step 8: Commit**

```bash
git add src/ocr/pipeline.py src/ocr/manifest.py tests/test_pipeline.py tests/test_ocr_manifest.py
git commit -m "fix OCR pipeline to traverse per-document image subdirectories"
```

---

### Task 2: Add OCR prompt variants for colonial documents

The current prompt is generic. CO 273 Straits Settlements documents include printed correspondence, tabular ledgers, and handwritten annotations. Create 3 tuned prompt variants.

**Files:**
- Modify: `src/ocr/config.py:24-29`
- Modify: `src/ocr/gemini_ocr.py:10,58`
- Test: `tests/test_gemini_ocr.py`

**Step 1: Write the failing test**

Add to `tests/test_gemini_ocr.py`:

```python
from src.ocr.config import OCR_PROMPTS

def test_ocr_prompts_has_variants():
    """OCR_PROMPTS dict has all 3 variant keys."""
    assert "general" in OCR_PROMPTS
    assert "tabular" in OCR_PROMPTS
    assert "handwritten" in OCR_PROMPTS
    for key, prompt in OCR_PROMPTS.items():
        assert isinstance(prompt, str)
        assert len(prompt) > 50


@pytest.mark.asyncio
async def test_ocr_single_page_uses_prompt_variant(tmp_path):
    """ocr_single_page accepts a prompt_key parameter."""
    from PIL import Image
    img = Image.new("RGB", (100, 100))
    img_path = tmp_path / "page_0001.jpg"
    img.save(str(img_path))

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Table text"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await ocr_single_page(
        model=mock_model,
        image_path=img_path,
        page_num=1,
        volume_id="CO273_534",
        source_document="GALE_AAA111",
        output_dir=tmp_path / "ocr",
        prompt_key="tabular",
    )
    assert result is True

    # Verify the tabular prompt was used (not the general one)
    call_args = mock_model.generate_content_async.call_args[0][0]
    prompt_used = call_args[0]
    assert "table" in prompt_used.lower() or "column" in prompt_used.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gemini_ocr.py -k "variants or prompt_variant" -v`
Expected: FAIL (OCR_PROMPTS doesn't exist, prompt_key parameter doesn't exist)

**Step 3: Add prompt variants to config**

Replace the single `OCR_PROMPT` in `src/ocr/config.py`:

```python
# OCR prompts for CO 273 Straits Settlements colonial documents
OCR_PROMPTS = {
    "general": (
        "Transcribe all text in this image of a 19th-century British colonial document "
        "from the CO 273 Straits Settlements Original Correspondence series. "
        "This is official government correspondence — expect formal letterheads, "
        "printed or typed text, dates, signatures, and filing stamps.\n\n"
        "Rules:\n"
        "- Preserve original spelling, capitalisation, punctuation, and line breaks exactly\n"
        "- Reproduce paragraph structure and indentation\n"
        "- Include all printed headers, stamps, folio numbers, and marginal notations\n"
        "- Mark genuinely illegible text with [illegible] — do not guess\n"
        "- If handwritten annotations appear alongside printed text, transcribe both "
        "and prefix handwritten sections with [handwritten:]\n"
        "- For signatures, write [signature: Name] if the name is readable\n"
        "- Preserve archaic spellings (e.g. 'connexion', 'shew', 'gaol') without correction"
    ),

    "tabular": (
        "Transcribe the tabular data in this image of a 19th-century British colonial document "
        "from the CO 273 Straits Settlements series. "
        "This page contains structured data — likely a financial ledger, shipping manifest, "
        "trade return, population register, or statistical table.\n\n"
        "Rules:\n"
        "- Reproduce table structure using Markdown table syntax (| col1 | col2 |)\n"
        "- Preserve all column headers exactly as printed\n"
        "- Align numbers in their correct columns — do not conflate adjacent columns\n"
        "- Use currency symbols as printed ($ for Straits dollars, Rs for rupees)\n"
        "- Preserve row labels, subtotals, and grand totals\n"
        "- Mark illegible cells with [illegible]\n"
        "- If the table spans multiple sections or has footnotes, include them after the table\n"
        "- Include any page headers or titles above the table"
    ),

    "handwritten": (
        "Transcribe all handwritten text in this image of a 19th-century British colonial document "
        "from the CO 273 Straits Settlements series. "
        "This page contains primarily handwritten content — a draft letter, minute sheet, "
        "personal note, or annotation-heavy document.\n\n"
        "Rules:\n"
        "- Transcribe handwriting character-by-character, preserving original spelling\n"
        "- Preserve line breaks as written, including mid-word line breaks with a hyphen\n"
        "- Mark deletions/strikethroughs with [deleted: text] if readable\n"
        "- Mark insertions (above-line text, carets) with [inserted: text]\n"
        "- Mark genuinely illegible words with [illegible] — do not guess\n"
        "- If multiple hands are visible, note transitions with [new hand:]\n"
        "- Include any printed elements (letterhead, stamps) separately, prefixed with [printed:]\n"
        "- For multilingual content, transcribe all languages as written — "
        "note language with [Malay:], [Chinese:], etc."
    ),
}

# Default prompt (backward compatibility)
OCR_PROMPT = OCR_PROMPTS["general"]
```

**Step 4: Update `ocr_single_page` to accept prompt_key**

In `src/ocr/gemini_ocr.py`, add `prompt_key` parameter:

```python
from src.ocr.config import OCR_PROMPTS, OCR_PROMPT, GEMINI_MODEL


async def ocr_single_page(
    model,
    image_path: Path,
    page_num: int,
    volume_id: str,
    source_document: str,
    output_dir: Path,
    prompt_key: str = "general",
) -> bool:
    """Run Gemini Vision OCR on a single page image."""
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        prompt = OCR_PROMPTS.get(prompt_key, OCR_PROMPT)
        img = Image.open(image_path)
        response = await model.generate_content_async([prompt, img])
        text = response.text

        txt_path = output_dir / f"page_{page_num:04d}.txt"
        txt_path.write_text(text, encoding="utf-8")

        metadata = build_page_metadata(
            page_num=page_num,
            volume_id=volume_id,
            source_document=source_document,
            text=text,
            model=GEMINI_MODEL,
        )
        metadata["prompt_key"] = prompt_key
        json_path = output_dir / f"page_{page_num:04d}.json"
        json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return True

    except Exception as e:
        print(f"  OCR failed for page {page_num}: {e}")
        return False
```

**Step 5: Run all OCR tests**

Run: `python -m pytest tests/test_gemini_ocr.py -v`
Expected: ALL pass

**Step 6: Commit**

```bash
git add src/ocr/config.py src/ocr/gemini_ocr.py tests/test_gemini_ocr.py
git commit -m "add 3 OCR prompt variants tuned for colonial documents"
```

---

### Task 3: Add jiwer dependency for WER/CER metrics

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add jiwer to dependencies**

```toml
dependencies = [
    "selenium>=4.15.0",
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "pypdf>=3.17.0",
    "Pillow>=10.0.0",
    "google-cloud-storage>=2.14.0",
    "python-dotenv>=1.0.0",
    "google-generativeai>=0.8.0",
    "jiwer>=3.0.0",
]
```

**Step 2: Install**

Run: `pip install -e ".[dev]"`
Expected: jiwer installs successfully

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "add jiwer dependency for WER/CER evaluation"
```

---

### Task 4: Create evaluation script (WER/CER vs Gale baseline)

The Gale baseline OCR text is saved by the scraper at `pdfs/{vol}/text/{doc_id}.txt` with page markers `--- Page N ---`. The Gemini OCR output is at `pdfs/{vol}/ocr/{doc_id}/page_NNNN.txt`. Compare them.

**Files:**
- Create: `src/ocr/evaluate.py`
- Create: `tests/test_evaluate.py`

**Step 1: Write the failing tests**

```python
# tests/test_evaluate.py
import pytest
from pathlib import Path

from src.ocr.evaluate import (
    parse_gale_text,
    load_gemini_page,
    compute_page_metrics,
    evaluate_document,
)


def test_parse_gale_text_splits_pages():
    """Gale text file is parsed into per-page dict."""
    gale_text = (
        "--- Page 1 ---\n"
        "First page content here.\n"
        "\n"
        "--- Page 2 ---\n"
        "Second page with more text.\n"
    )
    pages = parse_gale_text(gale_text)
    assert len(pages) == 2
    assert pages[1] == "First page content here."
    assert pages[2] == "Second page with more text."


def test_parse_gale_text_empty():
    """Empty text returns empty dict."""
    assert parse_gale_text("") == {}


def test_compute_page_metrics():
    """WER and CER computed between reference and hypothesis."""
    ref = "the cat sat on the mat"
    hyp = "the cat set on the mat"
    metrics = compute_page_metrics(ref, hyp)
    assert "wer" in metrics
    assert "cer" in metrics
    assert 0 < metrics["wer"] < 1  # one word wrong out of 6
    assert 0 < metrics["cer"] < 1  # one char wrong


def test_compute_page_metrics_identical():
    """Perfect match gives 0 WER and 0 CER."""
    text = "hello world"
    metrics = compute_page_metrics(text, text)
    assert metrics["wer"] == 0.0
    assert metrics["cer"] == 0.0


def test_evaluate_document(tmp_path):
    """End-to-end evaluation of one document."""
    # Set up Gale baseline
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    gale_text = "--- Page 1 ---\nthe cat sat on the mat\n\n--- Page 2 ---\nhello world\n"
    (text_dir / "GALE_AAA111.txt").write_text(gale_text, encoding="utf-8")

    # Set up Gemini OCR output
    ocr_dir = tmp_path / "ocr" / "GALE_AAA111"
    ocr_dir.mkdir(parents=True)
    (ocr_dir / "page_0001.txt").write_text("the cat set on the mat", encoding="utf-8")
    (ocr_dir / "page_0002.txt").write_text("hello world", encoding="utf-8")

    result = evaluate_document(
        doc_id="GALE_AAA111",
        text_dir=text_dir,
        ocr_dir=tmp_path / "ocr",
    )

    assert result["doc_id"] == "GALE_AAA111"
    assert result["pages_compared"] == 2
    assert len(result["page_metrics"]) == 2
    # Page 1 has error, page 2 is perfect
    assert result["page_metrics"][1]["wer"] > 0
    assert result["page_metrics"][2]["wer"] == 0.0
    assert "avg_wer" in result
    assert "avg_cer" in result
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_evaluate.py -v`
Expected: FAIL (module not found)

**Step 3: Write the evaluate module**

```python
# src/ocr/evaluate.py
"""Evaluate Gemini OCR output against Gale OCR baseline using WER/CER."""
import json
import re
from pathlib import Path

from jiwer import wer, cer


def parse_gale_text(text: str) -> dict[int, str]:
    """Parse Gale OCR text file into per-page dict.

    Gale text format:
        --- Page 1 ---
        page text here...

        --- Page 2 ---
        more text...

    Returns {page_num: text_content}.
    """
    if not text.strip():
        return {}

    pages = {}
    parts = re.split(r"---\s*Page\s+(\d+)\s*---", text)

    # parts[0] is before first marker (empty), then alternating: page_num, text
    for i in range(1, len(parts), 2):
        page_num = int(parts[i])
        page_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if page_text:
            pages[page_num] = page_text

    return pages


def load_gemini_page(ocr_dir: Path, doc_id: str, page_num: int) -> str | None:
    """Load Gemini OCR text for a specific page.

    Looks at ocr_dir/{doc_id}/page_NNNN.txt.
    Returns None if file doesn't exist.
    """
    path = ocr_dir / doc_id / f"page_{page_num:04d}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None


def compute_page_metrics(reference: str, hypothesis: str) -> dict:
    """Compute WER and CER between reference and hypothesis texts.

    Returns dict with wer, cer, ref_words, hyp_words.
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()

    if not ref_words:
        return {"wer": 0.0, "cer": 0.0, "ref_words": 0, "hyp_words": len(hyp_words)}

    w = wer(reference, hypothesis)
    c = cer(reference, hypothesis)

    return {
        "wer": round(w, 4),
        "cer": round(c, 4),
        "ref_words": len(ref_words),
        "hyp_words": len(hyp_words),
    }


def evaluate_document(
    doc_id: str,
    text_dir: Path,
    ocr_dir: Path,
) -> dict:
    """Evaluate Gemini OCR vs Gale baseline for one document.

    Args:
        doc_id: Sanitized document ID (e.g., "GALE_AAA111").
        text_dir: Directory containing Gale baseline text files.
        ocr_dir: Parent directory containing per-doc OCR output subdirs.

    Returns:
        Dict with doc_id, pages_compared, page_metrics, avg_wer, avg_cer.
    """
    gale_path = text_dir / f"{doc_id}.txt"
    if not gale_path.exists():
        return {
            "doc_id": doc_id,
            "error": f"Gale baseline not found: {gale_path}",
            "pages_compared": 0,
            "page_metrics": {},
            "avg_wer": None,
            "avg_cer": None,
        }

    gale_pages = parse_gale_text(gale_path.read_text(encoding="utf-8"))
    page_metrics = {}

    for page_num, gale_text in sorted(gale_pages.items()):
        gemini_text = load_gemini_page(ocr_dir, doc_id, page_num)
        if gemini_text is None:
            page_metrics[page_num] = {"error": "Gemini OCR not found"}
            continue

        metrics = compute_page_metrics(gale_text, gemini_text)
        page_metrics[page_num] = metrics

    # Compute averages (exclude pages with errors)
    valid = [m for m in page_metrics.values() if "wer" in m]
    avg_wer = sum(m["wer"] for m in valid) / len(valid) if valid else None
    avg_cer = sum(m["cer"] for m in valid) / len(valid) if valid else None

    return {
        "doc_id": doc_id,
        "pages_compared": len(valid),
        "page_metrics": page_metrics,
        "avg_wer": round(avg_wer, 4) if avg_wer is not None else None,
        "avg_cer": round(avg_cer, 4) if avg_cer is not None else None,
    }


def evaluate_volume(
    volume_id: str,
    volume_dir: Path,
    sample: int | None = None,
) -> dict:
    """Evaluate all documents in a volume.

    Args:
        volume_id: Volume identifier.
        volume_dir: Path to volume directory (contains text/ and ocr/).
        sample: If set, only evaluate this many documents (random sample).

    Returns:
        Dict with volume_id, documents (list of doc results), overall avg_wer/cer.
    """
    text_dir = volume_dir / "text"
    ocr_dir = volume_dir / "ocr"

    if not text_dir.exists():
        return {"volume_id": volume_id, "error": "No text/ directory (Gale baseline)"}
    if not ocr_dir.exists():
        return {"volume_id": volume_id, "error": "No ocr/ directory (Gemini output)"}

    # Find all documents with both baseline and OCR
    doc_ids = sorted(
        f.stem for f in text_dir.glob("*.txt")
        if (ocr_dir / f.stem).is_dir()
    )

    if sample and sample < len(doc_ids):
        import random
        doc_ids = random.sample(doc_ids, sample)

    doc_results = []
    for doc_id in doc_ids:
        result = evaluate_document(doc_id, text_dir, ocr_dir)
        doc_results.append(result)
        print(f"  {doc_id}: WER={result['avg_wer']}, CER={result['avg_cer']} "
              f"({result['pages_compared']} pages)")

    # Overall averages
    valid = [d for d in doc_results if d["avg_wer"] is not None]
    overall_wer = sum(d["avg_wer"] for d in valid) / len(valid) if valid else None
    overall_cer = sum(d["avg_cer"] for d in valid) / len(valid) if valid else None

    return {
        "volume_id": volume_id,
        "documents": doc_results,
        "total_documents": len(doc_results),
        "overall_wer": round(overall_wer, 4) if overall_wer is not None else None,
        "overall_cer": round(overall_cer, 4) if overall_cer is not None else None,
    }
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_evaluate.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
git add src/ocr/evaluate.py tests/test_evaluate.py
git commit -m "add WER/CER evaluation script for Gemini vs Gale OCR"
```

---

### Task 5: Add `evaluate` CLI command

**Files:**
- Modify: `scripts/run_ocr.py`

**Step 1: Add evaluate command**

Add to `scripts/run_ocr.py`:

```python
from src.ocr.evaluate import evaluate_volume


def cmd_evaluate(args):
    """Evaluate Gemini OCR quality against Gale baseline."""
    import json as json_mod

    print("=== Evaluating OCR Quality (Gemini vs Gale) ===")

    for volume_id in get_volume_ids(args):
        volume_dir = DOWNLOAD_DIR / volume_id
        print(f"\n[{volume_id}] Evaluating...")

        result = evaluate_volume(
            volume_id=volume_id,
            volume_dir=volume_dir,
            sample=args.sample,
        )

        if "error" in result:
            print(f"[{volume_id}] Error: {result['error']}")
            continue

        print(f"\n[{volume_id}] Overall: WER={result['overall_wer']}, "
              f"CER={result['overall_cer']} "
              f"({result['total_documents']} documents)")

        # Save report
        report_path = volume_dir / "eval_report.json"
        report_path.write_text(
            json_mod.dumps(result, indent=2), encoding="utf-8"
        )
        print(f"[{volume_id}] Report saved to {report_path}")

    print("\n=== Evaluation complete ===")
```

Add to the CLI parser in `main()`:

```python
    # evaluate
    sp_eval = subparsers.add_parser("evaluate", help="Compare Gemini vs Gale OCR quality")
    sp_eval.add_argument("--volume", type=str, help="Process only this volume")
    sp_eval.add_argument("--sample", type=int, default=None, help="Evaluate only N documents")
    sp_eval.set_defaults(func=cmd_evaluate)
```

**Step 2: Verify CLI help**

Run: `python -m scripts.run_ocr evaluate --help`
Expected: Shows usage with --volume and --sample flags

**Step 3: Commit**

```bash
git add scripts/run_ocr.py
git commit -m "add evaluate CLI command for OCR quality comparison"
```

---

### Task 6: Add post-correction pass

Optional second Gemini call that takes raw OCR output and corrects obvious errors. Flag-gated with `--correct`.

**Files:**
- Create: `src/ocr/correct.py`
- Create: `tests/test_correct.py`
- Modify: `src/ocr/pipeline.py`

**Step 1: Write the failing tests**

```python
# tests/test_correct.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from src.ocr.correct import correct_single_page, CORRECTION_PROMPT


def test_correction_prompt_exists():
    """Correction prompt is defined."""
    assert isinstance(CORRECTION_PROMPT, str)
    assert len(CORRECTION_PROMPT) > 50


@pytest.mark.asyncio
async def test_correct_single_page(tmp_path):
    """Correction pass reads OCR text and writes corrected version."""
    ocr_dir = tmp_path / "ocr" / "GALE_AAA111"
    ocr_dir.mkdir(parents=True)
    (ocr_dir / "page_0001.txt").write_text(
        "Tle Governor of tbe Straits Settlements", encoding="utf-8"
    )

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "The Governor of the Straits Settlements"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await correct_single_page(
        model=mock_model,
        page_txt_path=ocr_dir / "page_0001.txt",
    )
    assert result is True

    corrected = (ocr_dir / "page_0001.txt").read_text(encoding="utf-8")
    assert corrected == "The Governor of the Straits Settlements"

    # Original preserved as backup
    assert (ocr_dir / "page_0001.raw.txt").exists()


@pytest.mark.asyncio
async def test_correct_single_page_skips_if_corrected(tmp_path):
    """Skips correction if .raw.txt backup already exists."""
    ocr_dir = tmp_path / "ocr"
    ocr_dir.mkdir(parents=True)
    (ocr_dir / "page_0001.txt").write_text("corrected text", encoding="utf-8")
    (ocr_dir / "page_0001.raw.txt").write_text("raw text", encoding="utf-8")

    mock_model = MagicMock()
    result = await correct_single_page(
        model=mock_model,
        page_txt_path=ocr_dir / "page_0001.txt",
    )
    assert result is True
    # Model should not have been called
    mock_model.generate_content_async.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_correct.py -v`
Expected: FAIL (module not found)

**Step 3: Write the correction module**

```python
# src/ocr/correct.py
"""Post-correction pass for OCR output using LLM."""
from pathlib import Path


CORRECTION_PROMPT = (
    "You are a proofreader for OCR output of 19th-century British colonial documents. "
    "The text below was machine-transcribed from a scanned page of CO 273 "
    "Straits Settlements Original Correspondence.\n\n"
    "Fix only clear OCR errors:\n"
    "- Character substitutions (e.g. 'tbe' -> 'the', 'tle' -> 'the', 'rn' -> 'm')\n"
    "- Missing or extra spaces between words\n"
    "- Broken words across line endings that should be joined\n"
    "- Garbled sequences that are clearly a known English word\n\n"
    "Do NOT change:\n"
    "- Archaic spellings (connexion, shew, gaol) -- these are correct for the era\n"
    "- Names of people, places, or ships -- even if unfamiliar\n"
    "- [illegible] markers -- leave them as-is\n"
    "- Formatting, line breaks, or punctuation style\n"
    "- Table structure (Markdown tables)\n\n"
    "Return ONLY the corrected text. No commentary.\n\n"
    "---\n"
)


async def correct_single_page(
    model,
    page_txt_path: Path,
) -> bool:
    """Run post-correction on a single OCR'd page.

    Reads the existing .txt file, sends to LLM for correction,
    saves corrected text back. Original is preserved as .raw.txt.

    Returns True on success or skip (already corrected).
    """
    raw_backup = page_txt_path.with_suffix(".raw.txt")

    # Skip if already corrected
    if raw_backup.exists():
        return True

    if not page_txt_path.exists():
        return False

    try:
        raw_text = page_txt_path.read_text(encoding="utf-8")

        if not raw_text.strip():
            return True

        prompt = CORRECTION_PROMPT + raw_text
        response = await model.generate_content_async(prompt)
        corrected = response.text

        # Save backup of original
        raw_backup.write_text(raw_text, encoding="utf-8")

        # Overwrite with corrected version
        page_txt_path.write_text(corrected, encoding="utf-8")

        return True

    except Exception as e:
        print(f"  Correction failed for {page_txt_path.name}: {e}")
        return False
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_correct.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/ocr/correct.py tests/test_correct.py
git commit -m "add LLM post-correction pass for OCR output"
```

---

### Task 7: Wire post-correction into pipeline and CLI

**Files:**
- Modify: `src/ocr/pipeline.py`
- Modify: `scripts/run_ocr.py`
- Test: `tests/test_pipeline.py`

**Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
@pytest.mark.asyncio
async def test_run_ocr_pipeline_with_correction(tmp_path):
    """Pipeline runs post-correction when correct=True."""
    volume_dir = tmp_path / "CO273_534"
    images_dir = volume_dir / "images" / "GALE_AAA111"
    images_dir.mkdir(parents=True)
    img = Image.new("RGB", (100, 100))
    img.save(images_dir / "page_0001.jpg")

    mock_model = MagicMock()
    # First call: OCR
    # Second call: correction
    ocr_response = MagicMock()
    ocr_response.text = "Tle Governor"
    correct_response = MagicMock()
    correct_response.text = "The Governor"
    mock_model.generate_content_async = AsyncMock(
        side_effect=[ocr_response, correct_response]
    )

    with patch("src.ocr.pipeline.get_gemini_model", return_value=mock_model):
        result = await run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id="CO273_534",
            concurrency=1,
            correct=True,
        )

    assert len(result["completed_pages"]) == 1

    ocr_dir = volume_dir / "ocr" / "GALE_AAA111"
    # Corrected text is in .txt
    assert (ocr_dir / "page_0001.txt").read_text(encoding="utf-8") == "The Governor"
    # Raw backup exists
    assert (ocr_dir / "page_0001.raw.txt").exists()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py::test_run_ocr_pipeline_with_correction -v`
Expected: FAIL (`correct` parameter doesn't exist)

**Step 3: Add correction pass to pipeline**

In `src/ocr/pipeline.py`, add to `run_ocr_pipeline`:

```python
from src.ocr.correct import correct_single_page


async def run_ocr_pipeline(
    volume_dir: Path,
    volume_id: str,
    concurrency: int = OCR_CONCURRENCY,
    correct: bool = False,
) -> dict:
    # ... existing code through asyncio.gather ...

    # Post-correction pass (optional)
    if correct:
        print(f"[{volume_id}] Running post-correction pass...")
        ocr_files = sorted(ocr_dir.rglob("page_*.txt"))
        # Exclude .raw.txt backups
        ocr_files = [f for f in ocr_files if not f.name.endswith(".raw.txt")]

        correction_tasks = [
            _correct_with_semaphore(semaphore, model, txt_path)
            for txt_path in ocr_files
        ]
        await asyncio.gather(*correction_tasks)
        print(f"[{volume_id}] Correction complete")

    save_ocr_manifest(manifest_path, manifest)
    # ... rest of function ...


async def _correct_with_semaphore(
    semaphore: asyncio.Semaphore,
    model,
    txt_path: Path,
) -> None:
    """Run correction on a single page with concurrency control."""
    async with semaphore:
        await correct_single_page(model, txt_path)
```

**Step 4: Add `--correct` flag to CLI**

In `scripts/run_ocr.py`, add to `sp_ocr` and `sp_all`:

```python
    sp_ocr.add_argument("--correct", action="store_true", help="Run post-correction pass after OCR")
    sp_all.add_argument("--correct", action="store_true", help="Run post-correction pass after OCR")
```

And pass it through in `cmd_ocr`:

```python
        asyncio.run(run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id=volume_id,
            concurrency=args.concurrency,
            correct=getattr(args, 'correct', False),
        ))
```

**Step 5: Run all tests**

Run: `python -m pytest tests/test_pipeline.py tests/test_correct.py -v`
Expected: ALL pass

**Step 6: Commit**

```bash
git add src/ocr/pipeline.py src/ocr/correct.py scripts/run_ocr.py tests/test_pipeline.py
git commit -m "wire post-correction pass into pipeline with --correct flag"
```

---

### Task 8: Add `--prompt` CLI flag and prompt variant passthrough

Allow selecting prompt variant from CLI. Wire it through pipeline to `ocr_single_page`.

**Files:**
- Modify: `scripts/run_ocr.py`
- Modify: `src/ocr/pipeline.py`

**Step 1: Add `--prompt` flag to CLI**

In `scripts/run_ocr.py`:

```python
    sp_ocr.add_argument("--prompt", type=str, default="general",
                        choices=["general", "tabular", "handwritten"],
                        help="OCR prompt variant (default: general)")
    sp_all.add_argument("--prompt", type=str, default="general",
                        choices=["general", "tabular", "handwritten"],
                        help="OCR prompt variant (default: general)")
```

Pass through in `cmd_ocr`:

```python
        asyncio.run(run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id=volume_id,
            concurrency=args.concurrency,
            correct=getattr(args, 'correct', False),
            prompt_key=getattr(args, 'prompt', 'general'),
        ))
```

**Step 2: Add prompt_key to pipeline**

In `src/ocr/pipeline.py`, add `prompt_key` parameter to `run_ocr_pipeline` and `_ocr_with_retry`, passing it through to `ocr_single_page`:

```python
async def run_ocr_pipeline(
    volume_dir: Path,
    volume_id: str,
    concurrency: int = OCR_CONCURRENCY,
    correct: bool = False,
    prompt_key: str = "general",
) -> dict:
    # ... pass prompt_key to _ocr_with_retry ...


async def _ocr_with_retry(
    ...,
    prompt_key: str = "general",
) -> None:
    # ... pass prompt_key to ocr_single_page ...
            success = await ocr_single_page(
                ...,
                prompt_key=prompt_key,
            )
```

**Step 3: Run all tests**

Run: `python -m pytest tests/ --ignore=tests/test_gcs_upload.py -v`
Expected: ALL pass

**Step 4: Commit**

```bash
git add scripts/run_ocr.py src/ocr/pipeline.py
git commit -m "add --prompt CLI flag for prompt variant selection"
```

---

### Task 9: A/B testing script for prompt comparison

Create a script to run all 3 prompt variants on a sample of pages, evaluate each with WER/CER, and report which performs best.

**Files:**
- Create: `scripts/ab_test_prompts.py`

**Step 1: Write the A/B testing script**

```python
# scripts/ab_test_prompts.py
"""A/B test OCR prompt variants on a sample of pages.

Usage:
    python -m scripts.ab_test_prompts --volume CO273_534 --sample 10

Runs all 3 prompt variants on the same sample pages, computes WER/CER
for each, and reports which variant performs best.
"""
import argparse
import asyncio
import json
import shutil
from pathlib import Path

from src.config import DOWNLOAD_DIR
from src.ocr.config import OCR_PROMPTS
from src.ocr.evaluate import evaluate_document
from src.ocr.gemini_ocr import ocr_single_page
from src.ocr.pipeline import get_gemini_model, _discover_pages


async def ab_test(
    volume_dir: Path,
    volume_id: str,
    sample: int = 10,
    concurrency: int = 5,
) -> dict:
    """Run A/B test across all prompt variants."""
    images_dir = volume_dir / "images"
    text_dir = volume_dir / "text"
    ab_dir = volume_dir / "ab_test"

    pages = _discover_pages(images_dir)
    if not pages:
        print(f"No images found in {images_dir}")
        return {}

    # Sample pages
    if sample < len(pages):
        import random
        pages = random.sample(pages, sample)

    print(f"A/B testing {len(pages)} pages with {len(OCR_PROMPTS)} prompt variants")

    model = get_gemini_model()
    semaphore = asyncio.Semaphore(concurrency)
    results = {}

    for variant_name in OCR_PROMPTS:
        variant_dir = ab_dir / variant_name
        print(f"\n--- Variant: {variant_name} ---")

        for entry in pages:
            out_dir = variant_dir / entry["doc_id"] if entry["doc_id"] else variant_dir

            async with semaphore:
                await ocr_single_page(
                    model=model,
                    image_path=entry["image_path"],
                    page_num=entry["page_num"],
                    volume_id=volume_id,
                    source_document=entry["doc_id"],
                    output_dir=out_dir,
                    prompt_key=variant_name,
                )

        # Evaluate this variant
        doc_ids = set(e["doc_id"] for e in pages if e["doc_id"])
        variant_wer = []
        variant_cer = []

        for doc_id in doc_ids:
            eval_result = evaluate_document(doc_id, text_dir, variant_dir)
            if eval_result["avg_wer"] is not None:
                variant_wer.append(eval_result["avg_wer"])
                variant_cer.append(eval_result["avg_cer"])

        avg_wer = sum(variant_wer) / len(variant_wer) if variant_wer else None
        avg_cer = sum(variant_cer) / len(variant_cer) if variant_cer else None

        results[variant_name] = {
            "avg_wer": round(avg_wer, 4) if avg_wer else None,
            "avg_cer": round(avg_cer, 4) if avg_cer else None,
            "pages_tested": len(pages),
        }
        print(f"  WER={avg_wer}, CER={avg_cer}")

    # Report
    print("\n=== A/B Test Results ===")
    for name, r in sorted(results.items(), key=lambda x: x[1].get("avg_wer") or 999):
        print(f"  {name:15s}  WER={r['avg_wer']}  CER={r['avg_cer']}")

    best = min(results, key=lambda k: results[k].get("avg_wer") or 999)
    print(f"\nBest variant: {best}")

    # Save results
    report_path = ab_dir / "ab_results.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to {report_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="A/B test OCR prompt variants")
    parser.add_argument("--volume", type=str, required=True, help="Volume to test")
    parser.add_argument("--sample", type=int, default=10, help="Number of pages to test")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent requests")
    args = parser.parse_args()

    volume_dir = DOWNLOAD_DIR / args.volume
    asyncio.run(ab_test(volume_dir, args.volume, args.sample, args.concurrency))


if __name__ == "__main__":
    main()
```

**Step 2: Verify script shows help**

Run: `python -m scripts.ab_test_prompts --help`
Expected: Shows usage with --volume, --sample, --concurrency

**Step 3: Commit**

```bash
git add scripts/ab_test_prompts.py
git commit -m "add A/B testing script for OCR prompt variants"
```

---

### Task 10: Run full test suite and verify

**Step 1: Run all tests**

Run: `python -m pytest tests/ --ignore=tests/test_gcs_upload.py -v`
Expected: ALL pass (existing + new tests)

**Step 2: Verify all CLI commands**

```bash
python -m scripts.run_ocr --help
python -m scripts.run_ocr ocr --help
python -m scripts.run_ocr evaluate --help
python -m scripts.ab_test_prompts --help
```

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "verify all OCR enhancement tests pass"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Per-doc subdirectory traversal | pipeline.py, manifest.py |
| 2 | 3 prompt variants (general/tabular/handwritten) | config.py, gemini_ocr.py |
| 3 | Add jiwer dependency | pyproject.toml |
| 4 | WER/CER evaluation script | evaluate.py |
| 5 | `evaluate` CLI command | run_ocr.py |
| 6 | Post-correction pass | correct.py |
| 7 | Wire correction into pipeline + `--correct` flag | pipeline.py, run_ocr.py |
| 8 | `--prompt` CLI flag | run_ocr.py, pipeline.py |
| 9 | A/B testing script | ab_test_prompts.py |
| 10 | Full verification | all |

## Usage After Implementation

```bash
# Standard OCR with enhanced general prompt
python -m scripts.run_ocr ocr --volume CO273_534 --local

# OCR with post-correction
python -m scripts.run_ocr ocr --volume CO273_534 --local --correct

# OCR with tabular prompt for ledger-heavy volume
python -m scripts.run_ocr ocr --volume CO273_550 --local --prompt tabular

# Evaluate Gemini vs Gale quality
python -m scripts.run_ocr evaluate --volume CO273_534

# A/B test prompt variants on 20 sample pages
python -m scripts.ab_test_prompts --volume CO273_534 --sample 20

# Full pipeline: OCR + correction + evaluation
python -m scripts.run_ocr ocr --volume CO273_534 --local --correct
python -m scripts.run_ocr evaluate --volume CO273_534
```

## Not in scope (deferred)

- **Gold-standard test set curation**: Requires real downloaded data. After first scrape run, manually verify 10-20 pages to create `data/gold/` reference set. Then re-run A/B tests against gold rather than Gale baseline.
- **Automatic prompt detection**: Classify each page as printed/tabular/handwritten and auto-select prompt. Deferred until we see real data and understand the distribution.
- **CER-weighted confidence scores**: Per-page confidence scoring based on CER for downstream quality filtering.
