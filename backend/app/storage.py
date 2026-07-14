import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("data/voice_lab.db")


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute(
        """
        create table if not exists requests (
          request_id text primary key,
          status text not null,
          transcript text,
          assistant_response text,
          asr_ms integer,
          llm_total_ms integer,
          tts_total_ms integer,
          total_ms integer,
          created_at text not null
        )
        """
    )
    return db


def save_request(trace: dict[str, Any], path: Path = DB_PATH) -> None:
    with connect(path) as db:
        db.execute(
            """
            insert or replace into requests (
              request_id, status, transcript, assistant_response,
              asr_ms, llm_total_ms, tts_total_ms, total_ms, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace["request_id"],
                trace["status"],
                trace.get("transcript"),
                trace.get("assistant_response"),
                trace.get("asr_ms"),
                trace.get("llm_total_ms"),
                trace.get("tts_total_ms"),
                trace.get("total_ms"),
                trace["created_at"],
            ),
        )
