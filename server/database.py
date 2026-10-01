"""SQLite database layer for a single EventHub Server session.

Each event session lives in its own SQLite file (see paths.database_path).
This keeps sessions fully isolated and makes backup/restore trivial
(copy one file). WAL mode + short-lived connections-per-thread keep the
database safe under concurrent requests from multiple clients.
"""
from __future__ import annotations

import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .logging_setup import get_logger

logger = get_logger("database")

SCHEMA = """
CREATE TABLE IF NOT EXISTS event_session (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    event_code TEXT NOT NULL DEFAULT '',
    frozen INTEGER NOT NULL DEFAULT 0,
    freeze_reason TEXT NOT NULL DEFAULT '',
    freeze_by TEXT NOT NULL DEFAULT '',
    freeze_at TEXT,
    checkout_required INTEGER NOT NULL DEFAULT 0,
    checkin_stopped INTEGER NOT NULL DEFAULT 0,
    checkin_stopped_at TEXT,
    checkin_stopped_reason TEXT NOT NULL DEFAULT '',
    source_event_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS participant (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_session(id) ON DELETE CASCADE,
    identifier TEXT,
    voornaam TEXT NOT NULL,
    tussenvoegsel TEXT,
    achternaam TEXT NOT NULL,
    geboortedatum TEXT,
    geboorteplaats TEXT,
    geslacht TEXT,
    opleidingsniveau TEXT,
    profiel TEXT,
    telefoonnummer TEXT,
    email TEXT,
    gast_van TEXT,
    introducee INTEGER NOT NULL DEFAULT 0,
    temporary_walkin INTEGER NOT NULL DEFAULT 0,
    attendance_status TEXT NOT NULL DEFAULT 'not_checked_in',
    checkin_time TEXT,
    checkin_by TEXT,
    checkout_time TEXT,
    checkout_by TEXT,
    stop_marked_absent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_participant_event ON participant(event_id);
CREATE INDEX IF NOT EXISTS idx_participant_name ON participant(achternaam, voornaam);
CREATE INDEX IF NOT EXISTS idx_participant_status ON participant(attendance_status);

CREATE TABLE IF NOT EXISTS client_session (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_session(id),
    client_name TEXT NOT NULL,
    client_type TEXT,
    ip_address TEXT,
    role TEXT NOT NULL DEFAULT 'checkin',
    connected_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    checkin_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_client_event ON client_session(event_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    participant_id TEXT,
    client_id TEXT,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_id, timestamp);

CREATE TABLE IF NOT EXISTS emergency_incident (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES event_session(id) ON DELETE CASCADE,
    active INTEGER NOT NULL DEFAULT 1,
    instruction TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    started_by TEXT NOT NULL DEFAULT '',
    ended_at TEXT,
    ended_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_emergency_event ON emergency_incident(event_id, started_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_emergency_one_active ON emergency_incident(event_id) WHERE active=1;

CREATE TABLE IF NOT EXISTS emergency_status (
    incident_id TEXT NOT NULL REFERENCES emergency_incident(id) ON DELETE CASCADE,
    participant_id TEXT NOT NULL REFERENCES participant(id) ON DELETE CASCADE,
    safe INTEGER NOT NULL DEFAULT 0,
    assembly_point TEXT NOT NULL DEFAULT '',
    team TEXT NOT NULL DEFAULT '',
    marked_at TEXT,
    marked_by TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (incident_id, participant_id)
);
"""

