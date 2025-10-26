import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import yaml  # new import

ICS_PATH = Path(__file__).resolve().parent / "ics18tickets.ics"
HOST = "0.0.0.0"
DEFAULT_PORT = 8091

# load port from config.yml if available, otherwise use DEFAULT_PORT
CONFIG_PATH = Path(__file__).resolve().parent / "config.yml"
def _load_port(default: int = DEFAULT_PORT) -> int:
    try:
        if CONFIG_PATH.exists():
            cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
            port = int(cfg.get("port", default))
            return port
    except Exception:
        # on any error, fall back to default
        pass
    return default

PORT = _load_port()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stdout.write("%s - - [%s] %s\n" %
                         (self.client_address[0], self.log_date_time_string(), fmt % args))
        sys.stdout.flush()

    def _respond_ics(self, send_body=True):
        try:
            data = ICS_PATH.read_bytes()
        except Exception:
            self.send_response(503)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            if send_body:
                self.wfile.write(b"Service unavailable: calendar file not found\n")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/calendar; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if send_body:
            self.wfile.write(data)

    def do_HEAD(self):
        if self.path in ("/", "/ics18tickets.ics", "/ics/ics18tickets.ics"):
            self._respond_ics(send_body=False)
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "2")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/ics18tickets.ics", "/ics/ics18tickets.ics"):
            self._respond_ics(send_body=True)
        elif self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run():
    httpd = HTTPServer((HOST, PORT), Handler)

    def _shutdown(signum, frame):
        print(f"Received signal {signum}, shutting down...", file=sys.stderr)
        httpd.shutdown()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    print(f"Serving {ICS_PATH} on {HOST}:{PORT}", file=sys.stderr)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        print("Server stopped", file=sys.stderr)

if __name__ == "__main__":
    run()