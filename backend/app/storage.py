import json
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
          audio_path text,
          mime_type text,
          duration_ms integer,
          replay_of text,
          history text,
          conversation_turns text,
          asr_ms integer,
          llm_total_ms integer,
          tts_total_ms integer,
          total_ms integer,
          slowest_stage text,
          created_at text not null
        )
        """
    )
    for column, definition in {
        "audio_path": "text",
        "mime_type": "text",
        "duration_ms": "integer",
        "replay_of": "text",
        "history": "text",
        "conversation_turns": "text",
        "slowest_stage": "text",
    }.items():
        try:
            db.execute(f"alter table requests add column {column} {definition}")
        except sqlite3.OperationalError:
            pass
    return db


def save_request(trace: dict[str, Any], path: Path = DB_PATH) -> None:
    with connect(path) as db:
        db.execute(
            """
            insert or replace into requests (
              request_id, status, transcript, assistant_response, audio_path, mime_type, duration_ms, replay_of, history,
              conversation_turns, asr_ms, llm_total_ms, tts_total_ms, total_ms, slowest_stage, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace["request_id"],
                trace["status"],
                trace.get("transcript"),
                trace.get("assistant_response"),
                trace.get("audio_path"),
                trace.get("mime_type"),
                trace.get("duration_ms"),
                trace.get("replay_of"),
                json.dumps(trace.get("history") or []),
                json.dumps(trace.get("conversation_turns") or []),
                trace.get("asr_ms"),
                trace.get("llm_total_ms"),
                trace.get("tts_total_ms"),
                trace.get("total_ms"),
                trace.get("slowest_stage"),
                trace["created_at"],
            ),
        )


def recent_requests(limit: int = 20, path: Path = DB_PATH) -> list[dict[str, Any]]:
    with connect(path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            select request_id, status, transcript, total_ms, slowest_stage, audio_path, created_at
            from requests
            order by created_at desc
            limit ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_request(request_id: str, path: Path = DB_PATH) -> dict[str, Any] | None:
    with connect(path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("select * from requests where request_id = ?", (request_id,)).fetchone()
    if not row:
        return None
    trace = dict(row)
    for key in ("history", "conversation_turns"):
        value = trace.get(key)
        if isinstance(value, str) and value:
            try:
                trace[key] = json.loads(value)
            except json.JSONDecodeError:
                trace[key] = []
    return trace
