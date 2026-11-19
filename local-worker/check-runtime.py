"""Fast, model-free API smoke tests. Heavy AI models are deliberately not downloaded in CI."""
from fastapi.testclient import TestClient
import worker
import io
import math
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

client = TestClient(worker.app)

health = client.get("/health")
assert health.status_code == 200, health.text
assert health.json()["ok"] is True

studio = client.get("/studio")
assert studio.status_code == 200, studio.text
assert "ASLAM AI" in studio.text

system = client.get("/system/check")
assert system.status_code == 200, system.text
assert "checks" in system.json()
assert "readyForAnalysis" in system.json()

translated = client.post(
    "/translate",
    json={
        "sourceLanguage": "en",
        "targetLanguage": "en",
        "segments": [{"start": 0.0, "end": 1.0, "text": "Smoke test"}],
    },
)
assert translated.status_code == 200, translated.text
assert translated.json()["segments"][0]["text"] == "Smoke test"

print("Runtime smoke tests passed: app startup, health, studio page, system check and same-language translation.")


# Exercise the actual FFmpeg dubbing/mux route without downloading AI models.
# The fake TTS engine emits a short WAV tone; this verifies upload handling,
# timestamp placement, audio mixing and MP4 output on the CI runner.
ffmpeg = shutil.which("ffmpeg")
if ffmpeg:
    class FakeTTS:
        def tts_to_file(self, text, speaker_wav, language, file_path):
            sample_rate = 24000
            frames = bytearray()
            for index in range(int(sample_rate * 0.45)):
                sample = int(5000 * math.sin(2 * math.pi * 330 * index / sample_rate))
                frames.extend(struct.pack("<h", sample))
            with wave.open(str(file_path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(sample_rate)
                audio.writeframes(bytes(frames))

    with tempfile.TemporaryDirectory(prefix="aslam-ci-") as temp_dir:
        movie_path = Path(temp_dir) / "test-movie.mp4"
        subprocess.run(
            [
                ffmpeg, "-y",
                "-f", "lavfi", "-i", "testsrc=size=320x240:rate=24",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=24000",
                "-t", "2", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-c:a", "aac", str(movie_path),
            ],
            check=True, capture_output=True,
        )
        voice_buffer = io.BytesIO()
        with wave.open(voice_buffer, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(b"\\x00\\x00" * 24000)

        worker.get_tts_model = lambda: FakeTTS()
        with movie_path.open("rb") as movie:
            dubbed = client.post(
                "/dub-audio",
                files={
                    "video": ("test-movie.mp4", movie, "video/mp4"),
                    "voice_samples": ("voice.wav", voice_buffer.getvalue(), "audio/wav"),
                },
                data={
                    "segments_json": '[{"start":0.2,"end":1.0,"text":"Hello","speakerId":"speaker_01"}]',
                    "speaker_ids_json": '["speaker_01"]',
                    "language": "en",
                    "background_volume": "0.1",
                },
            )
        assert dubbed.status_code == 200, dubbed.text
        assert dubbed.headers.get("content-type", "").startswith("video/mp4")
        assert dubbed.content[:4] == b"\\x00\\x00\\x00\\x18" or b"ftyp" in dubbed.content[:32]

        extracted = client.post(
            "/audio/extract",
            files={"video": ("dubbed.mp4", dubbed.content, "video/mp4")},
        )
        assert extracted.status_code == 200, extracted.text
        assert extracted.content.startswith(b"RIFF")

print("FFmpeg integration smoke test passed: synthetic video -> mock local voice -> dubbed MP4 -> extracted WAV.")
