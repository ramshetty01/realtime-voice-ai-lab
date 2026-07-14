import wave

from app.pipeline import generate_response, synthesize_speech, synthesize_with_piper, transcribe_audio


def test_transcribe_audio_development_fallback() -> None:
    assert "3 bytes" in transcribe_audio(b"abc")


def test_generate_response_handles_missing_ollama(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    assert "Ollama is unavailable" in generate_response("hello")


def test_synthesize_speech_returns_playable_wav_data_url() -> None:
    audio_url = synthesize_speech("hello")
    assert audio_url.startswith("data:audio/wav;base64,")
    payload = audio_url.split(",", 1)[1]
    import base64
    import io

    with wave.open(io.BytesIO(base64.b64decode(payload)), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000


def test_missing_piper_model_uses_fallback(monkeypatch) -> None:
    monkeypatch.setenv("PIPER_MODEL_PATH", "/missing/model.onnx")
    assert synthesize_with_piper("hello") == ""