_local = threading.local()
_write_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _run_migrations(connection: sqlite3.Connection) -> None:
    """Add columns that didn't exist in earlier EventHub Server versions,
    so databases created before a feature was added keep working."""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(event_session)")}
    if "event_code" not in columns:
        connection.execute("ALTER TABLE event_session ADD COLUMN event_code TEXT NOT NULL DEFAULT ''")
        logger.info("Migratie: kolom event_code toegevoegd aan event_session.")
    for name, definition in {
        "frozen": "INTEGER NOT NULL DEFAULT 0",
        "freeze_reason": "TEXT NOT NULL DEFAULT ''",
        "freeze_by": "TEXT NOT NULL DEFAULT ''",
        "freeze_at": "TEXT",
        "checkout_required": "INTEGER NOT NULL DEFAULT 0",
        "checkin_stopped": "INTEGER NOT NULL DEFAULT 0",
        "checkin_stopped_at": "TEXT",
        "checkin_stopped_reason": "TEXT NOT NULL DEFAULT ''",
        "source_event_id": "TEXT NOT NULL DEFAULT ''",
    }.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE event_session ADD COLUMN {name} {definition}")
            logger.info("Migratie: kolom %s toegevoegd aan event_session.", name)
    audit_columns = {row["name"] for row in connection.execute("PRAGMA table_info(audit_log)")}
    if "operation_id" not in audit_columns:
        connection.execute("ALTER TABLE audit_log ADD COLUMN operation_id TEXT")
    participant_columns = {row["name"] for row in connection.execute("PRAGMA table_info(participant)")}
    if "temporary_walkin" not in participant_columns:
        connection.execute("ALTER TABLE participant ADD COLUMN temporary_walkin INTEGER NOT NULL DEFAULT 0")
    if "stop_marked_absent" not in participant_columns:
        connection.execute("ALTER TABLE participant ADD COLUMN stop_marked_absent INTEGER NOT NULL DEFAULT 0")
        # 2.11.0 could already have stopped a session before this migration.
        # In that version 'absent' was only assigned by the stop action, so it
        # is safe to mark those rows as reversible here.
        connection.execute(
            "UPDATE participant SET stop_marked_absent=1 WHERE attendance_status='absent' "
            "AND event_id IN (SELECT id FROM event_session WHERE checkin_stopped=1)"
        )
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_operation ON audit_log(operation_id) WHERE operation_id IS NOT NULL")
    connection.commit()


def connect(db_path: Path) -> sqlite3.Connection:
    """Return a thread-local connection for this db_path, creating schema if needed."""
    key = str(db_path)
    cache = getattr(_local, "connections", None)
    if cache is None:
        cache = {}
        _local.connections = cache
    connection = cache.get(key)
    if connection is not None:
        return connection

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL;")
    connection.execute("PRAGMA foreign_keys=ON;")
    connection.execute("PRAGMA busy_timeout=10000;")
    with _write_lock:
        connection.executescript(SCHEMA)
        connection.commit()
        _run_migrations(connection)
    cache[key] = connection
    logger.info("Database verbonden: %s", db_path)
    return connection


def transaction(connection: sqlite3.Connection):
    """Context manager performing a serialized write transaction.

    SQLite allows only one writer at a time; the process-wide lock plus
    BEGIN IMMEDIATE avoids 'database is locked' errors and the classic
    lost-update problem when two clients act on the same row at once.
    """
    return _Transaction(connection)


class _Transaction:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def __enter__(self):
        _write_lock.acquire()
        self.connection.execute("BEGIN IMMEDIATE;")
        return self.connection

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            _write_lock.release()
        return False


def backup_database(db_path: Path) -> Path:
    """Create a timestamped snapshot copy of the database file (safe, online backup)."""
    from .paths import backups_directory

    connection = connect(db_path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backups_directory() / f"{db_path.parent.name}-{stamp}.db"
    with _write_lock:
        backup_connection = sqlite3.connect(str(backup_path))
        try:
            connection.backup(backup_connection)
        finally:
            backup_connection.close()
    logger.info("Back-up gemaakt: %s", backup_path)
    return backup_path


def close_all() -> None:
    cache = getattr(_local, "connections", None)
    if not cache:
        return
    for connection in cache.values():
        try:
            connection.commit()
            connection.close()
        except sqlite3.Error:
            logger.exception("Fout bij netjes sluiten van databaseverbinding")
    cache.clear()


def close_database(db_path: Path) -> None:
    """Close this thread's cached connection for one session database."""
    cache = getattr(_local, "connections", None)
    if not cache:
        return
    connection = cache.pop(str(db_path), None)
    if connection is not None:
        try:
            connection.commit()
            connection.close()
        except sqlite3.Error:
            logger.exception("Fout bij sluiten van sessiedatabase %s", db_path)
