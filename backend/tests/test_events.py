from app.events import EVENT_TYPES, STAGES, is_known_event_type, new_request_id, voice_event


def test_event_contract_covers_request_lifecycle() -> None:
    assert "request_started" in EVENT_TYPES
    assert "request_completed" in EVENT_TYPES
    assert "request_failed" in EVENT_TYPES
    assert "asr" in STAGES
    assert "llm" in STAGES
    assert "tts" in STAGES


def test_unknown_event_type_is_rejected() -> None:
    assert is_known_event_type("request_started")
    assert not is_known_event_type("random_event")


def test_voice_event_adds_timestamp_and_request_id() -> None:
    request_id = new_request_id()
    event = voice_event("request_started", request_id=request_id)

    assert request_id.startswith("req_")
    assert event["type"] == "request_started"
    assert event["request_id"] == request_id
    assert "timestamp" in event
