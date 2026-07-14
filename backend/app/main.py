from datetime import UTC, datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.events import new_request_id, voice_event

app = FastAPI(title="Realtime Voice AI Reliability Lab")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "realtime-voice-ai-lab",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.websocket("/ws/voice")
async def voice_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    request_id = new_request_id()
    metadata: dict[str, object] = {}
    await websocket.send_json(voice_event("request_started", request_id=request_id))

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if text := message.get("text"):
                metadata = await handle_client_event(websocket, request_id, text)
            elif audio := message.get("bytes"):
                await handle_audio(websocket, request_id, audio, metadata)
    except WebSocketDisconnect:
        return


async def handle_client_event(websocket: WebSocket, request_id: str, text: str) -> dict[str, object]:
    await websocket.send_json(
        voice_event(
            "stage_started",
            request_id=request_id,
            stage="audio_validation",
            message="Audio metadata received.",
        )
    )
    try:
        import json

        payload = json.loads(text)
    except ValueError:
        await websocket.send_json(
            voice_event(
                "request_failed",
                request_id=request_id,
                stage="audio_validation",
                message="Invalid JSON event.",
            )
        )
        return {}

    if payload.get("type") != "client_audio_ready":
        return {}

    return {
        "mime_type": payload.get("mime_type"),
        "size": payload.get("size"),
        "duration_ms": payload.get("duration_ms"),
    }


async def handle_audio(
    websocket: WebSocket, request_id: str, audio: bytes, metadata: dict[str, object]
) -> None:
    if not audio:
        await websocket.send_json(
            voice_event(
                "request_failed",
                request_id=request_id,
                stage="audio_validation",
                message="Recorded audio was empty.",
            )
        )
        return

    await websocket.send_json(
        voice_event(
            "stage_completed",
            request_id=request_id,
            stage="audio_validation",
            message="Audio received.",
            audio_size=len(audio),
            mime_type=metadata.get("mime_type"),
            duration_ms=metadata.get("duration_ms"),
        )
    )
    await websocket.send_json(
        voice_event(
            "request_completed",
            request_id=request_id,
            message="Audio transfer completed.",
            audio_size=len(audio),
        )
    )
