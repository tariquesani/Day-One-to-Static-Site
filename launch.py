import http.server
import socketserver
import webbrowser
import sys
from pathlib import Path

PORT = 8000

# Directory of this script or executable (when frozen, e.g. PyInstaller)
SCRIPT_DIR = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).parent.resolve()

# Use script dir as root if index.html is there, otherwise use archive subfolder
if (SCRIPT_DIR / "index.html").is_file():
    ROOT = SCRIPT_DIR
else:
    ROOT = SCRIPT_DIR / "archive"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_request(self, code="-", size="-"):
        if code != "-":
            try:
                code_int = int(code)
                if 400 <= code_int < 600:
                    super().log_request(code, size)
            except (ValueError, TypeError):
                super().log_request(code, size)

try:
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        url = f"http://127.0.0.1:{PORT}/index.html"
        print(f"Serving DayOne Archive at {url}")
        webbrowser.open(url)
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nShutting down server...")
    sys.exit(0)
