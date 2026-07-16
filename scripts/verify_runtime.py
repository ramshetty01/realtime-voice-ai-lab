#!/usr/bin/env python3
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def check_nim() -> tuple[bool, str]:
    base_url = os.getenv("NVIDIA_NIM_BASE_URL", "").rstrip("/")
    model = os.getenv("NVIDIA_NIM_MODEL", "")
    api_key = os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NGC_API_KEY", "")
    if not base_url or not model or not api_key:
        return False, "missing NVIDIA_NIM_BASE_URL, NVIDIA_NIM_MODEL, or API key"

    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(
            {"model": model, "messages": [{"role": "user", "content": "Reply with ok."}], "max_tokens": 8}
        ).encode(),
        headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return bool(content), "chat completions returned content" if content else "empty NIM response"
    except urllib.error.HTTPError as error:
        return False, f"NIM HTTP {error.code}"
    except (OSError, TimeoutError, ValueError, KeyError, IndexError) as error:
        return False, f"NIM unavailable: {type(error).__name__}"


def check_asr() -> tuple[bool, str]:
    if importlib.util.find_spec("faster_whisper") is None:
        backend_python = Path("backend/.venv/bin/python")
        if backend_python.exists():
            result = subprocess.run(
                [str(backend_python), "-c", "import faster_whisper"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                return True, "faster-whisper import is available in backend/.venv"
        return False, "faster-whisper is not installed"
    return True, "faster-whisper import is available"


def check_tts() -> tuple[bool, str]:
    piper = shutil.which(os.getenv("PIPER_BIN", "piper"))
    model = Path(os.getenv("PIPER_MODEL_PATH", "./models/piper/default.onnx"))
    if piper and model.exists():
        try:
            with subprocess.Popen(
                [piper, "--model", str(model), "--output-raw"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ) as process:
                process.communicate(b"ok", timeout=15)
                if process.returncode == 0:
                    return True, "Piper generated audio"
        except (OSError, subprocess.SubprocessError, TimeoutError):
            pass

    if shutil.which(os.getenv("MACOS_SAY_BIN", "say")) and shutil.which(os.getenv("AFCONVERT_BIN", "afconvert")):
        return True, "macOS say + afconvert are available"

    return False, "no configured TTS runtime found"


def main() -> int:
    if "--self-test" in sys.argv:
        os.environ["TEST_VALUE"] = "kept"
        Path("/tmp/verify_runtime.env").write_text("TEST_VALUE=ignored\nNEW_VALUE='ok'\n")
        load_env(Path("/tmp/verify_runtime.env"))
        assert os.environ["TEST_VALUE"] == "kept"
        assert os.environ["NEW_VALUE"] == "ok"
        return 0

    load_env(Path(".env"))
    checks = {"nim": check_nim(), "asr": check_asr(), "tts": check_tts()}
    for name, (ok, message) in checks.items():
        print(f"{name}: {'ok' if ok else 'blocked'} - {message}")
    return 0 if all(ok for ok, _message in checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
