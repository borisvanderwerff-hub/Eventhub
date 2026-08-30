from __future__ import annotations

import sqlite3
from collections import Counter, OrderedDict
from datetime import date, datetime

AGE_BUCKETS = [
    (0, 17, "<18"),
    (18, 20, "18–20"),
    (21, 23, "21–23"),
    (24, 26, "24–26"),
    (27, 30, "27–30"),
    (31, 999, "31+"),
]


def _age_from_birthdate(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            born = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            continue
    else:
        return None
    today = date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return age if 0 <= age <= 120 else None


def _age_bucket(value: str) -> str | None:
    age = _age_from_birthdate(value)
    if age is None:
        return None
    for low, high, label in AGE_BUCKETS:
        if low <= age <= high:
            return label
    return None


def _fetch_participants(connection: sqlite3.Connection, event_id: str, include_introducees: bool) -> list[dict]:
    sql = "SELECT * FROM participant WHERE event_id = ?"
    params: list = [event_id]
    if not include_introducees:
        sql += " AND introducee = 0"
    rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def overview(connection: sqlite3.Connection, event_id: str, include_introducees: bool = True) -> dict:
    participants = _fetch_participants(connection, event_id, include_introducees)
    registered = len(participants)
    inside = sum(1 for p in participants if p["attendance_status"] == "present")
    checked_out = sum(1 for p in participants if p["attendance_status"] == "checked_out")
    absent = sum(1 for p in participants if p["attendance_status"] == "absent")
    attended = sum(1 for p in participants if p.get("checkin_time"))
    expected = sum(1 for p in participants if p["attendance_status"] == "not_checked_in")
    turnout = round((attended / registered) * 100, 1) if registered else 0.0
    return {
        "registered": registered,
        "present": attended,
        "inside": inside,
        "checked_out": checked_out,
        "absent": absent,
        "expected": expected,
        "turnout_percentage": turnout,
    }


def _breakdown(participants: list[dict], field: str, bucket_fn=None) -> list[dict]:
    registered_counts: "Counter[str]" = Counter()
    present_counts: "Counter[str]" = Counter()
    for participant in participants:
        raw_value = participant.get(field) or ""
        label = bucket_fn(raw_value) if bucket_fn else (raw_value.strip() or "Onbekend")
        if label is None:
            continue
        registered_counts[label] += 1
        if participant.get("checkin_time"):
            present_counts[label] += 1
    results = []
    for label, registered in sorted(registered_counts.items(), key=lambda item: -item[1]):
        present = present_counts.get(label, 0)
        turnout = round((present / registered) * 100, 1) if registered else 0.0
        results.append({
            "label": label, "registered": registered, "present": present,
            "expected": registered - present, "turnout_percentage": turnout,
        })
    return results


def breakdown_by_dimension(connection: sqlite3.Connection, event_id: str, dimension: str,
                            include_introducees: bool = True, inside_only: bool = False) -> list[dict]:
    participants = _fetch_participants(connection, event_id, include_introducees)
    if inside_only:
        participants = [p for p in participants if p.get("attendance_status") == "present"]
    if dimension == "education":
        return _breakdown(participants, "opleidingsniveau")
    if dimension == "profile":
        return _breakdown(participants, "profiel")
    if dimension == "gender":
        return _breakdown(participants, "geslacht")
    if dimension == "age":
        return _breakdown(participants, "geboortedatum", bucket_fn=_age_bucket)
    if dimension == "introducee":
        return _breakdown(
            [{**p, "_introducee_label": "Introducee" if p["introducee"] else "Reguliere bezoeker"}
             for p in participants],
            "_introducee_label",
        )
    raise ValueError(f"Onbekende statistiekdimensie: {dimension}")


def attendance_timeline(connection: sqlite3.Connection, event_id: str, bucket_minutes: int = 5) -> list[dict]:
    """Cumulative check-ins over time, bucketed to N-minute intervals."""
    rows = connection.execute(
        "SELECT checkin_time FROM participant WHERE event_id = ? AND checkin_time IS NOT NULL "
        "ORDER BY checkin_time ASC",
        (event_id,),
    ).fetchall()
    buckets: "OrderedDict[str, int]" = OrderedDict()
    for row in rows:
        try:
            moment = datetime.fromisoformat(row["checkin_time"])
        except ValueError:
            continue
        minute = (moment.minute // bucket_minutes) * bucket_minutes
        bucket_key = moment.replace(minute=minute, second=0, microsecond=0).strftime("%H:%M")
        buckets[bucket_key] = buckets.get(bucket_key, 0) + 1
    cumulative = 0
    timeline = []
    for bucket_key, count in buckets.items():
        cumulative += count
        timeline.append({"time": bucket_key, "count": count, "cumulative": cumulative})
    return timeline


def client_checkin_counts(connection: sqlite3.Connection, event_id: str) -> list[dict]:
    rows = connection.execute(
        "SELECT client_name, checkin_count FROM client_session WHERE event_id = ? "
        "ORDER BY checkin_count DESC",
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]
