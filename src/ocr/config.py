"""Phase 2 OCR pipeline configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

# Gemini settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# Concurrency
OCR_CONCURRENCY = int(os.getenv("OCR_CONCURRENCY", "20"))

# Retry settings
OCR_MAX_RETRIES = 3
OCR_RETRY_BACKOFF = 2.0  # exponential backoff multiplier
OCR_TIMEOUT = 30  # seconds per Gemini request

# Image extraction
IMAGE_FORMAT = "JPEG"
IMAGE_QUALITY = 95  # JPEG quality (1-100)

# OCR prompts for CO 273 Straits Settlements colonial documents
OCR_PROMPTS = {
    "general": (
        "Transcribe all text in this image of a 19th-century British colonial document "
        "from the CO 273 Straits Settlements Original Correspondence series. "
        "This is official government correspondence — expect formal letterheads, "
        "printed or typed text, dates, signatures, and filing stamps.\n\n"
        "Rules:\n"
        "- Preserve original spelling, capitalisation, punctuation, and line breaks exactly\n"
        "- Reproduce paragraph structure and indentation\n"
        "- Include all printed headers, stamps, folio numbers, and marginal notations\n"
        "- Mark genuinely illegible text with [illegible] — do not guess\n"
        "- If handwritten annotations appear alongside printed text, transcribe both "
        "and prefix handwritten sections with [handwritten:]\n"
        "- For signatures, write [signature: Name] if the name is readable\n"
        "- Preserve archaic spellings (e.g. 'connexion', 'shew', 'gaol') without correction"
    ),

    "tabular": (
        "Transcribe the tabular data in this image of a 19th-century British colonial document "
        "from the CO 273 Straits Settlements series. "
        "This page contains structured data — likely a financial ledger, shipping manifest, "
        "trade return, population register, or statistical table.\n\n"
        "Rules:\n"
        "- Reproduce table structure using Markdown table syntax (| col1 | col2 |)\n"
        "- Preserve all column headers exactly as printed\n"
        "- Align numbers in their correct columns — do not conflate adjacent columns\n"
        "- Use currency symbols as printed ($ for Straits dollars, Rs for rupees)\n"
        "- Preserve row labels, subtotals, and grand totals\n"
        "- Mark illegible cells with [illegible]\n"
        "- If the table spans multiple sections or has footnotes, include them after the table\n"
        "- Include any page headers or titles above the table"
    ),

    "handwritten": (
        "Transcribe all handwritten text in this image of a 19th-century British colonial document "
        "from the CO 273 Straits Settlements series. "
        "This page contains primarily handwritten content — a draft letter, minute sheet, "
        "personal note, or annotation-heavy document.\n\n"
        "Rules:\n"
        "- Transcribe handwriting character-by-character, preserving original spelling\n"
        "- Preserve line breaks as written, including mid-word line breaks with a hyphen\n"
        "- Mark deletions/strikethroughs with [deleted: text] if readable\n"
        "- Mark insertions (above-line text, carets) with [inserted: text]\n"
        "- Mark genuinely illegible words with [illegible] — do not guess\n"
        "- If multiple hands are visible, note transitions with [new hand:]\n"
        "- Include any printed elements (letterhead, stamps) separately, prefixed with [printed:]\n"
        "- For multilingual content, transcribe all languages as written — "
        "note language with [Malay:], [Chinese:], etc."
    ),
}

# Default prompt (backward compatibility)
OCR_PROMPT = OCR_PROMPTS["general"]
