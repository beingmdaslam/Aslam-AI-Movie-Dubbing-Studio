import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import torch
import torchaudio
import torch.nn.functional as F
from speechbrain.inference.speaker import EncoderClassifier

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
import argostranslate.package
import argostranslate.translate
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
_speaker_model = None


class TranslationRequest(BaseModel):
    sourceLanguage: str = Field(min_length=2, max_length=10, pattern=r"^[a-z]{2,3}$")
    targetLanguage: str = Field(min_length=2, max_length=10, pattern=r"^[a-z]{2,3}$")
    segments: list[dict] = Field(min_length=1, max_length=5000)


class InstallTranslationRequest(BaseModel):
    sourceLanguage: str = Field(min_length=2, max_length=10, pattern=r"^[a-z]{2,3}$")
    targetLanguage: str = Field(min_length=2, max_length=10, pattern=r"^[a-z]{2,3}$")


class SubtitleRequest(BaseModel):
    segments: list[dict] = Field(min_length=1, max_length=10000)
    useSourceText: bool = False


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
        "stage": "transcription_and_translation",
        "translationEngine": "Argos Translate (local open-source)",
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

@app.get("/translation/languages")
def translation_languages():
    installed = argostranslate.translate.get_installed_languages()
    return {
        "ok": True,
        "installed": [
            {"code": language.code, "name": language.name}
            for language in installed
        ],
    }


