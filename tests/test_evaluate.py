# tests/test_evaluate.py
import pytest
from pathlib import Path

from src.ocr.evaluate import (
    parse_gale_text,
    load_gemini_page,
    compute_page_metrics,
    evaluate_document,
)


def test_parse_gale_text_splits_pages():
    """Gale text file is parsed into per-page dict."""
    gale_text = (
        "--- Page 1 ---\n"
        "First page content here.\n"
        "\n"
        "--- Page 2 ---\n"
        "Second page with more text.\n"
    )
    pages = parse_gale_text(gale_text)
    assert len(pages) == 2
    assert pages[1] == "First page content here."
    assert pages[2] == "Second page with more text."


def test_parse_gale_text_empty():
    """Empty text returns empty dict."""
    assert parse_gale_text("") == {}


def test_compute_page_metrics():
    """WER and CER computed between reference and hypothesis."""
    ref = "the cat sat on the mat"
    hyp = "the cat set on the mat"
    metrics = compute_page_metrics(ref, hyp)
    assert "wer" in metrics
    assert "cer" in metrics
    assert 0 < metrics["wer"] < 1  # one word wrong out of 6
    assert 0 < metrics["cer"] < 1  # one char wrong


def test_compute_page_metrics_identical():
    """Perfect match gives 0 WER and 0 CER."""
    text = "hello world"
    metrics = compute_page_metrics(text, text)
    assert metrics["wer"] == 0.0
    assert metrics["cer"] == 0.0


def test_evaluate_document(tmp_path):
    """End-to-end evaluation of one document."""
    # Set up Gale baseline
    text_dir = tmp_path / "text"
    text_dir.mkdir()
    gale_text = "--- Page 1 ---\nthe cat sat on the mat\n\n--- Page 2 ---\nhello world\n"
    (text_dir / "GALE_AAA111.txt").write_text(gale_text, encoding="utf-8")

    # Set up Gemini OCR output
    ocr_dir = tmp_path / "ocr" / "GALE_AAA111"
    ocr_dir.mkdir(parents=True)
    (ocr_dir / "page_0001.txt").write_text("the cat set on the mat", encoding="utf-8")
    (ocr_dir / "page_0002.txt").write_text("hello world", encoding="utf-8")

    result = evaluate_document(
        doc_id="GALE_AAA111",
        text_dir=text_dir,
        ocr_dir=tmp_path / "ocr",
    )

    assert result["doc_id"] == "GALE_AAA111"
    assert result["pages_compared"] == 2
    assert len(result["page_metrics"]) == 2
    # Page 1 has error, page 2 is perfect
    assert result["page_metrics"][1]["wer"] > 0
    assert result["page_metrics"][2]["wer"] == 0.0
    assert "avg_wer" in result
    assert "avg_cer" in result
