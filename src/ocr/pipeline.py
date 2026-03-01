# src/ocr/pipeline.py
"""Async OCR pipeline orchestrator.

Coordinates page image extraction and Gemini Vision OCR
with configurable concurrency and resume support.
"""
import asyncio
from pathlib import Path

from src.ocr.config import GEMINI_API_KEY, GEMINI_MODEL, OCR_CONCURRENCY, OCR_MAX_RETRIES, OCR_RETRY_BACKOFF
from src.ocr.gemini_ocr import ocr_single_page
from src.ocr.manifest import load_ocr_manifest, save_ocr_manifest, update_manifest_page


def get_gemini_model():
    """Create and return a configured Gemini model."""
    import google.generativeai as genai
    genai.configure(api_key=GEMINI_API_KEY)
    return genai.GenerativeModel(GEMINI_MODEL)


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


def download_images_from_gcs(volume_id: str, local_dir: Path) -> int:
    """Download page images from GCS to local directory.

    Uses lazy import to avoid protobuf issues on Python 3.14.
    Skips files that already exist locally.
    Returns count of files downloaded.
    """
    from src.gcs_upload import get_bucket
    bucket = get_bucket()
    prefix = f"{volume_id}/images/"

    local_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for blob in bucket.list_blobs(prefix=prefix):
        filename = blob.name.split("/")[-1]
        if not filename:
            continue
        local_path = local_dir / filename
        if not local_path.exists():
            blob.download_to_filename(str(local_path))
            count += 1
    return count


def upload_ocr_to_gcs(volume_id: str, ocr_dir: Path) -> int:
    """Upload OCR results from local directory to GCS.

    Uses lazy import to avoid protobuf issues on Python 3.14.
    Returns count of files uploaded.
    """
    from src.gcs_upload import get_bucket, upload_file
    bucket = get_bucket()
    count = 0
    for file_path in sorted(ocr_dir.rglob("*")):
        if file_path.is_file():
            relative = file_path.relative_to(ocr_dir)
            gcs_path = f"{volume_id}/ocr/{relative.as_posix()}"
            upload_file(bucket, file_path, gcs_path)
            count += 1
    return count
