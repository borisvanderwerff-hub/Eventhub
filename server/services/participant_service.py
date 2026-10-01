from __future__ import annotations

import sqlite3
import uuid
import unicodedata
from typing import Optional

from ..database import connect, now_iso, transaction
from ..events_hub import hub
from ..logging_setup import get_logger
from .session_service import get_session, touch_session

logger = get_logger("participant_service")


class NotFoundError(LookupError):
    pass


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def surname_sort_key(participant: dict) -> tuple:
    """Defensievolgorde: achternaam is leidend; tussenvoegsel volgt als tweede sleutel."""
    def normalized(value):
        text = unicodedata.normalize("NFKD", str(value or "").casefold())
        return "".join(char for char in text if not unicodedata.combining(char))
    return (normalized(participant.get("achternaam")), normalized(participant.get("tussenvoegsel")),
            normalized(participant.get("voornaam")), str(participant.get("id", "")))


def defence_display_name(participant: dict) -> str:
    surname = str(participant.get("achternaam", "") or "").strip()
    first = str(participant.get("voornaam", "") or "").strip()
    prefix = str(participant.get("tussenvoegsel", "") or "").strip()
    given = " ".join(part for part in (first, prefix) if part)
    return f"{surname}, {given}" if surname and given else surname or given


def _log_audit(connection, event_id: str, participant_id: Optional[str], client_id: Optional[str],
                action: str, old_value: Optional[str] = None, new_value: Optional[str] = None,
                operation_id: Optional[str] = None) -> None:
    connection.execute(
        "INSERT INTO audit_log (event_id, participant_id, client_id, action, timestamp, old_value, new_value, operation_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (event_id, participant_id, client_id, action, now_iso(), old_value, new_value, operation_id),
    )


