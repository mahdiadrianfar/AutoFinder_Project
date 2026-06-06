"""PySide6 desktop client entry point."""

import json
import re
import sys
from pathlib import Path

from PySide6.QtCore import Qt
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
        self.search_input.setPlaceholderText("جستجوی عنوان آگهی...")
        self.search_button = QPushButton("جستجو")
        self.search_button.clicked.connect(self.on_search)

        search_layout = QHBoxLayout()
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self.on_item_selected)

        self.details_label = QLabel("نتایج جستجو در اینجا نمایش داده می‌شود.")
        self.details_label.setWordWrap(True)
        self.details_label.setAlignment(Qt.AlignmentFlag.AlignTop)

        main_layout = QVBoxLayout()
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.result_list)
        main_layout.addWidget(self.details_label)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.ads = self.load_ads()
        self.current_results: list[dict] = []
        self.sort_ads()
        self.show_results(self.ads)

    def load_ads(self) -> list[dict]:
        data_file = Path(__file__).resolve().parent.parent / "divar_tehran_car.json"
        if not data_file.exists():
            self.details_label.setText(
                f"فایل داده پیدا نشد: {data_file}"
            )
            return []

        with data_file.open("r", encoding="utf-8") as handle:
            ads = json.load(handle)

        normalized_ads = []
        for ad in ads:
            price = ad.get("price", "")
            normalized_price = normalize_price(price)
            ad["normalized_price"] = normalized_price
            ad["price_int"] = parse_price_int(normalized_price)
            normalized_ads.append(ad)

        return normalized_ads

    def sort_ads(self) -> None:
        self.ads.sort(
            key=lambda item: item.get("price_int") or 0,
            reverse=True,
        )

    def show_results(self, ads: list[dict]) -> None:
        self.result_list.clear()
        self.current_results = ads

        if not ads:
            self.details_label.setText("هیچ نتیجه‌ای پیدا نشد.")
            return

        for ad in ads:
            title = ad.get("title", "")
            price = ad.get("normalized_price", "")
            item = QListWidgetItem(f"{title} — {price}")
            self.result_list.addItem(item)

        self.details_label.setText(
            "روی یکی از آگهی‌ها کلیک کنید تا قیمت و جزئیات آن نمایش داده شود."
        )

    def on_search(self) -> None:
        query = self.search_input.text().strip().lower()
        if not query:
            self.show_results(self.ads)
            return

        results = [
            ad
            for ad in self.ads
            if query in str(ad.get("title", "")).lower()
        ]
        self.show_results(results)

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
