"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import type { VoiceEvent } from "../src/lib/events";

const wsUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8000/ws/voice";
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const [mode, setMode] = useState<"chat" | "voice">("chat");
  const [connection, setConnection] = useState("connecting");
  const [voiceStatus, setVoiceStatus] = useState("Ready for audio");
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [transcript, setTranscript] = useState("What is the current latency budget for the voice assistant pipeline?");
  const [response, setResponse] = useState(
    "Total response time is 1.18 seconds. ASR took 310 ms, LLM took 520 ms, TTS took 240 ms, and orchestration overhead used the remaining budget."
  );
  const [audioUrl, setAudioUrl] = useState("");

  function connectVoiceSocket() {
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.addEventListener("open", () => setConnection("connected"));
    socket.addEventListener("close", () => setConnection("disconnected"));
    socket.addEventListener("error", () => setConnection("error"));
    socket.addEventListener("message", (message) => {
      if (typeof message.data !== "string") return;
      const event = JSON.parse(message.data) as VoiceEvent;
      if (event.type === "transcript_completed" && event.transcript) setTranscript(event.transcript);
      if (event.type === "llm_token" && event.token) {
        setResponse((current) => (current === "No response yet." ? event.token ?? "" : current + event.token));
      }
      if (event.type === "llm_completed" && event.response) setResponse(event.response);
      if (event.type === "tts_audio_ready" && event.audio_url) setAudioUrl(event.audio_url);
      if (event.type === "request_completed") setVoiceStatus("Response ready");
      if (event.type === "request_failed") setVoiceStatus(event.message ?? "Voice request failed");
    });

    return socket;
  }

  useEffect(() => {
    const socket = connectVoiceSocket();
    return () => socket.close();
  }, []);

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = prompt.trim();
    if (!message) return;

    setIsSubmitting(true);
    setTranscript(message);
    setResponse("Thinking...");
    setAudioUrl("");
    try {
      const reply = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!reply.ok) throw new Error("Chat request failed.");
      const payload = await reply.json();
      setResponse(payload.response ?? "");
      setAudioUrl(payload.audio_url ?? "");
      setPrompt("");
    } catch {
      setResponse("The chat request failed. Check that the backend is running.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function startRecording() {
    if (socketRef.current?.readyState !== WebSocket.OPEN) connectVoiceSocket();
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceStatus("Microphone is unavailable");
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
      setVoiceStatus("Recording");
    } catch {
      setVoiceStatus("Microphone permission denied");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setVoiceStatus("Sending audio");
  }

  async function sendAudio() {
    const socket = socketRef.current;
    const audio = new Blob(chunksRef.current, { type: recorderRef.current?.mimeType });
    const duration_ms = Math.round(performance.now() - startedAtRef.current);
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setVoiceStatus("WebSocket disconnected");
      return;
    }
    if (!audio.size) {
      setVoiceStatus("Recorded audio was empty");
      return;
    }

    setTranscript("Transcribing...");
    setResponse("Thinking...");
    setAudioUrl("");
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
  }

  const isRecording = voiceStatus === "Recording";
  const canRecord = !isRecording && voiceStatus !== "Sending audio";

  return (
    <main className="shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Realtime Voice AI</p>
          <h1 className="title">Voice Pipeline Lab</h1>
        </div>
      </header>

      <section className="console-grid" aria-label="Voice assistant workspace">
        <section className="conversation-card" aria-label="Transcript and assistant response">
          <div className="mode-toggle" aria-label="Conversation mode">
            <button className={mode === "chat" ? "active-mode" : ""} type="button" onClick={() => setMode("chat")}>
              Chat
            </button>
            <button className={mode === "voice" ? "active-mode" : ""} type="button" onClick={() => setMode("voice")}>
              Voice
            </button>
          </div>

          {mode === "chat" ? (
            <>
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
              <form className="prompt-bar" onSubmit={submitChat}>
                <input
                  aria-label="Chat prompt"
                  disabled={isSubmitting}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="Ask anything and keep the conversation flowing..."
                  value={prompt}
                />
                <button type="submit" disabled={isSubmitting || !prompt.trim()}>
                  Send
                </button>
              </form>
            </>
          ) : (
            <div className="voice-panel" aria-label="Voice workspace">
              <div className="voice-wave" aria-hidden="true">
                <span />
                <span />
                <span />
                <span />
                <span />
                <span />
                <span />
              </div>
              <div className="voice-copy">
                <span>Voice mode</span>
                <strong>{voiceStatus}</strong>
              </div>
              {audioUrl ? (
                <audio className="player" controls src={audioUrl}>
                  <track kind="captions" />
                </audio>
              ) : null}
              <div className="voice-actions">
                <button type="button" disabled={!canRecord} onClick={startRecording}>
                  Record
                </button>
                <button type="button" disabled={!isRecording} onClick={stopRecording}>
                  Send
                </button>
              </div>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
