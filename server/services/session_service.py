from __future__ import annotations

import secrets
import sqlite3
import shutil
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import registry
from ..database import close_database, connect, now_iso, transaction
from ..events_hub import hub
from ..paths import database_path, events_directory
from ..logging_setup import get_logger

logger = get_logger("session_service")


class SessionValidationError(ValueError):
    pass


@dataclass
class SessionCreateResult:
    id: str
    name: str
    date: str
    location: str
    event_code: str
    db_path: Path
    checkout_required: bool = False
    source_event_id: str = ""


def validate_session_fields(name: str, date: str, location: str) -> None:
    errors = []
    if not (name or "").strip():
        errors.append("Naam evenement is verplicht.")
    if not (date or "").strip():
        errors.append("Datum is verplicht.")
    if not (location or "").strip():
        errors.append("Locatie is verplicht.")
    if errors:
        raise SessionValidationError(" ".join(errors))


def generate_event_code() -> str:
    """A random 4-digit code, e.g. '0472'. Not cryptographically sensitive on
    its own (short and re-used for the whole event), but drawn with `secrets`
    rather than `random` since it does gate who can register as a client."""
    return f"{secrets.randbelow(10000):04d}"


def create_session(name: str, date: str, location: str, checkout_required: bool = False,
                   source_event_id: str = "") -> SessionCreateResult:
    """Create a brand-new event session with its own database."""
    validate_session_fields(name, date, location)
    session_id = registry.new_session_id()
    db_path = database_path(session_id)
    connection = connect(db_path)
    timestamp = now_iso()
    event_code = generate_event_code()
    with transaction(connection) as tx:
        tx.execute(
            "INSERT INTO event_session (id, name, date, location, event_code, checkout_required, source_event_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)",
            (session_id, name.strip(), date.strip(), location.strip(), event_code,
             1 if checkout_required else 0, (source_event_id or "").strip(), timestamp, timestamp),
        )
    registry.upsert_session(session_id, name.strip(), date.strip(), location.strip(),
                             status="active", participant_count=0, updated_at=timestamp,
                             source_event_id=(source_event_id or "").strip())
    logger.info("Nieuwe sessie aangemaakt: %s (%s)", name, session_id)
    return SessionCreateResult(id=session_id, name=name.strip(), date=date.strip(),
                                location=location.strip(), event_code=event_code, db_path=db_path,
                                checkout_required=bool(checkout_required),
                                source_event_id=(source_event_id or "").strip())


def get_session(connection: sqlite3.Connection) -> Optional[dict]:
    row = connection.execute("SELECT * FROM event_session LIMIT 1").fetchone()
    return dict(row) if row else None


def ensure_event_code(connection: sqlite3.Connection) -> str:
    """Return the session's event code, generating and persisting one if this
    session's database predates the event-code feature (empty/missing)."""
    session = get_session(connection)
    if not session:
        raise SessionValidationError("Geen actieve sessie.")
    code = (session.get("event_code") or "").strip()
    if code:
        return code
    code = generate_event_code()
    with transaction(connection) as tx:
        tx.execute("UPDATE event_session SET event_code = ? WHERE id = ?", (code, session["id"]))
    logger.info("Sessiecode gegenereerd voor bestaande sessie %s.", session["id"])
    return code


def verify_event_code(connection: sqlite3.Connection, submitted_code: str) -> bool:
    session = get_session(connection)
    expected = (session or {}).get("event_code") or ""
    if not expected:
        # Pre-existing session without a code yet: don't lock people out
        # retroactively — Server Manager generates one as soon as it opens
        # this session (see ensure_event_code), so in practice this only
        # matters for the brief window before that happens.
        return True
    return (submitted_code or "").strip() == expected


def freeze_state(connection: sqlite3.Connection) -> dict:
    session = get_session(connection) or {}
    return {"frozen": bool(session.get("frozen", 0)),
            "reason": session.get("freeze_reason", "") or "",
            "by": session.get("freeze_by", "") or "", "at": session.get("freeze_at"),
            "checkout_required": bool(session.get("checkout_required", 0)),
            "checkin_stopped": bool(session.get("checkin_stopped", 0)),
            "checkin_stopped_at": session.get("checkin_stopped_at"),
            "checkin_stopped_reason": session.get("checkin_stopped_reason", "") or ""}


