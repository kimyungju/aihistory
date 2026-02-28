import os
import re
import time
import subprocess
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def safe_name(s: str) -> str:
    return re.sub(r"[^\w.\-() ]+", "_", s).strip()[:180]


GALE_BASE = "https://go-gale-com.libproxy1.nus.edu.sg"

# Fixed search parameters for CO 273 pagination
PAGINATE_PARAMS = {
    "tabID": "ManuscriptVolumeRecords",
    "lm": 'SUBCOL~"CO 273: Straits Settlements Original Correspondence"',
    "searchResultsType": "SingleTab",
    "qt": "OQE_COL~87WX",
    "searchId": "R1",
    "searchType": "AdvancedSearchForm",
    "userGroupName": "nuslib",
    "inPS": "true",
    "sort": "Pub Date Forward Chron",
    "prodId": "SPOC",
    "paginationClicked": "true",
}

RESULTS_PER_PAGE = 20


def build_paginate_url(current_position: int) -> str:
    params = {**PAGINATE_PARAMS, "currentPosition": current_position}
    return f"{GALE_BASE}/ps/paginate.do?{urlencode(params)}"


def parse_results_page(html: str, page_url: str):
    soup = BeautifulSoup(html, "html.parser")

    doc_links = []
    for a in soup.select("ul.SearchResultsList a.title__link.documentLink[href]"):
        doc_links.append(urljoin(page_url, a["href"]))

    return doc_links


def doc_id_from_url(url: str) -> str:
    qs = parse_qs(urlparse(url).query)
    doc_id = qs.get("docId", ["unknown"])[0]
    return safe_name(doc_id.replace("|", "_"))


def latest_pdf_in_dir(download_dir: Path) -> Path | None:
    pdfs = list(download_dir.glob("*.pdf"))
    if not pdfs:
        return None
    return max(pdfs, key=lambda p: p.stat().st_mtime)


def wait_for_new_pdf(download_dir: Path, since_ts: float, timeout_s: int = 120) -> Path:
    end = time.time() + timeout_s
    while time.time() < end:
        pdf = latest_pdf_in_dir(download_dir)
        if pdf and pdf.stat().st_mtime > since_ts and pdf.stat().st_size > 0:
            return pdf
        time.sleep(0.5)
    raise TimeoutError("Timed out waiting for PDF download.")


def upload_gsutil(local_path: Path, bucket: str, prefix: str):
    prefix = prefix.strip("/")
    dest = f"gs://{bucket}/{prefix}/" if prefix else f"gs://{bucket}/"
    subprocess.run(["gsutil", "cp", str(local_path), dest], check=True)


def click_download_pdf(driver: webdriver.Chrome):
    """
    This is the only part you'll likely need to tweak once you inspect a *document page*.
    Strategy:
      - Click the Download button/menu
      - Click the PDF option
    """

    wait = WebDriverWait(driver, 15)

    # 1) Click a "Download" button/menu (try a few common patterns)
    download_candidates = [
        (By.CSS_SELECTOR, 'button[aria-label*="Download" i]'),
        (By.CSS_SELECTOR, 'a[aria-label*="Download" i]'),
        (By.CSS_SELECTOR, 'button[data-testid*="download" i]'),
        (By.XPATH, "//button[contains(translate(., 'DOWNLOAD', 'download'), 'download')]"),
    ]

    clicked = False
    for by, sel in download_candidates:
        els = driver.find_elements(by, sel)
        if els:
            els[0].click()
            clicked = True
            break

    if not clicked:
        raise RuntimeError("Could not find a Download button on the document page. Need doc-page HTML to set selector.")

    # 2) Click PDF option in the opened menu/dialog
    pdf_candidates = [
        (By.XPATH, "//a[contains(., 'PDF') or contains(., 'Pdf')]"),
        (By.XPATH, "//button[contains(., 'PDF') or contains(., 'Pdf')]"),
        (By.CSS_SELECTOR, '[data-download-format="PDF"]'),
    ]

    for by, sel in pdf_candidates:
        els = driver.find_elements(by, sel)
        if els:
            els[0].click()
            return

    # If menu opened but PDF not found
    raise RuntimeError("Download menu opened, but no PDF option found. Need doc-page HTML to set selector.")


