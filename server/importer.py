"""Bezoekerslijst import for EventHub Server.

Uses ``server.registration_import`` — a self-contained copy of the
column-detection/name/date/introducee logic — so that EventHub Server
has zero dependency on the EventHub Desktop codebase and can run on a
machine that never had EventHub Desktop installed.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from .registration_import import is_introducee, read_registration_file
from .logging_setup import get_logger

logger = get_logger("importer")


def _normalize_name_key(record: dict) -> tuple:
    return (
        record.get("Voornaam", "").strip().lower(),
        record.get("Achternaam", "").strip().lower(),
        record.get("Geboortedatum", "").strip(),
    )


def _normalize_participant_key(participant: dict) -> tuple:
    """Same as _normalize_name_key but for Participant rows (server DB shape,
    lowercase field names) instead of bezoekerslijst_core's record shape."""
    return (
        (participant.get("voornaam") or "").strip().lower(),
        (participant.get("achternaam") or "").strip().lower(),
        (participant.get("geboortedatum") or "").strip(),
    )


def preview_import(file_path: str | Path, existing_participants: Optional[list[dict]] = None) -> dict:
    """Read an Excel file and return a preview (does not touch the database).

    existing_participants: rows already stored for this event (for the
    'mogelijke dubbele deelnemers' warning), each a dict with at least
    Voornaam/Achternaam/Geboortedatum keys.
    """
    result = read_registration_file(file_path)
    records = result["records"]
    report = result["report"]

    existing_keys = {_normalize_participant_key(row) for row in (existing_participants or [])}
    seen_keys: set[tuple] = set()
    duplicate_count = 0
    for record in records:
        key = _normalize_name_key(record)
        if key in existing_keys or key in seen_keys:
            duplicate_count += 1
        seen_keys.add(key)

    detected_columns = [
        field for field in ("Voornaam", "Achternaam", "Tussenvoegsel", "Geboortedatum",
                            "Geboorteplaats", "Opleiding", "Profiel", "Geslacht")
        if any(record.get(field) for record in records[:50])
    ]

    return {
        "file_name": report["file_name"],
        "sheet_name": report["sheet_name"],
        "row_count": len(records),
        "detected_columns": detected_columns,
        "duplicate_count": duplicate_count,
        "introducees": report["introducees"],
        "presence_detected": report["presence_detected"],
        "preview_rows": records[:10],
        "records": records,
    }


def records_to_participants(records: list[dict], event_id: str) -> list[dict]:
    """Convert raw imported rows (bezoekerslijst_core shape) to Participant rows.

    Per spec section 7 ("Importeren betekent NIET aanwezig"), every
    imported participant always starts as 'not_checked_in' here, even
    though bezoekerslijst_core may have detected a Present/Aanwezig
    column and pre-filled record['Aanwezig'] (that auto-detection is a
    EventHub Desktop convenience for its own manual/no-checkin workflow;
    on the Server, presence must only ever be set by an explicit
    check-in action from a client, so the source Excel's Aanwezig value
    is intentionally ignored here).
    """
    participants = []
    for record in records:
        participants.append({
            # Preserve EventHub Desktop's stable record id when a live session
            # is created from an event. Standalone Excel imports have no _id
            # and therefore still receive an independent UUID.
            "id": str(record.get("_id") or uuid.uuid4()),
            "event_id": event_id,
            "identifier": record.get("Identifier", ""),
            "voornaam": record.get("Voornaam", ""),
            "tussenvoegsel": record.get("Tussenvoegsel", ""),
            "achternaam": record.get("Achternaam", ""),
            "geboortedatum": record.get("Geboortedatum", ""),
            "geboorteplaats": record.get("Geboorteplaats", ""),
            "geslacht": record.get("Geslacht", ""),
            "opleidingsniveau": record.get("Opleiding", ""),
            "profiel": record.get("Profiel", ""),
            "telefoonnummer": record.get("Telefoonnummer", ""),
            "email": record.get("Email", ""),
            "gast_van": record.get("GastVan", ""),
            "introducee": 1 if is_introducee(record) else 0,
            "attendance_status": "not_checked_in",
        })
    return participants
