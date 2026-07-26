from app.storage import connect, get_request, recent_requests, save_request


def test_save_request_persists_trace(tmp_path) -> None:
    db_path = tmp_path / "voice_lab.db"
    save_request(
        {
            "request_id": "req_test",
            "status": "completed",
            "transcript": "hello",
            "assistant_response": "hi",
            "audio_path": "recordings/req_test.webm",
            "mime_type": "audio/webm",
            "duration_ms": 1234,
            "failure_stage": "tts",
            "error_message": "slow",
            "history": [{"role": "user", "content": "older"}],
            "conversation_turns": [
                {"role": "user", "content": "older"},
                {"role": "assistant", "content": "reply"},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
            "asr_ms": 1,
            "llm_total_ms": 2,
            "tts_total_ms": 3,
            "total_ms": 6,
            "slowest_stage": "tts",
            "created_at": "2026-07-14T00:00:00+00:00",
        },
        path=db_path,
    )

    with connect(db_path) as db:
        row = db.execute(
            "select transcript, total_ms, slowest_stage from requests where request_id = ?", ("req_test",)
        ).fetchone()

    assert row == ("hello", 6, "tts")
    trace = get_request("req_test", path=db_path)
    assert trace["assistant_response"] == "hi"
    assert trace["mime_type"] == "audio/webm"
    assert trace["duration_ms"] == 1234
    assert trace["failure_stage"] == "tts"
    assert trace["error_message"] == "slow"
    assert trace["history"] == [{"role": "user", "content": "older"}]
    assert trace["conversation_turns"][-1] == {"role": "assistant", "content": "hi"}
    assert recent_requests(path=db_path)[0]["audio_path"] == "recordings/req_test.webm"
    assert recent_requests(path=db_path)[0]["request_id"] == "req_test"


def test_save_request_applies_retention_limit(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "voice_lab.db"
    monkeypatch.setenv("REQUEST_RETENTION_LIMIT", "1")

    for request_id, created_at in (("req_old", "2026-07-14T00:00:00+00:00"), ("req_new", "2026-07-15T00:00:00+00:00")):
        save_request({"request_id": request_id, "status": "completed", "created_at": created_at}, path=db_path)

    assert [request["request_id"] for request in recent_requests(path=db_path)] == ["req_new"]
