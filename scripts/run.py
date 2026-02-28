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
from src.scraper import scrape_volume, extract_csrf_token, download_document_pdf, download_document_text, _visit_document_page
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


def cmd_test(args):
    """Test download of a single document to verify auth and endpoint work."""
    from src.config import GALE_BASE_URL, GALE_PROD_ID, GALE_USER_GROUP

    print("=== Test Mode: Single Document Download ===")
    session = authenticate_gale()

    test_doc_id = args.doc_id or "GALE|LBYSJJ528199212"
    test_dir = DOWNLOAD_DIR / "_test"

    print(f"\nSession cookies: {sorted(session.cookies.keys())}")

    csrf_url = f"{GALE_BASE_URL}/ps/start.do?prodId={GALE_PROD_ID}&userGroupName={GALE_USER_GROUP}"
    print(f"\nExtracting CSRF token from {csrf_url}...")
    csrf_token = extract_csrf_token(session, csrf_url)
    print(f"CSRF token: {csrf_token[:20]}...")

    print(f"\nVisiting document page for {test_doc_id}...")
    _visit_document_page(session, test_doc_id)

    print(f"\nDownloading PDF for {test_doc_id}...")
    pdf_ok = download_document_pdf(session, test_doc_id, csrf_token, test_dir / "documents")

    print(f"\nDownloading text for {test_doc_id}...")
    text_ok = download_document_text(session, test_doc_id, csrf_token, test_dir / "text")

    print(f"\n=== Results ===")
    print(f"PDF download: {'SUCCESS' if pdf_ok else 'FAILED'}")
    print(f"Text download: {'SUCCESS' if text_ok else 'FAILED'}")

    if pdf_ok:
        from src.scraper import sanitize_doc_id
        pdf_file = test_dir / "documents" / f"{sanitize_doc_id(test_doc_id)}.pdf"
        size = pdf_file.stat().st_size
        print(f"PDF size: {size:,} bytes ({size/1024:.1f} KB)")
        if size < 5000:
            print("WARNING: File is very small - may be a disclaimer")
        else:
            print("File size looks good - appears to be a real document")

    # Debug: inspect the document page for forms, images, and download links
    print(f"\n=== Debug: Inspecting document page ===")
    _debug_document_page(session, test_doc_id)


def _debug_document_page(session, doc_id):
    """Inspect a Gale document page to discover real download mechanisms."""
    import re
    from bs4 import BeautifulSoup
    from src.config import GALE_BASE_URL, GALE_PROD_ID, GALE_USER_GROUP

    encoded_id = doc_id.replace("|", "%7C")
    url = (
        f"{GALE_BASE_URL}/ps/retrieve.do"
        f"?tabID=Manuscripts&prodId={GALE_PROD_ID}"
        f"&userGroupName={GALE_USER_GROUP}"
        f"&docId={encoded_id}"
    )
    print(f"Fetching: {url}")
    resp = session.get(url, headers={"Accept": "text/html"})
    print(f"Status: {resp.status_code}, Size: {len(resp.text)} chars")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find all forms
    forms = soup.find_all("form")
    print(f"\n--- Found {len(forms)} forms ---")
    for i, form in enumerate(forms):
        action = form.get("action", "(no action)")
        method = form.get("method", "GET")
        form_id = form.get("id", "(no id)")
        inputs = form.find_all("input")
        print(f"\nForm {i}: id={form_id} method={method} action={action}")
        for inp in inputs:
            name = inp.get("name", "?")
            val = inp.get("value", "")
            itype = inp.get("type", "text")
            if val and len(val) > 80:
                val = val[:80] + "..."
            print(f"  {itype}: {name} = {val}")

    # Find image URLs referencing luna-gale-com or imgsrv
    print(f"\n--- Image URLs ---")
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "luna" in src or "imgsrv" in src or "FastFetch" in src:
            print(f"  IMG: {src}")
    for script in soup.find_all("script"):
        text = script.string or ""
        for match in re.findall(r'(https?://[^\s"\']+(?:luna|imgsrv|FastFetch)[^\s"\']*)', text):
            print(f"  JS: {match}")

    # Dump relevant JS snippets containing image/download/pdf keywords
    print(f"\n--- JS snippets with image/download info ---")
    for script in soup.find_all("script"):
        text = script.string or ""
        if not text:
            continue
        # Look for image-related JS
        for kw in ["FastFetch", "UBER2", "imgsrv", "imageUrl", "pageImage", "pageNum", "totalPages", "numPages", "pdfUrl", "downloadUrl", "callistoUrl", "BulkPDF"]:
            if kw.lower() in text.lower():
                # Extract surrounding context
                idx = text.lower().find(kw.lower())
                start = max(0, idx - 100)
                end = min(len(text), idx + 200)
                snippet = text[start:end].replace("\n", " ").strip()
                print(f"  [{kw}]: ...{snippet}...")
                break  # One snippet per script block

    # Find any links with "download" or "pdf" in them
    print(f"\n--- Download links ---")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)[:60]
        if any(kw in href.lower() for kw in ["download", "pdf", "callisto", "uber", "bulk"]):
            print(f"  <a href='{href}'>{text}</a>")


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

    # test
    sp_test = subparsers.add_parser("test", help="Test single document download")
    sp_test.add_argument("--doc-id", type=str, help="Specific docId to test (default: GALE|LBYSJJ528199212)")
    sp_test.set_defaults(func=cmd_test)

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
