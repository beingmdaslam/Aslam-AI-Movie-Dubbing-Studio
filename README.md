# ASLAM AI Movie Dubbing Studio

A zero-cost project with a phone-only browser subtitle editor and an optional local-computer AI processing workflow. No paid API is required by the current documented features.

## Phone-only, zero-cost mode

Open the hosted dashboard on your phone and choose **START AI DUBBING** to open `mobile-studio.html`. This browser-only mode can preview a locally selected video, import an existing SRT subtitle file, edit subtitle text and timestamps, preview subtitles synchronized over the video, sort entries, export an SRT file, and save/restore a complete subtitle project as JSON. When you choose a video on the dashboard and continue, the file is handed to the mobile editor using on-device IndexedDB when the browser permits it; the video is not uploaded to a server. If the browser storage quota is insufficient, select the video again inside the editor.

This mode does not yet perform automatic speech recognition, automatic translation, generated speech, voice cloning, lip-sync, or final video rendering. It is a subtitle editing workflow, not a completed AI dubbing pipeline. Those AI stages need a genuine on-device model/runtime or a verified free compute service; do not enter paid API keys.

The `local-worker/` folder remains available as an optional computer-based workflow. It is not required for the phone-only subtitle editor.

## Current workflow

1. Select a movie in the local studio.
2. Transcribe dialogue and timestamps with faster-whisper.
3. Group similar voices into speaker labels with SpeechBrain ECAPA (review is required; this is approximate).
4. Install and use a free Argos Translate language model locally.
5. Edit translated dialogue and speaker labels.
6. Export an SRT subtitle file or burn subtitles into an MP4 with FFmpeg.
7. Optionally run Wav2Lip with an existing dubbed audio track, if its separate model and compatible environment have been installed.

**Voice cloning is not part of the current guided workflow.** Wav2Lip only synchronizes mouth movement to audio you provide; it does not create speech. Use only audio you own or are authorized to use.

## Windows setup

Requirements: Windows, Python 3.11, internet for first-time package/model downloads, FFmpeg, and preferably 8 GB or more RAM.

1. Download this repository to your computer and extract the ZIP.
2. Open the `local-worker` folder.
3. Double-click `setup-windows.bat` and allow it to install the free local Python packages.
4. Install FFmpeg if the setup reports it is missing. Close and reopen Command Prompt after installing FFmpeg so PATH is refreshed.
5. Double-click `start-windows.bat` and keep its terminal window open.
6. Open `http://127.0.0.1:8765/studio` on that same computer.
7. On first use, select a video up to 1 GB. The first transcription and translation runs may download model files and take time.

The hosted dashboard now opens `mobile-studio.html`, which does not require the local worker. The local worker is an optional separate workflow and is not required for phone-only subtitle editing.

## Checks and troubleshooting

- Health: `http://127.0.0.1:8765/health`
- Prerequisites: `http://127.0.0.1:8765/system/check`
- API documentation: `http://127.0.0.1:8765/docs`
- Self-test: double-click `test-pipeline-windows.bat` after setup.

The automated self-test uses synthetic media and fake AI adapters. It checks application routes and FFmpeg plumbing; it does **not** prove real model quality or test your computer's performance. Real Whisper, SpeechBrain and Argos model downloads/inference still need to be tested on the target computer.

## Cost and limitations

- No paid API key is required for the guided local workflow.
- First-time Python packages and AI model files require internet and disk space.
- Processing is performed by your own CPU; long movies can take a long time. Keep the computer powered on.
- The local worker currently accepts files up to 1 GB.
- Translation quality and available language pairs vary by Argos model.
- Speaker grouping is approximate and should be manually reviewed.
- Wav2Lip is optional, requires a separate setup and compatible checkpoint, and its upstream license restricts commercial use. Review its terms before use.
- Do not expose the local worker directly to the public internet.

See [local-worker/README.md](local-worker/README.md) for detailed API routes, installation steps, model setup, and limitations.
