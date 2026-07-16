# Local ASR and TTS Setup

The app works without local ASR/TTS models, but the demo is better when these
are configured.

## ASR: faster-whisper

Install the optional ASR dependency in the backend environment:

```sh
cd backend
source .venv/bin/activate
pip install -e ".[asr]"
```

Recommended local env values:

```sh
ASR_MODEL=base
ASR_DEVICE=cpu
ASR_COMPUTE_TYPE=int8
ASR_AUDIO_SUFFIX=.webm
```

When faster-whisper is not installed or transcription fails, the backend returns
a development transcript that starts with `Received ... bytes of audio`.

## TTS: Piper or macOS `say`

Install Piper and place a voice model under `models/piper/`.

Recommended local env values:

```sh
PIPER_BIN=piper
PIPER_MODEL_PATH=./models/piper/default.onnx
```

When Piper or the configured model path is missing, the backend returns a short
playable WAV fallback so the frontend audio path can still be tested.

On macOS, the backend also tries native `say` plus `afconvert` before the WAV
fallback. That gives a real generated voice without installing Piper.

The macOS path returns an `audio/mp4` data URL for browser playback.

## Current Local Status

Check the current machine with:

```sh
python scripts/verify_runtime.py
```

It reports NIM, ASR, and TTS readiness without printing API keys.
