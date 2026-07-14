from app.main import build_metrics


def test_build_metrics_finds_slowest_stage() -> None:
    metrics = build_metrics(asr_ms=10, llm_ms=30, tts_ms=20, total_ms=70)

    assert metrics["slowest_stage"] == "llm"
    assert metrics["total_ms"] == 70
