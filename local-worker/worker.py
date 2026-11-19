import asyncio
import os
import sys
import threading
import shutil
import subprocess
import tempfile
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware

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
_tts_model = None
_wav2lip_lock = threading.Lock()


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
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Transcription package is missing. Run setup-windows.bat again.") from exc
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
        "stage": "local_transcription_translation_speaker_subtitle_and_lip_sync",
        "translationEngine": "Argos Translate (local open-source)",
        "speakerEngine": "SpeechBrain ECAPA (local)",
            "renderEngine": "FFmpeg",
        "model": MODEL_SIZE,
        "device": "cpu",
    }


@app.get("/studio")
def local_studio():
    studio_path = Path(__file__).with_name("studio.html")
    if not studio_path.is_file():
        raise HTTPException(status_code=404, detail="Local studio page was not found.")
    return FileResponse(studio_path, media_type="text/html")


@app.get("/system/check")
def system_check():
    """Report local prerequisites without downloading models or changing the machine."""
    import importlib.util

    ffmpeg_path = shutil.which("ffmpeg")
    checks = {
        "ffmpeg": {"available": bool(ffmpeg_path), "path": ffmpeg_path},
        "whisper": {"available": importlib.util.find_spec("faster_whisper") is not None},
        "argosTranslate": {"available": importlib.util.find_spec("argostranslate") is not None},
        "speechbrain": {"available": importlib.util.find_spec("speechbrain") is not None},
        "torch": {"available": importlib.util.find_spec("torch") is not None},
        "torchaudio": {"available": importlib.util.find_spec("torchaudio") is not None},
        "xttsPackage": {"available": importlib.util.find_spec("TTS") is not None},
    }
    return {
        "ok": all(checks[key]["available"] for key in ("ffmpeg", "whisper", "argosTranslate", "speechbrain", "torch", "torchaudio")),
        "readyForAnalysis": all(checks[key]["available"] for key in ("ffmpeg", "whisper", "argosTranslate", "speechbrain", "torch", "torchaudio")),
        "readyForVoiceGeneration": checks["xttsPackage"]["available"],
        "checks": checks,
        "notes": [
            "XTTS is optional and has a separate model license.",
            "Wav2Lip requires a separate repository and checkpoint.",
            "This check does not download models or prove that full movie processing will succeed.",
        ],
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
    try:
        import argostranslate.translate
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Argos Translate is not installed. Run setup-windows.bat.") from exc
    installed = argostranslate.translate.get_installed_languages()
    return {
        "ok": True,
        "installed": [
            {"code": language.code, "name": language.name}
            for language in installed
        ],
    }


def _installed_translation_route(source_code, target_code, installed_languages):
    """Return installed direct or English-pivot translators, or None."""
    source = next((item for item in installed_languages if item.code == source_code), None)
    target = next((item for item in installed_languages if item.code == target_code), None)
    if source is None or target is None:
        return None
    direct = source.get_translation(target)
    if direct is not None:
        return [direct]
    if source_code != "en" and target_code != "en":
        english = next((item for item in installed_languages if item.code == "en"), None)
        if english is not None:
            first = source.get_translation(english)
            second = english.get_translation(target)
            if first is not None and second is not None:
                return [first, second]
    return None


@app.post("/translation/install")
def install_translation_pair(request: InstallTranslationRequest):
    try:
        import argostranslate.package
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Argos Translate is not installed. Run setup-windows.bat.") from exc
    if request.sourceLanguage == request.targetLanguage:
        raise HTTPException(status_code=400, detail="Choose two different languages.")

    try:
        # Language presence alone does not mean the requested pair is installed.
        # Return early only when a usable direct or English-pivot route exists.
        try:
            import argostranslate.translate
            existing_languages = argostranslate.translate.get_installed_languages()
            existing_route = _installed_translation_route(
                request.sourceLanguage, request.targetLanguage, existing_languages
            )
            if existing_route:
                return {
                    "ok": True,
                    "installed": True,
                    "alreadyInstalled": True,
                    "sourceLanguage": request.sourceLanguage,
                    "targetLanguage": request.targetLanguage,
                    "installedPairs": [],
                    "route": "direct" if len(existing_route) == 1 else "via English",
                    "message": "A usable local translation route is already installed.",
                }
        except ImportError:
            pass
        argostranslate.package.update_package_index()
        packages = argostranslate.package.get_available_packages()
        # Prefer a direct model. If Argos does not publish one, try a
        # two-step route through English (source -> en -> target).
        route_options = [[(request.sourceLanguage, request.targetLanguage)]]
        if request.sourceLanguage != "en" and request.targetLanguage != "en":
            route_options.append([
                (request.sourceLanguage, "en"),
                ("en", request.targetLanguage),
            ])

        selected_route = None
        for route in route_options:
            route_packages = []
            for from_code, to_code in route:
                match = next(
                    (
                        package for package in packages
                        if package.from_code == from_code
                        and package.to_code == to_code
                    ),
                    None,
                )
                if match is None:
                    route_packages = []
                    break
                route_packages.append(match)
            if route_packages:
                selected_route = route_packages
                break

        if not selected_route:
            raise HTTPException(
                status_code=404,
                detail=(
                    "No free Argos translation route is listed for this language pair, "
                    "including the English-pivot option."
                ),
            )

        installed_pairs = []
        for package in selected_route:
            package_path = package.download()
            argostranslate.package.install_from_path(package_path)
            installed_pairs.append({
                "source": package.from_code,
                "target": package.to_code,
            })

        return {
            "ok": True,
            "installed": True,
            "sourceLanguage": request.sourceLanguage,
            "targetLanguage": request.targetLanguage,
            "installedPairs": installed_pairs,
            "route": "direct" if len(installed_pairs) == 1 else "via English",
            "message": "Free translation model route installed locally.",
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

    try:
        import argostranslate.translate
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Argos Translate is not installed. Run setup-windows.bat.") from exc
    installed = argostranslate.translate.get_installed_languages()
    route = _installed_translation_route(
        request.sourceLanguage, request.targetLanguage, installed
    )

    if not route:
        raise HTTPException(
            status_code=409,
            detail="No installed direct or English-pivot translation route exists for this language pair. Install the pair first.",
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
            translated_text = text
            for translator in route:
                translated_text = translator.translate(translated_text)
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
        "\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="aslam-ai-subtitles.srt"'},
    )

def _normalise_embedding(values):
    vector = [float(value) for value in values]
    magnitude = sum(value * value for value in vector) ** 0.5
    if not vector or magnitude == 0:
        raise ValueError("Speaker model returned an empty embedding.")
    return [value / magnitude for value in vector]


def _cosine_similarity(left, right):
    if len(left) != len(right):
        raise ValueError("Speaker embeddings have incompatible dimensions.")
    return sum(a * b for a, b in zip(left, right))


def _assign_speaker_embedding(embedding, known_speakers, threshold=0.72):
    """Assign a normalized SpeechBrain embedding to the closest known voice."""
    normalized = _normalise_embedding(embedding)
    best_index = -1
    best_score = -1.0
    for index, known in enumerate(known_speakers):
        score = _cosine_similarity(normalized, known["embedding"])
        if score > best_score:
            best_score = score
            best_index = index

    if best_index >= 0 and best_score >= threshold:
        speaker_id = known_speakers[best_index]["id"]
        previous = known_speakers[best_index]["embedding"]
        known_speakers[best_index]["embedding"] = _normalise_embedding(
            [old * 0.7 + new * 0.3 for old, new in zip(previous, normalized)]
        )
        return speaker_id

    speaker_id = f"speaker_{len(known_speakers) + 1:02d}"
    known_speakers.append({"id": speaker_id, "embedding": normalized})
    return speaker_id


def get_speaker_model():
    global _speaker_model
    if _speaker_model is None:
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError as exc:
            raise RuntimeError("Speaker detection packages are missing. Run setup-windows.bat.") from exc
        _speaker_model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir="pretrained_models/spkrec-ecapa-voxceleb",
            run_opts={"device": "cpu"},
        )
    return _speaker_model


@app.post("/diarize")
async def diarize(video: UploadFile = File(...)):
    """Transcribe a video and group utterance segments by similar voice embeddings."""
    try:
        import torch
        import torchaudio
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Speaker detection packages are missing. Run setup-windows.bat.") from exc
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
                        embedding = (
                            encoder.encode_batch(crop)
                            .squeeze()
                            .detach()
                            .cpu()
                            .tolist()
                        )
                    speaker_id = _assign_speaker_embedding(
                        embedding, known_speakers
                    )

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

# XTTS-v2 is loaded only when the user requests voice generation.
XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
SUPPORTED_XTTS_LANGUAGES = {
    "ar", "zh-cn", "cs", "nl", "en", "fr", "de", "hi",
    "hu", "it", "ja", "ko", "pl", "pt", "ru", "es", "tr",
}


def get_tts_model():
    global _tts_model
    if _tts_model is None:
        try:
            from TTS.api import TTS
        except ImportError as exc:
            raise RuntimeError(
                "Voice generation dependencies are missing. Install the optional XTTS package."
            ) from exc
        _tts_model = TTS(
            model_name=XTTS_MODEL_NAME,
            progress_bar=False,
            gpu=False,
        )
    return _tts_model


@app.get("/tts/languages")
def tts_languages():
    return {
        "ok": True,
        "engine": "Coqui XTTS-v2 (local)",
        "languages": sorted(SUPPORTED_XTTS_LANGUAGES),
        "note": "Language support and pronunciation quality vary. First use downloads model files.",
    }


@app.post("/tts/clone")
async def clone_voice(
    text: str = Form(..., min_length=1, max_length=1500),
    language: str = Form(..., min_length=2, max_length=5),
    reference_audio: UploadFile = File(...),
):
    """Generate one line in a voice matching an audio sample supplied by the user."""
    language = language.lower().strip()
    if language not in SUPPORTED_XTTS_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail="This language is not supported by the configured XTTS-v2 model.",
        )

    reference_suffix = Path(reference_audio.filename or "voice.wav").suffix.lower()
    if reference_suffix not in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
        raise HTTPException(
            status_code=400,
            detail="Voice sample must be WAV, MP3, M4A, FLAC or OGG.",
        )

    with tempfile.TemporaryDirectory(prefix="aslam-voice-") as temp_dir:
        reference_path = Path(temp_dir) / f"reference{reference_suffix}"
        output_path = Path(temp_dir) / "generated.wav"
        size = 0
        try:
            with reference_path.open("wb") as output:
                while True:
                    chunk = await reference_audio.read(256 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > 20 * 1024 * 1024:
                        raise HTTPException(
                            status_code=413,
                            detail="Voice sample limit is 20 MB.",
                        )
                    output.write(chunk)

            if size == 0:
                raise HTTPException(status_code=400, detail="Voice sample is empty.")

            engine = get_tts_model()
            engine.tts_to_file(
                text=text.strip(),
                speaker_wav=str(reference_path),
                language=language,
                file_path=str(output_path),
            )
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError("The voice model did not produce an audio file.")

            audio_bytes = output_path.read_bytes()
            return Response(
                content=audio_bytes,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": 'attachment; filename="aslam-ai-voice.wav"'
                },
            )
        except HTTPException:
            raise
        except Exception as exc:
            print("Local voice generation error:", repr(exc))
            raise HTTPException(
                status_code=500,
                detail="Voice generation failed. Check XTTS model download, language code and worker logs.",
            )
        finally:
            await reference_audio.close()

