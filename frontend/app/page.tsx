"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import type { VoiceEvent } from "../src/lib/events";

const wsUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8000/ws/voice";
const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
const welcomeMessage = "Ask me anything, or use the microphone to talk.";
const socketOpenTimeoutMs = 8000;
const silenceThreshold = Number(process.env.NEXT_PUBLIC_SILENCE_THRESHOLD ?? "0.025");
const silenceDurationMs = Number(process.env.NEXT_PUBLIC_SILENCE_DURATION_MS ?? "1200");

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  audioUrl?: string;
};

const newId = () => globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
const welcomeTurn = (): ChatMessage => ({
  id: newId(),
  role: "assistant",
  text: welcomeMessage,
});

export default function Home() {
  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const assistantIdRef = useRef("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const messageListRef = useRef<HTMLDivElement | null>(null);
  const socketReadyPromiseRef = useRef<Promise<WebSocket> | null>(null);
  const silenceRafRef = useRef(0);
  const audioContextRef = useRef<AudioContext | null>(null);
  const silenceStartedAtRef = useRef(0);
  const [connection, setConnection] = useState("connecting");
  const [voiceStatus, setVoiceStatus] = useState("ready");
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [audioUrl, setAudioUrl] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeTurn()]);

  function updateMessage(id: string, patch: Partial<ChatMessage>) {
    setMessages((current) => current.map((message) => (message.id === id ? { ...message, ...patch } : message)));
  }

  function resetConversation() {
    setMessages([welcomeTurn()]);
    setPrompt("");
    setAudioUrl("");
    setVoiceStatus("ready");
  }

  function conversationHistory() {
    return messages
      .filter((message) => message.text.trim() && message.text !== welcomeMessage)
      .slice(-8)
      .map((message) => ({ role: message.role, content: message.text }));
  }

  function connectVoiceSocket() {
    if (socketRef.current?.readyState === WebSocket.OPEN) return Promise.resolve(socketRef.current);
    if (socketReadyPromiseRef.current) return socketReadyPromiseRef.current;

    setConnection("connecting");
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socketReadyPromiseRef.current = new Promise((resolve, reject) => {
      let settled = false;
      const timeoutId = window.setTimeout(() => {
        settle(() => {
          setConnection("error");
          socket.close();
          reject(new Error("Voice socket timed out before opening."));
        });
      }, socketOpenTimeoutMs);
      const settle = (callback: () => void) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timeoutId);
        socketReadyPromiseRef.current = null;
        callback();
      };

      socket.addEventListener(
        "open",
        () =>
          settle(() => {
            setConnection("connected");
            resolve(socket);
          }),
        { once: true }
      );
      socket.addEventListener(
        "close",
        () =>
          settle(() => {
            setConnection("disconnected");
            reject(new Error("Voice socket closed before opening."));
          }),
        { once: true }
      );
      socket.addEventListener(
        "error",
        () =>
          settle(() => {
            setConnection("error");
            reject(new Error("Voice socket failed to open."));
          }),
        { once: true }
      );
      socket.addEventListener("message", (message) => {
        if (typeof message.data !== "string") return;
        const event = JSON.parse(message.data) as VoiceEvent;

        if (event.type === "transcript_completed" && event.transcript) {
          const assistantId = newId();
          assistantIdRef.current = assistantId;
          setVoiceStatus("thinking");
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
    });

    return socketReadyPromiseRef.current;
  }

  useEffect(() => {
    void connectVoiceSocket().catch(() => undefined);
    return () => {
      socketReadyPromiseRef.current = null;
      socketRef.current?.close();
      stopSilenceMonitor();
    };
  }, []);

  useEffect(() => {
    if (!audioUrl) return;
    setVoiceStatus("speaking");
    void audioRef.current?.play().catch(() => setVoiceStatus("playback failed"));
  }, [audioUrl]);

  useEffect(() => {
    messageListRef.current?.scrollTo({ top: messageListRef.current.scrollHeight });
  }, [messages]);

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = prompt.trim();
    if (!message) return;

    const assistantId = newId();
    const history = conversationHistory();
    assistantIdRef.current = assistantId;
    setIsSubmitting(true);
    setVoiceStatus("thinking");
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
        body: JSON.stringify({ message, history }),
      });
      if (!reply.ok) throw new Error("Chat request failed.");
      const payload = await reply.json();
      updateMessage(assistantId, { text: payload.response ?? "", audioUrl: payload.audio_url ?? "" });
      setAudioUrl(payload.audio_url ?? "");
      if (!payload.audio_url) setVoiceStatus("ready");
    } catch {
      updateMessage(assistantId, { text: "The chat request failed. Check that the backend is running." });
      setVoiceStatus("failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function startRecording() {
    try {
      await connectVoiceSocket();
    } catch {
      setVoiceStatus("disconnected");
      return;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setAudioUrl("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceStatus("microphone unavailable");
      return;
    }
    if (!window.MediaRecorder) {
      setVoiceStatus("recording unsupported");
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
        stopSilenceMonitor();
        stream.getTracks().forEach((track) => track.stop());
        void sendAudio();
      });
      recorder.start();
      setVoiceStatus(startSilenceMonitor(stream) ? "recording" : "manual stop");
    } catch {
      setVoiceStatus("microphone denied");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setVoiceStatus("sending");
  }

  function startSilenceMonitor(stream: MediaStream) {
    const AudioContextCtor =
      window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextCtor) return false;

    const context = new AudioContextCtor();
    const analyser = context.createAnalyser();
    const source = context.createMediaStreamSource(stream);
    const samples = new Uint8Array(analyser.fftSize);
    source.connect(analyser);
    audioContextRef.current = context;
    silenceStartedAtRef.current = 0;

    const tick = () => {
      analyser.getByteTimeDomainData(samples);
      const rms = Math.sqrt(samples.reduce((sum, value) => sum + (value - 128) ** 2, 0) / samples.length) / 128;
      const now = performance.now();
      if (rms > silenceThreshold) silenceStartedAtRef.current = 0;
      else if (now - startedAtRef.current > 800) silenceStartedAtRef.current ||= now;

      if (silenceStartedAtRef.current && now - silenceStartedAtRef.current > silenceDurationMs) {
        if (recorderRef.current?.state === "recording") stopRecording();
        return;
      }
      silenceRafRef.current = requestAnimationFrame(tick);
    };

    silenceRafRef.current = requestAnimationFrame(tick);
    return true;
  }

  function stopSilenceMonitor() {
    cancelAnimationFrame(silenceRafRef.current);
    void audioContextRef.current?.close().catch(() => undefined);
    audioContextRef.current = null;
    silenceStartedAtRef.current = 0;
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
        history: conversationHistory(),
      })
    );
    socket.send(await audio.arrayBuffer());
  }

  const isRecording = voiceStatus === "recording" || voiceStatus === "manual stop";
  const canRecord = connection === "connected" && !isRecording && voiceStatus !== "sending";

  return (
    <main className="shell">
      <section className="chat-app" aria-label="AI conversation">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Realtime Voice AI</p>
            <h1 className="title">Voice Pipeline Lab</h1>
          </div>
          <div className="header-actions">
            <span className="voice-state">{isRecording ? "Listening" : voiceStatus}</span>
            <button type="button" onClick={resetConversation}>
              Reset
            </button>
          </div>
        </header>

        <div className="message-list" aria-live="polite" ref={messageListRef}>
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
          <textarea
            aria-label="Message"
            disabled={isSubmitting}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Message the AI..."
            value={prompt}
          />
          <button type="submit" disabled={isSubmitting || !prompt.trim()}>
            Send
          </button>
        </form>
        {audioUrl ? <audio ref={audioRef} src={audioUrl} onEnded={() => setVoiceStatus("ready")} /> : null}
      </section>
    </main>
  );
}
