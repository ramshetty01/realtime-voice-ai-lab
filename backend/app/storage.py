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
          replay_of text,
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
        "replay_of": "text",
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
              request_id, status, transcript, assistant_response, audio_path, replay_of,
              asr_ms, llm_total_ms, tts_total_ms, total_ms, slowest_stage, created_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace["request_id"],
                trace["status"],
                trace.get("transcript"),
                trace.get("assistant_response"),
                trace.get("audio_path"),
                trace.get("replay_of"),
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
    return dict(row) if row else None
