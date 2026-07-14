from app.main import app, health


def test_health_route_returns_status() -> None:
    assert any(route.path == "/health" for route in app.routes)
    payload = health()
    assert payload["status"] == "ok"
    assert payload["service"] == "realtime-voice-ai-lab"
    assert "timestamp" in payload
