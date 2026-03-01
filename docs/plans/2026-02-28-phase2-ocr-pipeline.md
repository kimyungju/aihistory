# Phase 2: Enhanced OCR Pipeline — Implementation Plan

**Status**: COMPLETE (9/9 tasks, 2026-02-28). Extended by [OCR Enhancement Plan](2026-03-01-ocr-enhancement.md).

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an async pipeline that extracts page images from Phase 1's document PDFs in GCS, runs Gemini Vision OCR on each page, and writes enhanced text + metadata back to GCS with resume support.

**Architecture:** GCS-native pipeline. Read document PDFs from GCS → extract pages as JPEG images → upload images to GCS → async workers send images to Gemini Vision → write OCR text + JSON metadata back to GCS. Per-volume `ocr_manifest.json` tracks progress for resume.

**Tech Stack:** Python 3.11+, google-cloud-storage, google-generativeai, asyncio, pypdf, Pillow

---

### Task 1: Add Phase 2 Dependencies

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`

**Step 1: Add new dependencies to pyproject.toml**

Add `google-generativeai` to dependencies list in `pyproject.toml`:

```toml
[project]
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
]
```

**Step 2: Add Gemini API key to .env.example**

```
# Google Cloud Storage
GCS_BUCKET=aihistory-co273
GCS_KEY_PATH=path/to/service-account-key.json
GCS_REGION=asia-southeast1

# Gale (filled after network inspection)
GALE_BASE_URL=https://go-gale-com.libproxy1.nus.edu.sg

# Gemini (Phase 2 OCR)
GEMINI_API_KEY=your-gemini-api-key-here
```

**Step 3: Install updated dependencies**

Run:
```bash
source .venv/Scripts/activate
pip install -e ".[dev]"
```
Expected: installs `google-generativeai` successfully

**Step 4: Commit**

```bash
git add pyproject.toml .env.example
git commit -m "add Phase 2 OCR dependencies"
```

---

### Task 2: Phase 2 Configuration Module

**Files:**
- Create: `src/ocr/__init__.py`
- Create: `src/ocr/config.py`

**Step 1: Create empty init**

Create `src/ocr/__init__.py` as an empty file.

**Step 2: Create OCR config**

```python
# src/ocr/config.py
"""Phase 2 OCR pipeline configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

# Gemini settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Concurrency
OCR_CONCURRENCY = int(os.getenv("OCR_CONCURRENCY", "20"))

# Retry settings
OCR_MAX_RETRIES = 3
OCR_RETRY_BACKOFF = 2.0  # exponential backoff multiplier
OCR_TIMEOUT = 30  # seconds per Gemini request

# Image extraction
IMAGE_FORMAT = "JPEG"
IMAGE_QUALITY = 95  # JPEG quality (1-100)

# OCR prompt for colonial documents
OCR_PROMPT = (
    "Transcribe all text visible in this image of a 19th-century colonial document. "
    "Preserve original spelling, punctuation, and line breaks. "
    "If text is unclear, mark with [illegible]. "
    "Include any printed headers, stamps, or marginal notes."
)
```

**Step 3: Commit**

```bash
git add src/ocr/__init__.py src/ocr/config.py
git commit -m "add Phase 2 OCR config module"
```

---

### Task 3: PDF Page Extraction Module

**Files:**
- Create: `tests/test_extract.py`
- Create: `src/ocr/extract.py`

**Step 1: Write the failing tests**

```python
# tests/test_extract.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
from pypdf import PdfWriter

from src.ocr.extract import extract_pages_from_pdf, extract_volume_pages


def _create_test_pdf(path: Path, num_pages: int = 3) -> None:
    """Create a minimal PDF with blank pages for testing."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)  # Letter size
    with open(path, "wb") as f:
        writer.write(f)


def test_extract_pages_from_pdf(tmp_path):
    """Pages are extracted as JPEG images from a PDF."""
    pdf_path = tmp_path / "test.pdf"
    output_dir = tmp_path / "images"
    _create_test_pdf(pdf_path, num_pages=3)

    pages = extract_pages_from_pdf(pdf_path, output_dir, start_page_num=1)

    assert pages == 3
    assert len(list(output_dir.glob("*.jpg"))) == 3
    assert (output_dir / "page_0001.jpg").exists()
    assert (output_dir / "page_0002.jpg").exists()
    assert (output_dir / "page_0003.jpg").exists()


