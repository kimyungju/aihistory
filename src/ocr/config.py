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

# OCR prompt for colonial documents
OCR_PROMPT = (
    "Transcribe all text visible in this image of a 19th-century colonial document. "
    "Preserve original spelling, punctuation, and line breaks. "
    "If text is unclear, mark with [illegible]. "
    "Include any printed headers, stamps, or marginal notes."
)
