"""
CLI entry point for Phase 2 OCR pipeline.

Usage:
    python -m scripts.run_ocr extract [--volume CO273_534]
    python -m scripts.run_ocr ocr [--volume CO273_534] [--concurrency 20]
    python -m scripts.run_ocr all [--volume CO273_534] [--concurrency 20]
    python -m scripts.run_ocr evaluate [--volume CO273_534] [--sample 10]
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

        if not getattr(args, 'local', False):
            print(f"[{volume_id}] Downloading images from GCS...")
            from src.ocr.pipeline import download_images_from_gcs
            count = download_images_from_gcs(volume_id, volume_dir / "images")
            print(f"[{volume_id}] Downloaded {count} images from GCS")

        if not (volume_dir / "images").exists():
            print(f"Skipping {volume_id}: no images/ directory (run extract first)")
            continue

        print(f"\n[{volume_id}] Starting OCR...")
        asyncio.run(run_ocr_pipeline(
            volume_dir=volume_dir,
            volume_id=volume_id,
            concurrency=args.concurrency,
            correct=getattr(args, 'correct', False),
        ))

        if not getattr(args, 'local', False):
            print(f"[{volume_id}] Uploading OCR results to GCS...")
            from src.ocr.pipeline import upload_ocr_to_gcs
            count = upload_ocr_to_gcs(volume_id, volume_dir / "ocr")
            print(f"[{volume_id}] Uploaded {count} OCR files to GCS")

    print("\n=== OCR complete ===")


def cmd_evaluate(args):
    """Evaluate Gemini OCR quality against Gale baseline."""
    import json as json_mod
    from src.ocr.evaluate import evaluate_volume

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
    sp_ocr.add_argument("--local", action="store_true", help="Use local files instead of GCS")
    sp_ocr.add_argument("--correct", action="store_true", help="Run post-correction pass after OCR")
    sp_ocr.set_defaults(func=cmd_ocr)

    # all
    sp_all = subparsers.add_parser("all", help="Extract + OCR")
    sp_all.add_argument("--volume", type=str, help="Process only this volume")
    sp_all.add_argument("--concurrency", type=int, default=20, help="Max concurrent requests")
    sp_all.add_argument("--local", action="store_true", help="Use local files instead of GCS")
    sp_all.add_argument("--correct", action="store_true", help="Run post-correction pass after OCR")
    sp_all.set_defaults(func=cmd_all)

    # evaluate
    sp_eval = subparsers.add_parser("evaluate", help="Compare Gemini vs Gale OCR quality")
    sp_eval.add_argument("--volume", type=str, help="Process only this volume")
    sp_eval.add_argument("--sample", type=int, default=None, help="Evaluate only N documents")
    sp_eval.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