@app.post("/translation/install")
def install_translation_pair(request: InstallTranslationRequest):
    if request.sourceLanguage == request.targetLanguage:
        raise HTTPException(status_code=400, detail="Choose two different languages.")

    try:
        argostranslate.package.update_package_index()
        packages = argostranslate.package.get_available_packages()
        match = next(
            (
                package for package in packages
                if package.from_code == request.sourceLanguage
                and package.to_code == request.targetLanguage
            ),
            None,
        )
        if match is None:
            raise HTTPException(
                status_code=404,
                detail="No direct free Argos model is listed for this language pair.",
            )

        package_path = match.download()
        argostranslate.package.install_from_path(package_path)
        return {
            "ok": True,
            "installed": True,
            "sourceLanguage": request.sourceLanguage,
            "targetLanguage": request.targetLanguage,
            "message": "Free translation model installed locally.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        print("Argos model installation error:", repr(exc))
        raise HTTPException(
            status_code=502,
            detail="Could not download or install the free translation model.",
        )


@app.post("/translate")
def translate_segments(request: TranslationRequest):
    if request.sourceLanguage == request.targetLanguage:
        return {
            "ok": True,
            "stage": "translation_complete",
            "segments": request.segments,
        }

    installed = argostranslate.translate.get_installed_languages()
    source = next(
        (language for language in installed if language.code == request.sourceLanguage),
        None,
    )
    target = next(
        (language for language in installed if language.code == request.targetLanguage),
        None,
    )

    if source is None or target is None:
        raise HTTPException(
            status_code=409,
            detail="One or both language models are missing. Install the language pair first.",
        )

    translator = source.get_translation(target)
    if translator is None:
        raise HTTPException(
            status_code=409,
            detail="No installed translation route exists for this language pair.",
        )

    translated = []
    for index, segment in enumerate(request.segments):
        text = segment.get("text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(
                status_code=400,
                detail=f"Segment {index} has no valid text.",
            )
        try:
            translated_text = translator.translate(text)
        except Exception as exc:
            print("Segment translation error:", repr(exc))
            raise HTTPException(
                status_code=500,
                detail=f"Translation failed at segment {index}.",
            )

        translated.append({
            **segment,
            "sourceText": text,
            "text": translated_text,
        })

    return {
        "ok": True,
        "stage": "translation_complete",
        "sourceLanguage": request.sourceLanguage,
        "targetLanguage": request.targetLanguage,
        "segments": translated,
        "note": "Timestamps and word alignment are retained from the source transcript. Review translated dialogue before voice generation.",
    }

def srt_timestamp(seconds):
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{millis:03}"


@app.post("/subtitles/srt", response_class=PlainTextResponse)
def create_srt(request: SubtitleRequest):
    lines = []
    for index, segment in enumerate(request.segments, start=1):
        try:
            start = float(segment["start"])
            end = float(segment["end"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Segment {index} has invalid start/end timestamps.",
            )

        if start < 0 or end <= start:
            raise HTTPException(
                status_code=400,
                detail=f"Segment {index} has an invalid time range.",
            )

        text_value = segment.get(
            "sourceText" if request.useSourceText else "text"
        )
        if not isinstance(text_value, str) or not text_value.strip():
            raise HTTPException(
                status_code=400,
                detail=f"Segment {index} has no subtitle text.",
            )

        lines.extend([
            str(index),
            f"{srt_timestamp(start)} --> {srt_timestamp(end)}",
            text_value.strip(),
            "",
        ])

    return PlainTextResponse(
        "\\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="aslam-ai-subtitles.srt"'},
    )

def get_speaker_model():
    global _speaker_model
    if _speaker_model is None:
        _speaker_model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="pretrained_models/spkrec-ecapa-voxceleb",
            run_opts={"device": "cpu"},
        )
    return _speaker_model


@app.post("/diarize")
async def diarize(video: UploadFile = File(...)):
    """Transcribe a video and group utterance segments by similar voice embeddings."""
    filename = Path(video.filename or "upload.mp4").name
    suffix = Path(filename).suffix.lower()
    allowed = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported video format.")

    with tempfile.TemporaryDirectory(prefix="aslam-diarize-") as temp_dir:
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
                        raise HTTPException(status_code=413, detail="Local worker limit is 1 GB.")
                    output.write(chunk)
            if size == 0:
                raise HTTPException(status_code=400, detail="The uploaded file is empty.")

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise HTTPException(status_code=500, detail="FFmpeg is not installed.")
            result = subprocess.run(
                [ffmpeg, "-y", "-i", str(source_path), "-vn", "-ac", "1",
                 "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path)],
                capture_output=True, text=True, timeout=60 * 60,
            )
            if result.returncode != 0 or not audio_path.exists():
                raise HTTPException(status_code=422, detail="Could not extract video audio.")

            whisper = get_model()
            segments_iter, info = whisper.transcribe(
                str(audio_path), beam_size=5, vad_filter=True, word_timestamps=True
            )
            segments = list(segments_iter)
            waveform, sample_rate = torchaudio.load(str(audio_path))
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
            if sample_rate != 16000:
                waveform = torchaudio.functional.resample(waveform, sample_rate, 16000)

            encoder = get_speaker_model()
            known_speakers = []
            output_segments = []
            for segment in segments:
                start = max(0, int(segment.start * 16000))
                end = min(waveform.shape[1], int(segment.end * 16000))
                crop = waveform[:, start:end]
                speaker_id = "speaker_unknown"
                # Very short utterances do not provide reliable speaker embeddings.
                if crop.shape[1] >= 16000:
                    with torch.no_grad():
                        embedding = encoder.encode_batch(crop).squeeze().detach().cpu()
                    best_index = -1
                    best_score = -1.0
                    for index, known in enumerate(known_speakers):
                        score = F.cosine_similarity(
                            embedding.unsqueeze(0), known["embedding"].unsqueeze(0)
                        ).item()
                        if score > best_score:
                            best_score = score
                            best_index = index
                    if best_index >= 0 and best_score >= 0.72:
                        speaker_id = known_speakers[best_index]["id"]
                        previous = known_speakers[best_index]["embedding"]
                        known_speakers[best_index]["embedding"] = (
                            previous * 0.7 + embedding * 0.3
                        )
                        known_speakers[best_index]["embedding"] = F.normalize(
                            known_speakers[best_index]["embedding"], dim=0
                        )
                    else:
                        speaker_id = f"speaker_{len(known_speakers) + 1:02d}"
                        known_speakers.append({
                            "id": speaker_id,
                            "embedding": F.normalize(embedding, dim=0),
                        })

                output_segments.append({
                    "start": round(segment.start, 3),
                    "end": round(segment.end, 3),
                    "text": segment.text.strip(),
                    "speakerId": speaker_id,
                    "words": [
                        {"start": round(word.start, 3), "end": round(word.end, 3),
                         "text": word.word}
                        for word in (segment.words or [])
                    ],
                })

            return {
                "ok": True,
                "stage": "speaker_diarization_complete",
                "detectedLanguage": info.language,
                "speakerCount": len(known_speakers),
                "speakers": [
                    {"speakerId": item["id"], "label": f"Character {i + 1}"}
                    for i, item in enumerate(known_speakers)
                ],
                "segments": output_segments,
                "warning": "Automatic speaker grouping is an estimate. Short lines are marked speaker_unknown; review and correct speaker labels before voice assignment.",
            }
        except HTTPException:
            raise
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Audio extraction timed out.")
        except Exception as exc:
            print("Speaker diarization error:", repr(exc))
            raise HTTPException(
                status_code=500,
                detail="Speaker detection failed. Check installed PyTorch, torchaudio and model downloads.",
            )
        finally:
            await video.close()

