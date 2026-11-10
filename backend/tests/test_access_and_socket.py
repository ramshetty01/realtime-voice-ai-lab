import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app, handle_audio, positive_float_env, run_text_pipeline
from app.timing import Timer

ORIGIN = {"origin": "http://127.0.0.1:3000"}


def client(host="127.0.0.1"):
    return TestClient(app, client=(host, 50000), base_url="http://127.0.0.1")


def authenticate(socket, token=""):
    socket.send_json({"type": "authenticate", "token": token})
    assert socket.receive_json()["type"] == "session_ready"


def test_http_auth_protects_inference_and_traces(monkeypatch):
    monkeypatch.setenv("VOICE_API_TOKEN", "test-access-token")
    monkeypatch.setattr(
        "app.main.recent_requests", lambda limit: [{"request_id": "req_demo"}]
    )
    for path in ("/requests", "/requests/req_demo", "/requests/req_demo/export"):
        assert client().get(path).status_code == 401
    assert client().post("/chat", json={"message": "hello"}).status_code == 401
    assert client().post("/requests/req_demo/replay-transcript").status_code == 401
    assert client().get("/health").status_code == 200
    assert (
        client()
        .get("/requests", headers={"Authorization": "Bearer test-access-token"})
        .status_code
        == 200
    )
    assert (
        client().get("/requests", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )


def test_loopback_is_not_trusted_via_forwarded_headers(monkeypatch):
    monkeypatch.setattr("app.main.recent_requests", lambda limit: [])
    assert (
        client("198.51.100.7")
        .get("/requests", headers={"X-Forwarded-For": "127.0.0.1"})
        .status_code
        == 401
    )
    assert client().get("/requests").status_code == 200
    assert client().get("/requests", headers={"Host": "untrusted.example"}).status_code == 401
    assert (
        client()
        .post(
            "/chat",
            json={"message": "hello"},
            headers={"Origin": "https://untrusted.example"},
        )
        .status_code
        == 403
    )
    monkeypatch.setenv("VOICE_LOCAL_ONLY", "false")
    assert client().get("/requests").status_code == 401


def test_request_bounds_and_pagination():
    assert client().get("/requests?limit=-1").status_code == 422
    assert client().get("/requests?limit=101").status_code == 422
    assert client().post("/chat", content=b"x" * 262145).status_code == 413
    assert (
        client()
        .post(
            "/chat",
            json={
                "message": "hello",
                "history": [{"role": "user", "content": "x"}] * 33,
            },
        )
        .status_code
        == 422
    )


def test_websocket_rejects_untrusted_origin_and_invalid_token(monkeypatch):
    monkeypatch.setenv("VOICE_API_TOKEN", "test-token")
    with pytest.raises(WebSocketDisconnect):
        with client().websocket_connect(
            "/ws/voice", headers={"origin": "https://untrusted.example"}
        ):
            pass
    with client().websocket_connect("ws://127.0.0.1/ws/voice", headers=ORIGIN) as socket:
        socket.send_json({"type": "authenticate", "token": "wrong"})
        with pytest.raises(WebSocketDisconnect) as exc:
            socket.receive_json()
        assert exc.value.code == 1008
    with client("198.51.100.7").websocket_connect(
        "/ws/voice", headers=ORIGIN
    ) as socket:
        authenticate(socket, "test-token")


def test_socket_two_turns_have_distinct_traces_and_reset_metadata(monkeypatch):
    traces = []
    monkeypatch.setattr("app.main.transcribe_audio", lambda audio: audio.decode())
    monkeypatch.setattr("app.main.generate_response", lambda text, history: "reply")
    monkeypatch.setattr(
        "app.main.synthesize_speech", lambda text: "data:audio/wav;base64,AA=="
    )
    monkeypatch.setattr("app.main.save_request", lambda trace: traces.append(trace))
    with client().websocket_connect("ws://127.0.0.1/ws/voice", headers=ORIGIN) as socket:
        authenticate(socket)
        socket.send_json(
            {
                "type": "client_audio_ready",
                "mime_type": "audio/wav",
                "history": [{"role": "user", "content": "old"}],
            }
        )
        assert socket.receive_json()["type"] == "stage_started"
        for text in (b"first", b"second"):
            socket.send_bytes(text)
            while (event := socket.receive_json())["type"] != "request_completed":
                assert event["type"] != "request_failed"
            assert event["status"] == "completed"
    assert len(traces) == 2
    assert traces[0]["request_id"] != traces[1]["request_id"]
    assert traces[0]["history"] and not traces[1]["history"]
    assert traces[1]["mime_type"] is None


@pytest.mark.parametrize(
    "frame", ["[]", "null", '"text"', "{broken", '{"type":"unknown"}', "x" * 32769]
)
def test_malformed_metadata_does_not_crash_socket(frame):
    with client().websocket_connect("ws://127.0.0.1/ws/voice", headers=ORIGIN) as socket:
        authenticate(socket)
        socket.send_text(frame)
        assert socket.receive_json()["type"] == "stage_started"
        assert socket.receive_json()["type"] == "request_failed"
        socket.send_json({"type": "client_audio_ready"})
        assert socket.receive_json()["type"] == "stage_started"


def test_empty_audio_is_rejected_on_actual_websocket(monkeypatch):
    traces = []
    monkeypatch.setattr("app.main.save_request", lambda trace: traces.append(trace))
    with client().websocket_connect("ws://127.0.0.1/ws/voice", headers=ORIGIN) as socket:
        authenticate(socket)
        socket.send_bytes(b"")
        assert socket.receive_json()["type"] == "request_started"
        assert socket.receive_json()["type"] == "request_failed"
    assert traces[0]["status"] == "failed"


def test_asr_failure_never_sends_request_completed(monkeypatch):
    class Socket:
        events = []

        async def send_json(self, event):
            self.events.append(event)

    def fail(_):
        raise RuntimeError("private adapter detail")

    monkeypatch.setattr("app.main.transcribe_audio", fail)
    monkeypatch.setattr("app.main.save_request", lambda trace: None)
    socket = Socket()
    asyncio.run(handle_audio(socket, "req_test", b"valid audio", {}, Timer()))
    assert socket.events[-1]["type"] == "request_failed"
    assert not any(event["type"] == "request_completed" for event in socket.events)
    assert "private adapter detail" not in str(socket.events)


def test_llm_error_is_safe_failed_result(monkeypatch):
    def fail(*args):
        raise RuntimeError("private adapter detail")

    monkeypatch.setattr("app.main.generate_response", fail)
    monkeypatch.setattr("app.main.save_request", lambda trace: None)
    result = asyncio.run(run_text_pipeline("hello"))
    assert result["status"] == "failed"
    assert result["request_id"]
    assert "private adapter detail" not in str(result)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_timeout_settings_reject_nonfinite_values(monkeypatch, value):
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", value)
    with pytest.raises(RuntimeError):
        positive_float_env("LLM_TIMEOUT_SECONDS", 45)
