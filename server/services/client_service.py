from __future__ import annotations

import sqlite3
import uuid
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..database import connect, now_iso, transaction
from ..events_hub import hub
from ..logging_setup import get_logger

logger = get_logger("client_service")

ONLINE_THRESHOLD_SECONDS = 30


def register_client(connection: sqlite3.Connection, event_id: str, client_name: str,
                     client_type: str, ip_address: str, role: str = "checkin") -> dict:
    client_id = str(uuid.uuid4())
    timestamp = now_iso()
    with transaction(connection) as tx:
        tx.execute(
            "INSERT INTO client_session (id, event_id, client_name, client_type, ip_address, "
            "role, connected_at, last_seen, checkin_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)",
            (client_id, event_id, client_name, client_type, ip_address, role, timestamp, timestamp),
        )
    hub.publish("client_connected", {"client_id": client_id})
    logger.info("Client verbonden: %s (%s) vanaf %s", client_name, client_type, ip_address)
    return {"id": client_id, "event_id": event_id, "client_name": client_name,
            "client_type": client_type, "ip_address": ip_address, "role": role,
            "connected_at": timestamp, "last_seen": timestamp, "checkin_count": 0}


def heartbeat(connection: sqlite3.Connection, client_id: str) -> bool:
    with transaction(connection) as tx:
        cursor = tx.execute("UPDATE client_session SET last_seen = ? WHERE id = ?", (now_iso(), client_id))
    return cursor.rowcount > 0


def disconnect_client(connection: sqlite3.Connection, client_id: str) -> None:
    row = connection.execute("SELECT client_name FROM client_session WHERE id = ?", (client_id,)).fetchone()
    with transaction(connection) as tx:
        tx.execute("DELETE FROM client_session WHERE id = ?", (client_id,))
    if row:
        hub.publish("client_disconnected", {"client_id": client_id})


def disconnect_all_for_server_stop(connection: sqlite3.Connection, event_id: str) -> int:
    """Invalidate every registration after an intentional server shutdown.

    A network interruption deliberately does not call this function, allowing
    clients to resume with their existing local registration after recovery.
    """
    rows = connection.execute(
        "SELECT id FROM client_session WHERE event_id = ?", (event_id,)
    ).fetchall()
    client_ids = [row["id"] for row in rows]
    if not client_ids:
        hub.publish("server_stopped", {"event_id": event_id})
        return 0
    hub.publish("server_stopped", {"event_id": event_id})
    with transaction(connection) as tx:
        tx.execute("DELETE FROM client_session WHERE event_id = ?", (event_id,))
        tx.execute(
            "INSERT INTO audit_log (event_id, action, timestamp, new_value) "
            "VALUES (?, 'server_stopped_clients_disconnected', ?, ?)",
            (event_id, now_iso(), str(len(client_ids))),
        )
    logger.info("%s clientregistratie(s) verwijderd wegens bewust stoppen van de server.", len(client_ids))
    return len(client_ids)


def kick_client(connection: sqlite3.Connection, event_id: str, client_id: str, by: str = "") -> bool:
    row = connection.execute("SELECT client_name FROM client_session WHERE id=? AND event_id=?", (client_id, event_id)).fetchone()
    if not row:
        return False
    with transaction(connection) as tx:
        tx.execute("DELETE FROM client_session WHERE id=?", (client_id,))
        tx.execute("INSERT INTO audit_log (event_id, client_id, action, timestamp, new_value) VALUES (?, ?, 'client_kicked', ?, ?)",
                   (event_id, client_id, now_iso(), by or "beheerder"))
    hub.publish("client_kicked", {"client_id": client_id})
    return True


def set_role(connection: sqlite3.Connection, event_id: str, client_id: str, role: str, by: str = "") -> dict:
    if role not in {"admin", "event_manager", "checkin", "viewer"}:
        raise ValueError("Onbekende rol.")
    with transaction(connection) as tx:
        row = tx.execute("SELECT * FROM client_session WHERE id=? AND event_id=?", (client_id, event_id)).fetchone()
        if not row:
            raise ValueError("Client niet gevonden.")
        old_role = row["role"]
        tx.execute("UPDATE client_session SET role=?, last_seen=? WHERE id=?", (role, now_iso(), client_id))
        tx.execute("INSERT INTO audit_log (event_id, client_id, action, timestamp, old_value, new_value) VALUES (?, ?, 'client_role_changed', ?, ?, ?)",
                   (event_id, client_id, now_iso(), old_role, role))
    hub.publish("client_role_changed", {"client_id": client_id, "role": role})
    return {**dict(row), "role": role}


def update_own_preferences(connection: sqlite3.Connection, event_id: str, client_id: str,
                           client_name: str, role: str) -> dict:
    """Allow a browser client to edit its name while preserving its assigned role."""
    client_name = (client_name or "").strip()
    if not client_name:
        raise ValueError("Naam van het apparaat is verplicht.")
    if len(client_name) > 80:
        raise ValueError("Naam van het apparaat is te lang.")
    timestamp = now_iso()
    with transaction(connection) as tx:
        row = tx.execute("SELECT * FROM client_session WHERE id=? AND event_id=?", (client_id, event_id)).fetchone()
        if not row:
            raise ValueError("Client niet gevonden.")
        before = dict(row)
        if role and role != before["role"]:
            raise ValueError("Uw rol wordt door een eventmanager of beheerder toegewezen.")
        role = before["role"]
        tx.execute("UPDATE client_session SET client_name=?, last_seen=? WHERE id=?",
                   (client_name, timestamp, client_id))
        tx.execute(
            "INSERT INTO audit_log (event_id, client_id, action, timestamp, old_value, new_value) "
            "VALUES (?, ?, 'client_preferences_updated', ?, ?, ?)",
            (event_id, client_id, timestamp,
             json.dumps({"client_name": before["client_name"], "role": before["role"]}, ensure_ascii=False),
             json.dumps({"client_name": client_name, "role": role}, ensure_ascii=False)),
        )
    updated = {**before, "client_name": client_name, "role": role, "last_seen": timestamp}
    hub.publish("client_profile_changed", {"client_id": client_id, "client_name": client_name, "role": role})
    return updated


def _is_online(last_seen_iso: str) -> bool:
    try:
        last_seen = datetime.fromisoformat(last_seen_iso)
    except ValueError:
        return False
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - last_seen) <= timedelta(seconds=ONLINE_THRESHOLD_SECONDS)


def list_clients(connection: sqlite3.Connection, event_id: str) -> list[dict]:
    rows = connection.execute(
        "SELECT * FROM client_session WHERE event_id = ? ORDER BY connected_at DESC", (event_id,)
    ).fetchall()
    clients = []
    for row in rows:
        item = dict(row)
        item["online"] = _is_online(item["last_seen"])
        clients.append(item)
    return clients


def online_client_count(connection: sqlite3.Connection, event_id: str) -> int:
    return sum(1 for client in list_clients(connection, event_id) if client["online"])
