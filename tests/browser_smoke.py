"""Local Chrome smoke test for the standalone GitHub Pages Option Lab."""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import subprocess
import tempfile
import threading

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
SCREENSHOT = REPO / "assets" / "readme" / "showcase.png"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    if not CHROME.exists():
        raise SystemExit("Chrome executable not found; browser smoke test cannot run.")
    handler = partial(QuietHandler, directory=str(DOCS))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        address = "http://127.0.0.1:" + str(server.server_port) + "/"
        with tempfile.TemporaryDirectory(prefix="option-lab-chrome-") as profile:
            cmd = [
                str(CHROME), "--headless=new", "--disable-gpu", "--no-first-run",
                "--no-default-browser-check", "--disable-background-networking",
                "--user-data-dir=" + profile, "--window-size=1440,1000",
                "--hide-scrollbars", "--virtual-time-budget=4000",
                "--screenshot=" + str(SCREENSHOT), "--dump-dom", address
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=55)
        dom = result.stdout
        if result.returncode:
            raise AssertionError("Chrome exited " + str(result.returncode) + ": " + result.stderr[-1500:])
        extracted = {}
        for name in ("call", "put", "dc", "dp", "gc", "gp"):
            match = re.search(r'id="' + name + r'"[^>]*>([^<]+)', dom)
            if not match:
                raise AssertionError(name + " result node missing in browser-rendered DOM")
            extracted[name] = match.group(1).strip()
            if not extracted[name] or extracted[name] in ("—", "n/a"):
                raise AssertionError(name + " calculation did not run: " + extracted[name])
        print("BROWSER JS CALCULATIONS PASS", extracted)
        print("LOCAL HTTP SERVER PASS", address)
        print("SCREENSHOT", SCREENSHOT, "BYTES", SCREENSHOT.stat().st_size if SCREENSHOT.exists() else "MISSING")
        if not SCREENSHOT.exists() or SCREENSHOT.stat().st_size < 10000:
            raise AssertionError("Screenshot missing or unexpectedly small")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
