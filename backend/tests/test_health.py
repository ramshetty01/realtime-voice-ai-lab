import asyncio

from app.main import ChatRequest, app, chat, handle_audio, health
from app.timing import Timer


def test_health_route_returns_status() -> None:
    assert any(route.path == "/health" for route in app.routes)
    payload = health()
    assert payload["status"] == "ok"
    assert payload["service"] == "realtime-voice-ai-lab"
    assert "timestamp" in payload


def test_cors_middleware_is_configured() -> None:
    assert any(middleware.cls.__name__ == "CORSMiddleware" for middleware in app.user_middleware)


def test_chat_route_runs_text_pipeline(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    payload = asyncio.run(chat(ChatRequest(message="hello")))
    assert payload["transcript"] == "hello"
    assert payload["response"]
    assert str(payload["audio_url"]).startswith("data:audio/wav;base64,")


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
