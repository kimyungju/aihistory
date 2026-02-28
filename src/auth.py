# src/auth.py
"""
NUS SSO authentication via Selenium.

Opens a visible Chrome browser for the user to complete NUS SSO login,
then extracts session cookies for use with the requests library.
"""
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from src.config import GALE_BASE_URL


def extract_cookies_from_driver(driver) -> list[dict]:
    """Extract cookies from Selenium WebDriver with domain/path info."""
    return driver.get_cookies()


def create_session_with_cookies(cookies: list[dict]) -> requests.Session:
    """Create a requests.Session pre-loaded with cookies (including domains) and headers."""
    session = requests.Session()
    for c in cookies:
        session.cookies.set(
            c["name"],
            c["value"],
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
        )
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Origin": GALE_BASE_URL,
    })
    return session


def _create_driver(download_dir: str | None = None) -> webdriver.Chrome:
    """Create a Chrome driver with optional download directory."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    if download_dir:
        prefs = {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        }
        options.add_experimental_option("prefs", prefs)

    return webdriver.Chrome(options=options)


def _wait_for_sso(driver) -> None:
    """Navigate to Gale and wait for NUS SSO login to complete."""
    print(f"Opening {GALE_BASE_URL} - please complete NUS SSO login...")
    driver.get(GALE_BASE_URL)

    print("Waiting for login to complete...")
    WebDriverWait(driver, 300).until(
        lambda d: "gale" in d.current_url.lower()
        and "login" not in d.current_url.lower()
        and "auth" not in d.current_url.lower()
    )

    # Navigate to a Gale product page to trigger JSESSIONID cookie
    product_url = f"{GALE_BASE_URL}/ps/start.do?prodId=SPOC&userGroupName=nuslib"
    print("Navigating to Gale product page for session cookies...")
    driver.get(product_url)

    # Wait for JSESSIONID11_omni session cookie (up to 15 seconds)
    for _ in range(15):
        cookies = extract_cookies_from_driver(driver)
        cookie_names = [c["name"] for c in cookies]
        if "JSESSIONID11_omni" in cookie_names:
            break
        time.sleep(1)

    cookies = extract_cookies_from_driver(driver)
    cookie_names = sorted(c["name"] for c in cookies)
    print(f"Login successful. Captured {len(cookies)} cookies: {cookie_names}")

    if "JSESSIONID11_omni" not in cookie_names:
        print("  WARNING: JSESSIONID11_omni not found - downloads may return disclaimers")


def authenticate_gale() -> requests.Session:
    """
    Open browser for NUS SSO login, wait for success, return authenticated session.

    The browser is VISIBLE (not headless) so the user can complete
    NUS SSO login including any 2FA steps. Browser closes after auth.
    """
    driver = _create_driver()

    try:
        _wait_for_sso(driver)
        cookies = extract_cookies_from_driver(driver)
        session = create_session_with_cookies(cookies)
        return session
    finally:
        driver.quit()


def authenticate_gale_driver(download_dir: str) -> webdriver.Chrome:
    """
    Open browser for NUS SSO login and KEEP IT OPEN for Selenium-based downloads.

    Sets Chrome to auto-download PDFs to download_dir without prompting.
    Returns the driver (caller must call driver.quit() when done).
    """
    driver = _create_driver(download_dir=download_dir)
    _wait_for_sso(driver)
    return driver
