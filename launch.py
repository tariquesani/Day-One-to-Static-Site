import http.server
import socketserver
import webbrowser
import sys
from pathlib import Path

PORT = 8000

# Resolve directory of the executable itself
# ROOT = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).parent.resolve()
ROOT = "archive"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    url = f"http://127.0.0.1:{PORT}/index.html"
    print(f"Serving DayOne Archive at {url}")
    webbrowser.open(url)
    httpd.serve_forever()
