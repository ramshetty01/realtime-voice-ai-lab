export const EVENT_TYPES = [
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
] as const;

export const STAGES = ["audio_validation", "asr", "llm", "tts", "storage", "replay"] as const;

export type EventType = (typeof EVENT_TYPES)[number];
export type Stage = (typeof STAGES)[number];

export type VoiceEvent = {
  type: EventType;
  timestamp: string;
  request_id?: string;
  stage?: Stage;
  message?: string;
};
