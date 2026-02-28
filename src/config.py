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

# Target volumes: {volume_id: {"search_url": str}}
# search_url is the Gale faceted search URL listing all documents in this volume.
# Fill these in from the Gale sidebar facet filter URLs.
VOLUMES = {
    "CO273_534": {
        "search_url": "",  # TODO: paste from Gale volume facet filter
    },
    "CO273_550": {
        "search_url": "",  # TODO: paste from Gale volume facet filter
    },
    "CO273_579": {
        "search_url": "",  # TODO: paste from Gale volume facet filter
    },
}

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