def stop_checkin(connection: sqlite3.Connection, reason: str = "", by: str = "") -> dict:
    session = get_session(connection)
    if not session:
        raise SessionValidationError("Geen actieve sessie.")
    timestamp = now_iso()
    with transaction(connection) as tx:
        tx.execute("UPDATE event_session SET checkin_stopped=1, checkin_stopped_at=?, checkin_stopped_reason=?, updated_at=? WHERE id=?",
                   (timestamp, (reason or "").strip(), timestamp, session["id"]))
        tx.execute("UPDATE participant SET attendance_status='absent', stop_marked_absent=1, updated_at=? WHERE event_id=? AND attendance_status='not_checked_in'",
                   (timestamp, session["id"]))
        tx.execute("INSERT INTO audit_log (event_id, client_id, action, timestamp, new_value) VALUES (?, ?, 'checkin_stopped', ?, ?)",
                   (session["id"], by or None, timestamp, (reason or "").strip()))
    state = freeze_state(connection)
    hub.publish("checkin_stopped", {"event_id": session["id"], "reason": state["checkin_stopped_reason"], "at": timestamp})
    hub.publish("statistics_updated", {"event_id": session["id"]})
    return state


def resume_checkin(connection: sqlite3.Connection, by: str = "") -> dict:
    """Reopen check-in and restore only absences created by stop_checkin."""
    session = get_session(connection)
    if not session:
        raise SessionValidationError("Geen actieve sessie.")
    timestamp = now_iso()
    with transaction(connection) as tx:
        tx.execute(
            "UPDATE event_session SET checkin_stopped=0, checkin_stopped_at=NULL, "
            "checkin_stopped_reason='', updated_at=? WHERE id=?",
            (timestamp, session["id"]),
        )
        restored = tx.execute(
            "UPDATE participant SET attendance_status='not_checked_in', stop_marked_absent=0, "
            "updated_at=? WHERE event_id=? AND attendance_status='absent' AND stop_marked_absent=1",
            (timestamp, session["id"]),
        ).rowcount
        tx.execute(
            "INSERT INTO audit_log (event_id, client_id, action, timestamp, new_value) "
            "VALUES (?, ?, 'checkin_resumed', ?, ?)",
            (session["id"], by or None, timestamp, str(restored)),
        )
    state = freeze_state(connection)
    hub.publish("checkin_resumed", {"event_id": session["id"], "restored": restored, "at": timestamp})
    hub.publish("statistics_updated", {"event_id": session["id"]})
    return {**state, "restored": restored}


def set_frozen(connection: sqlite3.Connection, frozen: bool, reason: str = "", by: str = "") -> dict:
    session = get_session(connection)
    if not session:
        raise SessionValidationError("Geen actieve sessie.")
    timestamp = now_iso()
    with transaction(connection) as tx:
        tx.execute(
            "UPDATE event_session SET frozen=?, freeze_reason=?, freeze_by=?, freeze_at=?, updated_at=? WHERE id=?",
            (1 if frozen else 0, (reason or "").strip() if frozen else "",
             (by or "").strip() if frozen else "", timestamp if frozen else None,
             timestamp, session["id"]),
        )
        tx.execute(
            "INSERT INTO audit_log (event_id, client_id, action, timestamp, new_value) VALUES (?, ?, ?, ?, ?)",
            (session["id"], by or None, "session_frozen" if frozen else "session_unfrozen",
             timestamp, (reason or "").strip()),
        )
    state = freeze_state(connection)
    hub.publish("session_freeze_changed", {"event_id": session["id"], **state})
    return state


def recent_session_activity(connection: sqlite3.Connection, limit: int = 12) -> list[dict]:
    """Recent freeze/stop/resume events for the live dashboard."""
    session = get_session(connection)
    if not session:
        return []
    limit = max(1, min(int(limit or 12), 50))
    rows = connection.execute(
        "SELECT action, timestamp, client_id, new_value FROM audit_log "
        "WHERE event_id=? AND action IN ('session_frozen','session_unfrozen','checkin_stopped','checkin_resumed',"
        "'emergency_started','emergency_instruction_updated','emergency_ended') "
        "ORDER BY id DESC LIMIT ?",
        (session["id"], limit),
    ).fetchall()
    labels = {
        "session_frozen": ("Inchecken gepauzeerd", "warning"),
        "session_unfrozen": ("Inchecken hervat na pauze", "success"),
        "checkin_stopped": ("Inchecken gestopt", "danger"),
        "checkin_resumed": ("Inchecken opnieuw gestart", "success"),
        "emergency_started": ("Calamiteitenmodus gestart", "danger"),
        "emergency_instruction_updated": ("Calamiteiteninstructie gewijzigd", "warning"),
        "emergency_ended": ("Calamiteitenmodus beëindigd", "success"),
    }
    activity = []
    for row in rows:
        title, tone = labels[row["action"]]
        value = str(row["new_value"] or "").strip()
        if row["action"] == "checkin_resumed":
            detail = f"{value or '0'} automatisch afwezige bezoeker(s) teruggezet."
        else:
            detail = value
        activity.append({
            "action": row["action"], "title": title, "tone": tone,
            "detail": detail, "by": str(row["client_id"] or "Systeem"), "at": row["timestamp"],
        })
    return activity


