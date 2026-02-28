"""
CLI entry point for aihistory scraper pipeline.

Usage:
    python -m scripts.run scrape [--resume]    # Auth + download pages
    python -m scripts.run build                 # Combine pages into PDFs
    python -m scripts.run upload                # Upload to GCS
    python -m scripts.run all [--resume]        # Full pipeline
"""
import argparse
from pathlib import Path
from src.config import VOLUMES, DOWNLOAD_DIR
from src.auth import authenticate_gale
from src.scraper import scrape_volume
from src.pdf_builder import build_pdf_from_images
from src.gcs_upload import upload_all_volumes, list_bucket_contents


def cmd_scrape(args):
    """Authenticate and download all volume pages."""
    print("=== Step 1: NUS SSO Authentication ===")
    session = authenticate_gale()

    print("\n=== Step 2: Downloading pages ===")
    for volume_id, vol_config in VOLUMES.items():
        print(f"\nStarting {volume_id} ({vol_config['pages']} pages)...")
        scrape_volume(
            session=session,
            volume_id=volume_id,
            gale_id=vol_config["gale_id"],
            total_pages=vol_config["pages"],
            output_dir=DOWNLOAD_DIR,
            resume=args.resume,
        )

    print("\n=== Scraping complete ===")


def cmd_build(args):
    """Combine downloaded page images into PDFs."""
    print("=== Building PDFs ===")
    for volume_id in VOLUMES:
        pages_dir = DOWNLOAD_DIR / volume_id / "pages"
        output_pdf = DOWNLOAD_DIR / volume_id / f"{volume_id}_full.pdf"

        if not pages_dir.exists():
            print(f"Skipping {volume_id}: no pages directory found")
            continue

        print(f"\nBuilding {volume_id}...")
        build_pdf_from_images(pages_dir, output_pdf)

    print("\n=== PDF build complete ===")


def cmd_upload(args):
    """Upload all volumes to GCS."""
    print("=== Uploading to GCS ===")
    upload_all_volumes(DOWNLOAD_DIR)

    print("\n=== Verifying uploads ===")
    contents = list_bucket_contents()
    print(f"Bucket contains {len(contents)} objects")
    for name in contents[:20]:
        print(f"  {name}")
    if len(contents) > 20:
        print(f"  ... and {len(contents) - 20} more")


def cmd_all(args):
    """Run full pipeline: scrape → build → upload."""
    cmd_scrape(args)
    cmd_build(args)
    cmd_upload(args)


def main():
    parser = argparse.ArgumentParser(description="aihistory scraper pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scrape
    sp_scrape = subparsers.add_parser("scrape", help="Auth + download pages")
    sp_scrape.add_argument("--resume", action="store_true", help="Resume interrupted download")
    sp_scrape.set_defaults(func=cmd_scrape)

    # build
    sp_build = subparsers.add_parser("build", help="Combine pages into PDFs")
    sp_build.set_defaults(func=cmd_build)

    # upload
    sp_upload = subparsers.add_parser("upload", help="Upload to GCS")
    sp_upload.set_defaults(func=cmd_upload)

    # all
    sp_all = subparsers.add_parser("all", help="Full pipeline")
    sp_all.add_argument("--resume", action="store_true", help="Resume interrupted download")
    sp_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
