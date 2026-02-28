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
