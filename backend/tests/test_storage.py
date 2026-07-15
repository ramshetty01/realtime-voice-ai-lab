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
    assert get_request("req_test", path=db_path)["assistant_response"] == "hi"
    assert recent_requests(path=db_path)[0]["audio_path"] == "recordings/req_test.webm"
    assert recent_requests(path=db_path)[0]["request_id"] == "req_test"