def add_participants(connection: sqlite3.Connection, event_id: str, rows: list[dict],
                      client_id: Optional[str] = None) -> int:
    timestamp = now_iso()
    with transaction(connection) as tx:
        for row in rows:
            tx.execute(
                """INSERT INTO participant (
                    id, event_id, identifier, voornaam, tussenvoegsel, achternaam,
                    geboortedatum, geboorteplaats, geslacht, opleidingsniveau, profiel,
                    telefoonnummer, email, gast_van, introducee, temporary_walkin, attendance_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["id"], event_id, row.get("identifier", ""), row["voornaam"],
                    row.get("tussenvoegsel", ""), row["achternaam"], row.get("geboortedatum", ""),
                    row.get("geboorteplaats", ""), row.get("geslacht", ""),
                    row.get("opleidingsniveau", ""), row.get("profiel", ""),
                    row.get("telefoonnummer", ""), row.get("email", ""), row.get("gast_van", ""),
                    row.get("introducee", 0), row.get("temporary_walkin", 0), row.get("attendance_status", "not_checked_in"),
                    timestamp, timestamp,
                ),
            )
            _log_audit(tx, event_id, row["id"], client_id, "imported")
    touch_session(connection)
    hub.publish("statistics_updated", {"event_id": event_id})
    logger.info("%d deelnemer(s) toegevoegd aan evenement %s", len(rows), event_id)
    return len(rows)


def list_participants(connection: sqlite3.Connection, event_id: str,
                       query: str = "", attendance: str = "", limit: int = 500) -> list[dict]:
    sql = "SELECT * FROM participant WHERE event_id = ?"
    params: list = [event_id]
    if query:
        sql += (" AND (LOWER(voornaam) LIKE ? OR LOWER(achternaam) LIKE ? "
                "OR LOWER(geboorteplaats) LIKE ? OR geboortedatum LIKE ?)")
        like = f"%{query.strip().lower()}%"
        params.extend([like, like, like, like])
    if attendance:
        sql += " AND attendance_status = ?"
        params.append(attendance)
    sql += " LIMIT ?"
    params.append(limit)
    rows = connection.execute(sql, params).fetchall()
    return sorted((_row_to_dict(row) for row in rows), key=surname_sort_key)


def get_participant(connection: sqlite3.Connection, participant_id: str) -> dict:
    row = connection.execute("SELECT * FROM participant WHERE id = ?", (participant_id,)).fetchone()
    if not row:
        raise NotFoundError(f"Deelnemer {participant_id} niet gevonden.")
    return _row_to_dict(row)


def update_participant(connection: sqlite3.Connection, participant_id: str, changes: dict,
                        client_id: Optional[str] = None) -> dict:
    allowed = {
        "voornaam", "tussenvoegsel", "achternaam", "geboortedatum", "geboorteplaats",
        "geslacht", "opleidingsniveau", "profiel", "telefoonnummer", "email",
    }
    fields = {key: value for key, value in changes.items() if key in allowed}
    if not fields:
        return get_participant(connection, participant_id)
    before = get_participant(connection, participant_id)
    timestamp = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with transaction(connection) as tx:
        tx.execute(
            f"UPDATE participant SET {assignments}, updated_at = ? WHERE id = ?",
            (*fields.values(), timestamp, participant_id),
        )
        _log_audit(tx, before["event_id"], participant_id, client_id, "updated",
                   old_value=str({k: before.get(k) for k in fields}), new_value=str(fields))
    after = get_participant(connection, participant_id)
    hub.publish("participant_updated", {"participant_id": participant_id, "event_id": after["event_id"]})
    return after


def check_in(connection: sqlite3.Connection, participant_id: str,
             client_id: Optional[str] = None, client_name: str = "",
             operation_id: Optional[str] = None) -> dict:
    """Idempotent: checking in an already-present participant is a no-op
    that returns the current state instead of erroring or double-counting."""
    with transaction(connection) as tx:
        if operation_id and tx.execute("SELECT 1 FROM audit_log WHERE operation_id=?", (operation_id,)).fetchone():
            row = tx.execute("SELECT * FROM participant WHERE id=?", (participant_id,)).fetchone()
            return {"participant": dict(row), "already_processed": True}
        row = tx.execute("SELECT * FROM participant WHERE id = ?", (participant_id,)).fetchone()
        if not row:
            raise NotFoundError(f"Deelnemer {participant_id} niet gevonden.")
        participant = dict(row)
        if participant["attendance_status"] == "present":
            return {"participant": participant, "already_checked_in": True}
        timestamp = now_iso()
        tx.execute(
            "UPDATE participant SET attendance_status = 'present', checkin_time = ?, "
            "checkin_by = ?, checkout_time = NULL, checkout_by = NULL, updated_at = ? WHERE id = ?",
            (timestamp, client_name or client_id or "", timestamp, participant_id),
        )
        _log_audit(tx, participant["event_id"], participant_id, client_id, "checked_in",
                   old_value="not_checked_in", new_value="present", operation_id=operation_id)
        if client_id:
            tx.execute("UPDATE client_session SET checkin_count = checkin_count + 1, last_seen = ? "
                       "WHERE id = ?", (timestamp, client_id))
    updated = get_participant(connection, participant_id)
    touch_session(connection)
    hub.publish("participant_checked_in", {"participant_id": participant_id, "event_id": updated["event_id"]})
    hub.publish("statistics_updated", {"event_id": updated["event_id"]})
    return {"participant": updated, "already_checked_in": False}


def check_out(connection: sqlite3.Connection, participant_id: str,
              client_id: Optional[str] = None, client_name: str = "",
              operation_id: Optional[str] = None) -> dict:
    with transaction(connection) as tx:
        if operation_id and tx.execute("SELECT 1 FROM audit_log WHERE operation_id=?", (operation_id,)).fetchone():
            row = tx.execute("SELECT * FROM participant WHERE id=?", (participant_id,)).fetchone()
            return {"participant": dict(row), "already_processed": True}
        row = tx.execute("SELECT * FROM participant WHERE id = ?", (participant_id,)).fetchone()
        if not row:
            raise NotFoundError(f"Deelnemer {participant_id} niet gevonden.")
        participant = dict(row)
        if participant["attendance_status"] != "present":
            return {"participant": participant, "already_checked_out": True}
        timestamp = now_iso()
        tx.execute(
            "UPDATE participant SET attendance_status = 'checked_out', checkout_time = ?, "
            "checkout_by = ?, updated_at = ? WHERE id = ?",
            (timestamp, client_name or client_id or "", timestamp, participant_id),
        )
        _log_audit(tx, participant["event_id"], participant_id, client_id, "checked_out",
                   old_value="present", new_value="checked_out", operation_id=operation_id)
    updated = get_participant(connection, participant_id)
    touch_session(connection)
    hub.publish("participant_checked_out", {"participant_id": participant_id, "event_id": updated["event_id"]})
    hub.publish("statistics_updated", {"event_id": updated["event_id"]})
    return {"participant": updated, "already_checked_out": False}


def undo_check_in(connection: sqlite3.Connection, participant_id: str,
                  client_id: Optional[str] = None, client_name: str = "",
                  operation_id: Optional[str] = None) -> dict:
    with transaction(connection) as tx:
        if operation_id and tx.execute("SELECT 1 FROM audit_log WHERE operation_id=?", (operation_id,)).fetchone():
            row = tx.execute("SELECT * FROM participant WHERE id=?", (participant_id,)).fetchone()
            return {"participant": dict(row), "already_processed": True}
        row = tx.execute("SELECT * FROM participant WHERE id=?", (participant_id,)).fetchone()
        if not row:
            raise NotFoundError(f"Deelnemer {participant_id} niet gevonden.")
        participant = dict(row)
        timestamp = now_iso()
        tx.execute("UPDATE participant SET attendance_status='not_checked_in', checkin_time=NULL, checkin_by=NULL, "
                   "checkout_time=NULL, checkout_by=NULL, updated_at=? WHERE id=?", (timestamp, participant_id))
        _log_audit(tx, participant["event_id"], participant_id, client_id, "checkin_undone",
                   old_value=participant["attendance_status"], new_value="not_checked_in", operation_id=operation_id)
    updated = get_participant(connection, participant_id)
    touch_session(connection)
    hub.publish("participant_checkin_undone", {"participant_id": participant_id, "event_id": updated["event_id"]})
    hub.publish("statistics_updated", {"event_id": updated["event_id"]})
    return {"participant": updated}


def add_walkin(connection: sqlite3.Connection, event_id: str, name: str, phone: str = "",
               client_id: Optional[str] = None, client_name: str = "") -> dict:
    """Create a session-only walk-in and immediately check them in.

    Walk-ins deliberately live in the live-session database only and are marked
    temporary_walkin so normal participant exports/statistical profile breakdowns
    can exclude them while presence/emergency accounting can still include them.
    """
    full_name = " ".join(str(name or "").split()).strip()
    if not full_name:
        raise ValueError("Vul de naam van de deelnemer in.")
    if len(full_name) > 160:
        raise ValueError("De naam is te lang.")
    phone = " ".join(str(phone or "").split()).strip()[:40]
    parts = full_name.split()
    voornaam = parts[0]
    achternaam = " ".join(parts[1:]) if len(parts) > 1 else "(onbekend)"
    participant_id = str(uuid.uuid4())
    timestamp = now_iso()
    with transaction(connection) as tx:
        tx.execute(
            """INSERT INTO participant (
                id,event_id,identifier,voornaam,tussenvoegsel,achternaam,telefoonnummer,
                introducee,temporary_walkin,attendance_status,checkin_time,checkin_by,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (participant_id,event_id,"",voornaam,"",achternaam,phone,0,1,"present",timestamp,
             client_name or client_id or "",timestamp,timestamp),
        )
        _log_audit(tx,event_id,participant_id,client_id,"walkin_added",new_value=full_name)
        if client_id:
            tx.execute("UPDATE client_session SET checkin_count=checkin_count+1,last_seen=? WHERE id=?",
                       (timestamp,client_id))
    participant = get_participant(connection, participant_id)
    touch_session(connection)
    hub.publish("participant_walkin_added", {"participant_id": participant_id, "event_id": event_id})
    hub.publish("statistics_updated", {"event_id": event_id})
    return participant