@app.post("/dub-audio")
async def dub_audio(
    video: UploadFile = File(...),
    segments_json: str = Form(...),
    speaker_ids_json: str = Form(...),
    voice_samples: list[UploadFile] = File(...),
    language: str = Form(...),
    background_volume: float = Form(0.18, ge=0.0, le=1.0),
):
    """Generate assigned character voices, place each line at its timestamp and mux audio with video."""
    import json

    language = language.lower().strip()
    if language not in SUPPORTED_XTTS_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unsupported XTTS language code.")

    try:
        segments = json.loads(segments_json)
        speaker_ids = json.loads(speaker_ids_json)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="Segments or speaker IDs contain invalid JSON.")

    if not isinstance(segments, list) or not segments or len(segments) > 2000:
        raise HTTPException(status_code=400, detail="Provide between 1 and 2000 dialogue segments.")
    if not isinstance(speaker_ids, list) or len(speaker_ids) != len(voice_samples):
        raise HTTPException(status_code=400, detail="Each voice sample must have one matching speaker ID.")
    if len(set(speaker_ids)) != len(speaker_ids) or not all(
        isinstance(item, str) and item.strip() for item in speaker_ids
    ):
        raise HTTPException(status_code=400, detail="Speaker IDs must be unique non-empty strings.")

    voice_map = dict(zip(speaker_ids, voice_samples))
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise HTTPException(status_code=400, detail=f"Segment {index + 1} is invalid.")
        text_value = segment.get("text")
        speaker_id = segment.get("speakerId")
        try:
            start = float(segment.get("start"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Segment {index + 1} has invalid start time.")
        if not isinstance(text_value, str) or not text_value.strip() or len(text_value) > 1500:
            raise HTTPException(status_code=400, detail=f"Segment {index + 1} has invalid dialogue text.")
        try:
            end = float(segment.get("end"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Segment {index + 1} has invalid end time.")
        if start < 0 or end <= start or not isinstance(speaker_id, str) or speaker_id not in voice_map:
            raise HTTPException(
                status_code=400,
                detail=f"Segment {index + 1} needs valid timestamps and an assigned speaker voice.",
            )

    filename = Path(video.filename or "movie.mp4").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}:
        raise HTTPException(status_code=400, detail="Unsupported video format.")

    with tempfile.TemporaryDirectory(prefix="aslam-dub-mix-") as temp_dir:
        root = Path(temp_dir)
        source_path = root / filename
        background_path = root / "background.wav"
        output_path = root / "aslam-ai-dubbed.mp4"
        generated_paths = []
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
                raise HTTPException(status_code=400, detail="Video file is empty.")

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise HTTPException(status_code=500, detail="FFmpeg is not installed.")
            extract = subprocess.run(
                [ffmpeg, "-y", "-i", str(source_path), "-vn", "-ac", "2",
                 "-ar", "24000", str(background_path)],
                capture_output=True, text=True, timeout=60 * 60,
            )
            if extract.returncode != 0 or not background_path.exists():
                raise HTTPException(
                    status_code=422,
                    detail="Could not extract original audio. The video must contain an audio track.",
                )

            # Optional Demucs separation removes most speech/vocals from the backing track.
            # If the package/model is unavailable, keep the original soundtrack at reduced volume.
            background_mix_path = background_path
            separation_used = False
            try:
                import importlib.util
                if (
                    os.getenv("ASLAM_SEPARATE_BACKGROUND", "true").lower() == "true"
                    and importlib.util.find_spec("demucs") is not None
                ):
                    separated_dir = root / "separated"
                    separation = subprocess.run(
                        [
                            sys.executable, "-m", "demucs",
                            "-n", "htdemucs", "--two-stems=vocals",
                            "-o", str(separated_dir), str(background_path),
                        ],
                        capture_output=True, text=True, timeout=6 * 60 * 60,
                    )
                    candidate = separated_dir / "htdemucs" / background_path.stem / "no_vocals.wav"
                    if separation.returncode == 0 and candidate.exists():
                        background_mix_path = candidate
                        separation_used = True
                    else:
                        print("Demucs separation unavailable; using reduced original soundtrack:",
                              separation.stderr[-1500:])
            except Exception as separation_error:
                print("Demucs separation skipped:", repr(separation_error))

            engine = get_tts_model()
            reference_paths = {}
            for speaker_id, upload in voice_map.items():
                ref_suffix = Path(upload.filename or "voice.wav").suffix.lower()
                if ref_suffix not in {".wav", ".mp3", ".m4a", ".flac", ".ogg"}:
                    raise HTTPException(status_code=400, detail=f"Unsupported voice sample for {speaker_id}.")
                ref_path = root / f"voice_{len(reference_paths)}{ref_suffix}"
                ref_size = 0
                with ref_path.open("wb") as output:
                    while True:
                        chunk = await upload.read(256 * 1024)
                        if not chunk:
                            break
                        ref_size += len(chunk)
                        if ref_size > 20 * 1024 * 1024:
                            raise HTTPException(status_code=413, detail="Each voice sample is limited to 20 MB.")
                        output.write(chunk)
                if ref_size == 0:
                    raise HTTPException(status_code=400, detail=f"Voice sample for {speaker_id} is empty.")
                reference_paths[speaker_id] = ref_path

            for index, segment in enumerate(segments):
                generated_path = root / f"line_{index:04d}.wav"
                engine.tts_to_file(
                    text=segment["text"].strip(),
                    speaker_wav=str(reference_paths[segment["speakerId"]]),
                    language=language,
                    file_path=str(generated_path),
                )
                if not generated_path.exists() or generated_path.stat().st_size == 0:
                    raise RuntimeError(f"Voice generation failed for dialogue {index + 1}.")
                generated_paths.append((generated_path, float(segment["start"])))

            # Mix dialogue clips in batches to avoid a huge FFmpeg command for full-length movies.
            dialogue_mix_paths = []
            batch_size = 40
            for batch_number, offset in enumerate(range(0, len(generated_paths), batch_size)):
                batch = generated_paths[offset:offset + batch_size]
                batch_path = root / f"dialogue_mix_{batch_number:03d}.wav"
                batch_command = [ffmpeg, "-y"]
                for generated_path, _ in batch:
                    batch_command.extend(["-i", str(generated_path)])

                batch_filters = []
                batch_labels = []
                for index, (_, start_time) in enumerate(batch):
                    delay_ms = int(round(start_time * 1000))
                    batch_filters.append(
                        f"[{index}:a]adelay={delay_ms}|{delay_ms}[line{index}]"
                    )
                    batch_labels.append(f"[line{index}]")
                batch_filters.append(
                    "".join(batch_labels)
                    + f"amix=inputs={len(batch_labels)}:duration=longest:dropout_transition=0,"
                      "alimiter=limit=0.95[mix]"
                )
                batch_command.extend([
                    "-filter_complex", ";".join(batch_filters),
                    "-map", "[mix]", "-ac", "2", "-ar", "24000",
                    "-c:a", "pcm_s16le", str(batch_path),
                ])
                batch_result = subprocess.run(
                    batch_command, capture_output=True, text=True, timeout=2 * 60 * 60
                )
                if batch_result.returncode != 0 or not batch_path.exists():
                    print("FFmpeg dialogue batch mix error:", batch_result.stderr[-2500:])
                    raise HTTPException(
                        status_code=500,
                        detail=f"Could not mix generated dialogue batch {batch_number + 1}.",
                    )
                dialogue_mix_paths.append(batch_path)

            # Input 0 is the video; input 1 is the background soundtrack.
            command = [ffmpeg, "-y", "-i", str(source_path), "-i", str(background_mix_path)]
            for mix_path in dialogue_mix_paths:
                command.extend(["-i", str(mix_path)])

            filters = [f"[1:a]volume={background_volume:.3f}[bg]"]
            mix_inputs = ["[bg]"]
            for index in range(len(dialogue_mix_paths)):
                filters.append(f"[{index + 2}:a]volume=1.0[dub{index}]")
                mix_inputs.append(f"[dub{index}]")
            filters.append(
                "".join(mix_inputs)
                + f"amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0,"
                  "alimiter=limit=0.95[aout]"
            )
            command.extend([
                "-filter_complex", ";".join(filters),
                "-map", "0:v:0", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", "-shortest", str(output_path),
            ])
            render = subprocess.run(
                command, capture_output=True, text=True, timeout=6 * 60 * 60
            )
            if render.returncode != 0 or not output_path.exists():
                print("FFmpeg dub mix error:", render.stderr[-3000:])
                raise HTTPException(status_code=500, detail="Could not mix dubbed audio into the video.")

            return Response(
                content=output_path.read_bytes(),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": 'attachment; filename="aslam-ai-dubbed.mp4"',
                    "X-ASLAM-Background-Separation": "demucs" if separation_used else "reduced-original-audio",
                },
            )
        except HTTPException:
            raise
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Video dubbing or rendering timed out.")
        except Exception as exc:
            print("Dub audio pipeline error:", repr(exc))
            raise HTTPException(
                status_code=500,
                detail="Dubbing failed. Check XTTS model, voice samples and worker logs.",
            )
        finally:
            await video.close()
            for upload in voice_samples:
                await upload.close()

@app.post("/subtitles/burn-in")
async def burn_in_subtitles(
    video: UploadFile = File(...),
    subtitles: UploadFile = File(...),
    font_size: int = Form(24, ge=12, le=48),
):
    """Burn a supplied SRT subtitle track into a video using FFmpeg."""
    video_name = Path(video.filename or "movie.mp4").name
    video_suffix = Path(video_name).suffix.lower()
    if video_suffix not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}:
        raise HTTPException(status_code=400, detail="Unsupported video format.")
    if Path(subtitles.filename or "subtitles.srt").suffix.lower() != ".srt":
        raise HTTPException(status_code=400, detail="Upload an SRT subtitle file.")

    with tempfile.TemporaryDirectory(prefix="aslam-subtitle-burn-") as temp_dir:
        root = Path(temp_dir)
        video_path = root / video_name
        subtitle_path = root / "captions.srt"
        output_path = root / "aslam-ai-subtitled.mp4"
        try:
            video_size = 0
            with video_path.open("wb") as output:
                while True:
                    chunk = await video.read(1024 * 1024)
                    if not chunk:
                        break
                    video_size += len(chunk)
                    if video_size > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Local worker limit is 1 GB.")
                    output.write(chunk)
            if video_size == 0:
                raise HTTPException(status_code=400, detail="Video file is empty.")

            subtitle_size = 0
            with subtitle_path.open("wb") as output:
                while True:
                    chunk = await subtitles.read(128 * 1024)
                    if not chunk:
                        break
                    subtitle_size += len(chunk)
                    if subtitle_size > 10 * 1024 * 1024:
                        raise HTTPException(status_code=413, detail="SRT file limit is 10 MB.")
                    output.write(chunk)
            if subtitle_size == 0:
                raise HTTPException(status_code=400, detail="Subtitle file is empty.")

            try:
                subtitle_text = subtitle_path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="SRT must be UTF-8 encoded.")
            if "-->" not in subtitle_text or not any(line.strip().isdigit() for line in subtitle_text.splitlines()):
                raise HTTPException(status_code=400, detail="The uploaded SRT does not look valid.")

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise HTTPException(status_code=500, detail="FFmpeg is not installed.")

            escaped_path = str(subtitle_path.resolve()).replace("\\", "/")
            escaped_path = escaped_path.replace(":", "\\:").replace("'", "\\'")
            style = (
                f"FontName=Arial,FontSize={font_size},"
                "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                "BorderStyle=1,Outline=2,Shadow=1,MarginV=32"
            )
            command = [
                ffmpeg, "-y", "-i", str(video_path),
                "-vf", f"subtitles='{escaped_path}':force_style='{style}'",
                "-map", "0:v:0", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", str(output_path),
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=6 * 60 * 60
            )
            if result.returncode != 0 or not output_path.exists():
                print("Subtitle burn-in error:", result.stderr[-3000:])
                raise HTTPException(
                    status_code=500,
                    detail="Subtitle rendering failed. Check FFmpeg subtitle/libass support.",
                )
            return Response(
                content=output_path.read_bytes(),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": 'attachment; filename="aslam-ai-subtitled.mp4"'
                },
            )
        except HTTPException:
            raise
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Subtitle rendering timed out.")
        except Exception as exc:
            print("Subtitle burn-in error:", repr(exc))
            raise HTTPException(status_code=500, detail="Could not render subtitles.")
        finally:
            await video.close()
            await subtitles.close()

