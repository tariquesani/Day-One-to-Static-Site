import http.server
import socketserver
import webbrowser
import sys
from pathlib import Path

PORT = 8000


def _get_script_dir():
    """Base directory of script/exe. Handles PyInstaller --onefile (temp extraction)."""
    if not getattr(sys, 'frozen', False):
        return Path(__file__).parent.resolve()

    exe_dir = Path(sys.executable).parent.resolve()
    path_str = str(exe_dir).lower()

    # PyInstaller onefile: exe runs from temp (_MEIPASS). Get real exe location.
    if '_meipass' in path_str or ('_mei' in path_str and 'temp' in path_str):
        if sys.platform == 'win32':
            try:
                import ctypes
                buf = ctypes.create_unicode_buffer(1024)
                n = ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 1024)
                if n > 0:
                    win_dir = Path(buf.value).parent.resolve()
                    if '_meipass' not in str(win_dir).lower():
                        return win_dir
            except Exception:
                pass
        return Path.cwd()

    return exe_dir


SCRIPT_DIR = _get_script_dir()

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
