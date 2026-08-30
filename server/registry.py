"""Lightweight index of known sessions, used only for the 'Recente sessies'
resume screen in Server Manager. The authoritative data for each session
always lives in that session's own SQLite database (see database.py) —
this registry is a cache that is rebuilt/refreshed from there and is safe
to delete or regenerate at any time.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from .paths import config_directory, database_path
from .logging_setup import get_logger

logger = get_logger("registry")

REGISTRY_FILE = "sessions.json"


def _registry_path() -> Path:
    return config_directory() / REGISTRY_FILE


def _load() -> dict:
    path = _registry_path()
    if not path.is_file():
        return {"sessions": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.exception("Kon sessieregister niet lezen, begin met een leeg register.")
        return {"sessions": []}


def _save(data: dict) -> None:
    path = _registry_path()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def new_session_id() -> str:
    return str(uuid.uuid4())


def list_sessions() -> list[dict]:
    data = _load()
    sessions = data.get("sessions", [])
    return sorted(sessions, key=lambda item: item.get("updated_at", ""), reverse=True)


def upsert_session(session_id: str, name: str, date: str, location: str,
                    status: str = "active", participant_count: int = 0,
                    updated_at: Optional[str] = None, source_event_id: str = "") -> None:
    data = _load()
    sessions = data.get("sessions", [])
    entry = {
        "id": session_id,
        "name": name,
        "date": date,
        "location": location,
        "status": status,
        "participant_count": participant_count,
        "db_path": str(database_path(session_id)),
        "updated_at": updated_at or "",
        "source_event_id": source_event_id or "",
    }
    sessions = [item for item in sessions if item.get("id") != session_id]
    sessions.append(entry)
    data["sessions"] = sessions
    _save(data)


def remove_session(session_id: str) -> None:
    data = _load()
    data["sessions"] = [item for item in data.get("sessions", []) if item.get("id") != session_id]
    _save(data)