def test_extract_pages_continuous_numbering(tmp_path):
    """Page numbering continues from start_page_num."""
    pdf_path = tmp_path / "test.pdf"
    output_dir = tmp_path / "images"
    _create_test_pdf(pdf_path, num_pages=2)

    pages = extract_pages_from_pdf(pdf_path, output_dir, start_page_num=10)

    assert (output_dir / "page_0010.jpg").exists()
    assert (output_dir / "page_0011.jpg").exists()


def test_extract_volume_pages(tmp_path):
    """All PDFs in a volume's documents/ dir are extracted with continuous numbering."""
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()
    images_dir = tmp_path / "images"

    _create_test_pdf(docs_dir / "GALE_AAA111.pdf", num_pages=2)
    _create_test_pdf(docs_dir / "GALE_BBB222.pdf", num_pages=3)

    result = extract_volume_pages(docs_dir, images_dir)

    assert result["total_pages"] == 5
    assert len(result["doc_page_map"]) == 2
    assert len(list(images_dir.glob("*.jpg"))) == 5
    # Continuous numbering: 1-2 from first PDF, 3-5 from second
    assert (images_dir / "page_0001.jpg").exists()
    assert (images_dir / "page_0005.jpg").exists()
```

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_extract.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ocr.extract'`

**Step 3: Write the extract module**

```python
# src/ocr/extract.py
"""Extract page images from document PDFs.

Reads multi-page document PDFs (from Phase 1) and extracts each page
as a JPEG image. Supports continuous page numbering across documents.
"""
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from src.ocr.config import IMAGE_FORMAT, IMAGE_QUALITY


def extract_pages_from_pdf(
    pdf_path: Path,
    output_dir: Path,
    start_page_num: int = 1,
) -> int:
    """Extract all pages from a PDF as JPEG images.

    Args:
        pdf_path: Path to the PDF file.
        output_dir: Directory to save extracted images.
        start_page_num: Starting page number for filenames.

    Returns:
        Number of pages extracted.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    num_pages = len(reader.pages)

    for i, page in enumerate(reader.pages):
        page_num = start_page_num + i

        # Extract page as image via rendering
        # pypdf doesn't render pages directly; convert page to image via
        # extracting embedded images or using pdf2image-style approach.
        # For PDFs with embedded images (like scanned docs), extract the image.
        images = page.images
        if images:
            # Use the first (usually only) image on the page
            img_data = images[0].data
            img_path = output_dir / f"page_{page_num:04d}.jpg"
            with open(img_path, "wb") as f:
                f.write(img_data)
        else:
            # Blank or text-only page — create a placeholder image
            img = Image.new("RGB", (612, 792), color=(255, 255, 255))
            img_path = output_dir / f"page_{page_num:04d}.jpg"
            img.save(str(img_path), IMAGE_FORMAT, quality=IMAGE_QUALITY)

    return num_pages


def extract_volume_pages(
    docs_dir: Path,
    images_dir: Path,
) -> dict:
    """Extract pages from all document PDFs in a volume.

    Processes PDFs in sorted filename order with continuous page numbering.

    Args:
        docs_dir: Directory containing document PDFs.
        images_dir: Directory to save extracted images.

    Returns:
        Dict with total_pages and doc_page_map (doc_id → [start, end] pages).
    """
    pdf_files = sorted(f for f in docs_dir.iterdir() if f.suffix.lower() == ".pdf")

    if not pdf_files:
        return {"total_pages": 0, "doc_page_map": {}}

    current_page = 1
    doc_page_map = {}

    for pdf_path in pdf_files:
        doc_id = pdf_path.stem  # e.g., "GALE_AAA111"
        num_pages = extract_pages_from_pdf(pdf_path, images_dir, current_page)

        doc_page_map[doc_id] = {
            "start_page": current_page,
            "end_page": current_page + num_pages - 1,
            "num_pages": num_pages,
        }

        current_page += num_pages

    total_pages = current_page - 1
    return {"total_pages": total_pages, "doc_page_map": doc_page_map}
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_extract.py -v
```
Expected: 3 passed

**Step 5: Commit**

```bash
git add src/ocr/extract.py tests/test_extract.py
git commit -m "add PDF page extraction module"
```

