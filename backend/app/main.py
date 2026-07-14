from datetime import UTC, datetime

from fastapi import FastAPI

app = FastAPI(title="Realtime Voice AI Reliability Lab")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "realtime-voice-ai-lab",
        "timestamp": datetime.now(UTC).isoformat(),
    }
