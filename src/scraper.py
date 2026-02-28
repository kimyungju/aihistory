# src/scraper.py
"""
Download page images from Gale Primary Sources using authenticated requests.

Requires session cookies from auth.py. Tracks progress via manifest.json
to support resuming interrupted downloads.
"""
import json
import time
from pathlib import Path
import requests
from src.config import DOWNLOAD_DELAY, MAX_RETRIES, REQUEST_TIMEOUT


# NOTE: Update this after API endpoint discovery in Task 3.
# This is a placeholder pattern — replace with actual Gale endpoint.
PAGE_URL_TEMPLATE = (
    "https://go-gale-com.libproxy1.nus.edu.sg"
    "/ps/i.do?id={gale_id}&page={page_num}&action=PageImage"
)


def build_page_url(gale_id: str, page_num: int) -> str:
    """Build the URL for a specific page image."""
    return PAGE_URL_TEMPLATE.format(gale_id=gale_id, page_num=page_num)


def load_manifest(path: Path) -> dict:
    """Load download manifest from JSON, or return empty manifest."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {"downloaded": [], "failed": [], "total": 0}


def save_manifest(path: Path, data: dict) -> None:
    """Save download manifest to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def download_page(
    session: requests.Session,
    gale_id: str,
    page_num: int,
    output_dir: Path,
) -> bool:
    """
    Download a single page image. Returns True on success, False on failure.
    """
    url = build_page_url(gale_id, page_num)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        # Determine file extension from content type
        content_type = response.headers.get("Content-Type", "image/jpeg")
        ext = "pdf" if "pdf" in content_type else "jpg"
        filename = f"page_{page_num:04d}.{ext}"

        filepath = output_dir / filename
        with open(filepath, "wb") as f:
            f.write(response.content)

        return True

    except Exception as e:
        print(f"  Failed to download page {page_num}: {e}")
        return False


def scrape_volume(
    session: requests.Session,
    volume_id: str,
    gale_id: str,
    total_pages: int,
    output_dir: Path,
    resume: bool = True,
) -> dict:
    """
    Download all pages for a volume. Supports resume via manifest.

    Returns the final manifest dict.
    """
    volume_dir = output_dir / volume_id
    volume_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = volume_dir / "manifest.json"

    manifest = load_manifest(manifest_path) if resume else {
        "downloaded": [], "failed": [], "total": total_pages,
    }
    manifest["total"] = total_pages

    already_downloaded = set(manifest["downloaded"])

    for page_num in range(1, total_pages + 1):
        if page_num in already_downloaded:
            continue

        print(f"  [{volume_id}] Downloading page {page_num}/{total_pages}...")

        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            if download_page(session, gale_id, page_num, volume_dir / "pages"):
                success = True
                break
            print(f"    Retry {attempt}/{MAX_RETRIES}...")
            time.sleep(DOWNLOAD_DELAY)

        if success:
            manifest["downloaded"].append(page_num)
        else:
            manifest["failed"].append(page_num)

        # Save progress after each page
        save_manifest(manifest_path, manifest)
        time.sleep(DOWNLOAD_DELAY)

    downloaded = len(manifest["downloaded"])
    failed = len(manifest["failed"])
    print(f"  [{volume_id}] Done: {downloaded} downloaded, {failed} failed")
    return manifest