---

### Task 4: Gemini OCR Module

**Files:**
- Create: `tests/test_gemini_ocr.py`
- Create: `src/ocr/gemini_ocr.py`

**Step 1: Write the failing tests**

```python
# tests/test_gemini_ocr.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from src.ocr.gemini_ocr import ocr_single_page, build_page_metadata


def test_build_page_metadata():
    """Metadata JSON is built correctly from OCR result."""
    result = build_page_metadata(
        page_num=5,
        volume_id="CO273_534",
        source_document="GALE_AAA111",
        text="Some transcribed text with [illegible] parts",
        model="gemini-2.0-flash",
    )

    assert result["page_num"] == 5
    assert result["volume_id"] == "CO273_534"
    assert result["source_document"] == "GALE_AAA111"
    assert result["model"] == "gemini-2.0-flash"
    assert result["text"] == "Some transcribed text with [illegible] parts"
    assert result["illegible_count"] == 1
    assert "timestamp" in result


def test_build_page_metadata_no_illegible():
    """Illegible count is 0 when no markers present."""
    result = build_page_metadata(
        page_num=1,
        volume_id="CO273_534",
        source_document="GALE_AAA111",
        text="Clear text with no issues",
        model="gemini-2.0-flash",
    )
    assert result["illegible_count"] == 0


@pytest.mark.asyncio
async def test_ocr_single_page_success(tmp_path):
    """Successful OCR returns text and saves files."""
    # Create a fake image
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(200, 200, 200))
    img_path = tmp_path / "page_0001.jpg"
    img.save(str(img_path))

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Transcribed colonial text here"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    result = await ocr_single_page(
        model=mock_model,
        image_path=img_path,
        page_num=1,
        volume_id="CO273_534",
        source_document="GALE_AAA111",
        output_dir=tmp_path / "ocr",
    )

    assert result is True
    assert (tmp_path / "ocr" / "page_0001.txt").exists()
    assert (tmp_path / "ocr" / "page_0001.json").exists()

    text = (tmp_path / "ocr" / "page_0001.txt").read_text()
    assert text == "Transcribed colonial text here"

    metadata = json.loads((tmp_path / "ocr" / "page_0001.json").read_text())
    assert metadata["page_num"] == 1
    assert metadata["volume_id"] == "CO273_534"
```

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_gemini_ocr.py -v
```
Expected: FAIL — module not found

**Step 3: Install pytest-asyncio**

Add to `pyproject.toml` dev dependencies:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.23.0",
]
```

Run:
```bash
pip install -e ".[dev]"
```

**Step 4: Write the Gemini OCR module**

```python
# src/ocr/gemini_ocr.py
"""Send page images to Gemini Vision for OCR transcription."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from src.ocr.config import OCR_PROMPT, GEMINI_MODEL


def build_page_metadata(
    page_num: int,
    volume_id: str,
    source_document: str,
    text: str,
    model: str,
) -> dict:
    """Build metadata dict for an OCR'd page."""
    illegible_count = len(re.findall(r"\[illegible\]", text, re.IGNORECASE))
    return {
        "page_num": page_num,
        "volume_id": volume_id,
        "source_document": source_document,
        "model": model,
        "text": text,
        "illegible_count": illegible_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def ocr_single_page(
    model,
    image_path: Path,
    page_num: int,
    volume_id: str,
    source_document: str,
    output_dir: Path,
) -> bool:
    """Run Gemini Vision OCR on a single page image.

    Args:
        model: Gemini GenerativeModel instance.
        image_path: Path to the page JPEG image.
        page_num: Page number for filenames and metadata.
        volume_id: Volume identifier (e.g., "CO273_534").
        source_document: Source document ID (e.g., "GALE_AAA111").
        output_dir: Directory to save .txt and .json output.

    Returns:
        True on success, False on failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        img = Image.open(image_path)
        response = await model.generate_content_async([OCR_PROMPT, img])
        text = response.text

        # Save plain text
        txt_path = output_dir / f"page_{page_num:04d}.txt"
        txt_path.write_text(text, encoding="utf-8")

        # Save metadata JSON
        metadata = build_page_metadata(
            page_num=page_num,
            volume_id=volume_id,
            source_document=source_document,
            text=text,
            model=GEMINI_MODEL,
        )
        json_path = output_dir / f"page_{page_num:04d}.json"
        json_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return True

    except Exception as e:
        print(f"  OCR failed for page {page_num}: {e}")
        return False
```

