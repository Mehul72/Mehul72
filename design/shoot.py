"""Renders a local preview page to PNG with headless Chrome.

    .venv/bin/python shoot.py "<url>" out.png [width height [scale]]
"""

import glob
import os
import subprocess
import sys
import tempfile
from pathlib import Path

DESIGN = Path(__file__).resolve().parent
CACHE = DESIGN / ".cache"
SHELLS = sorted(
    glob.glob(os.path.expanduser("~/Library/Caches/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell"))
)
CHROME = Path(SHELLS[-1]) if SHELLS else Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def shoot(url: str, out: str, width: int = 1400, height: int = 600, scale: float = 1) -> None:
    if not CHROME.is_file():
        raise SystemExit("No headless browser found. Install Chrome or Playwright's Chromium shell.")
    output = Path(out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="chrome-", dir=CACHE) as profile:
        subprocess.run(
            [
                str(CHROME),
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                "--use-mock-keychain",
                "--password-store=basic",
                f"--user-data-dir={profile}",
                f"--window-size={width},{height}",
                f"--force-device-scale-factor={scale}",
                "--virtual-time-budget=5000",
                f"--screenshot={output}",
                url,
            ],
            check=True,
            capture_output=True,
        )


if __name__ == "__main__":
    url, out, *rest = sys.argv[1:]
    dims = [float(v) for v in rest]
    shoot(url, out, *(int(v) for v in dims[:2]), *(dims[2:3]))
