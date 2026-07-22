import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.events import new_request_id, utc_timestamp, voice_event
from app.logging import log_event
from app.pipeline import generate_response, llm_history, synthesize_speech, transcribe_audio
from app.storage import get_request, recent_requests, save_request
from app.timing import Timer

app = FastAPI(title="Realtime Voice AI Reliability Lab")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://127.0.0.1:3000,http://localhost:3000").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ConversationTurn] = Field(default_factory=list)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "realtime-voice-ai-lab",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/requests")
def list_requests(limit: int = 20) -> dict[str, object]:
    return {"requests": recent_requests(limit=min(limit, 100))}


@app.get("/requests/{request_id}")
def request_detail(request_id: str) -> dict[str, object]:
    trace = get_request(request_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Request not found")
    return trace


@app.post("/chat")
async def chat(payload: ChatRequest) -> dict[str, object]:
    result = await run_text_pipeline(payload.message, history=[turn.model_dump() for turn in payload.history])
    response = next((event.get("response") for event in result["events"] if event["type"] == "llm_completed"), "")
    audio_url = next((event.get("audio_url") for event in result["events"] if event["type"] == "tts_audio_ready"), "")
    return {
        "request_id": result["request_id"],
        "transcript": payload.message,
        "response": response,
        "audio_url": audio_url,
        "events": result["events"],
        "metrics": result["metrics"],
    }


@app.post("/requests/{request_id}/replay-transcript")
async def replay_transcript(request_id: str) -> dict[str, object]:
    trace = get_request(request_id)
    if not trace or not trace.get("transcript"):
        raise HTTPException(status_code=404, detail="Request transcript not found")
    history = llm_history(trace.get("conversation_turns")[:-2] if isinstance(trace.get("conversation_turns"), list) else None)
    return await run_text_pipeline(str(trace["transcript"]), history=history, replay_of=request_id)


@app.post("/requests/{request_id}/replay-audio")
async def replay_audio(request_id: str) -> dict[str, object]:
    trace = get_request(request_id)
    audio_path = trace.get("audio_path") if trace else None
    if not audio_path or not Path(str(audio_path)).exists():
        raise HTTPException(status_code=404, detail="Request audio not found")
    return await run_voice_pipeline(Path(str(audio_path)).read_bytes(), {}, replay_of=request_id)


@app.websocket("/ws/voice")
async def voice_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    request_id = new_request_id()
    total = Timer()
    metadata: dict[str, object] = {}
    log_event("request_started", request_id=request_id)
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

    history = sanitize_history(payload.get("history"))
    return {
        "mime_type": payload.get("mime_type"),
        "size": payload.get("size"),
        "duration_ms": payload.get("duration_ms"),
        "history": history,
    }


async def handle_audio(
    websocket: WebSocket, request_id: str, audio: bytes, metadata: dict[str, object], total: Timer
) -> None:
    if not audio:
        event = voice_event(
            "request_failed",
            request_id=request_id,
            stage="audio_validation",
            message="Recorded audio was empty.",
        )
        log_event("request_failed", request_id=request_id, stage="audio_validation", message=event["message"])
        await websocket.send_json(event)
        return

    max_audio_bytes = int(os.getenv("MAX_AUDIO_BYTES", str(10 * 1024 * 1024)))
    if len(audio) > max_audio_bytes:
        event = voice_event(
            "request_failed",
            request_id=request_id,
            stage="audio_validation",
            message="Recorded audio is too large for this demo.",
            audio_size=len(audio),
            max_audio_bytes=max_audio_bytes,
        )
        log_event("request_failed", request_id=request_id, stage="audio_validation", message=event["message"])
        await websocket.send_json(event)
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

    result = await run_voice_pipeline(audio, metadata, request_id=request_id, total=total)
    for event in result.pop("events"):
        await websocket.send_json(event)
    await websocket.send_json(
        voice_event(
            "request_completed",
            request_id=request_id,
            message="Voice pipeline completed.",
            audio_size=len(audio),
            metrics=result["metrics"],
        )
    )


async def run_voice_pipeline(
    audio: bytes,
    metadata: dict[str, object],
    request_id: str | None = None,
    total: Timer | None = None,
    replay_of: str | None = None,
) -> dict[str, object]:
    request_id = request_id or new_request_id()
    total = total or Timer()
    audio_path = save_audio(request_id, audio) if os.getenv("AUDIO_PERSISTENCE_ENABLED") == "true" else None
    events: list[dict[str, object]] = []

    asr = Timer()
    events.append(voice_event("stage_started", request_id=request_id, stage="asr"))
    try:
        transcript = await asyncio.wait_for(
            asyncio.to_thread(transcribe_audio, audio),
            timeout=float(os.getenv("ASR_TIMEOUT_SECONDS", "30")),
        )
        asr_ms = asr.ms()
        events.append(voice_event("transcript_completed", request_id=request_id, transcript=transcript))
        events.append(voice_event("stage_completed", request_id=request_id, stage="asr", duration_ms=asr_ms))
    except TimeoutError:
        return save_failure(request_id, "asr", "ASR timed out.", total, replay_of, audio_path)

    text_result = await run_text_pipeline(
        transcript,
        request_id=request_id,
        total=total,
        replay_of=replay_of,
        audio_path=audio_path,
        asr_ms=asr_ms,
        history=sanitize_history(metadata.get("history")),
        mime_type=metadata.get("mime_type") if isinstance(metadata.get("mime_type"), str) else None,
        duration_ms=metadata.get("duration_ms") if isinstance(metadata.get("duration_ms"), int) else None,
    )
    return {"events": events + text_result["events"], "metrics": text_result["metrics"]}


async def run_text_pipeline(
    transcript: str,
    request_id: str | None = None,
    total: Timer | None = None,
    replay_of: str | None = None,
    audio_path: str | None = None,
    asr_ms: int | None = None,
    history: list[dict[str, str]] | None = None,
    mime_type: str | None = None,
    duration_ms: int | None = None,
) -> dict[str, object]:
    request_id = request_id or new_request_id()
    total = total or Timer()
    events: list[dict[str, object]] = []

    llm = Timer()
    events.append(voice_event("stage_started", request_id=request_id, stage="llm"))
    try:
        assistant_response = await asyncio.wait_for(
            asyncio.to_thread(generate_response, transcript, history),
            timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "45")),
        )
    except TimeoutError:
        assistant_response = "I had trouble generating a full response from the local model. Please try again with a shorter request."
    for token in assistant_response.split():
        events.append(voice_event("llm_token", request_id=request_id, token=f"{token} "))
    llm_ms = llm.ms()
    events.append(voice_event("llm_completed", request_id=request_id, response=assistant_response))
    events.append(voice_event("stage_completed", request_id=request_id, stage="llm", duration_ms=llm_ms))

    tts = Timer()
    events.append(voice_event("stage_started", request_id=request_id, stage="tts"))
    try:
        audio_url = await asyncio.wait_for(
            asyncio.to_thread(synthesize_speech, assistant_response),
            timeout=float(os.getenv("TTS_TIMEOUT_SECONDS", "30")),
        )
        tts_ms: int | None = tts.ms()
        events.append(voice_event("tts_audio_ready", request_id=request_id, audio_url=audio_url))
        events.append(voice_event("stage_completed", request_id=request_id, stage="tts", duration_ms=tts_ms))
    except TimeoutError:
        tts_ms = None
        events.append(
            voice_event(
                "request_failed",
                request_id=request_id,
                stage="tts",
                message="Speech synthesis timed out. Text response is still available.",
            )
        )

    total_ms = total.ms()
    metrics = build_metrics(asr_ms, llm_ms, tts_ms, total_ms)
    status = "completed" if tts_ms is not None else "degraded"
    conversation_turns = [*llm_history(history), {"role": "user", "content": transcript}, {"role": "assistant", "content": assistant_response}]
    save_request(
        {
            "request_id": request_id,
            "status": status,
            "transcript": transcript,
            "assistant_response": assistant_response,
            "audio_path": audio_path,
            "mime_type": mime_type,
            "duration_ms": duration_ms,
            "replay_of": replay_of,
            "history": history or [],
            "conversation_turns": conversation_turns,
            "created_at": utc_timestamp(),
            **metrics,
        }
    )
    log_event("request_completed", request_id=request_id, status=status, **metrics)
    return {"request_id": request_id, "events": events, "metrics": metrics}