**Step 5: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_gemini_ocr.py -v
```
Expected: 3 passed

**Step 6: Commit**

```bash
git add src/ocr/gemini_ocr.py tests/test_gemini_ocr.py pyproject.toml
git commit -m "add Gemini Vision OCR module with async support"
```

---

### Task 5: OCR Manifest and GCS Helpers

**Files:**
- Create: `tests/test_ocr_manifest.py`
- Create: `src/ocr/manifest.py`

**Step 1: Write the failing tests**

```python
# tests/test_ocr_manifest.py
import json
import pytest
from pathlib import Path

from src.ocr.manifest import load_ocr_manifest, save_ocr_manifest, update_manifest_page


def test_load_ocr_manifest_new(tmp_path):
    """Loading non-existent manifest returns empty structure."""
    manifest = load_ocr_manifest(tmp_path / "ocr_manifest.json")
    assert manifest["completed_pages"] == []
    assert manifest["failed_pages"] == []
    assert manifest["total_pages"] == 0


def test_save_and_load_manifest(tmp_path):
    """Manifest round-trips through save and load."""
    path = tmp_path / "ocr_manifest.json"
    data = {
        "volume_id": "CO273_534",
        "total_pages": 100,
        "completed_pages": [1, 2, 3],
        "failed_pages": [{"page": 4, "error": "timeout"}],
        "doc_page_map": {},
    }
    save_ocr_manifest(path, data)
    loaded = load_ocr_manifest(path)
    assert loaded == data


def test_update_manifest_page_success():
    """Successful page is added to completed list."""
    manifest = {
        "completed_pages": [1, 2],
        "failed_pages": [],
        "total_pages": 10,
    }
    update_manifest_page(manifest, page_num=3, success=True)
    assert 3 in manifest["completed_pages"]


def test_update_manifest_page_failure():
    """Failed page is added to failed list with error."""
    manifest = {
        "completed_pages": [],
        "failed_pages": [],
        "total_pages": 10,
    }
    update_manifest_page(manifest, page_num=5, success=False, error="timeout")
    assert len(manifest["failed_pages"]) == 1
    assert manifest["failed_pages"][0]["page"] == 5
    assert manifest["failed_pages"][0]["error"] == "timeout"
```

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_ocr_manifest.py -v
```
Expected: FAIL — module not found

**Step 3: Write the manifest module**

```python
# src/ocr/manifest.py
"""OCR progress tracking via manifest files."""
import json
from pathlib import Path


def load_ocr_manifest(path: Path) -> dict:
    """Load OCR manifest from JSON, or return empty manifest."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "volume_id": "",
        "total_pages": 0,
        "completed_pages": [],
        "failed_pages": [],
        "doc_page_map": {},
    }


def save_ocr_manifest(path: Path, data: dict) -> None:
    """Save OCR manifest to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def update_manifest_page(
    manifest: dict,
    page_num: int,
    success: bool,
    error: str = "",
) -> None:
    """Update manifest with result of a single page OCR.

    Modifies manifest dict in-place.
    """
    if success:
        if page_num not in manifest["completed_pages"]:
            manifest["completed_pages"].append(page_num)
    else:
        manifest["failed_pages"].append({"page": page_num, "error": error})
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_ocr_manifest.py -v
```
Expected: 4 passed

**Step 5: Commit**

```bash
git add src/ocr/manifest.py tests/test_ocr_manifest.py
git commit -m "add OCR manifest module for progress tracking"
```

---

### Task 6: Async Pipeline Orchestrator

**Files:**
- Create: `tests/test_pipeline.py`
- Create: `src/ocr/pipeline.py`

**Step 1: Write the failing tests**