@app.post("/audio/extract")
async def extract_audio(video: UploadFile = File(...)):
    """Extract the current MP4 soundtrack as WAV for the optional lip-sync stage."""
    filename = Path(video.filename or "dubbed.mp4").name
    if Path(filename).suffix.lower() not in {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}:
        raise HTTPException(status_code=400, detail="Unsupported video format.")

    with tempfile.TemporaryDirectory(prefix="aslam-audio-extract-") as temp_dir:
        root = Path(temp_dir)
        source_path = root / filename
        audio_path = root / "dubbed-audio.wav"
        try:
            size = 0
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
                raise HTTPException(status_code=400, detail="Video file is empty.")

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise HTTPException(status_code=500, detail="FFmpeg is not installed.")
            result = subprocess.run(
                [ffmpeg, "-y", "-i", str(source_path), "-vn", "-ac", "1",
                 "-ar", "16000", "-c:a", "pcm_s16le", str(audio_path)],
                capture_output=True, text=True, timeout=60 * 60,
            )
            if result.returncode != 0 or not audio_path.exists():
                raise HTTPException(status_code=422, detail="Could not extract dubbed audio.")
            return Response(
                content=audio_path.read_bytes(),
                media_type="audio/wav",
                headers={"Content-Disposition": 'attachment; filename="aslam-ai-dubbed.wav"'},
            )
        except HTTPException:
            raise
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Audio extraction timed out.")
        except Exception as exc:
            print("Dubbed audio extraction error:", repr(exc))
            raise HTTPException(status_code=500, detail="Could not extract dubbed audio.")
        finally:
            await video.close()


