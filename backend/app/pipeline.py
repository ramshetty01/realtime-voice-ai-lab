import base64
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AdapterResult:
    value: str
    provider: str
    fallback: bool = False
    reason: str | None = None
    development: bool = False

    def provenance(self) -> dict[str, object]:
        return {"provider": self.provider, "fallback": self.fallback, "reason": self.reason, "development": self.development}


class AdapterUnavailable(Exception):
    def __init__(self, result: AdapterResult):
        super().__init__("A real adapter is unavailable; strict mode refuses development output.")
        self.result = result


def adapter_result(value: str, provider: str, fallback: bool = False, reason: str | None = None, *, development: bool = False) -> AdapterResult:
    result = AdapterResult(value, provider, fallback, reason, development)
    if development and os.getenv("VOICE_STRICT_ADAPTERS", "false").lower() == "true":
        raise AdapterUnavailable(result)
    return result


def transcribe_audio_result(audio: bytes) -> AdapterResult:
    if text := os.getenv("ASR_TRANSCRIPT_TEXT"):
        return adapter_result(text, "configured-development-transcript", True, "Using a configured transcript rather than speech recognition.", development=True)
    if transcript := transcribe_with_faster_whisper(audio):
        return adapter_result(transcript, "faster-whisper")
    return adapter_result(f"Received {len(audio)} bytes of audio. Configure local ASR to replace this development transcript.", "development-transcript", True, "Speech recognition is unavailable or returned no transcript.", development=True)


def transcribe_audio(audio: bytes) -> str:
    return transcribe_audio_result(audio).value


def transcribe_with_faster_whisper(audio: bytes) -> str:
    try:
        whisper_module = sys.modules.get("faster_whisper")
        if whisper_module is None:
            import faster_whisper as whisper_module  # type: ignore[import-not-found]
    except ImportError:
        return ""

    with tempfile.NamedTemporaryFile(suffix=os.getenv("ASR_AUDIO_SUFFIX", ".webm")) as source:
        source.write(audio)
        source.flush()
        try:
            model = whisper_module.WhisperModel(
                os.getenv("ASR_MODEL", "base"),
                device=os.getenv("ASR_DEVICE", "cpu"),
                compute_type=os.getenv("ASR_COMPUTE_TYPE", "int8"),
            )
            segments, _info = model.transcribe(source.name, beam_size=1)
            return " ".join(segment.text.strip() for segment in segments).strip()
        except Exception:
            return ""


def generate_response_result(transcript: str, history: list[dict[str, str]] | None = None) -> AdapterResult:
    if response := generate_with_nvidia_nim(transcript, history):
        return adapter_result(response, "nvidia-nim")

    nim_requested = bool(os.getenv("NVIDIA_NIM_BASE_URL") or os.getenv("NVIDIA_NIM_MODEL"))
    prompt = prompt_with_history(transcript, history)
    payload = json.dumps(
        {"model": os.getenv("OLLAMA_MODEL", "llama3.2"), "prompt": prompt, "stream": False}
    ).encode()
    request = urllib.request.Request(
        f"{os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')}/api/generate",
        data=payload,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode())
            text = body.get("response")
            if isinstance(text, str) and text.strip():
                return adapter_result(text, "ollama", nim_requested, "Configured NVIDIA adapter did not return a response; used Ollama." if nim_requested else None)
            return adapter_result("The local model returned an empty response.", "development-response", True, "The model returned no response.", development=True)
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return adapter_result("Local Ollama is unavailable. Start Ollama to generate a model response.", "development-response", True, "No configured text-model adapter returned a response.", development=True)


def generate_response(transcript: str, history: list[dict[str, str]] | None = None) -> str:
    return generate_response_result(transcript, history).value


def generate_with_nvidia_nim(transcript: str, history: list[dict[str, str]] | None = None) -> str:
    base_url = os.getenv("NVIDIA_NIM_BASE_URL", "").rstrip("/")
    model = os.getenv("NVIDIA_NIM_MODEL", "")
    api_key = os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NGC_API_KEY", "")
    if not base_url or not model or not api_key:
        return ""

    payload = json.dumps(
        {
            "model": model,
            "messages": [*llm_history(history), {"role": "user", "content": transcript}],
            "temperature": 0.2,
            "max_tokens": 512,
        }
    ).encode()
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
            return body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except (OSError, urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError):
        return ""


def llm_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for item in (history or [])[-max_history_turns():]:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content[:2000]})
    return messages


def prompt_with_history(transcript: str, history: list[dict[str, str]] | None) -> str:
    messages = llm_history(history)
    if not messages:
        return transcript
    turns = "\n".join(f"{item['role']}: {item['content']}" for item in messages)
    return f"Conversation so far:\n{turns}\n\nUser: {transcript}\nAssistant:"


def max_history_turns() -> int:
    try:
        return max(1, int(os.getenv("MAX_HISTORY_TURNS", "8")))
    except ValueError:
        return 8


def synthesize_speech_result(text: str) -> AdapterResult:
    if audio := synthesize_with_piper(text):
        return adapter_result(audio, "piper")
    if audio := synthesize_with_macos_say(text):
        return adapter_result(audio, "macos-say", bool(os.getenv("PIPER_MODEL_PATH")), "Configured Piper adapter was unavailable; used macOS speech." if os.getenv("PIPER_MODEL_PATH") else None)
    return adapter_result(wav_data_url(b"\x00\x00" * 1600), "silent-wav", True, "No speech synthesizer is available; this is silent demo audio.", development=True)


def synthesize_speech(text: str) -> str:
    return synthesize_speech_result(text).value


def synthesize_with_piper(text: str) -> str:
    model = Path(os.getenv("PIPER_MODEL_PATH", ""))
    if not model.exists():
        return ""
    with tempfile.NamedTemporaryFile(suffix=".wav") as output:
        try:
            subprocess.run(
                [os.getenv("PIPER_BIN", "piper"), "--model", str(model), "--output_file", output.name],
                input=text.encode(),
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            return data_url(Path(output.name).read_bytes())
        except (OSError, subprocess.SubprocessError):
            return ""


def synthesize_with_macos_say(text: str) -> str:
    say = os.getenv("MACOS_SAY_BIN", "say")
    afconvert = os.getenv("AFCONVERT_BIN", "afconvert")
    with tempfile.NamedTemporaryFile(suffix=".aiff") as source, tempfile.NamedTemporaryFile(suffix=".m4a") as output:
        try:
            subprocess.run(
                [say, "-o", source.name, text],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            subprocess.run(
                [afconvert, source.name, output.name, "-f", "m4af", "-d", "aac"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            return data_url(Path(output.name).read_bytes(), "audio/mp4")
        except (OSError, subprocess.SubprocessError):
            return ""


def wav_data_url(frames: bytes) -> str:
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(frames)
    return data_url(audio.getvalue())


def data_url(audio: bytes, mime_type: str = "audio/wav") -> str:
    encoded = base64.b64encode(audio).decode()
    return f"data:{mime_type};base64,{encoded}"
