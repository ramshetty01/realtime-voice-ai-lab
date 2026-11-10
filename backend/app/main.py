import asyncio
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.events import new_request_id, utc_timestamp, voice_event
from app.execution import PipelineBusy, runner
from app.logging import log_event
from app.pipeline import AdapterUnavailable, llm_history
from app.pipeline import generate_response_result as generate_response
from app.pipeline import synthesize_speech_result as synthesize_speech
from app.pipeline import transcribe_audio_result as transcribe_audio
from app.security import allowed_origins, authorized, origin_allowed
from app.storage import get_request, recent_requests, save_request
from app.timing import Timer


def configured_cors_origins() -> list[str]:
    return allowed_origins()


def positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero.")
    return value


def positive_float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a number.") from exc
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(f"{name} must be finite and greater than zero.")
    return value


app = FastAPI(title="Realtime Voice AI Reliability Lab")
app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def protect_requests(request: Request, call_next):
    if request.url.path not in {"/health", "/ready"}:
        if not origin_allowed(request.headers.get("origin")):
            return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
        if request.method != "OPTIONS":
            header = request.headers.get("authorization", "")
            token = header[7:] if header.startswith("Bearer ") else ""
            if not authorized(request.client.host if request.client else None, token, request.url.hostname):
                return JSONResponse({"detail": "A valid access token or loopback-only mode is required."}, status_code=401)
    if request.method == "POST":
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 262144:
                return JSONResponse({"detail": "Request body is too large."}, status_code=413)
        request._body = bytes(body)
    return await call_next(request)


@app.exception_handler(PipelineBusy)
async def busy_response(request: Request, exc: PipelineBusy):
    return JSONResponse({"detail": "Voice adapter capacity is busy. Retry later."}, status_code=429, headers={"Retry-After": "5"})


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ConversationTurn] = Field(default_factory=list, max_length=32)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "realtime-voice-ai-lab",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get("/ready")
def ready() -> dict[str, object]:
    return {
        "ready": True,
        "max_workers": runner.capacity,
        "strict_adapters": os.getenv("VOICE_STRICT_ADAPTERS", "false").lower() == "true",
        "cors_origins": len(configured_cors_origins()),
        "max_audio_bytes": positive_int_env("MAX_AUDIO_BYTES", 10 * 1024 * 1024),
        "timeouts": {
            "asr": positive_float_env("ASR_TIMEOUT_SECONDS", 30),
            "llm": positive_float_env("LLM_TIMEOUT_SECONDS", 45),
            "tts": positive_float_env("TTS_TIMEOUT_SECONDS", 30),
        },
    }


@app.get("/requests")
def list_requests(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, object]:
    return {"requests": recent_requests(limit=limit)}


