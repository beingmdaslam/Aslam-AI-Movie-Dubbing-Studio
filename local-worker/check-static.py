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

html_files = [STUDIO, ROOT.parent / "index.html", ROOT.parent / "mobile-studio.html"]
for html_path in html_files:
    html = html_path.read_text(encoding="utf-8")
    StudioParser().feed(html)
    scripts = re.findall(r"<script>(.*?)</script>", html, flags=re.DOTALL)
    if not scripts:
        raise SystemExit(f"No inline JavaScript found in {html_path.name}")
    for script in scripts:
        node = shutil.which("node")
        if not node:
            raise SystemExit("Node.js is required for JavaScript syntax checks.")
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
            handle.write(script)
            js_path = handle.name
        try:
            subprocess.run([node, "--check", js_path], check=True)
        finally:
            Path(js_path).unlink(missing_ok=True)


required_routes = [
    '@app.get("/studio")',
    '@app.get("/system/check")',
    '@app.post("/transcribe")',
    '@app.post("/diarize")',
    '@app.get("/translation/languages")',
    '@app.post("/translate")',
    '@app.post("/subtitles/srt"',
    '@app.post("/translation/install")',
    '@app.post("/speakers/assign")',
    '@app.post("/subtitles/burn-in")',
    '@app.get("/lip-sync/status")',
    '@app.post("/lip-sync")',
]
source = WORKER.read_text(encoding="utf-8")
missing = [route for route in required_routes if route not in source]
if missing:
    raise SystemExit("Missing expected API routes: " + ", ".join(missing))

if r'"\\n".join(lines)' in source:
    raise SystemExit("SRT exporter contains a literal \\n instead of real line breaks.")

index_source = (ROOT.parent / "index.html").read_text(encoding="utf-8")
if '/.netlify/functions/create-upload' in index_source:
    raise SystemExit("Main START button must not upload videos to paid/cloud storage.")
if 'mobile-studio.html' not in index_source:
    raise SystemExit("Main START button must open the phone-only mobile studio.")
if "Voice Matching" in index_source or "Character Voices / Clone" in index_source:
    raise SystemExit("The main page must not advertise voice cloning in the current steps 2-5 workflow.")
if 'window.location.href = "mobile-studio.html"' not in index_source:
    raise SystemExit("The main START action must hand off to the phone-only mobile studio.")
studio_source = STUDIO.read_text(encoding="utf-8")
if 'Voice cloning is intentionally excluded' not in studio_source:
    raise SystemExit("The current studio must clearly exclude voice cloning.")
for required_ui in ('/diarize', '/translation/install', '/translate', '/subtitles/srt', '/subtitles/burn-in', '/lip-sync'):
    if required_ui not in studio_source:
        raise SystemExit("Missing current studio workflow stage: " + required_ui)
if '/dub-audio' in studio_source or 'XTTS' in studio_source or 'generateDub' in studio_source:
    raise SystemExit("Voice cloning / XTTS must not be part of the current guided studio.")
if 'Character name' not in studio_source or 'updateSpeakerOptions' not in studio_source:
    raise SystemExit("Speaker review must let users rename detected characters and update dialogue assignment options.")
wav2lip_setup = (ROOT / "setup-wav2lip-windows.bat").read_text(encoding="utf-8")
if "py -3.8" not in wav2lip_setup or "WAV2LIP_PYTHON" not in wav2lip_setup:
    raise SystemExit("Wav2Lip setup must create and configure a separate Python 3.8 environment.")
if "setx PYTHON " in wav2lip_setup:
    raise SystemExit("Wav2Lip setup must not overwrite the global PYTHON setting.")
if "%%~zA LSS 1000000" not in wav2lip_setup or "%%~zA LSS 10000000" not in wav2lip_setup:
    raise SystemExit("Wav2Lip setup must reject incomplete model weight files.")

wav_helper = (ROOT / "configure-wav2lip-windows.bat").read_text(encoding="utf-8")
if "WAV2LIP_PYTHON" not in wav_helper or "setx WAV2LIP_PYTHON" not in wav_helper:
    raise SystemExit("Wav2Lip setup helper must support a separate Python environment.")
if "import torch, torchvision, cv2, librosa, numpy" not in wav_helper:
    raise SystemExit("Wav2Lip configuration must verify its separate runtime dependencies.")


mobile_source = (ROOT.parent / "mobile-studio.html").read_text(encoding="utf-8")
for required_ui in ('id="transcribeVideo"', 'id="translateAll"', 'id="loadTts"', 'id="generateDub"', 'id="renderMp4"', 'id="exportSrt"', 'id="saveProject"', 'speakerInput.className="speaker"'):
    if required_ui not in mobile_source:
        raise SystemExit("Missing mobile workflow control: " + required_ui)
for module_name in ("asr.js", "translation.js", "tts.js", "render.js"):
    module_path = ROOT.parent / module_name
    if not module_path.exists():
        raise SystemExit("Missing mobile processing module: " + module_name)
    subprocess.run([shutil.which("node") or "node", "--check", str(module_path)], check=True)

print("Static checks passed: Python syntax, both HTML pages, JavaScript syntax, local workflow routes and no R2 upload call.")
