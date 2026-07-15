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
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Realtime Voice AI / Structure</p>
          <h1 className="title">Voice Pipeline Lab</h1>
          <p className="subtitle">Audio input, ASR, LLM, TTS, latency traces, and replay in one live console.</p>
        </div>
        <div className="hero-status">
          <div className={`status status-${connection}`} aria-label="Backend connection status">
            <span className="status-dot" aria-hidden="true" />
            Backend {connection}
          </div>
          <div className={`status status-${status}`} aria-label="Request status">
            {status}
          </div>
        </div>
      </header>

      <section className="console-grid" aria-label="Voice assistant workspace">
        <aside className="recorder-card">
          <div className="recorder-top">
            <span className="label">Session</span>
            <strong>{status}</strong>
          </div>
          <div className="signal-panel" aria-hidden="true">
            <div className="meter">
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>
          </div>
          <div className="pipeline-tree" aria-label="Pipeline structure">
            <div className="tree-row tree-root">voice_lab/</div>
            <div className="tree-row tree-folder">audio/ input_stream.wav</div>
            <div className="tree-row tree-folder">asr/ transcript.json</div>
            <div className="tree-row tree-folder">llm/ response.tokens</div>
            <div className="tree-row tree-folder">tts/ output_audio.mp3</div>
            <div className="tree-row tree-file">traces/ latency.jsonl</div>
          </div>
          <div className="recorder-actions">
            <button className="primary record-button" type="button" disabled={!canStart} onClick={startRecording}>
              Start recording
            </button>
            <button type="button" disabled={!isRecording} onClick={stopRecording}>
              Stop
            </button>
          </div>
          <div className="audio-note">
            <span className="label">Last audio</span>
            <p>{audioInfo}</p>
            {error ? <p className="error-text">{error}</p> : null}
          </div>
        </aside>

        <section className="conversation-card" aria-label="Transcript and assistant response">
          <div className="message-block user-block">
            <div className="message-meta">
              <span>You</span>
              <span>Transcript</span>
            </div>
            <div className="message-body">{transcript}</div>
          </div>

          <div className="message-block assistant-block">
            <div className="message-meta">
              <span>Assistant</span>
              <span>Response</span>
            </div>
            {audioUrl ? (
              <audio className="player" controls src={audioUrl}>
                <track kind="captions" />
              </audio>
            ) : null}
            <div className="message-body">{response}</div>
          </div>
        </section>

        <aside className="diagnostics" aria-label="Diagnostics">
          <section className="panel compact-panel" aria-labelledby="latency-title">
            <div className="panel-header">
              <div>
                <span className="label">Latency</span>
                <h2 className="panel-title" id="latency-title">
                  {totalMs ? `${totalMs} ms` : "- ms"}
                </h2>
              </div>
              {metrics?.slowest_stage ? <span className="pill">Slowest: {metrics.slowest_stage}</span> : null}
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
              </div>
            </div>
          </section>

          <section className="panel compact-panel" aria-labelledby="events-title">
            <div className="panel-header">
              <h2 className="panel-title" id="events-title">
                Event Stream
              </h2>
            </div>
            <div className="panel-body">
              <div className="event-log">
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
        </aside>
      </section>

      <section className="requests" aria-labelledby="requests-title">
        <div className="panel-header">
          <h2 className="panel-title" id="requests-title">
            Trace History
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
                  <td colSpan={6}>No requests stored yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
