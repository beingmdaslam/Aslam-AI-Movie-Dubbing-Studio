from html.parser import HTMLParser
from pathlib import Path
import py_compile
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "worker.py"
STUDIO = ROOT / "studio.html"

py_compile.compile(str(WORKER), doraise=True)

class StudioParser(HTMLParser):
    pass

html = STUDIO.read_text(encoding="utf-8")
StudioParser().feed(html)
match = re.search(r"<script>(.*?)</script>", html, flags=re.DOTALL)
if not match:
    raise SystemExit("No inline JavaScript found in studio.html")

node = shutil.which("node")
if not node:
    raise SystemExit("Node.js is required for the studio JavaScript syntax check.")

with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
    handle.write(match.group(1))
    js_path = handle.name

try:
    subprocess.run([node, "--check", js_path], check=True)
finally:
    Path(js_path).unlink(missing_ok=True)

required_routes = [
    '@app.get("/studio")',
    '@app.get("/system/check")',
    '@app.post("/diarize")',
    '@app.post("/translate")',
    '@app.post("/dub-audio")',
    '@app.post("/subtitles/burn-in")',
]
source = WORKER.read_text(encoding="utf-8")
missing = [route for route in required_routes if route not in source]
if missing:
    raise SystemExit("Missing expected API routes: " + ", ".join(missing))

print("Static checks passed: Python syntax, HTML parsing, JavaScript syntax and workflow routes.")
