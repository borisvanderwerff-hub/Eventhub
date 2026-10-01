from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from urllib.parse import urlparse, urlunparse


RUDDER_HOSTS = {"werkenbijdefensie.nl", "www.werkenbijdefensie.nl"}
RUDDER_EVENTS_OVERVIEW_URL = "https://werkenbijdefensie.nl/rudder/event/events"
RUDDER_EVENT_FORMAT = "EventHub Rudder Event"
RUDDER_EVENT_SCHEMA_VERSION = 1

# Rudder noemt zijn exports meeloopdag-marine-varend-5900-registrations-...
# Dat nummer is per evenement uniek en keert terug bij elke volgende export van
# hetzelfde evenement. De datum verderop in die naam is het moment van
# exporteren, niet de evenementdatum, en is dus onbruikbaar.
RUDDER_EXPORT_ID = re.compile(r"-(\d{3,6})-registrations[-.]")


def rudder_id_from_filename(name) -> str:
    """Het Rudder-evenementnummer uit de naam van een export, of leeg."""
    match = RUDDER_EXPORT_ID.search(str(name or ""))
    return match.group(1) if match else ""


RUDDER_STRING_FIELDS = (
    "event_template_id",
    "event_template",
    "reference",
    "event_type",
    "form_type",
    "owner_id",
    "owner",
    "publication_date",
    "expiration_date",
    "maximum_registrants",
    "invitees_per_registrant",
    "registration_url",
    "prior_closing_days",
    "event_location_id",
    "event_location",
    "location_address",
    "location_instructions",
    "minimal_education",
    "minimal_age",
    "maximal_age",
)

RUDDER_BOOL_FIELDS = (
    "active",
    "internal_registration",
    "registrant_limit",
    "allows_invitees",
    "license_plate_registration",
)


def _clean_text(value, maximum=20_000) -> str:
    return str(value or "").replace("\x00", "").strip()[:maximum]


def _clean_optional_bool(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "ja"}


def rudder_event_id_from_url(url: str) -> str:
    """Return the numeric Rudder event id for a safe event URL."""
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() not in RUDDER_HOSTS:
        return ""
    match = re.fullmatch(
        r"/rudder/event/events/(\d+)(?:/(?:edit|registrations|attendance))?/?",
        parsed.path or "",
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def canonical_rudder_url(event_id: str, section: str = "edit") -> str:
    event_id = _clean_text(event_id, 30)
    if not event_id.isdigit() or section not in {"edit", "attendance", "registrations"}:
        return ""
    return urlunparse(("https", "werkenbijdefensie.nl", f"/rudder/event/events/{event_id}/{section}", "", "", ""))


def is_rudder_event_linked(event: dict | None) -> bool:
    """Only a completed event-data import counts as a Rudder event link.

    Attendance export also stores a Rudder event id. Requiring the canonical edit
    URL, a sync timestamp and the imported snapshot keeps that older integration
    from producing a false 'Rudder gekoppeld' label.
    """
    if not isinstance(event, dict):
        return False
    event_id = _clean_text(event.get("rudder_event_id"), 30)
    edit_url = _clean_text(event.get("rudder_edit_url"), 500)
    synced_at = _clean_text(event.get("rudder_last_synced_at"), 80)
    snapshot = event.get("rudder_data")
    return bool(
        event_id.isdigit()
        and rudder_event_id_from_url(edit_url) == event_id
        and synced_at
        and isinstance(snapshot, dict)
        and snapshot
    )


def sanitize_rudder_event_payload(payload: dict) -> dict:
    """Validate and reduce browser data to the explicit, non-secret allowlist."""
    if not isinstance(payload, dict) or payload.get("format") != RUDDER_EVENT_FORMAT:
        raise ValueError("Rudder stuurde geen geldig EventHub-evenementpakket.")
    try:
        version = int(payload.get("version", 0))
    except (TypeError, ValueError):
        version = 0
    if version != RUDDER_EVENT_SCHEMA_VERSION:
        raise ValueError("Deze Rudder-koppeling gebruikt een niet-ondersteunde gegevensversie.")
    event_id = _clean_text(payload.get("event_id"), 30)
    if not event_id.isdigit():
        raise ValueError("Het Rudder-eventnummer ontbreekt of is ongeldig.")

    source = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    result = {field: _clean_text(source.get(field)) for field in RUDDER_STRING_FIELDS}
    for field in RUDDER_BOOL_FIELDS:
        result[field] = _clean_optional_bool(source.get(field))

    dates = []
    for item in source.get("dates", []) if isinstance(source.get("dates"), list) else []:
        if not isinstance(item, dict) or len(dates) >= 10:
            continue
        day = _clean_text(item.get("date"), 20)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            continue
        dates.append({
            "id": _clean_text(item.get("id"), 50),
            "date": day,
            "start_time": _clean_text(item.get("start_time"), 20),
            "end_time": _clean_text(item.get("end_time"), 20),
        })
    result["dates"] = dates
    return {
        "event_id": event_id,
        "edit_url": canonical_rudder_url(event_id, "edit"),
        "data": result,
    }


def _eventhub_date(value: str) -> str:
    raw = _clean_text(value, 30)
    for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, pattern).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return raw


