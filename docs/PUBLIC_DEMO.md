# Public Demo Safeguards

This app is built for portfolio demos, not anonymous high-volume traffic.

## Required Settings

- Set `CORS_ORIGINS` to the exact frontend origin.
- Keep `AUDIO_PERSISTENCE_ENABLED=false` unless recorded audio is explicitly
  needed for debugging.
- Keep `MAX_AUDIO_BYTES` small. The default is `10485760` bytes.
- Use short model timeouts: `ASR_TIMEOUT_SECONDS`, `LLM_TIMEOUT_SECONDS`, and
  `TTS_TIMEOUT_SECONDS`.
- Do not commit `.env` or API keys.

## Current Guards

- Chat input is limited to 4000 characters.
- Voice audio must be non-empty.
- Voice audio larger than `MAX_AUDIO_BYTES` is rejected before ASR.
- Logs include request ids, stages, and timings, not raw audio bytes.
- Local fallback responses avoid hanging when ASR, LLM, or TTS is unavailable.

## Known Gaps Before Real Public Traffic

- Add a reverse-proxy rate limit per IP.
- Add HTTPS at the hosting layer.
- Add authentication if demos are shared beyond a small reviewer group.
- Disable or expire stored traces if transcripts may contain sensitive content.
