const stages = ["ASR", "LLM", "TTS", "Overhead"];

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <h1 className="title">Realtime Voice AI Reliability Lab</h1>
        <div className="status" aria-label="Backend connection status">
          <span className="status-dot" aria-hidden="true" />
          Backend not connected
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
                <button className="primary" type="button" disabled>
                  Start
                </button>
                <button type="button" disabled>
                  Stop
                </button>
              </div>
            </div>
            <div className="panel-body">
              <div className="text-box">Recording controls connect in the microphone capture step.</div>
            </div>
          </section>

          <section className="panel" aria-labelledby="transcript-title">
            <div className="panel-header">
              <h2 className="panel-title" id="transcript-title">
                Transcript
              </h2>
            </div>
            <div className="panel-body">
              <div className="text-box">No transcript yet.</div>
            </div>
          </section>

          <section className="panel" aria-labelledby="response-title">
            <div className="panel-header">
              <h2 className="panel-title" id="response-title">
                Assistant Response
              </h2>
            </div>
            <div className="panel-body">
              <div className="text-box">No response yet.</div>
            </div>
          </section>
        </div>

        <aside className="panel" aria-labelledby="latency-title">
          <div className="panel-header">
            <h2 className="panel-title" id="latency-title">
              Latency
            </h2>
          </div>
          <div className="panel-body">
            <div className="metrics">
              {stages.map((stage) => (
                <div className="metric-row" key={stage}>
                  <span>{stage}</span>
                  <div className="bar" aria-hidden="true">
                    <span />
                  </div>
                  <span>- ms</span>
                </div>
              ))}
            </div>
          </div>
        </aside>
      </section>
    </main>
  );
}