def run_wav2lip_subprocess(command, repo_path):
    """Serialize Wav2Lip runs because upstream inference shares repo_path/temp files."""
    with _wav2lip_lock:
        return subprocess.run(
            command,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=6 * 60 * 60,
        )


def resolve_wav2lip_python():
    """Resolve a dedicated Wav2Lip interpreter without changing the main worker Python."""
    configured = (
        os.getenv("WAV2LIP_PYTHON", "").strip()
        or os.getenv("PYTHON", "").strip()  # legacy compatibility with earlier setup
    )
    if not configured:
        return sys.executable
    candidate = Path(configured).expanduser()
    if candidate.is_file():
        return str(candidate.resolve())
    return shutil.which(configured)


@app.get("/lip-sync/status")
def lip_sync_status():
    """Report whether a local Wav2Lip checkout, checkpoint and interpreter are configured."""
    wav2lip_dir = os.getenv("WAV2LIP_DIR", "").strip()
    checkpoint = os.getenv("WAV2LIP_CHECKPOINT", "").strip()
    repo_path = Path(wav2lip_dir).expanduser() if wav2lip_dir else None
    checkpoint_path = Path(checkpoint).expanduser() if checkpoint else None
    inference_exists = bool(repo_path and (repo_path / "inference.py").is_file())
    checkpoint_exists = bool(checkpoint_path and checkpoint_path.is_file())
    face_detector_exists = bool(repo_path and (repo_path / "face_detection" / "detection" / "sfd" / "s3fd.pth").is_file())
    python_path = resolve_wav2lip_python()
    python_exists = bool(python_path)
    configured = inference_exists and checkpoint_exists and face_detector_exists and python_exists
    if not inference_exists:
        message = "Wav2Lip needs a local repository containing inference.py."
    elif not checkpoint_exists:
        message = "Wav2Lip needs a compatible local checkpoint file."
    elif not face_detector_exists:
        message = "Wav2Lip needs S3FD face-detection weights at face_detection/detection/sfd/s3fd.pth."
    elif not python_exists:
        message = "The configured Wav2Lip Python executable was not found. Check the PYTHON setting."
    else:
        message = "Wav2Lip files and Python interpreter are ready for a local inference attempt."
    return {
        "ok": True,
        "configured": configured,
        "repositoryFound": inference_exists,
        "checkpointFound": checkpoint_exists,
        "faceDetectorFound": face_detector_exists,
        "pythonFound": python_exists,
        "pythonExecutable": python_path,
        "message": message + " No model is bundled or downloaded automatically.",
    }

