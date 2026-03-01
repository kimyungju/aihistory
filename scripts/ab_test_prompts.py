"""A/B test OCR prompt variants on a sample of pages.

Usage:
    python -m scripts.ab_test_prompts --volume CO273_534 --sample 10

Runs all 3 prompt variants on the same sample pages, computes WER/CER
for each, and reports which variant performs best.
"""
import argparse
import asyncio
import json
from pathlib import Path

from src.config import DOWNLOAD_DIR
from src.ocr.config import OCR_PROMPTS
from src.ocr.evaluate import evaluate_document
from src.ocr.gemini_ocr import ocr_single_page
from src.ocr.pipeline import get_gemini_model, _discover_pages


async def ab_test(
    volume_dir: Path,
    volume_id: str,
    sample: int = 10,
    concurrency: int = 5,
) -> dict:
    """Run A/B test across all prompt variants."""
    images_dir = volume_dir / "images"
    text_dir = volume_dir / "text"
    ab_dir = volume_dir / "ab_test"

    pages = _discover_pages(images_dir)
    if not pages:
        print(f"No images found in {images_dir}")
        return {}

    # Sample pages
    if sample < len(pages):
        import random
        pages = random.sample(pages, sample)

    print(f"A/B testing {len(pages)} pages with {len(OCR_PROMPTS)} prompt variants")

    model = get_gemini_model()
    semaphore = asyncio.Semaphore(concurrency)
    results = {}

    for variant_name in OCR_PROMPTS:
        variant_dir = ab_dir / variant_name
        print(f"\n--- Variant: {variant_name} ---")

        for entry in pages:
            out_dir = variant_dir / entry["doc_id"] if entry["doc_id"] else variant_dir

            async with semaphore:
                await ocr_single_page(
                    model=model,
                    image_path=entry["image_path"],
                    page_num=entry["page_num"],
                    volume_id=volume_id,
                    source_document=entry["doc_id"],
                    output_dir=out_dir,
                    prompt_key=variant_name,
                )

        # Evaluate this variant
        doc_ids = set(e["doc_id"] for e in pages if e["doc_id"])
        variant_wer = []
        variant_cer = []

        for doc_id in doc_ids:
            eval_result = evaluate_document(doc_id, text_dir, variant_dir)
            if eval_result["avg_wer"] is not None:
                variant_wer.append(eval_result["avg_wer"])
                variant_cer.append(eval_result["avg_cer"])

        avg_wer = sum(variant_wer) / len(variant_wer) if variant_wer else None
        avg_cer = sum(variant_cer) / len(variant_cer) if variant_cer else None

        results[variant_name] = {
            "avg_wer": round(avg_wer, 4) if avg_wer else None,
            "avg_cer": round(avg_cer, 4) if avg_cer else None,
            "pages_tested": len(pages),
        }
        print(f"  WER={avg_wer}, CER={avg_cer}")

    # Report
    print("\n=== A/B Test Results ===")
    for name, r in sorted(results.items(), key=lambda x: x[1].get("avg_wer") or 999):
        print(f"  {name:15s}  WER={r['avg_wer']}  CER={r['avg_cer']}")

    best = min(results, key=lambda k: results[k].get("avg_wer") or 999)
    print(f"\nBest variant: {best}")

    # Save results
    ab_dir.mkdir(parents=True, exist_ok=True)
    report_path = ab_dir / "ab_results.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to {report_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="A/B test OCR prompt variants")
    parser.add_argument("--volume", type=str, required=True, help="Volume to test")
    parser.add_argument("--sample", type=int, default=10, help="Number of pages to test")
    parser.add_argument("--concurrency", type=int, default=5, help="Max concurrent requests")
    args = parser.parse_args()

    volume_dir = DOWNLOAD_DIR / args.volume
    asyncio.run(ab_test(volume_dir, args.volume, args.sample, args.concurrency))


if __name__ == "__main__":
    main()
