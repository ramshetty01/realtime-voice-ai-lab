import wave
from types import SimpleNamespace

from app.pipeline import (
    generate_response,
    generate_with_nvidia_nim,
    llm_history,
    prompt_with_history,
    synthesize_speech,
    synthesize_with_macos_say,
    synthesize_with_piper,
    transcribe_audio,
    transcribe_with_faster_whisper,
)


def test_transcribe_audio_development_fallback() -> None:
    assert "3 bytes" in transcribe_audio(b"abc")


def test_transcribe_audio_uses_faster_whisper_when_available(monkeypatch) -> None:
    class FakeModel:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def transcribe(self, _path: str, beam_size: int) -> tuple[list[SimpleNamespace], object]:
            return [SimpleNamespace(text=" hello "), SimpleNamespace(text="world")], object()

    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeModel))

    assert transcribe_with_faster_whisper(b"audio") == "hello world"


def test_generate_response_handles_missing_ollama(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    assert "Ollama is unavailable" in generate_response("hello")


def test_generate_response_uses_nvidia_nim_when_configured(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def read(self) -> bytes:
            return b'{"choices":[{"message":{"content":"nim response"}}]}'

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        assert timeout == 30
        assert "chat/completions" in request.full_url
        assert request.headers["Authorization"] == "Bearer test-key"
        payload = __import__("json").loads(request.data.decode())
        assert payload["messages"] == [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
            {"role": "user", "content": "hello"},
        ]
        return FakeResponse()

    monkeypatch.setenv("NVIDIA_NIM_BASE_URL", "http://nim.test/v1")
    monkeypatch.setenv("NVIDIA_NIM_MODEL", "test-model")
    monkeypatch.setenv("NVIDIA_NIM_API_KEY", "test-key")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert (
        generate_response(
            "hello",
            [
                {"role": "user", "content": "previous question"},
                {"role": "assistant", "content": "previous answer"},
            ],
        )
        == "nim response"
    )


def test_llm_history_keeps_recent_valid_turns() -> None:
    history = [{"role": "user", "content": f"turn {index}"} for index in range(10)]
    history.extend(
        [
            {"role": "system", "content": "ignore"},
            {"role": "assistant", "content": "  final answer  "},
            {"role": "user", "content": ""},
        ]
    )

    messages = llm_history(history)

    assert {"role": "system", "content": "ignore"} not in messages
    assert messages[0] == {"role": "user", "content": "turn 5"}
    assert messages[-1] == {"role": "assistant", "content": "final answer"}


def test_prompt_with_history_formats_ollama_context() -> None:
    prompt = prompt_with_history("continue", [{"role": "user", "content": "hello"}])

    assert "Conversation so far:" in prompt
    assert "user: hello" in prompt
    assert prompt.endswith("User: continue\nAssistant:")


def test_nvidia_nim_requires_configuration(monkeypatch) -> None:
    monkeypatch.delenv("NVIDIA_NIM_BASE_URL", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_MODEL", raising=False)
    monkeypatch.delenv("NVIDIA_NIM_API_KEY", raising=False)
    monkeypatch.delenv("NGC_API_KEY", raising=False)
    assert generate_with_nvidia_nim("hello") == ""


def test_synthesize_speech_returns_playable_wav_data_url(monkeypatch) -> None:
    monkeypatch.setenv("MACOS_SAY_BIN", "/missing/say")
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


def test_missing_macos_say_uses_fallback(monkeypatch) -> None:
    monkeypatch.setenv("MACOS_SAY_BIN", "/missing/say")
    assert synthesize_with_macos_say("hello") == ""
