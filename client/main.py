"""PySide6 desktop client entry point."""

import json
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

URL = "https://divar.ir/s/tehran/car"


def persian_to_english_digits(value: str) -> str:
    if not value:
        return ""

    mapping = {
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
        "٫": ",",
        "،": ",",
    }
    for persian_digit, latin_digit in mapping.items():
        value = value.replace(persian_digit, latin_digit)
    return value


def normalize_price(price: str) -> str:
    if not price:
        return ""

    cleaned = price.replace("تومان", "").replace("تومن", "")
    cleaned = cleaned.strip()
    cleaned = persian_to_english_digits(cleaned)
    cleaned = re.sub(r"[^0-9,]", "", cleaned)
    cleaned = cleaned.strip(", ")

    if not cleaned:
        return ""

    return f"{cleaned} T"


def parse_price_int(price: str) -> int | None:
    if not price:
        return None

    digits = re.sub(r"[^0-9]", "", price)
    if not digits:
        return None

    try:
        return int(digits)
    except ValueError:
        return None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoIndex Client")
        self.resize(900, 700)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(" Search box...")
        self.search_input.returnPressed.connect(self.on_search)
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.on_search)

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self.on_item_selected)

        self.status_label = QLabel("Last update: Initial upload : ")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.details_label = QLabel("Search results are displayed here.")
        self.details_label.setWordWrap(True)
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.status_label)
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.result_list)
        main_layout.addWidget(self.details_label)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.ads = self.load_ads()
        self.current_results: list[dict] = []
        self.show_results(self.ads)
        self.update_status_label()

        QTimer.singleShot(500, self.refresh_on_startup)

    def load_ads(self) -> list[dict]:
        data_file = Path(__file__).resolve().parent.parent / \
            "divar_tehran_car.json"
        if not data_file.exists():
            self.details_label.setText(
                f"Data file not found:   {data_file}"
            )
            return []

        with data_file.open("r", encoding="utf-8") as handle:
            ads = json.load(handle)

        self.data_file_mtime = data_file.stat().st_mtime
        self.data_file_path = str(data_file)

        normalized_ads = []
        for ad in ads:
            price = ad.get("price", "")
            normalized_price = normalize_price(price)
            ad["normalized_price"] = normalized_price
            ad["price_int"] = parse_price_int(normalized_price)
            normalized_ads.append(ad)

        return normalized_ads

    def sort_ads(self) -> None:
        # Keep original order from website, don't sort
        pass

    def fetch_html(self, url: str) -> str:
        try:
            response = requests.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return response.text
        except Exception as e:
            self._refresh_error = str(e)
            return ""

    def extract_items(self, html: str, base_url: str, max_items: int = 50) -> list[dict]:
        items = []
        anchor_pattern = re.compile(
            r"<a[^>]*class=\"[^\"]*kt-post-card__action[^\"]*\"[^>]*>.*?</a>",
            re.DOTALL,
        )

        for anchor_html in anchor_pattern.findall(html):
            if len(items) >= max_items:
                break

            href_match = re.search(r'href="([^"]+)"', anchor_html)
            if not href_match:
                continue
            href = href_match.group(1)
            url = urljoin(base_url, href)

            title_match = re.search(
                r'<h2[^>]*class="[^"]*kt-post-card__title[^"]*"[^>]*>(.*?)</h2>',
                anchor_html,
                re.DOTALL,
            )
            title = _cleanup(title_match.group(1)) if title_match else None
            if not title:
                continue

            description_matches = re.findall(
                r'<div[^>]*class="[^"]*kt-post-card__description[^"]*"[^>]*>(.*?)</div>',
                anchor_html,
                re.DOTALL,
            )
            description_matches = [
                _cleanup(d) for d in description_matches if _cleanup(d)]
            kms = description_matches[0] if len(
                description_matches) > 0 else None
            price = description_matches[1] if len(
                description_matches) > 1 else None

            location_match = re.search(
                r'<span[^>]*class="[^"]*kt-post-card__bottom-description[^"]*"[^>]*>(.*?)</span>',
                anchor_html,
                re.DOTALL,
            )
            location = _cleanup(location_match.group(
                1)) if location_match else None

            badge_match = re.search(
                r'<span[^>]*class="[^"]*kt-post-card__red-text[^"]*"[^>]*>(.*?)</span>',
                anchor_html,
                re.DOTALL,
            )
            badge = _cleanup(badge_match.group(1)) if badge_match else None

            img_match = re.search(r'<img[^>]*src="([^"]+)"', anchor_html)
            image = img_match.group(1) if img_match else None

            items.append(
                {
                    "url": url,
                    "title": title,
                    "kms": kms,
                    "price": price,
                    "price_value": parse_price_int(price),
                    "location": location,
                    "badge": badge,
                    "image": image,
                }
            )

        return items

    def fetch_latest_ads(self) -> list[dict]:
        html = self.fetch_html(URL)
        if not html:
            return []

        items = self.extract_items(html, URL)
        if not items and not getattr(self, "_refresh_error", None):
            self._refresh_error = "No ads found on the page"
        return items

    def show_results(self, ads: list[dict]) -> None:
        self.result_list.clear()
        self.current_results = ads

        if not ads:
            self.details_label.setText("No results found.")
            return

        for ad in ads:
            title = ad.get("title", "")
            item = QListWidgetItem(title)
            self.result_list.addItem(item)

        self.details_label.setText(
            "Click on one of the ads to display its full details."
        )

    def matches_query(self, title: str, query: str) -> bool:
        title_text = str(title).lower()
        query_text = str(query).strip().lower()
        if not query_text:
            return True

        for token in query_text.split():
            if token not in title_text:
                return False
        return True

    def on_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            self.show_results(self.ads)
            return

        results = [
            ad
            for ad in self.ads
            if self.matches_query(ad.get("title", ""), query)
        ]
        self.show_results(results)

    def update_status_label(self) -> None:
        file_time = getattr(self, "data_file_mtime", None)
        file_path = getattr(self, "data_file_path", None)
        if file_time and file_path:
            timestamp = datetime.fromtimestamp(
                file_time).strftime("%Y-%m-%d %H:%M:%S")
            self.status_label.setText(
                f"Last upload : {Path(file_path).name} — {timestamp}"
            )
        else:
            self.status_label.setText("Last update: Unknown  ")

    def refresh_on_startup(self) -> None:
        self.status_label.setText("در حال به‌روزرسانی اولیه...⏳")
        self.details_label.setText("لطفاً منتظر بمانید...")

        def worker():
            self._refresh_error = None
            latest_ads = self.fetch_latest_ads()
            if getattr(self, "_refresh_error", None):
                QTimer.singleShot(0, self._show_refresh_error)
                return

            if latest_ads:
                self.ads = latest_ads
                QTimer.singleShot(0, self._show_latest_ads)
            else:
                QTimer.singleShot(0, self._show_refresh_error)

        threading.Thread(target=worker, daemon=True).start()

    def _show_latest_ads(self) -> None:
        self.on_search()
        self.update_status_label()
        self.details_label.setText(
            f"✓ داده‌ها بروز شدند ({len(self.ads)} آگهی)")

    def _show_refresh_error(self) -> None:
        self.status_label.setText("خطا در دریافت آگهی‌ها")
        self.details_label.setText(
            getattr(self, "_refresh_error", "خطای نامشخص")
        )

    def on_item_selected(self, item: QListWidgetItem) -> None:
        index = self.result_list.row(item)
        if index < 0 or index >= len(self.current_results):
            return

        selected = self.current_results[index]
        title = selected.get("title", "")
        price = selected.get("normalized_price", "")
        kms = selected.get("kms", "")
        location = selected.get("location", "")
        badge = selected.get("badge", "")

        details = [
            f"عنوان: {title}",
            f"قیمت: {price}",
        ]

        if kms:
            details.append(f"کیلومتر: {kms}")
        if location:
            details.append(f"محل: {location}")
        if badge:
            details.append(f"توضیح کوتاه: {badge}")

        self.details_label.setText("\n".join(details))


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
