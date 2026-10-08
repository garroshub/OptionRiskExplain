"""Local HTTP server for option pricing and market data."""
from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sysconfig
from urllib.parse import parse_qs, urlsplit

from . import market
from .risk import explain_csv

_source_docs = Path(__file__).resolve().parent.parent / "docs"
_installed_docs = Path(sysconfig.get_path("data")) / "share" / "garros-option-lab" / "docs"
DOCS = _source_docs if (_source_docs / "index.html").is_file() else _installed_docs


def respond(path: str) -> tuple[int, dict]:
    url = urlsplit(path)
    query = parse_qs(url.query, keep_blank_values=True)

    def get(name: str, default: str = "") -> str:
        return query.get(name, [default])[0]

    try:
        if url.path == "/api/health":
            return 200, {"ok": True, "market_data": "local_yfinance", "site": "option_lab"}
        if url.path == "/api/quote":
            return 200, market.quote(get("ticker", "SPY"))
        if url.path == "/api/expirations":
            return 200, market.expirations(get("ticker", "SPY"))
        if url.path == "/api/chain":
            return 200, market.option_chain(get("ticker", "SPY"), get("expiry"), get("side", "both"))
        return 404, {"error": "Unknown API endpoint"}
    except ValueError as exc:
        return 400, {"error": str(exc)}
    except market.MarketDataError as exc:
        return 502, {"error": str(exc)}
    except Exception:
        return 500, {"error": "Unexpected local service error"}


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if urlsplit(self.path).path != "/api/explain":
            self._json(404, {"error": "Unknown API endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 3_000_000:
                self._json(413, {"error": "Request body must be 1 byte to 3 MB"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self._json(415, {"error": "Content-Type must be application/json"})
                return
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected JSON object")
            result = explain_csv(payload.get("start_csv", ""), payload.get("end_csv", ""),
                                 payload.get("threshold", 500.0))
            self._json(200, result)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            self._json(500, {"error": "Unexpected risk attribution error"})

    def _json(self, status: int, data: dict):
        content = json.dumps(data, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if urlsplit(self.path).path.startswith("/api/"):
            status, data = respond(self.path)
            self._json(status, data)
            return
        return super().do_GET()

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


def serve(host: str = "127.0.0.1", port: int = 8765):
    if host != "127.0.0.1":
        raise ValueError("For safety the local market API only binds to 127.0.0.1")
    if not (DOCS / "index.html").is_file():
        raise FileNotFoundError("Options Lab web assets missing. Install from the project wheel or run from the repository checkout.")
    handler = partial(Handler, directory=str(DOCS))
    with ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"Options Lab: http://{host}:{httpd.server_port}/", flush=True)
        httpd.serve_forever()