```python
# tests/test_pipeline.py
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from PIL import Image
from pypdf import PdfWriter

from src.ocr.pipeline import run_ocr_pipeline


def _create_test_pdf(path: Path, num_pages: int = 2) -> None:
    """Create a minimal PDF with blank pages."""
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    with open(path, "wb") as f:
        writer.write(f)


def _create_test_images(images_dir: Path, count: int = 3) -> None:
    """Create test JPEG images."""
    images_dir.mkdir(parents=True, exist_ok=True)
    for i in range(1, count + 1):
        img = Image.new("RGB", (100, 100), color=(i * 50, i * 50, i * 50))
        img.save(images_dir / f"page_{i:04d}.jpg")


@pytest.mark.asyncio
async def test_run_ocr_pipeline(tmp_path):
    """Pipeline extracts pages and runs OCR on all images."""
    volume_dir = tmp_path / "CO273_534"

    # Create test images (simulating already-extracted pages)
    images_dir = volume_dir / "images"
    _create_test_images(images_dir, count=3)

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

    assert result["total_pages"] == 3
    assert len(result["completed_pages"]) == 3

    # Check output files exist
    ocr_dir = volume_dir / "ocr"
    assert (ocr_dir / "page_0001.txt").exists()
    assert (ocr_dir / "page_0001.json").exists()
    assert (ocr_dir / "page_0003.txt").exists()


@pytest.mark.asyncio
async def test_run_ocr_pipeline_resumes(tmp_path):
    """Pipeline skips already-completed pages on resume."""
    volume_dir = tmp_path / "CO273_534"
    images_dir = volume_dir / "images"
    _create_test_images(images_dir, count=3)

    # Pre-populate manifest with page 1 already done
    manifest_path = volume_dir / "ocr_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({
        "volume_id": "CO273_534",
        "total_pages": 3,
        "completed_pages": [1],
        "failed_pages": [],
        "doc_page_map": {},
    }))

    # Also create the existing output for page 1
    ocr_dir = volume_dir / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    (ocr_dir / "page_0001.txt").write_text("Already done")

    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "New transcription"
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)

    with patch("src.ocr.pipeline.get_gemini_model", return_value=mock_model):
        result = await run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id="CO273_534",
            concurrency=2,
        )

    # Only pages 2 and 3 should have been OCR'd
    assert mock_model.generate_content_async.call_count == 2
    assert len(result["completed_pages"]) == 3  # 1 (resumed) + 2 (new)
```

**Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_pipeline.py -v
```
Expected: FAIL — module not found

**Step 3: Write the pipeline module**

```python
# src/ocr/pipeline.py
"""Async OCR pipeline orchestrator.

Coordinates page image extraction and Gemini Vision OCR
with configurable concurrency and resume support.
"""
import asyncio
from pathlib import Path

import google.generativeai as genai

from src.ocr.config import GEMINI_API_KEY, GEMINI_MODEL, OCR_CONCURRENCY, OCR_MAX_RETRIES, OCR_RETRY_BACKOFF
from src.ocr.gemini_ocr import ocr_single_page
from src.ocr.manifest import load_ocr_manifest, save_ocr_manifest, update_manifest_page


def get_gemini_model():
    """Create and return a configured Gemini model."""
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(GEMINI_MODEL)


async def _ocr_with_retry(
    semaphore: asyncio.Semaphore,
    model,
    image_path: Path,
    page_num: int,
    volume_id: str,
    output_dir: Path,
    manifest: dict,
    manifest_path: Path,
) -> None:
    """OCR a single page with retries and concurrency control."""
    async with semaphore:
        last_error = ""
        for attempt in range(1, OCR_MAX_RETRIES + 1):
            success = await ocr_single_page(
                model=model,
                image_path=image_path,
                page_num=page_num,
                volume_id=volume_id,
                source_document="",  # filled from doc_page_map if available
                output_dir=output_dir,
            )
            if success:
                update_manifest_page(manifest, page_num, success=True)
                save_ocr_manifest(manifest_path, manifest)
                completed = len(manifest["completed_pages"])
                total = manifest["total_pages"]
                print(f"  [{volume_id}] Page {page_num} done ({completed}/{total})")
                return

            last_error = f"attempt {attempt} failed"
            if attempt < OCR_MAX_RETRIES:
                wait = OCR_RETRY_BACKOFF ** attempt
                print(f"  [{volume_id}] Page {page_num} retry {attempt}, waiting {wait}s...")
                await asyncio.sleep(wait)

        update_manifest_page(manifest, page_num, success=False, error=last_error)
        save_ocr_manifest(manifest_path, manifest)
        print(f"  [{volume_id}] Page {page_num} FAILED after {OCR_MAX_RETRIES} attempts")


