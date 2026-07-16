"use client";

import { useEffect, useState } from "react";

import type { VoiceEvent } from "../src/lib/events";

const wsUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL ?? "ws://127.0.0.1:8000/ws/voice";

export default function Home() {
  const [mode, setMode] = useState<"chat" | "voice">("chat");
  const [transcript, setTranscript] = useState("What is the current latency budget for the voice assistant pipeline?");
  const [response, setResponse] = useState(
    "Total response time is 1.18 seconds. ASR took 310 ms, LLM took 520 ms, TTS took 240 ms, and orchestration overhead used the remaining budget."
  );
  const [audioUrl, setAudioUrl] = useState("");

  useEffect(() => {
    const socket = new WebSocket(wsUrl);

    socket.addEventListener("message", (message) => {
      if (typeof message.data !== "string") return;
      const event = JSON.parse(message.data) as VoiceEvent;
      if (event.type === "transcript_completed" && event.transcript) setTranscript(event.transcript);
      if (event.type === "llm_token" && event.token) {
        setResponse((current) => (current === "No response yet." ? event.token ?? "" : current + event.token));
      }
      if (event.type === "llm_completed" && event.response) setResponse(event.response);
      if (event.type === "tts_audio_ready" && event.audio_url) setAudioUrl(event.audio_url);
    });

    return () => socket.close();
  }, []);
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
              <div className="prompt-bar">
                <span>Ask anything and keep the conversation flowing...</span>
              </div>
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
                <strong>Ready for audio</strong>
              </div>
              {audioUrl ? (
                <audio className="player" controls src={audioUrl}>
                  <track kind="captions" />
                </audio>
              ) : null}
              <div className="prompt-bar">
                <span>Speak, stream, and listen for the assistant response...</span>
              </div>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
