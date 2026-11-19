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

**Windows quick start:** double-click `setup-windows.bat`. After it finishes, double-click `start-windows.bat`. Keep the black terminal window open while using the worker. The setup script installs the base Python packages but does not install FFmpeg or optional XTTS/Wav2Lip models.

Manual setup:

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
# Optional: install XTTS voice generation separately (large ML dependency set)
pip install -r requirements-voice.txt
uvicorn worker:app --host 127.0.0.1 --port 8765
```

Local studio UI: http://127.0.0.1:8765/studio
Health check: http://127.0.0.1:8765/health
Prerequisite check (no model downloads): http://127.0.0.1:8765/system/check
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

## 4. Detect and group speakers

Call `POST /diarize` and upload a video. The worker extracts audio, transcribes it and uses the local SpeechBrain ECAPA voice-embedding model to group similar utterances into `speaker_01`, `speaker_02`, etc. It returns transcript timestamps and speaker labels. First use downloads the model. CPU inference can be slow.

Automatic diarization is approximate: short utterances may be marked `speaker_unknown`, and similar-sounding characters may be grouped together. Review and correct speaker labels before assigning cloned/generated voices. It does not identify a real person's identity.

## 5. Review and correct speaker labels

Use `POST /speakers/assign` with the transcript segments and an `assignments` object mapping detected IDs to the final character IDs. Example: `{\"segments\":[{\"start\":1,\"end\":2,\"text\":\"Hello\",\"speakerId\":\"speaker_01\"}],\"assignments\":{\"speaker_01\":\"hero\",\"speaker_unknown\":\"hero\"}}`. The response returns corrected segments; use those in `/dub-audio`.

## 6. Generate dialogue with a reference voice (XTTS-v2)

The local `POST /tts/clone` endpoint accepts multipart form fields `text` and `language`, plus a `reference_audio` file (WAV/MP3/M4A/FLAC/OGG, up to 20 MB). It returns a WAV file generated to resemble the supplied voice sample. Check supported language codes with `GET /tts/languages`. Hindi (`hi`), Arabic (`ar`) and English (`en`) are included by the model; quality varies and each language should be tested.

Install the optional dependency first with `pip install -r requirements-voice.txt`. The first request downloads the XTTS-v2 model and can take time and substantial disk space. CPU generation may be slow. Use only voice recordings you own or have explicit permission to use; never clone someone else's voice without consent. XTTS-v2 model weights are governed by the Coqui Public Model License, which has restrictions including non-commercial use; check that license before any commercial/public deployment. The software and model download do not require a paid API, but this does not mean the model is cleared for every use.

Example multipart fields in `/docs`:
- `text`: `नमस्ते, आप कैसे हैं?`
- `language`: `hi`
- `reference_audio`: a clean voice sample

## 7. Render character voices into the movie

`POST /dub-audio` creates each dialogue line with XTTS-v2 using the voice sample assigned to that segment's `speakerId`, delays the line to its `start` timestamp, mixes all generated dialogue with the original soundtrack, and returns an MP4. The video stream is copied without re-encoding; audio is encoded as AAC.

Multipart fields:
- `video`: source video file
- `segments_json`: JSON array; each item must include `start`, `text`, and `speakerId` (up to 300 lines)
- `speaker_ids_json`: JSON array of unique speaker IDs, in the same order as the voice sample files
- `voice_samples`: one WAV/MP3/M4A/FLAC/OGG file for each speaker ID (up to 20 MB each)
- `language`: XTTS language code such as `hi`, `ar`, or `en`
- `background_volume`: original soundtrack volume from `0.0` to `1.0` (default `0.18`)

Example `segments_json`:
```json
[
  {"start": 1.25, "text": "नमस्ते, आप कैसे हैं?", "speakerId": "speaker_01"},
  {"start": 4.8, "text": "मैं बिल्कुल ठीक हूँ।", "speakerId": "speaker_02"}
]
```

This first version starts each generated line at the supplied timestamp but does not time-stretch it to fit the original line duration. Long generated dialogue can overlap later dialogue. Listen to the result and adjust the translated script/timing before final use. The video must contain an audio track. Rendering is CPU-heavy and the response is the complete MP4, so large movies require substantial RAM and disk space.

## 8. Export subtitle files

Call `POST /subtitles/srt` with the translated segments. The endpoint returns a downloadable `.srt` file. Set `useSourceText` to `true` to export the original transcript instead of translated text.

## 9. Burn subtitles into the video

`POST /subtitles/burn-in` accepts a video file, an SRT subtitle file and optional `font_size` (12–48; default 24). FFmpeg renders the subtitles into the picture and returns an MP4. This re-encodes the video and can take substantial CPU time. FFmpeg must include the `subtitles`/libass filter; use a UTF-8 SRT file.

## 10. Optional local lip-sync (Wav2Lip)

`POST /lip-sync` accepts `video` and `dubbed_audio` multipart files and runs a local Wav2Lip checkout. This is optional and is not installed by the base requirements file. Install the Wav2Lip repository and its own Python dependencies separately, obtain a compatible checkpoint from a legitimate source, then set environment variables:

- `WAV2LIP_DIR`: absolute path to the Wav2Lip repository folder containing `inference.py`
- `WAV2LIP_CHECKPOINT`: absolute path to its checkpoint file
- `PYTHON`: optional Python executable path (defaults to `python`)

The Wav2Lip model/checkpoint has licensing and usage restrictions; review the exact repository and checkpoint license before use, especially for commercial projects. Lip-sync quality depends on a clear, mostly frontal visible face, suitable frame rate and clean dubbed audio. It may fail on profiles, occlusions, multiple faces or animation. This endpoint is a local integration wrapper, not a bundled or tested model install.

## Current scope

Implemented in the repository (not yet locally tested end-to-end):
1. Local video upload and FFmpeg audio extraction
2. faster-whisper transcription with word timestamps
3. Argos Translate local language-pair installation and translation
4. SRT subtitle file export
5. Experimental SpeechBrain ECAPA speaker grouping
6. Manual speaker assignment/correction API
7. XTTS-v2 reference-voice generation API
8. Timestamp-based dialogue generation and original soundtrack mixing
9. MP4 audio muxing with FFmpeg
10. SRT subtitle burn-in with FFmpeg
11. Optional Wav2Lip integration wrapper (requires separate model/checkpoint setup)

Remaining limitations and work:
- The complete movie pipeline has not yet been run end-to-end on the target computer.
- First-time model downloads, dependency compatibility and actual CPU processing time still need validation on that computer.
- Dialogue duration fitting is basic: long generated lines can overlap later dialogue.
- Speaker detection is experimental and should be reviewed manually.
- Improve job progress, cancellation, storage management and large-file streaming.
- Wav2Lip remains an optional integration wrapper requiring a separate repository, dependencies and checkpoint.

Important: the Wav2Lip endpoint is only an integration wrapper. The model repository, Python dependencies and checkpoint must be installed separately. No end-to-end run has been performed yet.
 
Do not expose this worker directly to the public internet without authentication and upload limits.


## Windows helper files

- `setup-windows.bat` creates a Python 3.11 virtual environment and installs the base local worker requirements.
- `install-audio-windows.bat` installs optional Demucs speech/music separation (large download).
- `install-voice-windows.bat` installs optional XTTS voice generation after asking for confirmation and reminding you to review its license.
- `start-windows.bat` starts the API on `127.0.0.1:8765`.
- `/system/check` reports whether FFmpeg and the required Python packages are available. It does not download model weights or certify end-to-end operation.

The local guided studio at `/studio` is served by this worker. It runs the local analysis → translation → speaker review → voice sample assignment → dubbing → subtitle burn-in flow. The existing `index.html` START button opens this local studio in a new tab; because browsers do not transfer a selected file between pages, select the movie again in the local studio. The existing hosted Netlify page has not yet been connected to this local workflow; do not deploy this version expecting its existing START button to run local dubbing.
