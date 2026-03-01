"""Evaluate Gemini OCR output against Gale OCR baseline using WER/CER."""
import json
import re
from pathlib import Path

from jiwer import wer, cer


def parse_gale_text(text: str) -> dict[int, str]:
    """Parse Gale OCR text file into per-page dict.

    Gale text format:
        --- Page 1 ---
        page text here...

        --- Page 2 ---
        more text...

    Returns {page_num: text_content}.
    """
    if not text.strip():
        return {}

    pages = {}
    parts = re.split(r"---\s*Page\s+(\d+)\s*---", text)

    # parts[0] is before first marker (empty), then alternating: page_num, text
    for i in range(1, len(parts), 2):
        page_num = int(parts[i])
        page_text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if page_text:
            pages[page_num] = page_text

    return pages


def load_gemini_page(ocr_dir: Path, doc_id: str, page_num: int) -> str | None:
    """Load Gemini OCR text for a specific page.

    Looks at ocr_dir/{doc_id}/page_NNNN.txt.
    Returns None if file doesn't exist.
    """
    path = ocr_dir / doc_id / f"page_{page_num:04d}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return None


def compute_page_metrics(reference: str, hypothesis: str) -> dict:
    """Compute WER and CER between reference and hypothesis texts.

    Returns dict with wer, cer, ref_words, hyp_words.
    """
    ref_words = reference.split()
    hyp_words = hypothesis.split()

    if not ref_words:
        return {"wer": 0.0, "cer": 0.0, "ref_words": 0, "hyp_words": len(hyp_words)}

    w = wer(reference, hypothesis)
    c = cer(reference, hypothesis)

    return {
        "wer": round(w, 4),
        "cer": round(c, 4),
        "ref_words": len(ref_words),
        "hyp_words": len(hyp_words),
    }


def evaluate_document(
    doc_id: str,
    text_dir: Path,
    ocr_dir: Path,
) -> dict:
    """Evaluate Gemini OCR vs Gale baseline for one document.

    Args:
        doc_id: Sanitized document ID (e.g., "GALE_AAA111").
        text_dir: Directory containing Gale baseline text files.
        ocr_dir: Parent directory containing per-doc OCR output subdirs.

    Returns:
        Dict with doc_id, pages_compared, page_metrics, avg_wer, avg_cer.
    """
    gale_path = text_dir / f"{doc_id}.txt"
    if not gale_path.exists():
        return {
            "doc_id": doc_id,
            "error": f"Gale baseline not found: {gale_path}",
            "pages_compared": 0,
            "page_metrics": {},
            "avg_wer": None,
            "avg_cer": None,
        }

    gale_pages = parse_gale_text(gale_path.read_text(encoding="utf-8"))
    page_metrics = {}

    for page_num, gale_text in sorted(gale_pages.items()):
        gemini_text = load_gemini_page(ocr_dir, doc_id, page_num)
        if gemini_text is None:
            page_metrics[page_num] = {"error": "Gemini OCR not found"}
            continue

        metrics = compute_page_metrics(gale_text, gemini_text)
        page_metrics[page_num] = metrics

    # Compute averages (exclude pages with errors)
    valid = [m for m in page_metrics.values() if "wer" in m]
    avg_wer = sum(m["wer"] for m in valid) / len(valid) if valid else None
    avg_cer = sum(m["cer"] for m in valid) / len(valid) if valid else None

    return {
        "doc_id": doc_id,
        "pages_compared": len(valid),
        "page_metrics": page_metrics,
        "avg_wer": round(avg_wer, 4) if avg_wer is not None else None,
        "avg_cer": round(avg_cer, 4) if avg_cer is not None else None,
    }


def evaluate_volume(
    volume_id: str,
    volume_dir: Path,
    sample: int | None = None,
) -> dict:
    """Evaluate all documents in a volume.

    Args:
        volume_id: Volume identifier.
        volume_dir: Path to volume directory (contains text/ and ocr/).
        sample: If set, only evaluate this many documents (random sample).

    Returns:
        Dict with volume_id, documents (list of doc results), overall avg_wer/cer.
    """
    text_dir = volume_dir / "text"
    ocr_dir = volume_dir / "ocr"

    if not text_dir.exists():
        return {"volume_id": volume_id, "error": "No text/ directory (Gale baseline)"}
    if not ocr_dir.exists():
        return {"volume_id": volume_id, "error": "No ocr/ directory (Gemini output)"}

    # Find all documents with both baseline and OCR
    doc_ids = sorted(
        f.stem for f in text_dir.glob("*.txt")
        if (ocr_dir / f.stem).is_dir()
    )

    if sample and sample < len(doc_ids):
        import random
        doc_ids = random.sample(doc_ids, sample)

    doc_results = []
    for doc_id in doc_ids:
        result = evaluate_document(doc_id, text_dir, ocr_dir)
        doc_results.append(result)
        print(f"  {doc_id}: WER={result['avg_wer']}, CER={result['avg_cer']} "
              f"({result['pages_compared']} pages)")

    # Overall averages
    valid = [d for d in doc_results if d["avg_wer"] is not None]
    overall_wer = sum(d["avg_wer"] for d in valid) / len(valid) if valid else None
    overall_cer = sum(d["avg_cer"] for d in valid) / len(valid) if valid else None

    return {
        "volume_id": volume_id,
        "documents": doc_results,
        "total_documents": len(doc_results),
        "overall_wer": round(overall_wer, 4) if overall_wer is not None else None,
        "overall_cer": round(overall_cer, 4) if overall_cer is not None else None,
    }
