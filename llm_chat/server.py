"""Tiny local chat demo with a deliberately unavailable LLM response."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).parent


class ChatHandler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="text/html; charset=utf-8"):
        encoded = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (ROOT / "index.html").read_text(encoding="utf-8"))
        else:
            self._send(404, "Not found", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/api/chat":
            self._send(404, "Not found", "text/plain; charset=utf-8")
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send(400, json.dumps({"error": "Некорректный JSON"}), "application/json")
            return

        if not isinstance(payload.get("message"), str) or not payload["message"].strip():
            self._send(400, json.dumps({"error": "Введите сообщение"}), "application/json")
            return

        response = {
            "error": "Сейчас пока ничего не работает, но скоро будет.",
            "status": "unavailable",
        }
        self._send(200, json.dumps(response, ensure_ascii=False), "application/json")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), ChatHandler)
    print("Chat is running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
