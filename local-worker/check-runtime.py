"""Fast, model-free API smoke tests. Heavy AI models are deliberately not downloaded in CI."""
from fastapi.testclient import TestClient
import worker

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
