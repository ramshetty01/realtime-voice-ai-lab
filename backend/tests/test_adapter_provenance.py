import asyncio
from threading import Event

import pytest
from app import main, pipeline, storage
from app.execution import BlockingRunner
from app.pipeline import AdapterResult, AdapterUnavailable
from fastapi.testclient import TestClient


def test_fallback_provenance_is_degraded_and_persisted(monkeypatch, tmp_path):
    saved = []
    monkeypatch.setattr(
        main,
        "generate_response",
        lambda *args: AdapterResult(
            "development reply",
            "development-response",
            True,
            "No model available",
            True,
        ),
    )
    monkeypatch.setattr(
        main,
        "synthesize_speech",
        lambda *args: AdapterResult(
            "data:audio/wav;base64,AA==", "silent-wav", True, "No TTS available", True
        ),
    )
    monkeypatch.setattr(main, "save_request", lambda trace: saved.append(trace))
    result = asyncio.run(main.run_text_pipeline("hello"))
    assert result["status"] == "degraded"
    assert result["metrics"]["adapters"]["llm"]["development"] is True
    assert result["metrics"]["adapters"]["tts"]["provider"] == "silent-wav"
    path = tmp_path / "trace.db"
    storage.save_request(saved[0], path=path)
    exported = storage.get_request(saved[0]["request_id"], path=path)
    assert exported["adapters"] == result["metrics"]["adapters"]


def test_strict_mode_refuses_development_transcript(monkeypatch):
    monkeypatch.setenv("VOICE_STRICT_ADAPTERS", "true")
    monkeypatch.setenv("ASR_TRANSCRIPT_TEXT", "configured demo text")
    with pytest.raises(AdapterUnavailable) as exc:
        pipeline.transcribe_audio_result(b"audio")
    assert exc.value.result.development
    assert "configured demo text" not in str(exc.value)


def test_missing_adapters_have_explicit_development_provenance(monkeypatch):
    monkeypatch.setattr(pipeline, "transcribe_with_faster_whisper", lambda _: "")
    monkeypatch.setattr(pipeline, "synthesize_with_piper", lambda _: "")
    monkeypatch.setattr(pipeline, "synthesize_with_macos_say", lambda _: "")
    assert pipeline.transcribe_audio_result(b"audio").development
    assert pipeline.generate_response_result("hello").development
    result = pipeline.synthesize_speech_result("hello")
    assert result.provider == "silent-wav" and result.development


def test_real_alternate_provider_is_distinct_from_development_output(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self):
            return b'{"response": "A real alternative model response"}'

    monkeypatch.setenv("NVIDIA_NIM_MODEL", "preferred-model")
    monkeypatch.setenv("VOICE_STRICT_ADAPTERS", "true")
    monkeypatch.setattr(pipeline, "generate_with_nvidia_nim", lambda *args: "")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: Response())
    result = pipeline.generate_response_result("hello")
    assert result.provider == "ollama" and result.fallback
    assert result.development is False


def test_http_busy_after_timeout_until_worker_finishes(monkeypatch):
    runner = BlockingRunner(1)
    release, finished = Event(), Event()

    def block(*args):
        try:
            assert release.wait(5)
        finally:
            finished.set()
        return AdapterResult("real reply", "test-model")

    monkeypatch.setattr(main, "runner", runner)
    monkeypatch.setattr(main, "generate_response", block)
    monkeypatch.setattr(main, "save_request", lambda trace: None)
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "0.02")
    monkeypatch.setenv("VOICE_STRICT_ADAPTERS", "true")
    try:
        with TestClient(
            main.app, client=("127.0.0.1", 50000), base_url="http://localhost"
        ) as client:
            first = client.post("/chat", json={"message": "hello"})
            assert first.status_code == 200
            assert first.json()["status"] == "failed"
            assert not first.json()["response"]
            assert not finished.is_set()
            overflow = client.post("/chat", json={"message": "hello"})
            assert (
                overflow.status_code == 429 and overflow.headers["Retry-After"] == "5"
            )
            assert client.get("/health").status_code == 200
            release.set()
            assert finished.wait(2)
            monkeypatch.setattr(
                main,
                "generate_response",
                lambda *args: AdapterResult("reply", "test-llm"),
            )
            monkeypatch.setattr(
                main,
                "synthesize_speech",
                lambda *args: AdapterResult("data:audio/wav;base64,AA==", "test-tts"),
            )
            assert (
                client.post("/chat", json={"message": "hello"}).json()["status"]
                == "completed"
            )
    finally:
        release.set()
        runner.close()


def test_strict_failure_records_stage_and_provenance(monkeypatch):
    monkeypatch.setenv("VOICE_STRICT_ADAPTERS", "true")
    monkeypatch.setattr(main, "save_request", lambda trace: None)
    monkeypatch.setattr(pipeline, "generate_with_nvidia_nim", lambda *args: "")
    result = asyncio.run(main.run_text_pipeline("hello"))
    assert result["status"] == "failed"
    assert result["metrics"]["adapters"]["llm"]["development"] is True
    assert not any(event["type"] == "llm_completed" for event in result["events"])