def build_metrics(asr_ms: int | None, llm_ms: int | None, tts_ms: int | None, total_ms: int) -> dict[str, object]:
    stages = {"asr": asr_ms, "llm": llm_ms, "tts": tts_ms}
    measured = {stage: value for stage, value in stages.items() if value is not None}
    slowest = max(measured, key=lambda stage: measured[stage]) if measured else None
    return {
        "asr_ms": asr_ms,
        "llm_total_ms": llm_ms,
        "tts_total_ms": tts_ms,
        "total_ms": total_ms,
        "slowest_stage": slowest,
    }


def save_failure(
    request_id: str, stage: str, message: str, total: Timer, replay_of: str | None, audio_path: str | None
) -> dict[str, object]:
    total_ms = total.ms()
    save_request(
        {
            "request_id": request_id,
            "status": "failed",
            "audio_path": audio_path,
            "replay_of": replay_of,
            "created_at": utc_timestamp(),
            "total_ms": total_ms,
        }
    )
    log_event("request_failed", request_id=request_id, stage=stage, message=message, total_ms=total_ms)
    return {
        "events": [voice_event("request_failed", request_id=request_id, stage=stage, message=message)],
        "metrics": {"total_ms": total_ms, "slowest_stage": stage},
    }


def save_audio(request_id: str, audio: bytes) -> str:
    path = Path("recordings") / f"{request_id}.webm"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio)
    return str(path)


def sanitize_history(history: object | None) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []
    limit = max_history_turns()
    turns: list[dict[str, str]] = []
    for item in history[-limit:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            turns.append({"role": role, "content": content[:2000]})
    return turns


def max_history_turns() -> int:
    try:
        return max(1, int(os.getenv("MAX_HISTORY_TURNS", "8")))
    except ValueError:
        return 8
