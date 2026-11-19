import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

app = FastAPI(title="ASLAM AI Free Local Worker", version="0.1.0")

# Local development origins only. Add the final app origin when the frontend
# is connected to this worker; do not expose this service publicly without auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8888",
        "http://127.0.0.1:8888",
        "https://dazzling-sawine-32156a.netlify.app",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
MAX_UPLOAD_BYTES = 1024 * 1024 * 1024  # 1 GB local-worker safety cap
_model = None


def get_model():
    global _model
    if _model is None:
        _model = WhisperModel(
            MODEL_SIZE,
            device="cpu",
            compute_type=COMPUTE_TYPE,
        )
    return _model


@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "ASLAM AI Free Local Worker",
        "stage": "audio_transcription",
        "model": MODEL_SIZE,
        "device": "cpu",
    }


@app.post("/transcribe")
async def transcribe(video: UploadFile = File(...)):
    filename = Path(video.filename or "upload.mp4").name
    suffix = Path(filename).suffix.lower()
    allowed = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported video format.")

    with tempfile.TemporaryDirectory(prefix="aslam-ai-") as temp_dir:
        source_path = Path(temp_dir) / filename
        audio_path = Path(temp_dir) / "audio.wav"
        size = 0

        try:
            with source_path.open("wb") as output:
                while True:
                    chunk = await video.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail="Local worker limit is 1 GB per video.",
                        )
                    output.write(chunk)

            if size == 0:
                raise HTTPException(status_code=400, detail="The uploaded file is empty.")

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise HTTPException(
                    status_code=500,
                    detail="FFmpeg is not installed on the worker computer.",
                )

            command = [
                ffmpeg, "-y", "-i", str(source_path),
                "-vn", "-ac", "1", "-ar", "16000",
                "-c:a", "pcm_s16le", str(audio_path),
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=60 * 60
            )
            if result.returncode != 0 or not audio_path.exists():
                raise HTTPException(
                    status_code=422,
                    detail="Could not extract audio from this video.",
                )

            model = get_model()
            segments, info = model.transcribe(
                str(audio_path),
                beam_size=5,
                vad_filter=True,
                word_timestamps=True,
            )

            transcript = []
            for segment in segments:
                words = []
                if segment.words:
                    words = [
                        {
                            "start": round(word.start, 3),
                            "end": round(word.end, 3),
                            "text": word.word,
                        }
                        for word in segment.words
                    ]
                transcript.append({
                    "start": round(segment.start, 3),
                    "end": round(segment.end, 3),
                    "text": segment.text.strip(),
                    "words": words,
                })

            return {
                "ok": True,
                "stage": "transcription_complete",
                "detectedLanguage": info.language,
                "languageProbability": round(info.language_probability, 4),
                "durationSeconds": round(info.duration, 2),
                "segments": transcript,
                "note": "Transcript only. Translation, voice generation, mixing, lip-sync and final video export are separate stages.",
            }
        except HTTPException:
            raise
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Audio extraction timed out.")
        except Exception as exc:
            print("Local transcription worker error:", repr(exc))
            raise HTTPException(
                status_code=500,
                detail="Transcription failed. Check worker logs and available RAM.",
            )
        finally:
            await video.close()
