# src/ocr/correct.py
"""Post-correction pass for OCR output using LLM."""
from pathlib import Path


CORRECTION_PROMPT = (
    "You are a proofreader for OCR output of 19th-century British colonial documents. "
    "The text below was machine-transcribed from a scanned page of CO 273 "
    "Straits Settlements Original Correspondence.\n\n"
    "Fix only clear OCR errors:\n"
    "- Character substitutions (e.g. 'tbe' -> 'the', 'tle' -> 'the', 'rn' -> 'm')\n"
    "- Missing or extra spaces between words\n"
    "- Broken words across line endings that should be joined\n"
    "- Garbled sequences that are clearly a known English word\n\n"
    "Do NOT change:\n"
    "- Archaic spellings (connexion, shew, gaol) -- these are correct for the era\n"
    "- Names of people, places, or ships -- even if unfamiliar\n"
    "- [illegible] markers -- leave them as-is\n"
    "- Formatting, line breaks, or punctuation style\n"
    "- Table structure (Markdown tables)\n\n"
    "Return ONLY the corrected text. No commentary.\n\n"
    "---\n"
)


async def correct_single_page(
    model,
    page_txt_path: Path,
) -> bool:
    """Run post-correction on a single OCR'd page.

    Reads the existing .txt file, sends to LLM for correction,
    saves corrected text back. Original is preserved as .raw.txt.

    Returns True on success or skip (already corrected).
    """
    raw_backup = page_txt_path.with_suffix(".raw.txt")

    # Skip if already corrected
    if raw_backup.exists():
        return True

    if not page_txt_path.exists():
        return False

    try:
        raw_text = page_txt_path.read_text(encoding="utf-8")

        if not raw_text.strip():
            return True

        prompt = CORRECTION_PROMPT + raw_text
        response = await model.generate_content_async(prompt)
        corrected = response.text

        # Save backup of original
        raw_backup.write_text(raw_text, encoding="utf-8")

        # Overwrite with corrected version
        page_txt_path.write_text(corrected, encoding="utf-8")

        return True

    except Exception as e:
        print(f"  Correction failed for {page_txt_path.name}: {e}")
        return False
