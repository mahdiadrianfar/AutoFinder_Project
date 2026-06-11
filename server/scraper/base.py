import re
from typing import Dict, List
from urllib.parse import urljoin

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DIVAR_POST_LIST_CLASS = "post-list-eb562"


def _cleanup_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_price_value(price: str) -> int | None:
    if not price:
        return None

    digits = re.sub(r"[^0-9]", "", price)
    if not digits:
        return None

    try:
        return int(digits)
    except ValueError:
        return None


def _normalize_url(base_url: str, href: str) -> str:
    return urljoin(base_url, href)


def scrape_divar_list(url: str, wait_seconds: int = 15) -> List[Dict[str, str]]:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        raise RuntimeError(
            "Cannot start Selenium WebDriver. "
            "Make sure Chrome is installed and the driver is available to Selenium."
        ) from exc

    try:
        driver.get(url)
        wait = WebDriverWait(driver, wait_seconds)
        wait.until(EC.presence_of_element_located(
            (By.CLASS_NAME, DIVAR_POST_LIST_CLASS)))

        container = driver.find_element(By.CLASS_NAME, DIVAR_POST_LIST_CLASS)
        anchors = container.find_elements(
            By.XPATH, ".//a[@href and contains(@href, '/v/')]")

        seen_urls = set()
        ads = []

        for anchor in anchors:
            href = anchor.get_attribute("href") or ""
            if not href or href in seen_urls:
                continue

            seen_urls.add(href)
            card_text = _cleanup_text(anchor.text)
            raw_html = anchor.get_attribute("outerHTML") or ""
            lines = [line.strip()
                     for line in card_text.splitlines() if line.strip()]

            title = anchor.get_attribute(
                "aria-label") or (lines[0] if lines else None)
            price = None
            location = None
            description = None

            if lines:
                candidates = [line for line in lines if re.search(r"\d", line)]
                price = next((line for line in candidates if "تومان" in line or "تومن" in line),
                             candidates[0] if candidates else None)

            if len(lines) >= 2:
                location = lines[-1]
                if title and title == location:
                    location = None

            if len(lines) > 2:
                description = " | ".join(lines[1:-1])

            price_value = _extract_price_value(price)

            ads.append(
                {
                    "url": _normalize_url(url, href),
                    "title": _cleanup_text(title or ""),
                    "price": _cleanup_text(price or ""),
                    "price_value": price_value,
                    "location": _cleanup_text(location or ""),
                    "description": _cleanup_text(description or ""),
                    "source": "divar",
                    "raw_data": raw_html,
                }
            )

        return ads
    except TimeoutException as exc:
        raise RuntimeError(
            "Timed out waiting for Divar list content to load.") from exc
    finally:
        driver.quit()
