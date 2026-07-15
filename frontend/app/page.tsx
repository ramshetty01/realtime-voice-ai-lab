"use client";

import { useEffect, useRef, useState } from "react";

import type { VoiceEvent } from "../src/lib/events";

const stages = ["ASR", "LLM", "TTS", "Overhead"];
const wsUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8000/ws/voice";
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type RequestRow = {
  request_id: string;
  status: string;
  transcript?: string;
  total_ms?: number;
  slowest_stage?: string;
  audio_path?: string;
  created_at: string;
};

export default function Home() {
  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const [connection, setConnection] = useState("connecting");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [events, setEvents] = useState<VoiceEvent[]>([]);
  const [audioInfo, setAudioInfo] = useState("No audio sent yet.");
  const [transcript, setTranscript] = useState("No transcript yet.");
  const [response, setResponse] = useState("No response yet.");
  const [audioUrl, setAudioUrl] = useState("");
  const [metrics, setMetrics] = useState<VoiceEvent["metrics"]>({});
  const [requests, setRequests] = useState<RequestRow[]>([]);

  useEffect(() => {
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.addEventListener("open", () => setConnection("connected"));
    socket.addEventListener("close", () => setConnection("disconnected"));
    socket.addEventListener("error", () => {
      setConnection("error");
      setError("WebSocket connection failed.");
    });
    socket.addEventListener("message", (message) => {
      if (typeof message.data !== "string") return;
      const event = JSON.parse(message.data) as VoiceEvent;
      setEvents((current) => [event, ...current].slice(0, 8));
      if (event.type === "transcript_completed" && event.transcript) setTranscript(event.transcript);
      if (event.type === "llm_token" && event.token) {
        setResponse((current) => (current === "No response yet." ? event.token ?? "" : current + event.token));
      }
      if (event.type === "llm_completed" && event.response) setResponse(event.response);
      if (event.type === "tts_audio_ready" && event.audio_url) setAudioUrl(event.audio_url);
      if (event.type === "request_completed") {
        setStatus("completed");
        setMetrics(event.metrics ?? {});
        void loadRequests();
      }
      if (event.type === "request_failed") {
        setStatus("failed");
        setError(event.message ?? "Request failed.");
      }
    });

    void loadRequests();
    return () => socket.close();
  }, []);

  async function loadRequests() {
    try {
      const response = await fetch(`${apiUrl}/requests?limit=8`);
      const payload = (await response.json()) as { requests: RequestRow[] };
      setRequests(payload.requests);
    } catch {
      setRequests([]);
    }
  }

  async function startRecording() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Microphone recording is not supported in this browser.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunksRef.current = [];
      startedAtRef.current = performance.now();
      const recorder = new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      });
      recorder.addEventListener("stop", () => {
        stream.getTracks().forEach((track) => track.stop());
        void sendAudio();
      });
      recorder.start();
      setStatus("recording");
    } catch {
      setError("Microphone permission was denied.");
      setStatus("idle");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setStatus("sending");
  }

  async function sendAudio() {
    const socket = socketRef.current;
    const audio = new Blob(chunksRef.current, { type: recorderRef.current?.mimeType });
    const duration_ms = Math.round(performance.now() - startedAtRef.current);
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setError("WebSocket is not connected.");
      setStatus("failed");
      return;
    }
    if (!audio.size) {
      setError("Recorded audio was empty.");
      setStatus("failed");
      return;
    }

    socket.send(
      JSON.stringify({
        type: "client_audio_ready",
        timestamp: new Date().toISOString(),
        mime_type: audio.type,
        size: audio.size,
        duration_ms,
      })
    );
    socket.send(await audio.arrayBuffer());
    setAudioInfo(`${audio.type || "audio"} · ${audio.size} bytes · ${duration_ms} ms`);
    setTranscript("Transcribing...");
    setResponse("No response yet.");
    setAudioUrl("");
    setMetrics({});
  }

  async function replay(requestId: string, mode: "transcript" | "audio") {
    const endpoint = mode === "audio" ? "replay-audio" : "replay-transcript";
    const replayResponse = await fetch(`${apiUrl}/requests/${requestId}/${endpoint}`, { method: "POST" });
    if (!replayResponse.ok) {
      setError(`${mode} replay is unavailable for this request.`);
      return;
    }
    const payload = await replayResponse.json();
    const replayEvents = (payload.events ?? []) as VoiceEvent[];
    setEvents([...replayEvents].reverse());
    setMetrics(payload.metrics ?? {});
    setTranscript(replayEvents.find((event) => event.type === "transcript_completed")?.transcript ?? transcript);
    setResponse(replayEvents.find((event) => event.type === "llm_completed")?.response ?? response);
    setAudioUrl(replayEvents.find((event) => event.type === "tts_audio_ready")?.audio_url ?? "");
    void loadRequests();
  }

  const isRecording = status === "recording";
  const canStart = connection === "connected" && !isRecording && status !== "sending";
  const totalMs = metrics?.total_ms ?? 0;

  return (
    <main className="shell">
      <header className="topbar hero">
        <div>
          <p className="eyebrow">Local realtime voice pipeline</p>
          <h1 className="title">Realtime Voice AI Reliability Lab</h1>
        </div>
        <div className="topbar-actions">
          <div className={`status status-${connection}`} aria-label="Backend connection status">
            <span className="status-dot" aria-hidden="true" />
            Backend {connection}
          </div>
          <div className={`status status-${status}`} aria-label="Request status">
            {status}
          </div>
        </div>
      </header>

      <section className="workspace" aria-label="Voice assistant workspace">
        <div className="stack">
          <section className="panel" aria-labelledby="controls-title">
            <div className="panel-header">
              <h2 className="panel-title" id="controls-title">
                Voice Request
              </h2>
              <div className="controls">
                <button className="primary record-button" type="button" disabled={!canStart} onClick={startRecording}>
                  Start
                </button>
                <button type="button" disabled={!isRecording} onClick={stopRecording}>
                  Stop
                </button>
              </div>
            </div>
            <div className="panel-body">
              <div className="voice-console">
                <div className="meter" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                  <span />
                  <span />
                </div>
                <div className="console-copy">
                  <span className="label">Audio</span>
                  <strong>{audioInfo}</strong>
                  {error ? <p className="error-text">{error}</p> : null}
                </div>
              </div>
            </div>
          </section>

          <section className="panel" aria-labelledby="transcript-title">
            <div className="panel-header">
              <h2 className="panel-title" id="transcript-title">
                Transcript
              </h2>
            </div>
            <div className="panel-body">
              <div className="text-box transcript-box">{transcript}</div>
            </div>
          </section>

          <section className="panel" aria-labelledby="response-title">
            <div className="panel-header">
              <h2 className="panel-title" id="response-title">
                Assistant Response
              </h2>
            </div>
            <div className="panel-body">
              {audioUrl ? (
                <audio className="player" controls src={audioUrl}>
                  <track kind="captions" />
                </audio>
              ) : null}
              <div className="text-box response-box">{response}</div>
            </div>
          </section>

          <section className="panel" aria-labelledby="events-title">
            <div className="panel-header">
              <h2 className="panel-title" id="events-title">
                Backend Events
              </h2>
            </div>
            <div className="panel-body">
              <div className="text-box event-log">
                {events.length ? (
                  events.map((event, index) => (
                    <div key={`${event.timestamp}-${index}`}>
                      {event.type}
                      {event.request_id ? ` · ${event.request_id}` : ""}
                      {event.stage ? ` · ${event.stage}` : ""}
                      {event.message ? ` · ${event.message}` : ""}
                    </div>
                  ))
                ) : (
                  "No backend events yet."
                )}
              </div>
            </div>
          </section>
        </div>

        <aside className="panel" aria-labelledby="latency-title">
          <div className="panel-header">
            <h2 className="panel-title" id="latency-title">
              Latency
            </h2>
            <strong>{totalMs ? `${totalMs} ms` : "- ms"}</strong>
          </div>
          <div className="panel-body">
            <div className="metrics">
              {stages.map((stage) => {
                const key =
                  stage === "ASR"
                    ? "asr_ms"
                    : stage === "LLM"
                      ? "llm_total_ms"
                      : stage === "TTS"
                        ? "tts_total_ms"
                        : "total_ms";
                const value = metrics?.[key];
                const width = value && metrics?.total_ms ? Math.min(100, (value / metrics.total_ms) * 100) : 0;
                return (
                  <div className="metric-row" key={stage}>
                    <span>{stage}</span>
                    <div className="bar" aria-hidden="true">
                      <span style={{ width: `${width}%` }} />
                    </div>
                    <span>{value ?? "-"} ms</span>
                  </div>
                );
              })}
              {metrics?.total_ms ? (
                <div className="metric-row total-row">
                  <span>Total</span>
                  <div className="bar" aria-hidden="true">
                    <span style={{ width: "100%" }} />
                  </div>
                  <span>{metrics.total_ms} ms</span>
                </div>
              ) : null}
              {metrics?.slowest_stage ? <p className="slowest">Slowest: {metrics.slowest_stage}</p> : null}
            </div>
          </div>
        </aside>
      </section>

      <section className="requests panel" aria-labelledby="requests-title">
        <div className="panel-header">
          <h2 className="panel-title" id="requests-title">
            Recent Requests
          </h2>
          <button type="button" onClick={loadRequests}>
            Refresh
          </button>
        </div>
        <div className="panel-body table-wrap">
          <table>
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Transcript</th>
                <th>Total</th>
                <th>Slowest</th>
                <th>Replay</th>
              </tr>
            </thead>
            <tbody>
              {requests.length ? (
                requests.map((request) => (
                  <tr key={request.request_id}>
                    <td title={request.transcript}>{request.request_id}</td>
                    <td>{request.status}</td>
                    <td className="truncate">{request.transcript ?? "-"}</td>
                    <td>{request.total_ms ?? "-"} ms</td>
                    <td>{request.slowest_stage ?? "-"}</td>
                    <td className="row-actions">
                      <button type="button" onClick={() => replay(request.request_id, "transcript")}>
                        Transcript
                      </button>
                      <button type="button" disabled={!request.audio_path} onClick={() => replay(request.request_id, "audio")}>
                        Audio
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5}>No requests stored yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
