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
from src.ocr.manifest import save_ocr_manifest, load_ocr_manifest
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
        asyncio.run(run_ocr_pipeline(
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
