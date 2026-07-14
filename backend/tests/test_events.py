from app.events import EVENT_TYPES, STAGES, is_known_event_type


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