async def run_ocr_pipeline(
    volume_dir: Path,
    volume_id: str,
    concurrency: int = OCR_CONCURRENCY,
) -> dict:
    """Run OCR pipeline on all page images in a volume directory.

    Expects images at volume_dir/images/page_NNNN.jpg.
    Writes output to volume_dir/ocr/page_NNNN.txt and .json.
    Tracks progress in volume_dir/ocr_manifest.json.

    Args:
        volume_dir: Volume directory containing images/ subfolder.
        volume_id: Volume identifier (e.g., "CO273_534").
        concurrency: Max concurrent Gemini API requests.

    Returns:
        Final manifest dict.
    """
    images_dir = volume_dir / "images"
    ocr_dir = volume_dir / "ocr"
    manifest_path = volume_dir / "ocr_manifest.json"

    # List all page images
    image_files = sorted(images_dir.glob("page_*.jpg"))
    if not image_files:
        print(f"[{volume_id}] No images found in {images_dir}")
        return load_ocr_manifest(manifest_path)

    # Load or create manifest
    manifest = load_ocr_manifest(manifest_path)
    manifest["volume_id"] = volume_id
    manifest["total_pages"] = len(image_files)

    # Determine which pages still need OCR
    completed = set(manifest["completed_pages"])
    pages_to_process = []
    for img_path in image_files:
        # Extract page number from filename: page_0001.jpg → 1
        page_num = int(img_path.stem.split("_")[1])
        if page_num not in completed:
            pages_to_process.append((img_path, page_num))

    if not pages_to_process:
        print(f"[{volume_id}] All {len(image_files)} pages already OCR'd")
        return manifest

    print(f"[{volume_id}] Processing {len(pages_to_process)} pages "
          f"({len(completed)} already done, concurrency={concurrency})")

    # Create Gemini model and semaphore
    model = get_gemini_model()
    semaphore = asyncio.Semaphore(concurrency)

    # Launch all OCR tasks
    tasks = [
        _ocr_with_retry(
            semaphore=semaphore,
            model=model,
            image_path=img_path,
            page_num=page_num,
            volume_id=volume_id,
            output_dir=ocr_dir,
            manifest=manifest,
            manifest_path=manifest_path,
        )
        for img_path, page_num in pages_to_process
    ]

    await asyncio.gather(*tasks)

    # Final save
    save_ocr_manifest(manifest_path, manifest)

    completed = len(manifest["completed_pages"])
    failed = len(manifest["failed_pages"])
    print(f"[{volume_id}] OCR complete: {completed} done, {failed} failed")

    return manifest
```

**Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_pipeline.py -v
```
Expected: 2 passed

**Step 5: Commit**

```bash
git add src/ocr/pipeline.py tests/test_pipeline.py
git commit -m "add async OCR pipeline orchestrator with resume support"
```

---

### Task 7: CLI Entry Point

**Files:**
- Create: `scripts/run_ocr.py`

**Step 1: Write the CLI**