def action_conflicts_with_freeze(connection: sqlite3.Connection, created_at: str) -> bool:
    """Reject an offline operation whose client timestamp falls in a recorded freeze window."""
    if not created_at:
        return False
    try:
        action_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    rows = connection.execute(
        "SELECT action, timestamp FROM audit_log WHERE action IN ('session_frozen','session_unfrozen') ORDER BY timestamp"
    ).fetchall()
    frozen_at = None
    for row in rows:
        moment = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
        if row["action"] == "session_frozen":
            frozen_at = moment
        elif frozen_at is not None:
            if frozen_at <= action_time <= moment:
                return True
            frozen_at = None
    return frozen_at is not None and action_time >= frozen_at


def touch_session(connection: sqlite3.Connection) -> None:
    """Update the session's updated_at timestamp and refresh the resume registry entry."""
    session = get_session(connection)
    if not session:
        return
    timestamp = now_iso()
    with transaction(connection) as tx:
        tx.execute("UPDATE event_session SET updated_at = ? WHERE id = ?", (timestamp, session["id"]))
    count_row = connection.execute("SELECT COUNT(*) AS n FROM participant WHERE event_id = ?",
                                    (session["id"],)).fetchone()
    registry.upsert_session(session["id"], session["name"], session["date"], session["location"],
                             status=session["status"], participant_count=count_row["n"],
                             updated_at=timestamp, source_event_id=session.get("source_event_id", ""))


def list_recent_sessions() -> list[dict]:
    return registry.list_sessions()


def find_session_for_event(source_event_id: str, name: str = "", date: str = "") -> Optional[dict]:
    """Find an existing live session linked to an EventHub event.

    Exact name/date matching keeps sessions made before source_event_id existed
    discoverable, after which the caller can open rather than duplicate them.
    """
    source_event_id = (source_event_id or "").strip()
    wanted_name = (name or "").strip().casefold()
    wanted_date = (date or "").strip()
    legacy_match = None
    for item in list_recent_sessions():
        if source_event_id and item.get("source_event_id") == source_event_id:
            return item
        if wanted_name and wanted_date and str(item.get("name", "")).strip().casefold() == wanted_name \
                and str(item.get("date", "")).strip() == wanted_date:
            legacy_match = item
    return legacy_match


def link_session_to_event(session_id: str, source_event_id: str) -> None:
    db_path = database_path(session_id)
    connection = connect(db_path)
    with transaction(connection) as tx:
        tx.execute("UPDATE event_session SET source_event_id=? WHERE id=?", ((source_event_id or "").strip(), session_id))
    session = get_session(connection)
    count = connection.execute("SELECT COUNT(*) AS n FROM participant WHERE event_id=?", (session_id,)).fetchone()["n"]
    registry.upsert_session(session_id, session["name"], session["date"], session["location"],
                            session["status"], count, session["updated_at"], source_event_id)


def delete_session(session_id: str) -> None:
    """Delete one live-session database and its event directory."""
    known = next((item for item in list_recent_sessions() if item.get("id") == session_id), None)
    if not known:
        raise SessionValidationError("Sessie niet gevonden.")
    session_dir = events_directory() / session_id
    if session_dir.parent.resolve() != events_directory().resolve():
        raise SessionValidationError("Ongeldig sessiepad.")
    close_database(session_dir / "event.db")
    if session_dir.is_dir():
        shutil.rmtree(session_dir)
    registry.remove_session(session_id)
    logger.info("Sessie verwijderd: %s", session_id)


def resume_session(session_id: str) -> Path:
    db_path = database_path(session_id)
    if not db_path.is_file():
        raise SessionValidationError("Geen databasebestand gevonden voor deze sessie.")
    connection = connect(db_path)
    session = get_session(connection)
    if not session:
        raise SessionValidationError("Sessie niet gevonden in databasebestand.")
    logger.info("Sessie hervat: %s (%s)", session["name"], session_id)
    return db_path