@app.get("/requests/{request_id}")
def request_detail(request_id: str) -> dict[str, object]:
    trace = get_request(request_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Request not found")
    return trace


@app.get("/requests/{request_id}/export")
def export_request(request_id: str) -> JSONResponse:
    trace = request_detail(request_id)
    return JSONResponse(trace, headers={"content-disposition": f'attachment; filename="{request_id}.json"'})


@app.post("/chat")
async def chat(payload: ChatRequest) -> dict[str, object]:
    result = await run_text_pipeline(payload.message, history=[turn.model_dump() for turn in payload.history])
    response = next((event.get("response") for event in result["events"] if event["type"] == "llm_completed"), "")
    audio_url = next((event.get("audio_url") for event in result["events"] if event["type"] == "tts_audio_ready"), "")
    return {
        "request_id": result["request_id"],
        "transcript": payload.message,
        "response": response,
        "status": result["status"],
        "audio_url": audio_url,
        "events": result["events"],
        "metrics": result["metrics"],
    }


@app.post("/requests/{request_id}/replay-transcript")
async def replay_transcript(request_id: str) -> dict[str, object]:
    trace = get_request(request_id)
    if not trace or not trace.get("transcript"):
        raise HTTPException(status_code=404, detail="Request transcript not found")
    source_turns = trace.get("conversation_turns") if isinstance(trace.get("conversation_turns"), list) else []
    history = llm_history(source_turns[:-2])
    result = await run_text_pipeline(str(trace["transcript"]), history=history, replay_of=request_id)
    result["source_conversation_turns"] = source_turns
    return result


@app.post("/requests/{request_id}/replay-audio")
async def replay_audio(request_id: str) -> dict[str, object]:
    trace = get_request(request_id)
    audio_path = trace.get("audio_path") if trace else None
    if not audio_path:
        raise HTTPException(status_code=404, detail="Request audio not found")
    path = safe_recording_path(str(audio_path))
    if not path.exists():
        raise HTTPException(status_code=404, detail="Request audio not found")
    return await run_voice_pipeline(path.read_bytes(), {}, replay_of=request_id)


@app.websocket("/ws/voice")
async def voice_socket(websocket: WebSocket) -> None:
    if not origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        frame = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        if len(frame) > 4096:
            await websocket.close(code=1008)
            return
        credentials = json.loads(frame)
        token = credentials.get("token", "") if isinstance(credentials, dict) else None
        if not isinstance(credentials, dict) or credentials.get("type") != "authenticate" or not isinstance(token, str) or not authorized(websocket.client.host if websocket.client else None, token, websocket.url.hostname):
            await websocket.close(code=1008)
            return
        await websocket.send_json(voice_event("session_ready"))
        metadata: dict[str, object] = {}
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            if message.get("text") is not None:
                metadata = await handle_client_event(websocket, new_request_id(), message["text"])
            elif message.get("bytes") is not None:
                request_id = new_request_id()
                total = Timer()
                log_event("request_started", request_id=request_id)
                await websocket.send_json(voice_event("request_started", request_id=request_id))
                await handle_audio(websocket, request_id, message["bytes"], metadata, total)
                metadata = {}
    except WebSocketDisconnect:
        return
    except (TimeoutError, ValueError, KeyError):
        await websocket.close(code=1008)


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
        if len(text) > 32768:
            raise ValueError("Metadata exceeds limit")
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Metadata must be an object")
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
        await websocket.send_json(
            voice_event(
                "request_failed",
                request_id=request_id,
                stage="audio_validation",
                message="Unknown websocket event type.",
            )
        )
        return {}

    history = sanitize_history(payload.get("history"))
    return {
        "mime_type": payload.get("mime_type"),
        "size": positive_metadata_int(payload.get("size")),
        "duration_ms": positive_metadata_int(payload.get("duration_ms")),
        "history": history,
    }


async def handle_audio(
    websocket: WebSocket, request_id: str, audio: bytes, metadata: dict[str, object], total: Timer
) -> None:
    if not audio:
        result = save_failure(request_id, "audio_validation", "Recorded audio was empty.", total, None, None)
        event = result["events"][0]
        log_event("request_failed", request_id=request_id, stage="audio_validation", message=event["message"])
        await websocket.send_json(event)
        return

    max_audio_bytes = positive_int_env("MAX_AUDIO_BYTES", 10 * 1024 * 1024)
    if len(audio) > max_audio_bytes:
        result = save_failure(request_id, "audio_validation", "Recorded audio is too large for this demo.", total, None, None)
        event = result["events"][0] | {"audio_size": len(audio), "max_audio_bytes": max_audio_bytes}
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

    try:
        result = await run_voice_pipeline(audio, metadata, request_id=request_id, total=total)
    except PipelineBusy:
        result = save_failure(request_id, "admission", "Voice adapter capacity is busy. Retry later.", total, None, None)
    for event in result["events"]:
        await websocket.send_json(event)
    if result["status"] == "failed":
        return
    await websocket.send_json(
        voice_event(
            "request_completed",
            request_id=request_id,
            message="Voice pipeline finished.",
            status=result["status"],
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
    audio_path = (
        save_audio(request_id, audio, metadata.get("mime_type") if isinstance(metadata.get("mime_type"), str) else "")
        if os.getenv("AUDIO_PERSISTENCE_ENABLED") == "true"
        else None
    )
    events: list[dict[str, object]] = []

    asr = Timer()
    events.append(voice_event("stage_started", request_id=request_id, stage="asr"))
    try:
        transcription = await runner.run(transcribe_audio, audio, timeout=positive_float_env("ASR_TIMEOUT_SECONDS", 30))
        transcript = transcription.value
        asr_ms = asr.ms()
        events.append(voice_event("transcript_completed", request_id=request_id, transcript=transcript))
        events.append(voice_event("stage_completed", request_id=request_id, stage="asr", duration_ms=asr_ms))
    except PipelineBusy:
        raise
    except AdapterUnavailable as exc:
        return save_failure(request_id, "asr", str(exc), total, replay_of, audio_path, adapters={"asr": exc.result.provenance()})
    except TimeoutError:
        return save_failure(request_id, "asr", "ASR timed out.", total, replay_of, audio_path)
    except Exception:
        return save_failure(request_id, "asr", "ASR failed. Check the configured adapter.", total, replay_of, audio_path)

    text_result = await run_text_pipeline(
        transcript,
        request_id=request_id,
        total=total,
        replay_of=replay_of,
        audio_path=audio_path,
        asr_ms=asr_ms,
        adapters={"asr": transcription.provenance()},
        history=sanitize_history(metadata.get("history")),
        mime_type=metadata.get("mime_type") if isinstance(metadata.get("mime_type"), str) else None,
        duration_ms=metadata.get("duration_ms") if isinstance(metadata.get("duration_ms"), int) else None,
    )
    return {**text_result, "events": events + text_result["events"]}


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
    adapters: dict[str, object] | None = None,
) -> dict[str, object]:
    request_id = request_id or new_request_id()
    total = total or Timer()
    events: list[dict[str, object]] = []

    adapters = dict(adapters or {})
    llm_degraded = False
    llm = Timer()
    events.append(voice_event("stage_started", request_id=request_id, stage="llm"))
    try:
        generated = await runner.run(generate_response, transcript, history, timeout=positive_float_env("LLM_TIMEOUT_SECONDS", 45))
        assistant_response = generated.value
        adapters["llm"] = generated.provenance()
    except PipelineBusy:
        if adapters:
            return save_failure(request_id, "admission", "Voice adapter capacity is busy. Retry later.", total, replay_of, audio_path, adapters=adapters)
        raise
    except AdapterUnavailable as exc:
        adapters["llm"] = exc.result.provenance()
        return save_failure(request_id, "llm", str(exc), total, replay_of, audio_path, adapters=adapters)
    except TimeoutError:
        adapters["llm"] = {"provider": "unavailable", "fallback": True, "development": True, "reason": "Response generation timed out."}
        if os.getenv("VOICE_STRICT_ADAPTERS", "false").lower() == "true":
            return save_failure(request_id, "llm", "Response generation timed out; strict mode withheld development output.", total, replay_of, audio_path, adapters=adapters)
        llm_degraded = True
        assistant_response = "I had trouble generating a full response from the local model. Please try again with a shorter request."
    except Exception:
        return save_failure(request_id, "llm", "Response generation failed. Check the configured adapter.", total, replay_of, audio_path, adapters=adapters)
    for token in assistant_response.split():
        events.append(voice_event("llm_token", request_id=request_id, token=f"{token} "))
    llm_ms = llm.ms()
    events.append(voice_event("llm_completed", request_id=request_id, response=assistant_response))
    events.append(voice_event("stage_completed", request_id=request_id, stage="llm", duration_ms=llm_ms))

    tts = Timer()
    events.append(voice_event("stage_started", request_id=request_id, stage="tts"))
    try:
        synthesized = await runner.run(synthesize_speech, assistant_response, timeout=positive_float_env("TTS_TIMEOUT_SECONDS", 30))
        audio_url = synthesized.value
        adapters["tts"] = synthesized.provenance()
        tts_ms: int | None = tts.ms()
        events.append(voice_event("tts_audio_ready", request_id=request_id, audio_url=audio_url))
        events.append(voice_event("stage_completed", request_id=request_id, stage="tts", duration_ms=tts_ms))
    except Exception as exc:
        adapters["tts"] = exc.result.provenance() if isinstance(exc, AdapterUnavailable) else {"provider": "unavailable", "fallback": True, "reason": "Speech generation was unavailable, busy, failed or timed out."}
        tts_ms = None
        events.append(
            voice_event(
                "request_failed",
                request_id=request_id,
                stage="tts",
                message="Speech synthesis failed or timed out. Text response is still available.",
            )
        )

    total_ms = total.ms()
    metrics = build_metrics(asr_ms, llm_ms, tts_ms, total_ms)
    metrics["adapters"] = adapters
    has_fallback = any(isinstance(item, dict) and item.get("fallback") for item in adapters.values())
    status = "completed" if tts_ms is not None and not llm_degraded and not has_fallback else "degraded"
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
    return {"request_id": request_id, "status": status, "events": events, "metrics": metrics}


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
    request_id: str, stage: str, message: str, total: Timer, replay_of: str | None, audio_path: str | None, adapters: dict[str, object] | None = None
) -> dict[str, object]:
    total_ms = total.ms()
    save_request(
        {
            "request_id": request_id,
            "status": "failed",
            "audio_path": audio_path,
            "replay_of": replay_of,
            "failure_stage": stage,
            "adapters": adapters or {},
            "error_message": message,
            "created_at": utc_timestamp(),
            "total_ms": total_ms,
        }
    )
    log_event("request_failed", request_id=request_id, stage=stage, message=message, total_ms=total_ms)
    return {
        "request_id": request_id,
        "status": "failed",
        "events": [voice_event("request_failed", request_id=request_id, stage=stage, message=message)],
        "metrics": {"total_ms": total_ms, "slowest_stage": stage, "adapters": adapters or {}},
    }


def save_audio(request_id: str, audio: bytes, mime_type: str = "") -> str:
    extension = { "audio/mp4": ".m4a", "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/webm": ".webm" }.get(
        mime_type.split(";", 1)[0],
        ".webm",
    )
    path = Path("recordings") / f"{request_id}{extension}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio)
    return str(path)


def safe_recording_path(audio_path: str) -> Path:
    recordings = Path("recordings").resolve()
    path = Path(audio_path)
    resolved = (path if path.is_absolute() else Path.cwd() / path).resolve()
    if recordings not in (resolved, *resolved.parents):
        raise HTTPException(status_code=400, detail="Request audio path is outside recordings")
    return resolved


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


def positive_metadata_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def max_history_turns() -> int:
    try:
        return max(1, int(os.getenv("MAX_HISTORY_TURNS", "8")))
    except ValueError:
        return 8