@app.post("/lip-sync")
async def lip_sync(
    video: UploadFile = File(...),
    dubbed_audio: UploadFile = File(...),
):
    """Run a separately installed local Wav2Lip checkout using its supplied checkpoint."""
    wav2lip_dir = os.getenv("WAV2LIP_DIR", "").strip()
    checkpoint = os.getenv("WAV2LIP_CHECKPOINT", "").strip()
    if not wav2lip_dir or not checkpoint:
        raise HTTPException(
            status_code=503,
            detail="Wav2Lip is not configured. Set WAV2LIP_DIR and WAV2LIP_CHECKPOINT after installing its model.",
        )
    if not resolve_wav2lip_python():
        raise HTTPException(status_code=503, detail="The configured Wav2Lip Python executable was not found. Check the PYTHON setting.")

    repo_path = Path(wav2lip_dir).expanduser().resolve()
    inference_script = repo_path / "inference.py"
    checkpoint_path = Path(checkpoint).expanduser().resolve()
    if not inference_script.is_file() or not checkpoint_path.is_file():
        raise HTTPException(
            status_code=503,
            detail="Wav2Lip inference.py or checkpoint file was not found at the configured path.",
        )
    face_detector_path = repo_path / "face_detection" / "detection" / "sfd" / "s3fd.pth"
    if not face_detector_path.is_file():
        raise HTTPException(status_code=503, detail="Wav2Lip S3FD face-detection weights are missing. Place s3fd.pth at face_detection/detection/sfd/s3fd.pth.")

    video_name = Path(video.filename or "face-video.mp4").name
    video_suffix = Path(video_name).suffix.lower()
    audio_suffix = Path(dubbed_audio.filename or "dubbed.wav").suffix.lower()
    if video_suffix not in {".mp4", ".mov", ".mkv", ".avi", ".m4v"}:
        raise HTTPException(status_code=400, detail="Unsupported face video format.")
    if audio_suffix not in {".wav", ".mp3", ".m4a", ".flac"}:
        raise HTTPException(status_code=400, detail="Dubbed audio must be WAV, MP3, M4A or FLAC.")

    with tempfile.TemporaryDirectory(prefix="aslam-lipsync-") as temp_dir:
        root = Path(temp_dir)
        video_path = root / video_name
        audio_path = root / f"dubbed{audio_suffix}"
        output_path = root / "aslam-ai-lipsynced.mp4"
        try:
            video_size = 0
            with video_path.open("wb") as output:
                while True:
                    chunk = await video.read(1024 * 1024)
                    if not chunk:
                        break
                    video_size += len(chunk)
                    if video_size > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="Local worker limit is 1 GB.")
                    output.write(chunk)
            if video_size == 0:
                raise HTTPException(status_code=400, detail="Video file is empty.")

            audio_size = 0
            with audio_path.open("wb") as output:
                while True:
                    chunk = await dubbed_audio.read(256 * 1024)
                    if not chunk:
                        break
                    audio_size += len(chunk)
                    if audio_size > 200 * 1024 * 1024:
                        raise HTTPException(status_code=413, detail="Dubbed audio limit is 200 MB.")
                    output.write(chunk)
            if audio_size == 0:
                raise HTTPException(status_code=400, detail="Dubbed audio is empty.")

            (repo_path / "temp").mkdir(parents=True, exist_ok=True)
            command = [
                resolve_wav2lip_python() or sys.executable,
                str(inference_script),
                "--checkpoint_path", str(checkpoint_path),
                "--face", str(video_path),
                "--audio", str(audio_path),
                "--outfile", str(output_path),
            ]
            result = await asyncio.to_thread(run_wav2lip_subprocess, command, repo_path)
            if result.returncode != 0 or not output_path.exists():
                print("Wav2Lip error:", result.stderr[-3000:])
                raise HTTPException(
                    status_code=500,
                    detail="Lip-sync failed. Check Wav2Lip dependencies, checkpoint and worker logs.",
                )

            return Response(
                content=output_path.read_bytes(),
                media_type="video/mp4",
                headers={
                    "Content-Disposition": 'attachment; filename="aslam-ai-lipsynced.mp4"'
                },
            )
        except HTTPException:
            raise
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=408, detail="Lip-sync processing timed out.")
        except Exception as exc:
            print("Lip-sync pipeline error:", repr(exc))
            raise HTTPException(status_code=500, detail="Lip-sync processing failed.")
        finally:
            await video.close()
            await dubbed_audio.close()

