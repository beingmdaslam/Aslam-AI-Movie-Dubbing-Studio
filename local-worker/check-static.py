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
for safety_check in ("10*1024*1024", "20*1024*1024", "invalid entries skipped", "allowedVoices=new Set", "e.source.length>10000", "e.translated.length>10000"):
    if safety_check not in mobile_source:
        raise SystemExit("Mobile subtitle/project import safety check is missing: " + safety_check)
for required_ui in ('id="transcribeVideo"', 'id="translateAll"', 'id="loadTts"', 'id="generateDub"', 'id="renderMp4"', 'id="outputQuality"', 'id="ttsEngine"', 'id="exportSrt"', 'id="saveProject"', 'speakerInput.className="speaker"'):
    if required_ui not in mobile_source:
        raise SystemExit("Missing mobile workflow control: " + required_ui)
for module_name in ("asr.js", "translation.js", "tts.js", "render.js", "ffmpeg-worker.js", "ffmpeg-constants.js", "ffmpeg-errors.js", "supertonic-helper.js"):
    module_path = ROOT.parent / module_name
    if not module_path.exists():
        raise SystemExit("Missing mobile processing module: " + module_name)
    subprocess.run([shutil.which("node") or "node", "--check", str(module_path)], check=True)



if 'className="speakerVoice"' not in mobile_source or 'voice:c.querySelector(".speakerVoice")' not in mobile_source:
    raise SystemExit("Per-character voice styles must be editable and saved in project JSON.")
if 'supertonic-helper.js' not in (ROOT.parent / "sw.js").read_text(encoding="utf-8"):
    raise SystemExit("PWA cache must include the optional Supertonic TTS helper.")
if 'supertone-oss-archive/supertonic-3' not in (ROOT.parent / "tts.js").read_text(encoding="utf-8"):
    raise SystemExit("Supertonic multilingual model source is not configured.")

asr_source = (ROOT.parent / "asr.js").read_text(encoding="utf-8")
if "window.addLine=addLine" not in mobile_source or "window.addLine(" not in asr_source:
    raise SystemExit("Whisper transcription must connect to the dialogue editor.")
if any(name in asr_source for name in ("asrPipeline", "transcribeButton", "asrMessage")):
    raise SystemExit("Whisper memory release contains stale variable names.")
if 'window.aslamASRBusy=true' not in asr_source or 'window.aslamTTSBusy=true' not in (ROOT.parent / "tts.js").read_text(encoding="utf-8"):
    raise SystemExit("Mobile AI model memory coordination is missing.")
if "await window.aslamReleaseTTS()" not in asr_source:
    raise SystemExit("Whisper must wait for TTS model release before allocating memory.")
if "video.duration>900" not in asr_source:
    raise SystemExit("Whisper transcription must be capped at 15 minutes on phones.")
if 'value="ru"' not in mobile_source or 'ru:"russian"' not in asr_source:
    raise SystemExit("Russian language option is missing from mobile transcription.")


tts_source = (ROOT.parent / "tts.js").read_text(encoding="utf-8")
if 'ur:"payam1394/traxlate-mms-tts-urd"' not in tts_source or "@huggingface/transformers@3.8.1" not in tts_source:
    raise SystemExit("Urdu local TTS model or Transformers.js runtime is missing.")
if "ort.webgpu.min.js" not in tts_source or "supertonicLanguages" not in tts_source:
    raise SystemExit("Supertonic must use the WebGPU-capable ONNX Runtime bundle and language guard.")
if 'const maxDuration=engine==="supertonic"?300:900' not in tts_source:
    raise SystemExit("Supertonic phone-memory duration limit is missing.")
if 'releaseSupertonic().catch(()=>{})' not in tts_source:
    raise SystemExit("Supertonic memory should be released when switching to an unsupported language.")
if "dist/esm" not in (ROOT.parent / "render.js").read_text(encoding="utf-8"):
    raise SystemExit("FFmpeg module worker must load the ESM core.")

if 'classWorkerURL:new URL("/ffmpeg-worker.js"' not in (ROOT.parent / "render.js").read_text(encoding="utf-8"):
    raise SystemExit("FFmpeg renderer must use the same-origin worker.")
if not all(path in (ROOT.parent / "sw.js").read_text(encoding="utf-8") for path in ("/ffmpeg-worker.js", "/ffmpeg-constants.js", "/ffmpeg-errors.js")):
    raise SystemExit("PWA cache must include the same-origin FFmpeg worker files.")
print("Static checks passed: Python syntax, all HTML and JavaScript modules, mobile controls, FFmpeg worker, local routes and no R2 upload call.")
