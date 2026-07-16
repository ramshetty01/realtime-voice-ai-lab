"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import type { VoiceEvent } from "../src/lib/events";

const wsUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8000/ws/voice";
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  audioUrl?: string;
};

const newId = () => Math.random().toString(36).slice(2);

export default function Home() {
  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const assistantIdRef = useRef("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [connection, setConnection] = useState("connecting");
  const [voiceStatus, setVoiceStatus] = useState("ready");
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [audioUrl, setAudioUrl] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: newId(),
      role: "assistant",
      text: "Ask me anything, or use the microphone to talk.",
    },
  ]);

  function updateMessage(id: string, patch: Partial<ChatMessage>) {
    setMessages((current) => current.map((message) => (message.id === id ? { ...message, ...patch } : message)));
  }

  function connectVoiceSocket() {
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.addEventListener("open", () => setConnection("connected"));
    socket.addEventListener("close", () => setConnection("disconnected"));
    socket.addEventListener("error", () => setConnection("error"));
    socket.addEventListener("message", (message) => {
      if (typeof message.data !== "string") return;
      const event = JSON.parse(message.data) as VoiceEvent;

      if (event.type === "transcript_completed" && event.transcript) {
        const assistantId = newId();
        assistantIdRef.current = assistantId;
        setMessages((current) => [
          ...current,
          { id: newId(), role: "user", text: event.transcript ?? "" },
          { id: assistantId, role: "assistant", text: "" },
        ]);
      }
      if (event.type === "llm_token" && event.token) {
        const assistantId = assistantIdRef.current;
        setMessages((current) =>
          current.map((item) => (item.id === assistantId ? { ...item, text: item.text + event.token } : item))
        );
      }
      if (event.type === "llm_completed" && event.response) updateMessage(assistantIdRef.current, { text: event.response });
      if (event.type === "tts_audio_ready" && event.audio_url) {
        setAudioUrl(event.audio_url);
        updateMessage(assistantIdRef.current, { audioUrl: event.audio_url });
      }
      if (event.type === "request_completed") setVoiceStatus("ready");
      if (event.type === "request_failed") setVoiceStatus(event.message ?? "failed");
    });

    return socket;
  }

  useEffect(() => {
    const socket = connectVoiceSocket();
    return () => socket.close();
  }, []);

  useEffect(() => {
    if (!audioUrl) return;
    void audioRef.current?.play().catch(() => undefined);
  }, [audioUrl]);

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = prompt.trim();
    if (!message) return;

    const assistantId = newId();
    assistantIdRef.current = assistantId;
    setIsSubmitting(true);
    setPrompt("");
    setAudioUrl("");
    setMessages((current) => [
      ...current,
      { id: newId(), role: "user", text: message },
      { id: assistantId, role: "assistant", text: "Thinking..." },
    ]);

    try {
      const reply = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (!reply.ok) throw new Error("Chat request failed.");
      const payload = await reply.json();
      updateMessage(assistantId, { text: payload.response ?? "", audioUrl: payload.audio_url ?? "" });
      setAudioUrl(payload.audio_url ?? "");
    } catch {
      updateMessage(assistantId, { text: "The chat request failed. Check that the backend is running." });
    } finally {
      setIsSubmitting(false);
    }
  }

  async function startRecording() {
    if (socketRef.current?.readyState !== WebSocket.OPEN) connectVoiceSocket();
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceStatus("microphone unavailable");
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
      setVoiceStatus("recording");
    } catch {
      setVoiceStatus("microphone denied");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setVoiceStatus("sending");
  }

  async function sendAudio() {
    const socket = socketRef.current;
    const audio = new Blob(chunksRef.current, { type: recorderRef.current?.mimeType });
    const duration_ms = Math.round(performance.now() - startedAtRef.current);
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setVoiceStatus("disconnected");
      return;
    }
    if (!audio.size) {
      setVoiceStatus("empty audio");
      return;
    }

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

  const isRecording = voiceStatus === "recording";
  const canRecord = connection === "connected" && !isRecording && voiceStatus !== "sending";

  return (
    <main className="shell">
      <section className="chat-app" aria-label="AI conversation">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Realtime Voice AI</p>
            <h1 className="title">Voice Pipeline Lab</h1>
          </div>
          <span className="voice-state">{isRecording ? "Listening" : voiceStatus}</span>
        </header>

        <div className="message-list" aria-live="polite">
          {messages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="message-label">{message.role === "user" ? "You" : "AI"}</div>
              <div className="message-text">{message.text}</div>
              {message.audioUrl ? (
                <audio className="player" controls src={message.audioUrl}>
                  <track kind="captions" />
                </audio>
              ) : null}
            </article>
          ))}
        </div>

        <form className="composer" onSubmit={submitChat}>
          <button className="mic-button" type="button" disabled={!canRecord && !isRecording} onClick={isRecording ? stopRecording : startRecording}>
            {isRecording ? "Stop" : "Voice"}
          </button>
          <input
            aria-label="Message"
            disabled={isSubmitting}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Message the AI..."
            value={prompt}
          />
          <button type="submit" disabled={isSubmitting || !prompt.trim()}>
            Send
          </button>
        </form>
        {audioUrl ? <audio ref={audioRef} src={audioUrl} /> : null}
      </section>
    </main>
  );
}
