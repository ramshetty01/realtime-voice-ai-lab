from app.main import app, health


def test_health_route_returns_status() -> None:
    assert any(route.path == "/health" for route in app.routes)
    payload = health()
    assert payload["status"] == "ok"
    assert payload["service"] == "realtime-voice-ai-lab"
    assert "timestamp" in payload


def test_cors_middleware_is_configured() -> None:
    assert any(middleware.cls.__name__ == "CORSMiddleware" for middleware in app.user_middleware)
