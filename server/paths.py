"""Application data locations for EventHub Server.

Kept dependency-free (no PySide6) so the server/API layer can in
principle run headless (service mode) without the desktop GUI stack.
Mirrors the conventions already used by the EventHub Desktop app
(``bezoekerslijst_app.py``): local app-data root, with subfolders per
concern (config, events, database, logs, backups).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DATA_FOLDER_NAME = "EventHub Server"


def application_data_root() -> Path:
    """Return (and create) the per-user application data root.

    Windows: %LOCALAPPDATA%\\EventHub Server
    macOS:   ~/Library/Application Support/EventHub Server
    Linux:   $XDG_DATA_HOME/EventHub Server or ~/.local/share/EventHub Server
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) / APP_DATA_FOLDER_NAME if base else Path.home() / APP_DATA_FOLDER_NAME
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / APP_DATA_FOLDER_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = Path(base) / APP_DATA_FOLDER_NAME if base else Path.home() / ".local" / "share" / APP_DATA_FOLDER_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sub(name: str) -> Path:
    path = application_data_root() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_directory() -> Path:
    return _sub("config")


def events_directory() -> Path:
    return _sub("events")


def database_directory() -> Path:
    return _sub("database")


def logs_directory() -> Path:
    return _sub("logs")


def backups_directory() -> Path:
    return _sub("backups")


def exports_directory() -> Path:
    return _sub("exports")


def database_path(session_id: str) -> Path:
    """Each event session gets its own SQLite file: events/<id>/event.db."""
    session_dir = events_directory() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / "event.db"


def program_directory() -> Path:
    """Directory containing the running executable/script (for bundled assets)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
