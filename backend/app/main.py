from datetime import UTC, datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.events import new_request_id, utc_timestamp, voice_event
from app.pipeline import generate_response, synthesize_speech, transcribe_audio
from app.storage import save_request
from app.timing import Timer

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
    total = Timer()
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
                await handle_audio(websocket, request_id, audio, metadata, total)
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
    websocket: WebSocket, request_id: str, audio: bytes, metadata: dict[str, object], total: Timer
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

    asr = Timer()
    await websocket.send_json(voice_event("stage_started", request_id=request_id, stage="asr"))
    transcript = transcribe_audio(audio)
    asr_ms = asr.ms()
    await websocket.send_json(
        voice_event("transcript_completed", request_id=request_id, transcript=transcript)
    )
    await websocket.send_json(
        voice_event("stage_completed", request_id=request_id, stage="asr", duration_ms=asr_ms)
    )

    llm = Timer()
    await websocket.send_json(voice_event("stage_started", request_id=request_id, stage="llm"))
    assistant_response = generate_response(transcript)
    for token in assistant_response.split():
        await websocket.send_json(voice_event("llm_token", request_id=request_id, token=f"{token} "))
    llm_ms = llm.ms()
    await websocket.send_json(
        voice_event("llm_completed", request_id=request_id, response=assistant_response)
    )
    await websocket.send_json(
        voice_event("stage_completed", request_id=request_id, stage="llm", duration_ms=llm_ms)
    )

    tts = Timer()
    await websocket.send_json(voice_event("stage_started", request_id=request_id, stage="tts"))
    audio_url = synthesize_speech(assistant_response)
    tts_ms = tts.ms()
    await websocket.send_json(voice_event("tts_audio_ready", request_id=request_id, audio_url=audio_url))
    await websocket.send_json(
        voice_event("stage_completed", request_id=request_id, stage="tts", duration_ms=tts_ms)
    )

    total_ms = total.ms()
    metrics = {
        "asr_ms": asr_ms,
        "llm_total_ms": llm_ms,
        "tts_total_ms": tts_ms,
        "total_ms": total_ms,
    }
    save_request(
        {
            "request_id": request_id,
            "status": "completed",
            "transcript": transcript,
            "assistant_response": assistant_response,
            "created_at": utc_timestamp(),
            **metrics,
        }
    )
    await websocket.send_json(
        voice_event(
            "request_completed",
            request_id=request_id,
            message="Voice pipeline completed.",
            audio_size=len(audio),
            metrics=metrics,
        )
    )
