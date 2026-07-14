import base64
import io
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
import wave
from pathlib import Path


def transcribe_audio(audio: bytes) -> str:
    if text := os.getenv("ASR_TRANSCRIPT_TEXT"):
        return text
    return f"Received {len(audio)} bytes of audio. Configure local ASR to replace this development transcript."


def generate_response(transcript: str) -> str:
    payload = json.dumps(
        {"model": os.getenv("OLLAMA_MODEL", "llama3.2"), "prompt": transcript, "stream": False}
    ).encode()
    request = urllib.request.Request(
        f"{os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')}/api/generate",
        data=payload,
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode())
            return body.get("response") or "The local model returned an empty response."
    except (OSError, urllib.error.URLError, TimeoutError):
        return "Local Ollama is unavailable. Start Ollama to generate a model response."


def synthesize_speech(text: str) -> str:
    if audio := synthesize_with_piper(text):
        return audio
    return wav_data_url(b"\x00\x00" * 1600)


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


def wav_data_url(frames: bytes) -> str:
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(frames)
    return data_url(audio.getvalue())


def data_url(audio: bytes) -> str:
    encoded = base64.b64encode(audio).decode()
    return f"data:audio/wav;base64,{encoded}"
