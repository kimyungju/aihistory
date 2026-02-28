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


def authenticate_gale() -> requests.Session:
    """
    Open browser for NUS SSO login, wait for success, return authenticated session.

    The browser is VISIBLE (not headless) so the user can complete
    NUS SSO login including any 2FA steps.
    """
    options = Options()
    # Not headless -user needs to see and interact with SSO
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=options)

    try:
        # Navigate to Gale -will redirect through NUS SSO
        print(f"Opening {GALE_BASE_URL} -please complete NUS SSO login...")
        driver.get(GALE_BASE_URL)

        # Wait for user to complete login and land on Gale
        # Detected by URL containing "gale" and not "login" or "auth"
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
        time.sleep(3)

        cookies = extract_cookies_from_driver(driver)
        cookie_names = sorted(c["name"] for c in cookies)
        print(f"Login successful. Captured {len(cookies)} cookies: {cookie_names}")

        session = create_session_with_cookies(cookies)
        return session

    finally:
        driver.quit()
