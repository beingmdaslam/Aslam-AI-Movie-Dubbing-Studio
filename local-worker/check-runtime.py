"""Fast, model-free API smoke tests. Heavy AI models are deliberately not downloaded in CI."""
import os
import sys
import types
import contextlib
from fastapi.testclient import TestClient
import worker
import io
import shutil
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


# Exercise transcription, subtitle export/burn-in and Wav2Lip command wiring
# without downloading or running any AI models. The lip-sync test uses a fake
# inference script and an already-dubbed synthetic WAV.
ffmpeg = shutil.which("ffmpeg")
if ffmpeg:
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
        # Verify the upload -> FFmpeg audio extraction -> Whisper result
        # handling path with a deterministic fake model (no model download).
        from types import SimpleNamespace

        class FakeWhisper:
            def transcribe(self, audio_path, **kwargs):
                words = [
                    SimpleNamespace(start=0.25, end=0.55, word=" Hello"),
                    SimpleNamespace(start=0.56, end=0.95, word=" world."),
                ]
                segment = SimpleNamespace(
                    start=0.25, end=0.95, text=" Hello world.", words=words
                )
                info = SimpleNamespace(
                    language="en", language_probability=0.99, duration=2.0
                )
                return iter([segment]), info

        worker.get_model = lambda: FakeWhisper()
        with movie_path.open("rb") as movie:
            transcription = client.post(
                "/transcribe",
                files={"video": ("test-movie.mp4", movie, "video/mp4")},
            )
        assert transcription.status_code == 200, transcription.text
        transcript_data = transcription.json()
        assert transcript_data["detectedLanguage"] == "en"
        assert transcript_data["segments"][0]["text"] == "Hello world."
        assert len(transcript_data["segments"][0]["words"]) == 2

        # Exercise the full diarization route with fake tensor/audio/embedding adapters.
        class FakeWaveform:
            def __init__(self, length=32000):
                self.shape = (1, length)

            def __getitem__(self, key):
                sample_slice = key[1]
                return FakeWaveform(max(0, sample_slice.stop - sample_slice.start))

        class FakeEmbedding:
            def squeeze(self): return self
            def detach(self): return self
            def cpu(self): return self
            def tolist(self): return [1.0, 0.0, 0.0]

        class FakeEncoder:
            def encode_batch(self, crop):
                return FakeEmbedding()

        class FakeDiarizeWhisper:
            def transcribe(self, audio_path, **kwargs):
                words = [
                    SimpleNamespace(start=0.2, end=0.7, word=" Hello"),
                    SimpleNamespace(start=0.8, end=1.4, word=" there."),
                ]
                segment = SimpleNamespace(start=0.2, end=1.6, text=" Hello there.", words=words)
                info = SimpleNamespace(language="en", language_probability=0.99, duration=2.0)
                return iter([segment]), info

        fake_torch = types.ModuleType("torch")
        fake_torch.no_grad = contextlib.nullcontext
        fake_torchaudio = types.ModuleType("torchaudio")
        fake_torchaudio.load = lambda path: (FakeWaveform(), 16000)
        old_torch = sys.modules.get("torch")
        old_torchaudio = sys.modules.get("torchaudio")
        worker.get_model = lambda: FakeDiarizeWhisper()
        worker.get_speaker_model = lambda: FakeEncoder()
        sys.modules["torch"] = fake_torch
        sys.modules["torchaudio"] = fake_torchaudio
        try:
            with movie_path.open("rb") as movie:
                diarized = client.post(
                    "/diarize",
                    files={"video": ("test-movie.mp4", movie, "video/mp4")},
                )
            assert diarized.status_code == 200, diarized.text
            diarized_json = diarized.json()
            assert diarized_json["speakerCount"] == 1, diarized_json
            assert diarized_json["segments"][0]["speakerId"] == "speaker_01"
        finally:
            if old_torch is None:
                sys.modules.pop("torch", None)
            else:
                sys.modules["torch"] = old_torch
            if old_torchaudio is None:
                sys.modules.pop("torchaudio", None)
            else:
                sys.modules["torchaudio"] = old_torchaudio
        print("Speaker diarization route test passed with fake Whisper, audio and embedding models.")

        # Create a synthetic already-dubbed WAV for the optional lip-sync integration test.
        lip_audio_buffer = io.BytesIO()
        with wave.open(lip_audio_buffer, "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(bytes(32000))

        # Subtitle export, speaker correction and subtitle burn-in are model-free.
        srt_response = client.post(
            "/subtitles/srt",
            json={"segments": transcript_data["segments"], "useSourceText": False},
        )
        assert srt_response.status_code == 200, srt_response.text
        assert "Hello world." in srt_response.text

        assignment = client.post(
            "/speakers/assign",
            json={
                "segments": [{"start": 0.2, "end": 0.8, "text": "Hello", "speakerId": "speaker_01"}],
                "assignments": {"speaker_01": "main_character"},
            },
        )
        assert assignment.status_code == 200, assignment.text
        assert assignment.json()["segments"][0]["speakerId"] == "main_character"

        with movie_path.open("rb") as movie:
            burned = client.post(
                "/subtitles/burn-in",
                files={
                    "video": ("test-movie.mp4", movie, "video/mp4"),
                    "subtitles": ("captions.srt", srt_response.content, "text/plain"),
                },
            )
        assert burned.status_code == 200, burned.text
        assert burned.headers.get("content-type", "").startswith("video/mp4")

        # Test Wav2Lip subprocess wiring with a fake local inference.py.
        # This deliberately does not claim to test actual AI lip-sync quality.
        fake_wav2lip = Path(temp_dir) / "fake-wav2lip"
        fake_wav2lip.mkdir()
        checkpoint = fake_wav2lip / "checkpoint.pth"
        checkpoint.write_bytes(b"test checkpoint placeholder")
        detector_weights = fake_wav2lip / "face_detection" / "detection" / "sfd" / "s3fd.pth"
        detector_weights.parent.mkdir(parents=True)
        detector_weights.write_bytes(b"fake detector weights")
        (fake_wav2lip / "inference.py").write_text(
            "import argparse, shutil\n"
            "p=argparse.ArgumentParser()\n"
            "p.add_argument('--checkpoint_path'); p.add_argument('--face'); "
            "p.add_argument('--audio'); p.add_argument('--outfile')\n"
            "a=p.parse_args(); shutil.copyfile(a.face, a.outfile)\n",
            encoding="utf-8",
        )
        old_dir = os.environ.get("WAV2LIP_DIR")
        old_checkpoint = os.environ.get("WAV2LIP_CHECKPOINT")
        old_python = os.environ.get("PYTHON")
        old_wav2lip_python = os.environ.get("WAV2LIP_PYTHON")
        try:
            os.environ["WAV2LIP_DIR"] = str(fake_wav2lip)
            os.environ["WAV2LIP_CHECKPOINT"] = str(checkpoint)
            os.environ.pop("WAV2LIP_PYTHON", None)
            os.environ["PYTHON"] = "aslam-missing-python-executable"
            os.environ["WAV2LIP_PYTHON"] = sys.executable
            assert worker.resolve_wav2lip_python() == sys.executable
            os.environ.pop("WAV2LIP_PYTHON", None)
            invalid_python_status = client.get("/lip-sync/status")
            assert invalid_python_status.status_code == 200
            assert invalid_python_status.json()["configured"] is False
            assert invalid_python_status.json()["pythonFound"] is False
            invalid_python = client.post(
                "/lip-sync",
                files={
                    "video": ("test-movie.mp4", b"not-a-real-video", "video/mp4"),
                    "dubbed_audio": ("dubbed.wav", lip_audio_buffer.getvalue(), "audio/wav"),
                },
            )
            assert invalid_python.status_code == 503, invalid_python.text
            os.environ["PYTHON"] = sys.executable
            ready_status = client.get("/lip-sync/status")
            assert ready_status.status_code == 200
            assert ready_status.json()["configured"] is True, ready_status.text
            assert ready_status.json()["faceDetectorFound"] is True
            with movie_path.open("rb") as movie:
                lip_result = client.post(
                    "/lip-sync",
                    files={
                        "video": ("test-movie.mp4", movie, "video/mp4"),
                        "dubbed_audio": ("dubbed.wav", lip_audio_buffer.getvalue(), "audio/wav"),
                    },
                )
            assert lip_result.status_code == 200, lip_result.text
            assert lip_result.headers.get("content-type", "").startswith("video/mp4")
        finally:
            for key, value in (("WAV2LIP_DIR", old_dir), ("WAV2LIP_CHECKPOINT", old_checkpoint), ("PYTHON", old_python), ("WAV2LIP_PYTHON", old_wav2lip_python)):
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        print("Wav2Lip subprocess wiring test passed with a fake inference script.")

print("FFmpeg integration smoke test passed: synthetic video -> Whisper upload path -> subtitle export/burn-in -> mocked Wav2Lip invocation.")


# Verify real Argos route selection logic with lightweight fake language models.
# This covers both direct translation and the English-pivot fallback without
# downloading language packages in CI.
import sys
import types

class FakeTranslator:
    def __init__(self, mapping):
        self.mapping = mapping

    def translate(self, value):
        return self.mapping.get(value, value + " [translated]")

class FakeLanguage:
    def __init__(self, code, links=None):
        self.code = code
        self.links = links or {}

    def get_translation(self, target):
        return self.links.get(target.code)

fake_en = FakeLanguage("en")
fake_fr = FakeLanguage("fr")
fake_hi = FakeLanguage("hi")
fake_fr.links["en"] = FakeTranslator({"bonjour": "hello"})
fake_en.links["hi"] = FakeTranslator({"hello": "नमस्ते"})
fake_en.links["fr"] = FakeTranslator({"hello": "bonjour"})
fake_hi.links["en"] = FakeTranslator({"नमस्ते": "hello"})
# Installed language codes alone are insufficient: the exact route must exist.
assert len(worker._installed_translation_route("fr", "hi", [fake_fr, fake_en, fake_hi])) == 2
fake_es = FakeLanguage("es")
assert worker._installed_translation_route("fr", "es", [fake_fr, fake_es]) is None
fake_translate_module = types.ModuleType("argostranslate.translate")
fake_translate_module.get_installed_languages = lambda: [fake_fr, fake_en, fake_hi]
fake_package_module = types.ModuleType("argostranslate")
fake_package_module.__path__ = []
fake_package_module.translate = fake_translate_module
previous_argos = {
    key: sys.modules.get(key)
    for key in ("argostranslate", "argostranslate.translate")
}
sys.modules["argostranslate"] = fake_package_module
sys.modules["argostranslate.translate"] = fake_translate_module
try:
    pivot = client.post(
        "/translate",
        json={
            "sourceLanguage": "fr",
            "targetLanguage": "hi",
            "segments": [{"start": 0.0, "end": 1.0, "text": "bonjour"}],
        },
    )
    assert pivot.status_code == 200, pivot.text
    assert pivot.json()["segments"][0]["text"] == "नमस्ते", pivot.text

    direct = client.post(
        "/translate",
        json={
            "sourceLanguage": "en",
            "targetLanguage": "hi",
            "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
        },
    )
    assert direct.status_code == 200, direct.text
    assert direct.json()["segments"][0]["text"] == "नमस्ते", direct.text
finally:
    for key, value in previous_argos.items():
        if value is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = value

print("Argos route tests passed: direct translation and two-step English-pivot translation.")


# Verify that the model installer selects both required packages for a
# source -> English -> target route and installs the packages in order.
class FakePackage:
    def __init__(self, from_code, to_code):
        self.from_code = from_code
        self.to_code = to_code

    def download(self):
        return f"{self.from_code}-{self.to_code}.argosmodel"

installed_paths = []
fake_package_api = types.ModuleType("argostranslate.package")
fake_package_api.update_package_index = lambda: None
fake_package_api.get_available_packages = lambda: [
    FakePackage("fr", "en"),
    FakePackage("en", "hi"),
]
fake_package_api.install_from_path = lambda path: installed_paths.append(path)
fake_argos_package_root = types.ModuleType("argostranslate")
fake_argos_package_root.__path__ = []
fake_argos_package_root.package = fake_package_api
previous_package_modules = {
    key: sys.modules.get(key)
    for key in ("argostranslate", "argostranslate.package")
}
sys.modules["argostranslate"] = fake_argos_package_root
sys.modules["argostranslate.package"] = fake_package_api
try:
    from worker import InstallTranslationRequest
    install_response = client.post(
        "/translation/install",
        json={"sourceLanguage": "fr", "targetLanguage": "hi"},
    )
    assert install_response.status_code == 200, install_response.text
    install_json = install_response.json()
    assert install_json["route"] == "via English", install_json
    assert installed_paths == ["fr-en.argosmodel", "en-hi.argosmodel"], installed_paths
finally:
    for key, value in previous_package_modules.items():
        if value is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = value

print("Argos installer test passed: both English-pivot packages are selected and installed in order.")


# Wav2Lip must fail clearly and safely when the optional local checkout or
# checkpoint has not been configured; no external service is contacted.
import os
old_wav2lip_dir = os.environ.pop("WAV2LIP_DIR", None)
old_wav2lip_checkpoint = os.environ.pop("WAV2LIP_CHECKPOINT", None)
try:
    lip_status = client.get("/lip-sync/status")
    assert lip_status.status_code == 200, lip_status.text
    assert lip_status.json()["configured"] is False, lip_status.text
    lip = client.post(
        "/lip-sync",
        files={
            "video": ("face.mp4", b"not-a-real-video", "video/mp4"),
            "dubbed_audio": ("dubbed.wav", b"not-a-real-audio", "audio/wav"),
        },
    )
    assert lip.status_code == 503, lip.text
    assert "Wav2Lip is not configured" in lip.json()["detail"]
finally:
    if old_wav2lip_dir is not None:
        os.environ["WAV2LIP_DIR"] = old_wav2lip_dir
    if old_wav2lip_checkpoint is not None:
        os.environ["WAV2LIP_CHECKPOINT"] = old_wav2lip_checkpoint

print("Wav2Lip readiness test passed: missing local model is reported without crashing.");


# Exercise the speaker-clustering decision logic without loading the large
# SpeechBrain model. Real audio embeddings are still produced locally at runtime.
known = []
speaker_a = worker._assign_speaker_embedding([1.0, 0.0, 0.0], known)
speaker_a_repeat = worker._assign_speaker_embedding([0.99, 0.01, 0.0], known)
speaker_b = worker._assign_speaker_embedding([-1.0, 0.0, 0.0], known)
assert speaker_a == "speaker_01"
assert speaker_a_repeat == "speaker_01"
assert speaker_b == "speaker_02"
assert len(known) == 2
print("Speaker clustering tests passed: similar embeddings are grouped and distinct embeddings create a new speaker.")
