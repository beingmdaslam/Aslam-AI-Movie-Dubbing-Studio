# ASLAM AI Movie Dubbing Studio

A zero-cost project with a phone-only browser subtitle editor and an optional local-computer AI processing workflow. No paid API is required by the current documented features.

## Phone-only, zero-cost mode

Open the hosted dashboard on your phone and choose **START AI DUBBING** to open `mobile-studio.html`. This browser-only mode can preview a locally selected video, import an existing SRT subtitle file, edit subtitle text and timestamps, preview subtitles synchronized over the video, sort entries, export an SRT file, and save/restore a complete subtitle project as JSON. When you choose a video on the dashboard and continue, the file is handed to the mobile editor using on-device IndexedDB when the browser permits it; the video is not uploaded to a server. If the browser storage quota is insufficient, select the video again inside the editor.

The mobile editor now includes an experimental on-device Whisper Tiny speech-to-text stage. The first use downloads the free model and browser runtime; speech recognition runs in the browser and the video is not uploaded. The browser captures and transcribes the selected video's audio in short segments. Performance and maximum practical video length depend on phone memory, browser support, and model download/cache availability. Review the generated text and timestamps. Local MMS text-to-speech is now connected for selected languages and can export a synchronized WAV audio track. MMS models are licensed CC-BY-NC 4.0 (non-commercial only); do not use these model weights for commercial work without separate permission. Voice cloning, multi-speaker identity matching, lip-sync, and final MP4 rendering are not connected yet. It is a subtitle editing workflow, not a completed AI dubbing pipeline. Those AI stages need a genuine on-device model/runtime or a verified free compute service; do not enter paid API keys.

The `local-worker/` folder remains available as an optional computer-based workflow. It is not required for the phone-only subtitle editor.

## Current workflow

1. Select a movie in the local studio.
2. Transcribe dialogue and timestamps with faster-whisper.
3. Alternatively, use the phone editor's experimental local Whisper Tiny ASR to generate draft dialogue segments. This first-use model download requires internet and enough browser storage/RAM.\n4. Group similar voices into speaker labels with SpeechBrain ECAPA (review is required; this is approximate).
5. Install and use a free Argos Translate language model locally.
6. Edit translated dialogue and speaker labels.
7. Export an SRT subtitle file or burn subtitles into an MP4 with FFmpeg.
8. Optionally run Wav2Lip with an existing dubbed audio track, if its separate model and compatible environment have been installed.

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


### Browser-native translation
- Choose source and target languages, then use Translate on a single dialogue or Translate All.
- Translation uses the browser's built-in `Translator` API; source auto-detection uses `LanguageDetector` when available.
- These APIs are not present in every browser/device or language pair. Unsupported combinations are reported rather than silently sent to a third party.
- The app does not upload subtitle text to an external translation API.


### Local text-to-speech (TTS)
- The mobile editor can generate a WAV audio track from translated dialogue and place each generated utterance at its subtitle start timestamp.
- Available browser model packs: Hindi, Arabic, English, French, Spanish, German, Portuguese and Russian.
- Models run in the browser using Transformers.js; first use downloads model weights and requires free storage, memory and a supported browser.
- The underlying Meta MMS-TTS models are licensed CC-BY-NC 4.0. This is **not a commercial-use license**. Obtain suitable permission or replace the model before any commercial use.
- This creates a separate dubbed WAV track, not a final MP4. Video/audio muxing and voice cloning are still outstanding.


### Final MP4 muxing
- The render stage uses FFmpeg WebAssembly in the browser to combine the original video stream with the generated WAV audio. It can also embed the edited SRT as a selectable MP4 subtitle track (not permanently burned into the picture).
- It first tries to copy the original video codec; if that cannot be muxed into MP4, it tries H.264 re-encoding.
- The video is not uploaded to a server. The browser needs substantial memory and storage; long or high-resolution videos may fail on phones.
- You can replace the original audio or mix it quietly (20%) under the generated dubbing. Lip-sync is not included.
