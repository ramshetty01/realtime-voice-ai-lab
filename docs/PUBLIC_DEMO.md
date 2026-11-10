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
- Shared-token access is now enforced when `VOICE_API_TOKEN` is configured; it is not per-user authorization. Add account identity and trace ownership before multi-user use.
- Disable or expire stored traces if transcripts may contain sensitive content.

## Access and transport changes

- Set `VOICE_API_TOKEN` for shared access and `VOICE_LOCAL_ONLY=false`; the browser
  API access field sends this token only in a header or initial WebSocket frame.
- Never publish this token with `NEXT_PUBLIC_*`, persist it in browser storage, or
  place it in a query string. It is a lab access token, not the model-provider key.
- Without a configured token, only direct loopback clients are allowed in local mode.
  Both peer IP and Host must be loopback/localhost; forwarded headers do not establish trust. Never expose local mode behind a proxy.
- HTTP bodies are capped at 256 KiB, history at 32 items, metadata at 32 KiB and
  trace pagination at 1–100. A WebSocket auth frame must arrive within five seconds.
- Docker publishes both ports on 127.0.0.1 and requires VOICE_API_TOKEN.
- Set the ASGI server's WebSocket message-size and connection limits at deployment
  too; application byte checks happen after a frame is received. TLS/WSS is required
  beyond loopback. There is no current distributed rate limiter or cancellation
  of work already running in asyncio.to_thread after a timeout.
