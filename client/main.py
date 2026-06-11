"""PySide6 desktop client entry point."""

import json
import re
import sys
import threading
import subprocess
import time
from datetime import datetime
from pathlib import Path

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
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.on_search)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.on_refresh)

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.refresh_button)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self.on_item_selected)

        self.status_label = QLabel("آخرین به‌روزرسانی: بارگذاری اولیه")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.details_label = QLabel("نتایج جستجو در اینجا نمایش داده می‌شود.")
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

        # Auto-refresh on startup after 500ms
        QTimer.singleShot(500, self.on_refresh)

    def load_ads(self) -> list[dict]:
        data_file = Path(__file__).resolve().parent.parent / \
            "divar_tehran_car.json"
        if not data_file.exists():
            self.details_label.setText(
                f"فایل داده پیدا نشد: {data_file}"
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

    def show_results(self, ads: list[dict]) -> None:
        self.result_list.clear()
        self.current_results = ads

        if not ads:
            self.details_label.setText("هیچ نتیجه‌ای پیدا نشد.")
            return

        for ad in ads:
            title = ad.get("title", "")
            item = QListWidgetItem(title)
            self.result_list.addItem(item)

        self.details_label.setText(
            "روی یکی از آگهی‌ها کلیک کنید تا جزئیات کامل آن نمایش داده شود."
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
                f"آخرین بارگذاری: {Path(file_path).name} — {timestamp}"
            )
        else:
            self.status_label.setText("آخرین به‌روزرسانی: نامشخص")

    def on_refresh(self) -> None:
        # Run scraper script in background to avoid blocking UI
        self.refresh_button.setEnabled(False)
        self.status_label.setText("در حال بررسی سایت و دریافت آگهی‌ها...")

        script_path = Path(__file__).resolve(
        ).parent.parent / "scrape_divar_to_json.py"

        def worker():
            try:
                subprocess.run([sys.executable, str(script_path)], check=False)
                # Wait a bit to ensure file is fully written to disk
                time.sleep(0.5)
            except Exception as e:
                # store error for main thread to show
                self._refresh_error = str(e)
            # schedule UI update on main thread
            QTimer.singleShot(0, self._on_refresh_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_refresh_done(self) -> None:
        self.refresh_button.setEnabled(True)
        # reload and reapply filtering (without sorting)
        try:
            self.ads = self.load_ads()
            new_ads_count = len(self.ads)

            self.on_search()
            self.update_status_label()

            if getattr(self, "_refresh_error", None):
                self.details_label.setText(
                    f"خطا در بروزرسانی: {self._refresh_error}")
                del self._refresh_error
            else:
                msg = f"✓ داده‌ها بروز شدند ({new_ads_count} آگهی)"
                self.details_label.setText(msg)
        except Exception as e:
            self.details_label.setText(f"❌ خطا: {str(e)}")
            self.refresh_button.setEnabled(True)

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
