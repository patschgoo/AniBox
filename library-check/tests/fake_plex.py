"""A tiny fake Plex Media Server for tests. It records every request and refuses anything but GET."""

from __future__ import annotations

import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.fixtures import make_fixtures as fx

TOKEN = "test-token"


class FakePlex:
    def __init__(self):
        self.requests = []  # (method, path)
        handler = self._handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _refuse(self):
                fake.requests.append((self.command, self.path))
                self.send_response(405)
                self.end_headers()

            do_POST = do_PUT = do_DELETE = do_PATCH = _refuse

            def do_GET(self):
                fake.requests.append(("GET", self.path))
                if self.headers.get("X-Plex-Token") != TOKEN:
                    self.send_response(401)
                    self.end_headers()
                    return
                url = urllib.parse.urlparse(self.path)
                q = dict(urllib.parse.parse_qsl(url.query))
                body = self._route(url.path, q)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _page(self, items):
                start = int(self.headers.get("X-Plex-Container-Start", 0))
                size = int(self.headers.get("X-Plex-Container-Size", len(items) or 1))
                page = items[start:start + size]
                return {"MediaContainer": {"size": len(page), "offset": start, "totalSize": len(items), "Metadata": page}}

            def _route(self, path, q):
                if path == "/identity":
                    return fx.IDENTITY
                if path == "/library/sections":
                    return fx.SECTIONS
                if path == "/library/sections/1/prefs":
                    return fx.PREFS
                if path == "/library/sections/1/all":
                    return self._page(fx.EPISODES if q.get("type") == "4" else fx.SHOWS)
                if path == "/library/sections/2/all":
                    return self._page(fx.MOVIES)
                return None

        return Handler