def _rudder_date(value: str) -> str:
    raw = _clean_text(value, 30)
    for pattern in ("%d-%m-%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, pattern).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def event_type_for_eventhub(rudder_type: str, template_name: str = "") -> str:
    exact_types = {
        "meeloopdag": "Meeloopdag",
        "voorlichting": "Voorlichting",
        "online voorlichting": "Online voorlichting",
    }
    normalized_type = " ".join(_clean_text(rudder_type, 100).casefold().split())
    if normalized_type in exact_types:
        return exact_types[normalized_type]
    value = f"{rudder_type} {template_name}".casefold()
    if "online" in value:
        return "Online voorlichting"
    if "voorlichting" in value:
        return "Voorlichting"
    return "Meeloopdag"


def matching_eventhub_template(imported: dict, templates: list[dict] | None) -> dict | None:
    """Find the EventHub template that Rudder names for this event."""
    data = imported.get("data", {}) if isinstance(imported, dict) else {}
    candidates = {
        " ".join(_clean_text(data.get(key), 300).casefold().split())
        for key in ("event_type", "event_template")
        if _clean_text(data.get(key), 300)
    }
    for template in templates or []:
        if not isinstance(template, dict):
            continue
        name = " ".join(_clean_text(template.get("name"), 300).casefold().split())
        if name and name in candidates:
            return template
    return None


def _place_from_address(value: str) -> str:
    address = _clean_text(value, 500)
    match = re.search(r"\b\d{4}\s?[A-Z]{2}\s+(.+)$", address, re.IGNORECASE)
    return _clean_text(match.group(1), 200) if match else ""


def _target_audience(data: dict) -> str:
    parts = []
    education = _clean_text(data.get("minimal_education"), 200)
    minimum_age = _clean_text(data.get("minimal_age"), 20)
    maximum_age = _clean_text(data.get("maximal_age"), 20)
    if education:
        parts.append(f"Opleiding vanaf {education}")
    if minimum_age and maximum_age:
        parts.append(f"Leeftijd {minimum_age}–{maximum_age} jaar")
    elif minimum_age:
        parts.append(f"Leeftijd vanaf {minimum_age} jaar")
    elif maximum_age:
        parts.append(f"Leeftijd tot en met {maximum_age} jaar")
    return " · ".join(parts)


def rudder_eventhub_updates(imported: dict) -> dict:
    """Map one sanitized Rudder package onto EventHub's core event fields."""
    data = imported.get("data", {}) if isinstance(imported, dict) else {}
    dates = data.get("dates", []) if isinstance(data.get("dates"), list) else []
    dated_items = [item for item in dates if item.get("date")]
    first_item = min(dated_items, key=lambda item: item.get("date", "")) if dated_items else {}
    first_date = first_item.get("date", "")
    name = _clean_text(data.get("event_template")) or _clean_text(data.get("reference")) or "Rudder-evenement"
    location = _clean_text(data.get("event_location"))
    updates = {
        "name": name,
        "event_type": event_type_for_eventhub(data.get("event_type", ""), name),
        "date": _eventhub_date(first_date),
        "start_time": _clean_text(first_item.get("start_time"), 20),
        "end_time": _clean_text(first_item.get("end_time"), 20),
        "location": location or ("Online" if "online" in name.lower() else ""),
        "location_address": _clean_text(data.get("location_address"), 500),
        "location_instructions": _clean_text(data.get("location_instructions"), 20_000),
        "maximum_registrants": _clean_text(data.get("maximum_registrants"), 20),
        "status": "In voorbereiding" if data.get("active") is not False else "Concept",
    }
    place = _place_from_address(data.get("location_address", ""))
    target_audience = _target_audience(data)
    if place:
        updates["place"] = place
    if target_audience:
        updates["target_audience"] = target_audience
    return updates


def rudder_export_package(event: dict) -> dict:
    """Build the allowlisted package the browser assistant may use to fill Rudder."""
    original = deepcopy(event.get("rudder_data", {})) if isinstance(event.get("rudder_data"), dict) else {}
    known_fields = {field for field in (*RUDDER_STRING_FIELDS, *RUDDER_BOOL_FIELDS, "dates") if field in original}
    data = deepcopy(original)
    for field in RUDDER_STRING_FIELDS:
        data[field] = _clean_text(data.get(field))
    for field in RUDDER_BOOL_FIELDS:
        data[field] = _clean_optional_bool(data.get(field))
    dates = data.get("dates", []) if isinstance(data.get("dates"), list) else []
    if dates:
        dates = deepcopy(dates[:10])
        dates[0]["date"] = _rudder_date(event.get("date", dates[0].get("date", "")))
        dates[0]["start_time"] = _clean_text(event.get("start_time", dates[0].get("start_time", "")), 20)
        dates[0]["end_time"] = _clean_text(event.get("end_time", dates[0].get("end_time", "")), 20)
    elif event.get("date"):
        dates = [{
            "id": "",
            "date": _rudder_date(event.get("date", "")),
            "start_time": _clean_text(event.get("start_time", ""), 20),
            "end_time": _clean_text(event.get("end_time", ""), 20),
        }]
        known_fields.add("dates")
    data["dates"] = dates
    if "maximum_registrants" in known_fields:
        data["maximum_registrants"] = _clean_text(event.get("maximum_registrants", data.get("maximum_registrants", "")), 20)
    if "location_instructions" in known_fields:
        data["location_instructions"] = _clean_text(event.get("location_instructions", data.get("location_instructions", "")))
    event_id = _clean_text(event.get("rudder_event_id"), 30)
    return {
        "format": RUDDER_EVENT_FORMAT,
        "version": RUDDER_EVENT_SCHEMA_VERSION,
        "direction": "export",
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "event_id": event_id,
        "known_fields": sorted(known_fields),
        "data": data,
    }


def human_sync_time(value: str) -> str:
    raw = _clean_text(value, 80)
    if not raw:
        return "nog niet gesynchroniseerd"
    try:
        parsed = datetime.fromisoformat(raw)
        return parsed.strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return raw
