import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

VERSION = os.environ.get("DAVDEPLOY_TEST_VERSION", "local")
SCOPE = os.environ.get("DAVDEPLOY_TEST_SCOPE", "same-account-customer-sandbox")
FAIL_HEALTH = os.environ.get("DAVDEPLOY_TEST_FAIL_HEALTH", "false").lower() == "true"


def response(status, payload):
    body = json.dumps(payload, sort_keys=True).encode()
    return status, body


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {"/healthz", "/version"}:
            self.send_error(404)
            return

        if self.path == "/healthz":
            status, body = response(
                503 if FAIL_HEALTH else 200,
                {
                    "status": "unhealthy" if FAIL_HEALTH else "ok",
                    "scope": SCOPE,
                    "version": VERSION,
                },
            )
        else:
            status, body = response(200, {"version": VERSION, "scope": SCOPE})

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8000"))), Handler).serve_forever()
