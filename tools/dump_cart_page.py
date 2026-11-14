"""Diagnostic tool: save the HTML of the currently open REWE page and locate embedded cart data.

Reads the DOM of the first open REWE tab (normally the cart page) without issuing any
request to the shop, saves it, and lists <script> elements containing cart data
("lineItems"). Used to verify how the basket JSON is embedded in the cart page.

Usage: open the cart page in the Shopatron browser, then
       .venv\\Scripts\\python.exe tools\\dump_cart_page.py

Output: local/cart_page.html. Contains personal data; local/ is excluded from version control.
"""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

CDP_URL = "http://127.0.0.1:9222"
OUT_FILE = Path(__file__).parent.parent / "local" / "cart_page.html"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        pages = [pg for ctx in browser.contexts for pg in ctx.pages if "rewe.de" in pg.url]
        if not pages:
            raise SystemExit("No open REWE tab found.")
        for pg in pages:
            print("Open REWE tab:", pg.url)
        page = pages[0]
        html = page.content()

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(html, encoding="utf-8")
    print(f"\nSaved {len(html):,} characters of HTML from {page.url}\n -> {OUT_FILE}")

    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", html, flags=re.S)
    print(f"{len(scripts)} <script> elements in the page")
    for attrs, body in scripts:
        if "lineItems" in body:
            print(f"\n<script{attrs}> contains 'lineItems' ({len(body):,} chars). Start:")
            print("  ", body[:300].replace("\n", " "))


if __name__ == "__main__":
    main()
