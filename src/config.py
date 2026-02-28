import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DOWNLOAD_DIR = PROJECT_ROOT / "pdfs"

# Gale settings
GALE_BASE_URL = os.getenv(
    "GALE_BASE_URL",
    "https://go-gale-com.libproxy1.nus.edu.sg",
)

# Gale API endpoints
PDF_DOWNLOAD_URL = f"{GALE_BASE_URL}/ps/pdfGenerator/html"
TEXT_DOWNLOAD_URL = f"{GALE_BASE_URL}/ps/htmlGenerator/forText"

# Gale product identifiers
GALE_PROD_ID = "SPOC"
GALE_PRODUCT_CODE = "SPOC-3"
GALE_USER_GROUP = "nuslib"

# Volume configuration — loaded from data/volumes.json
VOLUMES_JSON = PROJECT_ROOT / "data" / "volumes.json"


def load_volumes() -> dict:
    """Load volume config from data/volumes.json.

    Returns {volume_id: {"doc_ids": [...], "volume_ref": "..."}}.
    """
    with open(VOLUMES_JSON) as f:
        data = json.load(f)
    return {
        v["volume_id"]: {
            "doc_ids": [d["doc_id"] for d in v["documents"]],
            "volume_ref": v.get("volume_ref", ""),
        }
        for v in data["volumes"]
    }


VOLUMES = load_volumes()

# Scraper settings
DOWNLOAD_DELAY = 1.5  # seconds between requests
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30  # seconds
PDF_DOWNLOAD_TIMEOUT = 120  # seconds; multi-page PDFs take longer
SEARCH_RESULTS_PER_PAGE = 25  # Gale's default pagination size

# GCS settings
GCS_BUCKET = os.getenv("GCS_BUCKET", "aihistory-co273")
GCS_KEY_PATH = os.getenv("GCS_KEY_PATH", "")
GCS_REGION = os.getenv("GCS_REGION", "asia-southeast1")
