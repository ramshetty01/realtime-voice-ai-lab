from app.storage import connect, save_request


def test_save_request_persists_trace(tmp_path) -> None:
    db_path = tmp_path / "voice_lab.db"
    save_request(
        {
            "request_id": "req_test",
            "status": "completed",
            "transcript": "hello",
            "assistant_response": "hi",
            "asr_ms": 1,
            "llm_total_ms": 2,
            "tts_total_ms": 3,
            "total_ms": 6,
            "created_at": "2026-07-14T00:00:00+00:00",
        },
        path=db_path,
    )

    with connect(db_path) as db:
        row = db.execute("select transcript, total_ms from requests where request_id = ?", ("req_test",)).fetchone()

    assert row == ("hello", 6)
