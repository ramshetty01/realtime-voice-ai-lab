import pytest


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch):
    for name in (
        "NVIDIA_NIM_API_KEY",
        "NGC_API_KEY",
        "NVIDIA_NIM_BASE_URL",
        "VOICE_API_TOKEN",
        "ASR_TRANSCRIPT_TEXT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VOICE_LOCAL_ONLY", "true")
    monkeypatch.setenv("VOICE_STRICT_ADAPTERS", "false")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("MACOS_SAY_BIN", "/missing/say")
    monkeypatch.setenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000")
