# ASLAM AI Movie Dubbing Studio

A zero-cost project with a phone-only browser subtitle editor and an optional local-computer AI processing workflow. No paid API is required by the current documented features.

## Phone-only, zero-cost mode

Open the hosted dashboard on your phone and choose **START AI DUBBING** to open `mobile-studio.html`. This browser-only mode can preview a locally selected video, import an existing SRT subtitle file, edit subtitle text and timestamps, preview subtitles synchronized over the video, sort entries, export an SRT file, and save/restore a complete subtitle project as JSON (up to 1,000 dialogue lines per mobile project to protect phone memory). When you choose a video on the dashboard and continue, the file is handed to the mobile editor using on-device IndexedDB when the browser permits it; the video is not uploaded to a server. If the browser storage quota is insufficient, select the video again inside the editor.

The mobile editor includes experimental on-device Whisper Tiny speech-to-text, local MMS or optional Supertonic 3 text-to-speech, and browser-based FFmpeg MP4 muxing. First use downloads free model/runtime files; speech recognition, voice generation, and muxing run in the browser and do not upload the video. Performance and practical video length depend on phone memory, browser support, and model download/cache availability. Review generated text, timestamps, synchronization, and audio quality. MMS models are licensed CC-BY-NC 4.0 (non-commercial only); do not use these model weights commercially without separate permission. Dialogue lines support manual speaker labels and per-character preset voice assignment through Supertonic 3 (10 preset voices). Automatic speaker diarization, personal voice cloning, and lip-sync are not implemented. This is an experimental local workflow, not a guarantee of full-length movie processing on every phone.

The `local-worker/` folder remains available as an optional computer-based workflow. It is not required for the phone-only subtitle editor.

## Current workflow

1. Select a movie in the local studio.
2. Transcribe dialogue and timestamps with faster-whisper.
3. Alternatively, use the phone editor's experimental local Whisper Tiny ASR to generate draft dialogue segments. This first-use model download requires internet and enough browser storage/RAM.
4. Group similar voices into speaker labels with SpeechBrain ECAPA (review is required; this is approximate).
5. Install and use a free Argos Translate language model locally.
6. Edit translated dialogue and speaker labels.
7. Export an SRT subtitle file or burn subtitles into an MP4 with FFmpeg.
8. Render a dubbed MP4 in the phone browser using FFmpeg WebAssembly, replacing or mixing the original audio and optionally embedding selectable subtitles. The phone may run out of memory on long/high-resolution videos.

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

The hosted dashboard opens `mobile-studio.html`, which provides the experimental phone-only workflow. The local worker is an optional separate computer-based workflow.

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
- Mobile MP4 rendering uses FFmpeg WebAssembly and may fail when the browser cannot allocate enough memory. Test short clips first.
- Do not expose the local worker directly to the public internet.

See [local-worker/README.md](local-worker/README.md) for detailed API routes, installation steps, model setup, and limitations.


### Browser-native translation
- Choose source and target languages, then use Translate on a single dialogue or Translate All.
- Translation uses the browser's built-in `Translator` API; source auto-detection uses `LanguageDetector` when available.
- These APIs are not present in every browser/device or language pair. Unsupported combinations are reported rather than silently sent to a third party.
- The app does not upload subtitle text to an external translation API.


### Local text-to-speech (TTS)
- The mobile editor can generate a WAV audio track from translated dialogue and place each generated utterance at its subtitle start timestamp. Select MMS for a single voice per language, or optionally load Supertonic 3 for ten preset male/female voices and consistent per-character voice assignments across 31 supported languages. Supertonic 3 downloads about 400 MB on first use and runs locally with ONNX Runtime Web (WebGPU where available, otherwise WASM).
- Available browser model packs: Hindi, Arabic, English, French, Spanish, German, Portuguese, Russian and Urdu.
- Whisper and MMS run in the browser using Transformers.js; Supertonic runs with ONNX Runtime Web. First use downloads model weights and requires free storage, memory and a supported browser.
- The underlying Meta MMS-TTS models are licensed CC-BY-NC 4.0. This is **not a commercial-use license**. Obtain suitable permission or replace the model before any commercial use. Supertonic 3 weights use the OpenRAIL-M license; review its restrictions before redistribution or commercial use.
- This creates a separate dubbed WAV track. The editor can mux it into MP4 locally. Supertonic's preset voices are not voice cloning and do not imitate a real person.


### Final MP4 muxing
- The render stage uses FFmpeg WebAssembly in the browser with a same-origin worker helper to combine the original video stream with the generated WAV audio. It supports keeping the original resolution or limiting output to 720p, 1080p or 4K (it does not upscale a smaller source). It can also embed the edited SRT as a selectable MP4 subtitle track (not permanently burned into the picture).
- It first tries to copy the original video codec; if that cannot be muxed into MP4, it tries H.264 re-encoding.
- The video is not uploaded to a server. The browser needs substantial memory and storage; long or high-resolution videos may fail on phones. Resolution changes re-encode video and may take much longer than keeping the original codec.
- You can replace the original audio or mix it quietly (20%) under the generated dubbing. Lip-sync is not included.


## Third-party licenses

See [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) for the browser runtimes, FFmpeg components, and AI model license notices. Review model restrictions before commercial use or redistribution.
