# ASLAM AI Movie Dubbing Studio — Free Local Worker

This worker is the first offline/open-source processing component. It extracts audio with FFmpeg and creates a timestamped transcript using faster-whisper.

## Cost model

- No paid API key is used.
- Models run on the computer that starts this worker.
- The first run downloads the Whisper model; this needs internet once.
- Processing uses local CPU/RAM and can be slow on long movies.
- This is not free cloud hosting. It requires a computer that remains on while processing.

## Requirements

- Python 3.10 or 3.11
- FFmpeg installed and available in PATH
- 8 GB RAM minimum recommended for the small model; more is better
- Internet for the first model download

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

## Transcription test

Use the API docs and upload an MP4/MOV/MKV/WEBM/AVI/M4V file to `POST /transcribe`.

The response contains detected source language, segment timestamps, transcript text and word timestamps.

## Current scope

Implemented:
1. Local video upload to the worker
2. FFmpeg audio extraction to mono 16 kHz WAV
3. faster-whisper transcription
4. Segment and word timestamps

Not yet implemented:
- Translation
- Speaker diarization and speaker review
- Voice cloning / TTS
- Speech/music separation and audio mixing
- Lip-sync
- Final MP4 rendering and subtitle burn-in

Do not expose this worker directly to the public internet without authentication and upload limits.
