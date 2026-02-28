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

# Target volumes: {volume_id: {"gale_id": str, "pages": int}}
# gale_id will be filled after inspecting the Gale viewer URLs
VOLUMES = {
    "CO273_534": {"gale_id": "", "pages": 1436},
    "CO273_550": {"gale_id": "", "pages": 460},
    "CO273_579": {"gale_id": "", "pages": 842},
}

# Scraper settings
DOWNLOAD_DELAY = 1.5  # seconds between requests
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30  # seconds

# GCS settings
GCS_BUCKET = os.getenv("GCS_BUCKET", "aihistory-co273")
GCS_KEY_PATH = os.getenv("GCS_KEY_PATH", "")
GCS_REGION = os.getenv("GCS_REGION", "asia-southeast1")
