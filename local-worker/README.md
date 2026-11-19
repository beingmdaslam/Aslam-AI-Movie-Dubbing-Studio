# ASLAM AI Movie Dubbing Studio — Free Local Worker

This worker runs on the user's own computer. It uses FFmpeg, faster-whisper and Argos Translate; it does not call paid AI APIs.

## Zero-rupee operating model

- No paid API keys or subscriptions are used.
- Models run locally on the computer that starts this worker.
- First-time model downloads require internet; the model files are then stored locally.
- CPU processing can be slow for long movies. This is not free cloud GPU hosting.
- Keep the computer on while a job is running.

## Requirements

- Python 3.10 or 3.11
- FFmpeg installed and available in PATH
- 8 GB RAM minimum recommended for the Whisper small model
- More RAM and a modern CPU improve processing speed

## Install

```bash
python -m venv .venv
```

Windows:
```bash
.venv\\Scripts\\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Then:
```bash
pip install -r requirements.txt
uvicorn worker:app --host 127.0.0.1 --port 8765
```

Health check: http://127.0.0.1:8765/health
Interactive API test: http://127.0.0.1:8765/docs

## 1. Transcription

Use the API docs and upload an MP4/MOV/MKV/WEBM/AVI/M4V file to `POST /transcribe`.

The response includes detected source language, segment timestamps, transcript text and word timestamps.

## 2. Install a free translation model

Check installed languages:
`GET /translation/languages`

Install a language pair (downloads the open-source model from the Argos package index):
`POST /translation/install`

Example request:
```json
{
  "sourceLanguage": "en",
  "targetLanguage": "hi"
}
```

Installation needs internet and disk space. The language pair must be available in the Argos package index. Model availability and translation quality vary by language pair.

## 3. Translate transcript segments

Call `POST /translate` with the source/target language codes and transcript segments from `/transcribe`.

Example:
```json
{
  "sourceLanguage": "en",
  "targetLanguage": "hi",
  "segments": [
    {"start": 1.2, "end": 3.8, "text": "Hello, how are you?"}
  ]
}
```

The response keeps segment timestamps and includes the original text in `sourceText`. Human review is recommended before generating voices.

## Current scope

Implemented:
1. Local video upload to worker
2. FFmpeg audio extraction to mono 16 kHz WAV
3. faster-whisper transcription with segment and word timestamps
4. Local Argos Translate language-pair installation
5. Timestamp-preserving transcript translation

Still to build:
- Speaker diarization and manual speaker review
- Free local text-to-speech and authorized voice cloning
- Speech/music separation and audio mixing
- Lip-sync
- Final MP4 rendering and subtitle burn-in

Do not expose this worker directly to the public internet without authentication and upload limits.
