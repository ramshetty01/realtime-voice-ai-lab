# Lower-Latency Voice Spike

## Current Path

```txt
record complete audio
-> send one websocket binary payload
-> ASR returns one transcript
-> LLM returns text
-> TTS returns one audio clip
-> browser plays response
```

This is a chained voice pipeline. It is simple to debug and good for latency
breakdowns, but it cannot feel exactly like ChatGPT Voice because each stage
waits on the previous stage.

## What We Can Improve Now

- Keep automatic turn detection so users do not need to press Stop.
- Send partial UI events as soon as the backend has them.
- Stream LLM tokens to the browser, which the app already does over
  `llm_token` events.
- Add chunked microphone upload only after ASR can consume chunks or short
  rolling audio windows.

## What NIM Changes

NVIDIA NIM chat completions gives this project a real reasoning layer, but it
does not replace ASR or TTS. With the current NIM setup, the realistic path is:

```txt
browser audio chunks
-> ASR partial/final transcript
-> NIM chat completion
-> TTS audio
-> playback
```

True speech-to-speech would require a realtime audio model or a provider that
accepts live audio and returns live audio in one session.

## Recommendation

Do not rewrite the app to WebRTC yet. For this portfolio project, the best next
step is to keep FastAPI WebSockets and improve the chained pipeline:

1. Capture small microphone chunks in the browser.
2. Buffer chunks server-side by request id.
3. Run ASR on short rolling windows when a real streaming-capable ASR provider
   is configured.
4. Keep the current full-blob fallback for local/demo reliability.

Existing issue #44 should own that implementation. Creating another issue would
duplicate the same work.