```python
# scripts/run_ocr.py
"""
CLI entry point for Phase 2 OCR pipeline.

Usage:
    python -m scripts.run_ocr extract [--volume CO273_534]
    python -m scripts.run_ocr ocr [--volume CO273_534] [--concurrency 20]
    python -m scripts.run_ocr all [--volume CO273_534] [--concurrency 20]
"""
import argparse
import asyncio
from pathlib import Path

from src.config import VOLUMES, DOWNLOAD_DIR
from src.ocr.extract import extract_volume_pages
from src.ocr.manifest import save_ocr_manifest
from src.ocr.pipeline import run_ocr_pipeline


def get_volume_ids(args) -> list[str]:
    """Return list of volume IDs to process."""
    if args.volume:
        if args.volume not in VOLUMES:
            print(f"Unknown volume: {args.volume}")
            print(f"Available: {', '.join(VOLUMES.keys())}")
            raise SystemExit(1)
        return [args.volume]
    return list(VOLUMES.keys())


def cmd_extract(args):
    """Extract page images from document PDFs."""
    print("=== Extracting page images from PDFs ===")

    for volume_id in get_volume_ids(args):
        volume_dir = DOWNLOAD_DIR / volume_id
        docs_dir = volume_dir / "documents"
        images_dir = volume_dir / "images"

        if not docs_dir.exists():
            print(f"Skipping {volume_id}: no documents/ directory")
            continue

        print(f"\n[{volume_id}] Extracting pages...")
        result = extract_volume_pages(docs_dir, images_dir)
        print(f"[{volume_id}] Extracted {result['total_pages']} pages")

        # Save doc_page_map to manifest
        manifest_path = volume_dir / "ocr_manifest.json"
        from src.ocr.manifest import load_ocr_manifest
        manifest = load_ocr_manifest(manifest_path)
        manifest["volume_id"] = volume_id
        manifest["total_pages"] = result["total_pages"]
        manifest["doc_page_map"] = result["doc_page_map"]
        save_ocr_manifest(manifest_path, manifest)

    print("\n=== Extraction complete ===")


def cmd_ocr(args):
    """Run Gemini Vision OCR on extracted page images."""
    print("=== Running Gemini Vision OCR ===")

    for volume_id in get_volume_ids(args):
        volume_dir = DOWNLOAD_DIR / volume_id

        if not (volume_dir / "images").exists():
            print(f"Skipping {volume_id}: no images/ directory (run extract first)")
            continue

        print(f"\n[{volume_id}] Starting OCR...")
        result = asyncio.run(run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id=volume_id,
            concurrency=args.concurrency,
        ))

    print("\n=== OCR complete ===")


def cmd_all(args):
    """Extract pages then run OCR."""
    cmd_extract(args)
    cmd_ocr(args)


def main():
    parser = argparse.ArgumentParser(description="Phase 2: Enhanced OCR Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # extract
    sp_extract = subparsers.add_parser("extract", help="Extract page images from PDFs")
    sp_extract.add_argument("--volume", type=str, help="Process only this volume")
    sp_extract.set_defaults(func=cmd_extract)

    # ocr
    sp_ocr = subparsers.add_parser("ocr", help="Run Gemini Vision OCR")
    sp_ocr.add_argument("--volume", type=str, help="Process only this volume")
    sp_ocr.add_argument("--concurrency", type=int, default=20, help="Max concurrent requests")
    sp_ocr.set_defaults(func=cmd_ocr)

    # all
    sp_all = subparsers.add_parser("all", help="Extract + OCR")
    sp_all.add_argument("--volume", type=str, help="Process only this volume")
    sp_all.add_argument("--concurrency", type=int, default=20, help="Max concurrent requests")
    sp_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

**Step 2: Verify CLI shows help**

Run:
```bash
python -m scripts.run_ocr --help
```
Expected: Shows usage with extract, ocr, all commands

**Step 3: Commit**

```bash
git add scripts/run_ocr.py
git commit -m "add Phase 2 OCR CLI entry point"
```

---

### Task 8: Run All Tests + Smoke Test

**Step 1: Run full test suite**

Run:
```bash
python -m pytest tests/ -v
```
Expected: All tests pass (Phase 1 tests + Phase 2 tests)

**Step 2: Verify CLI commands**

Run:
```bash
python -m scripts.run_ocr --help
python -m scripts.run_ocr extract --help
python -m scripts.run_ocr ocr --help
```
Expected: Help text displays correctly for all commands

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "verify all Phase 2 tests pass"
```

---

### Task 9: GCS Integration (After Phase 1 Data Exists)

This task runs after Phase 1 has uploaded data to GCS. It adds GCS read/write to the pipeline instead of local-only paths.

**Files:**
- Modify: `src/ocr/pipeline.py` — add GCS download/upload for images and OCR output
- Modify: `scripts/run_ocr.py` — add `--local` flag for local-only mode vs GCS mode

This is deferred until Phase 1 has real data in the bucket. The local-only pipeline from Tasks 1-8 works for development and testing.

---

## Verification Checklist

- [ ] `pip install -e ".[dev]"` — installs all Phase 2 dependencies
- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] `python -m scripts.run_ocr extract --volume CO273_534` — extracts page images from PDFs
- [ ] `python -m scripts.run_ocr ocr --volume CO273_534 --concurrency 5` — runs Gemini OCR
- [ ] OCR output exists at `pdfs/CO273_534/ocr/page_0001.txt` and `.json`
- [ ] `ocr_manifest.json` tracks completed/failed pages
- [ ] Resume works: re-running skips already-completed pages
