export type AdapterProvenance = {
  provider: string;
  fallback: boolean;
  reason?: string | null;
  development?: boolean;
};

export const EVENT_TYPES = [
  "session_ready",
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

export const STAGES = ["audio_validation", "asr", "llm", "tts", "storage", "replay", "admission"] as const;

export type EventType = (typeof EVENT_TYPES)[number];
export type Stage = (typeof STAGES)[number];

export type VoiceEvent = {
  type: EventType;
  timestamp: string;
  request_id?: string;
  stage?: Stage;
  message?: string;
  status?: "completed" | "degraded" | "failed";
  token?: string;
  transcript?: string;
  response?: string;
  audio_url?: string;
  duration_ms?: number;
  metrics?: {
    asr_ms?: number;
    llm_total_ms?: number;
    tts_total_ms?: number;
    total_ms?: number;
    slowest_stage?: string;
    adapters?: Record<string, AdapterProvenance>;
  };
};
