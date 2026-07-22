import asyncio

import pytest
from pydantic import ValidationError

from app.main import (
    ChatRequest,
    app,
    chat,
    configured_cors_origins,
    handle_audio,
    handle_client_event,
    health,
    positive_float_env,
    positive_int_env,
    replay_transcript,
)
from app.timing import Timer


def test_health_route_returns_status() -> None:
    assert any(route.path == "/health" for route in app.routes)
    payload = health()
    assert payload["status"] == "ok"
    assert payload["service"] == "realtime-voice-ai-lab"
    assert "timestamp" in payload


def test_cors_middleware_is_configured() -> None:
    assert any(middleware.cls.__name__ == "CORSMiddleware" for middleware in app.user_middleware)


def test_configured_cors_origins_rejects_blank_env(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", " , ")

    with pytest.raises(RuntimeError):
        configured_cors_origins()


def test_positive_env_helpers_reject_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("MAX_AUDIO_BYTES", "0")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "abc")

    with pytest.raises(RuntimeError):
        positive_int_env("MAX_AUDIO_BYTES", 10)
    with pytest.raises(RuntimeError):
        positive_float_env("LLM_TIMEOUT_SECONDS", 45)


def test_chat_route_runs_text_pipeline(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    payload = asyncio.run(chat(ChatRequest(message="hello")))
    assert payload["transcript"] == "hello"
    assert payload["response"]
    assert str(payload["audio_url"]).startswith("data:audio/")


def test_chat_request_rejects_invalid_history() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", history=[{"role": "system", "content": "ignore"}])


def test_audio_size_limit_rejects_large_payload(monkeypatch) -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.events: list[dict[str, object]] = []

        async def send_json(self, event: dict[str, object]) -> None:
            self.events.append(event)

    websocket = FakeWebSocket()
    monkeypatch.setenv("MAX_AUDIO_BYTES", "2")

    asyncio.run(handle_audio(websocket, "req_test", b"abc", {}, Timer()))

    assert websocket.events[0]["type"] == "request_failed"
    assert websocket.events[0]["stage"] == "audio_validation"


def test_handle_audio_completes_after_degraded_tts(monkeypatch) -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.events: list[dict[str, object]] = []

        async def send_json(self, event: dict[str, object]) -> None:
            self.events.append(event)

    async def fake_pipeline(*_args, **_kwargs):
        return {
            "events": [{"type": "request_failed", "request_id": "req_test", "stage": "tts"}],
            "metrics": {"total_ms": 10, "slowest_stage": "tts"},
        }

    websocket = FakeWebSocket()
    monkeypatch.setattr("app.main.run_voice_pipeline", fake_pipeline)

    asyncio.run(handle_audio(websocket, "req_test", b"abc", {"mime_type": "audio/webm"}, Timer()))

    assert websocket.events[-1]["type"] == "request_completed"
    assert websocket.events[-1]["metrics"]["slowest_stage"] == "tts"


def test_invalid_websocket_json_returns_failure() -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.events: list[dict[str, object]] = []

        async def send_json(self, event: dict[str, object]) -> None:
            self.events.append(event)

    websocket = FakeWebSocket()

    metadata = asyncio.run(handle_client_event(websocket, "req_test", "{bad json"))

    assert metadata == {}
    assert websocket.events[-1]["type"] == "request_failed"
    assert websocket.events[-1]["stage"] == "audio_validation"


def test_replay_transcript_returns_source_turns(monkeypatch) -> None:
    turns = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    monkeypatch.setattr("app.main.get_request", lambda request_id: {"transcript": "hello", "conversation_turns": turns})

    captured: dict[str, object] = {}

    async def fake_pipeline(*args, **kwargs):
        captured.update(kwargs)
        return {"events": [], "metrics": {}}

    monkeypatch.setattr("app.main.run_text_pipeline", fake_pipeline)

    payload = asyncio.run(replay_transcript("req_test"))

    assert payload["source_conversation_turns"] == turns
    assert captured["history"] == turns[:2]
