"""
CLI entry point for aihistory scraper pipeline.

Usage:
    python -m scripts.run scrape [--resume] [--volume ID]
    python -m scripts.run build [--volume ID]
    python -m scripts.run upload
    python -m scripts.run test [--doc-id GALE|...]
    python -m scripts.run all [--resume] [--volume ID]
"""
import argparse
from src.config import VOLUMES, DOWNLOAD_DIR
from src.auth import authenticate_gale
from src.scraper import scrape_volume, get_document_data, download_document_pages, save_ocr_text, sanitize_doc_id
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

    print(f"\n=== Step 2: Downloading documents ({len(volumes)} volume(s)) ===")
    for volume_id, vol_config in volumes.items():
        print(f"\nStarting {volume_id}...")
        scrape_volume(
            session=session,
            volume_id=volume_id,
            doc_ids=vol_config["doc_ids"],
            output_dir=DOWNLOAD_DIR,
            resume=args.resume,
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


def cmd_test(args):
    """Test single document download using the dviViewer API."""
    test_doc_id = args.doc_id or "GALE|LBYSJJ528199212"
    test_dir = DOWNLOAD_DIR / "_test"

    print("=== Test Mode: dviViewer API Download ===")
    print(f"Doc: {test_doc_id}")

    print("\n1. Authenticating via NUS SSO...")
    session = authenticate_gale()

    print("\n2. Calling dviViewer/getDviDocument API...")
    try:
        doc_data = get_document_data(session, test_doc_id)
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    image_list = doc_data.get("imageList", [])
    original_doc = doc_data.get("originalDocument", {})
    ocr_map = original_doc.get("pageOcrTextMap", {})
    pdf_ids = original_doc.get("pdfRecordIds", [])

    print(f"   Pages: {len(image_list)}")
    print(f"   OCR text pages: {len(ocr_map)}")
    print(f"   PDF record IDs: {len(pdf_ids)}")

    if image_list:
        print(f"   First page recordId: {image_list[0]['recordId'][:80]}...")
        print(f"   First page sourceRecordId: {image_list[0].get('sourceRecordId', 'N/A')}")

    # Download first 3 pages as test
    safe_id = sanitize_doc_id(test_doc_id)
    images_dir = test_dir / "images" / safe_id

    if image_list:
        test_pages = min(3, len(image_list))
        print(f"\n3. Downloading first {test_pages} page images...")
        test_data = {"imageList": image_list[:test_pages]}
        downloaded = download_document_pages(session, test_data, images_dir)
        print(f"   Downloaded: {downloaded}/{test_pages}")

        # Check saved files
        for f in sorted(images_dir.glob("*.jpg")):
            size_kb = f.stat().st_size / 1024
            print(f"   {f.name}: {size_kb:.1f} KB")

    # Save OCR text
    if ocr_map:
        text_dir = test_dir / "text"
        print(f"\n4. Saving OCR text...")
        ocr_count = save_ocr_text(doc_data, text_dir, test_doc_id)
        print(f"   Saved {ocr_count} pages of OCR text")
        txt_file = text_dir / f"{safe_id}.txt"
        if txt_file.exists():
            size_kb = txt_file.stat().st_size / 1024
            print(f"   {txt_file.name}: {size_kb:.1f} KB")
            # Show preview
            with open(txt_file, encoding="utf-8") as f:
                preview = f.read(500)
            print(f"   Preview: {preview[:300]}...")

    print("\n=== Test complete ===")


def cmd_all(args):
    """Run full pipeline: scrape -> build -> upload."""
    cmd_scrape(args)
    cmd_build(args)
    cmd_upload(args)


def main():
    parser = argparse.ArgumentParser(description="aihistory scraper pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # scrape
    sp_scrape = subparsers.add_parser("scrape", help="Auth + download documents")
    sp_scrape.add_argument("--resume", action="store_true", help="Resume interrupted download")
    sp_scrape.add_argument("--volume", type=str, help="Scrape only this volume (e.g., CO273_534)")
    sp_scrape.set_defaults(func=cmd_scrape)

    # build
    sp_build = subparsers.add_parser("build", help="Merge document PDFs into volume PDFs")
    sp_build.add_argument("--volume", type=str, help="Build only this volume")
    sp_build.set_defaults(func=cmd_build)

    # upload
    sp_upload = subparsers.add_parser("upload", help="Upload to GCS")
    sp_upload.set_defaults(func=cmd_upload)

    # test
    sp_test = subparsers.add_parser("test", help="Test single document download")
    sp_test.add_argument("--doc-id", type=str, help="Specific docId to test (default: GALE|LBYSJJ528199212)")
    sp_test.set_defaults(func=cmd_test)

    # all
    sp_all = subparsers.add_parser("all", help="Full pipeline")
    sp_all.add_argument("--resume", action="store_true", help="Resume interrupted download")
    sp_all.add_argument("--volume", type=str, help="Process only this volume")
    sp_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
