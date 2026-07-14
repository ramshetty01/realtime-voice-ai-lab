from typing import Literal, NotRequired, TypedDict

EventType = Literal[
    "client_audio_ready",
    "request_started",
    "stage_started",
    "stage_completed",
    "transcript_completed",
    "llm_token",
    "llm_completed",
    "tts_audio_ready",
    "request_completed",
    "request_failed",
]

Stage = Literal["audio_validation", "asr", "llm", "tts", "storage", "replay"]

EVENT_TYPES: tuple[EventType, ...] = (
    "client_audio_ready",
    "request_started",
    "stage_started",
    "stage_completed",
    "transcript_completed",
    "llm_token",
    "llm_completed",
    "tts_audio_ready",
    "request_completed",
    "request_failed",
)

STAGES: tuple[Stage, ...] = ("audio_validation", "asr", "llm", "tts", "storage", "replay")


class VoiceEvent(TypedDict):
    type: EventType
    timestamp: str
    request_id: NotRequired[str]
    stage: NotRequired[Stage]
    message: NotRequired[str]


def is_known_event_type(value: str) -> bool:
    return value in EVENT_TYPES
