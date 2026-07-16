"use client";

import { useEffect, useRef, useState } from "react";

import type { VoiceEvent } from "../src/lib/events";

const wsUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8000/ws/voice";

export default function Home() {
  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const [connection, setConnection] = useState("connecting");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [audioInfo, setAudioInfo] = useState("demo/webm · 184320 bytes · 3200 ms");
  const [transcript, setTranscript] = useState("What is the current latency budget for the voice assistant pipeline?");
  const [response, setResponse] = useState(
    "Total response time is 1.18 seconds. ASR took 310 ms, LLM took 520 ms, TTS took 240 ms, and orchestration overhead used the remaining budget."
  );
  const [audioUrl, setAudioUrl] = useState("");

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
      if (event.type === "transcript_completed" && event.transcript) setTranscript(event.transcript);
      if (event.type === "llm_token" && event.token) {
        setResponse((current) => (current === "No response yet." ? event.token ?? "" : current + event.token));
      }
      if (event.type === "llm_completed" && event.response) setResponse(event.response);
      if (event.type === "tts_audio_ready" && event.audio_url) setAudioUrl(event.audio_url);
      if (event.type === "request_completed") setStatus("completed");
      if (event.type === "request_failed") {
        setStatus("failed");
        setError(event.message ?? "Request failed.");
      }
    });

    return () => socket.close();
  }, []);

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
  }

  const isRecording = status === "recording";
  const canStart = connection === "connected" && !isRecording && status !== "sending";
  return (
    <main className="shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Realtime Voice AI</p>
          <h1 className="title">Voice Pipeline Lab</h1>
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
          <div className="mode-toggle" aria-label="Input mode">
            <span>Chat</span>
            <span className="active-mode">Voice</span>
          </div>
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
          <div className="mode-toggle" aria-label="Conversation mode">
            <span className="active-mode">Chat</span>
            <span>Voice</span>
          </div>
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
          <div className="prompt-bar">
            <span>Ask anything and keep the conversation flowing...</span>
          </div>
        </section>
      </section>
    </main>
  );
}
