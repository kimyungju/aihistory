"""
CLI entry point for aihistory scraper pipeline.

Usage:
    python -m scripts.run scrape [--resume] [--no-text] [--volume ID]
    python -m scripts.run build [--volume ID]
    python -m scripts.run upload
    python -m scripts.run all [--resume] [--no-text] [--volume ID]
"""
import argparse
from src.config import VOLUMES, DOWNLOAD_DIR
from src.auth import authenticate_gale
from src.scraper import scrape_volume
from src.pdf_builder import merge_pdfs
from src.gcs_upload import upload_all_volumes, list_bucket_contents


def _get_volumes(args):
    """Return volumes to process, filtered by --volume if specified."""
    if hasattr(args, "volume") and args.volume:
        if args.volume not in VOLUMES:
            print(f"Unknown volume: {args.volume}")
            print(f"Available: {', '.join(VOLUMES.keys())}")
            raise SystemExit(1)
        return {args.volume: VOLUMES[args.volume]}
    return VOLUMES


def cmd_scrape(args):
    """Authenticate and download all documents for configured volumes."""
    print("=== Step 1: NUS SSO Authentication ===")
    session = authenticate_gale()

    volumes = _get_volumes(args)
    download_text = not args.no_text

    print(f"\n=== Step 2: Downloading documents ({len(volumes)} volume(s)) ===")
    for volume_id, vol_config in volumes.items():
        print(f"\nStarting {volume_id}...")
        scrape_volume(
            session=session,
            volume_id=volume_id,
            doc_ids=vol_config["doc_ids"],
            output_dir=DOWNLOAD_DIR,
            resume=args.resume,
            download_text=download_text,
        )

    print("\n=== Scraping complete ===")


def cmd_build(args):
    """Merge downloaded document PDFs into per-volume PDFs."""
    print("=== Merging PDFs ===")
    volumes = _get_volumes(args)

    for volume_id in volumes:
        docs_dir = DOWNLOAD_DIR / volume_id / "documents"
        output_pdf = DOWNLOAD_DIR / volume_id / f"{volume_id}_full.pdf"

        if not docs_dir.exists():
            print(f"Skipping {volume_id}: no documents directory found")
            continue

        print(f"\nMerging {volume_id}...")
        merge_pdfs(docs_dir, output_pdf)

    print("\n=== PDF merge complete ===")


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
    sp_scrape = subparsers.add_parser("scrape", help="Auth + download documents")
    sp_scrape.add_argument("--resume", action="store_true", help="Resume interrupted download")
    sp_scrape.add_argument("--no-text", action="store_true", help="Skip OCR text downloads")
    sp_scrape.add_argument("--volume", type=str, help="Scrape only this volume (e.g., CO273_534)")
    sp_scrape.set_defaults(func=cmd_scrape)

    # build
    sp_build = subparsers.add_parser("build", help="Merge document PDFs into volume PDFs")
    sp_build.add_argument("--volume", type=str, help="Build only this volume")
    sp_build.set_defaults(func=cmd_build)

    # upload
    sp_upload = subparsers.add_parser("upload", help="Upload to GCS")
    sp_upload.set_defaults(func=cmd_upload)

    # all
    sp_all = subparsers.add_parser("all", help="Full pipeline")
    sp_all.add_argument("--resume", action="store_true", help="Resume interrupted download")
    sp_all.add_argument("--no-text", action="store_true", help="Skip OCR text downloads")
    sp_all.add_argument("--volume", type=str, help="Process only this volume")
    sp_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
