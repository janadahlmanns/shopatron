"""Diagnostic tool: record the background requests of the REWE web shop.

Attaches to the Chrome instance started by start_browser.py and logs all XHR/fetch and
non-GET requests to REWE domains, including (truncated) response bodies. Passive only:
no clicks, no requests of its own. Cookie and authorization headers are redacted.

Intended for analysing the shop's internal API, e.g. after a site change breaks Shopatron.

Usage:
  1. Start the browser (start_browser.py) and log in.
  2. .venv\\Scripts\\python.exe tools\\watch_network.py
  3. Perform the actions of interest in the browser window.
  4. Press Enter to stop.

Output: local/network_log.jsonl. Response bodies contain personal data (customer ID,
market, cart contents); the local/ directory is therefore excluded from version control.
"""

import asyncio
import json
import time
from pathlib import Path

from playwright.async_api import Page, Request, Response, async_playwright

CDP_URL = "http://127.0.0.1:9222"
LOG_FILE = Path(__file__).parent.parent / "local" / "network_log.jsonl"
SECRET_HEADERS = {"cookie", "set-cookie", "authorization", "x-csrf-token", "x-xsrf-token"}
MAX_BODY = 4000  # characters retained per response body


def is_relevant(request: Request) -> bool:
    return "rewe" in request.url and (
        request.resource_type in ("xhr", "fetch") or request.method != "GET"
    )


def redact_headers(headers: dict) -> dict:
    return {k: ("<redacted>" if k.lower() in SECRET_HEADERS else v) for k, v in headers.items()}


async def main() -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    log = LOG_FILE.open("w", encoding="utf-8")
    count = 0

    async def on_response(response: Response) -> None:
        nonlocal count
        request = response.request
        if not is_relevant(request):
            return
        try:
            body = await response.text()
        except Exception as exc:  # redirects, binary content, closed pages
            body = f"<unreadable: {exc}>"
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "method": request.method,
            "url": request.url,
            "type": request.resource_type,
            "request_headers": redact_headers(await request.all_headers()),
            "post_data": request.post_data,
            "status": response.status,
            "response_body": body[:MAX_BODY],
        }
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.flush()
        count += 1
        print(f"[{entry['time']}] {request.method} {response.status} {request.url[:120]}")

    def watch(page: Page) -> None:
        page.on("response", lambda r: asyncio.ensure_future(on_response(r)))

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CDP_URL)
        for context in browser.contexts:
            context.on("page", watch)
            for page in context.pages:
                watch(page)
        print("Recording. Press Enter to stop.\n")
        await asyncio.get_running_loop().run_in_executor(None, input)
        # Detaches from the browser; the Chrome window stays open.
        await browser.close()

    log.close()
    print(f"\nRecorded {count} requests -> {LOG_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