def make_driver(download_dir: Path, reuse_profile: bool = False) -> webdriver.Chrome:
    opts = Options()

    # If you need to be logged in through NUS proxy / SSO:
    # easiest is to reuse your existing Chrome profile (already logged in).
    if reuse_profile:
        # CHANGE THIS path to your Chrome user data dir (Windows example):
        # C:\Users\<YOU>\AppData\Local\Google\Chrome\User Data
        opts.add_argument(r"--user-data-dir=C:\Users\yjkim\AppData\Local\Google\Chrome\User Data")
        # Optional: choose profile, e.g. "Default" or "Profile 1"
        opts.add_argument("--profile-directory=Default")

    prefs = {
        "download.default_directory": str(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,  # don't open in Chrome viewer
    }
    opts.add_experimental_option("prefs", prefs)

    # opts.add_argument("--headless=new")  # keep OFF while debugging login/download UI
    return webdriver.Chrome(options=opts)


def run(bucket: str, prefix: str, reuse_profile: bool = True):
    download_dir = Path("downloads").resolve()
    download_dir.mkdir(parents=True, exist_ok=True)

    driver = make_driver(download_dir, reuse_profile=reuse_profile)
    wait = WebDriverWait(driver, 20)

    try:
        # First load triggers NUS SSO login
        driver.get(build_paginate_url(1))

        if not reuse_profile:
            # Wait for NUS SSO login to complete (URL returns to Gale)
            print("Waiting for NUS SSO login... Complete login in the Chrome window.")
            login_timeout = time.time() + 300  # 5 min to login
            while time.time() < login_timeout:
                try:
                    url = driver.current_url
                except Exception:
                    print("Browser disconnected. Retrying...")
                    time.sleep(3)
                    continue
                if "go-gale-com" in url or "go.gale.com" in url:
                    break
                time.sleep(2)
            else:
                raise TimeoutError("Login timed out after 5 minutes.")
            print("Login detected. Continuing...")

        seen_docs = set()
        current_position = 1
        page_i = 0

        while True:
            page_i += 1
            page_url = build_paginate_url(current_position)
            print(f"\n=== Results page {page_i} (position {current_position})")

            driver.get(page_url)

            time.sleep(3)  # let page render
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.SearchResultsList")))
            except Exception:
                # Dump page for debugging
                debug_path = Path("downloads/debug_page.html")
                debug_path.write_text(driver.page_source, encoding="utf-8")
                print(f"No results list found. Page saved to {debug_path}")
                print(f"Current URL: {driver.current_url}")
                break

            html = driver.page_source
            doc_links = parse_results_page(html, page_url)

            print(f"Found {len(doc_links)} document links on this page.")

            if not doc_links:
                print("No documents found. Done.")
                break

            for doc_url in doc_links:
                doc_key = doc_id_from_url(doc_url)
                if doc_key in seen_docs:
                    continue
                seen_docs.add(doc_key)

                print(f"\nOpening doc: {doc_key}")
                driver.get(doc_url)

                time.sleep(1.0)

                before = time.time()
                click_download_pdf(driver)

                pdf_path = wait_for_new_pdf(download_dir, since_ts=before, timeout_s=180)

                new_name = download_dir / f"{doc_key}.pdf"
                pdf_path.rename(new_name)

                print(f"Downloaded: {new_name.name}")
                print(f"Uploading to gs://{bucket}/{prefix}/")
                upload_gsutil(new_name, bucket=bucket, prefix=prefix)

                new_name.unlink(missing_ok=True)

                time.sleep(0.5)

            if len(doc_links) < RESULTS_PER_PAGE:
                print(f"\nLast page ({len(doc_links)} < {RESULTS_PER_PAGE} results). Done.")
                break

            current_position += RESULTS_PER_PAGE

        print(f"\nFinished. Scraped {len(seen_docs)} documents total.")

    finally:
        driver.quit()


if __name__ == "__main__":
    run(
        bucket="aihistory-co273",
        prefix="pdfs/gale",
        reuse_profile=False,
    )