class SpeakerAssignmentRequest(BaseModel):
    segments: list[dict] = Field(min_length=1, max_length=10000)
    assignments: dict[str, str] = Field(min_length=1, max_length=100)


@app.post("/speakers/assign")
def assign_speakers(request: SpeakerAssignmentRequest):
    """Apply human-reviewed speaker labels to transcript segments."""
    valid_assignments = {}
    for source_id, target_id in request.assignments.items():
        if not source_id.strip() or not target_id.strip() or len(target_id) > 80:
            raise HTTPException(status_code=400, detail="Speaker assignment IDs must be non-empty and under 80 characters.")
        valid_assignments[source_id] = target_id

    updated = []
    for index, segment in enumerate(request.segments):
        if not isinstance(segment, dict):
            raise HTTPException(status_code=400, detail=f"Segment {index + 1} is invalid.")
        current_id = segment.get("speakerId")
        if current_id is not None and not isinstance(current_id, str):
            raise HTTPException(status_code=400, detail=f"Segment {index + 1} has an invalid speaker ID.")
        updated.append({
            **segment,
            "speakerId": valid_assignments.get(current_id, current_id or "speaker_unknown"),
        })

    return {
        "ok": True,
        "stage": "speaker_assignment_complete",
        "segments": updated,
        "note": "Assignments are applied to the submitted transcript only; keep the returned segments for the next dubbing stage.",
    }

