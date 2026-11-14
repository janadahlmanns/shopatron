"""Launch the dedicated Chrome instance used by Shopatron.

- A separate profile directory (./browser-profile) isolates the REWE session from the
  default Chrome profile and persists the session cookies between runs. Login, including
  two-factor authentication, is performed manually in this browser window.
- A remote debugging port bound to 127.0.0.1 allows Playwright to attach to the running,
  manually authenticated browser. The port is not reachable from other machines.

Usage:  .venv\\Scripts\\python.exe start_browser.py
"""

import subprocess
import sys
from pathlib import Path

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
]
PROFILE_DIR = Path(__file__).parent / "browser-profile"
DEBUG_PORT = 9222
START_URL = "https://www.rewe.de/shop/"


def main() -> None:
    chrome = next((p for p in CHROME_CANDIDATES if p.exists()), None)
    if chrome is None:
        sys.exit("Chrome not found. Adjust CHROME_CANDIDATES in start_browser.py.")

    PROFILE_DIR.mkdir(exist_ok=True)
    subprocess.Popen(
        [
            str(chrome),
            f"--user-data-dir={PROFILE_DIR.resolve()}",
            f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-debugging-address=127.0.0.1",
            "--no-first-run",
            "--no-default-browser-check",
            START_URL,
        ]
    )
    print(f"Chrome started with profile {PROFILE_DIR.resolve()}")
    print(f"Debugging endpoint: http://127.0.0.1:{DEBUG_PORT}")


if __name__ == "__main__":
    main()
