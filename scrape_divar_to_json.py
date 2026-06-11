import json
import re
import ssl
import urllib.request
from urllib.parse import urljoin
import sys

URL = "https://divar.ir/s/tehran/car"
OUTPUT_FILE = "divar_tehran_car.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_html(url: str) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, context=ctx, timeout=15) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return ""


def extract_items(html: str, base_url: str, max_items: int = 50) -> list[dict]:
    anchor_pattern = re.compile(
        r"<a[^>]*class=\"[^\"]*kt-post-card__action[^\"]*\"[^>]*>.*?</a>",
        re.DOTALL,
    )
    items = []

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

        description_matches = re.findall(
            r'<div[^>]*class="[^"]*kt-post-card__description[^"]*"[^>]*>(.*?)</div>',
            anchor_html,
            re.DOTALL,
        )
        description_matches = [_cleanup(d)
                               for d in description_matches if _cleanup(d)]

        kms = description_matches[0] if len(description_matches) > 0 else None
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
                "price_value": _parse_price(price),
                "location": location,
                "badge": badge,
                "image": image,
                "raw_html": anchor_html,
            }
        )

    return items


def _cleanup(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_price(price: str | None) -> int | None:
    if not price:
        return None
    digits = re.sub(r"[^0-9]", "", price)
    return int(digits) if digits else None


def main() -> None:
    print("Fetching from Divar...", file=sys.stderr)
    html = fetch_html(URL)
    if not html:
        print("Failed to fetch HTML", file=sys.stderr)
        return

    print(f"Extracting items from HTML...", file=sys.stderr)
    items = extract_items(html, URL)
    print(f"Found {len(items)} items", file=sys.stderr)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(items)} items to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
