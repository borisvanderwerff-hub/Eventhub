"""Participant attendance and callback status rules."""

import re
import unicodedata

# Contact- en terugbelstatussen van deelnemers.
CALLBACK_STATUSES = [
    "Nog bellen",
    "Geen gehoor",
    "Voicemail",
    "Gesproken",
    "Terugbellen op verzoek",
    "WhatsApp verzonden",
    "Afgerond",
    "Niet meer benaderen",
]

CALLBACK_DONE_STATUSES = {"Gesproken", "WhatsApp verzonden", "Afgerond", "Niet meer benaderen"}

# De vier standen die een aanmelding kan hebben. Tot bestandsversie 11 was dit
# een ja/nee, waardoor "niet gekomen" en "onbekend" door elkaar konden lopen.
PRESENT_VALUES = {
    "ja", "yes", "y", "aanwezig", "present", "1", "true", "waar", "opgekomen", "gekomen", "show",
}

ABSENT_VALUES = {
    "nee", "no", "n", "afwezig", "absent", "0", "false", "onwaar",
    "noshow", "no-show", "nietopgekomen", "nietgekomen",
}

CANCELLED_VALUES = {
    "afgemeld", "cancelled", "canceled", "geannuleerd", "annulering", "afgezegd",
}

UNKNOWN_VALUES = {
    "onbekend", "unknown", "nvt", "geen", "nogniet",
}

AANWEZIG = "aanwezig"

AFWEZIG = "afwezig"

AFGEMELD = "afgemeld"

ONBEKEND = "onbekend"

ATTENDANCE_STATUSES = (AANWEZIG, AFWEZIG, AFGEMELD, ONBEKEND)

# Bron van de aanmelding en reden waarom een record niet meer meetelt.
INSCHRIJVING = "Inschrijving"

OVERGESLAGEN = "Overgeslagen"

DUBBELE_INSCHRIJVING = "Dubbele inschrijving"

ATTENDANCE_LABELS = {
    AANWEZIG: "Aanwezig",
    AFWEZIG: "Niet gekomen",
    AFGEMELD: "Afgemeld",
    ONBEKEND: "Onbekend",
}

_STATUS_GEWICHT = {ONBEKEND: 0, AFGEMELD: 1, AFWEZIG: 2, AANWEZIG: 3}

def infer_presence_from_text(value) -> bool | None:
    """Ja of nee uit vrije tekst; afgemeld en onbekend zijn geen uitspraak."""
    key = normalize(value)
    if not key:
        return None
    key = key.replace("-", "")
    if key in PRESENT_VALUES:
        return True
    if key in ABSENT_VALUES:
        return False
    return None

def infer_attendance_from_text(value) -> str | None:
    """De volledige stand uit vrije tekst, zoals Rudder hem aanlevert.

    Rudder schrijft Yes, No, Canceled en Unknown. De eerste twee zijn een
    uitspraak over de opkomst, de laatste twee juist niet: afgemeld betekent
    dat iemand zich heeft teruggetrokken en onbekend dat er niets bekend is.
    """
    key = normalize(value)
    if not key:
        return None
    key = key.replace("-", "")
    if key in PRESENT_VALUES:
        return AANWEZIG
    if key in ABSENT_VALUES:
        return AFWEZIG
    if key in CANCELLED_VALUES:
        return AFGEMELD
    if key in UNKNOWN_VALUES:
        return ONBEKEND
    return None

def attendance_value(value) -> str:
    """Breng een opgeslagen waarde terug tot een van de vier standen."""
    if isinstance(value, bool):
        # Bestandsversie 11 en ouder: een ja/nee per evenement.
        return AANWEZIG if value else AFWEZIG
    key = str(value or "").strip().casefold()
    if key in ATTENDANCE_STATUSES:
        return key
    return infer_attendance_from_text(key) or ONBEKEND

def is_introducee(record: dict) -> bool:
    return bool(text(record.get("GastVan", "")))

def callback_status(record: dict) -> str:
    status = text(record.get("Terugbelstatus", ""))
    if status in CALLBACK_STATUSES:
        return status
    return "Afgerond" if bool(record.get("Teruggebeld", False)) else "Nog bellen"

def callback_is_done(record: dict) -> bool:
    return callback_status(record) in CALLBACK_DONE_STATUSES

def record_events(record: dict) -> list[str]:
    return [value.strip() for value in text(record.get("Evenement", "")).split(";") if value.strip()]

def attendance_map(record: dict) -> dict:
    """Aanwezigheidsstand per evenement, met migratie van oudere formaten.

    Tot bestandsversie 10 was ``Aanwezig`` één boolean voor de hele persoon.
    Bij een bezoeker die aan meerdere evenementen hangt overschreef elke
    livesessie daardoor de registratie van het vorige evenement. Vanaf
    versie 11 is het een dict per evenementnaam, en vanaf versie 12 staat
    daar een van de vier standen in plaats van een ja/nee.

    Een oude boolean geldt bij het lezen voor alle gekoppelde evenementen:
    bij het gebruikelijke ene evenement is dat exact, bij meerdere is het de
    enige aanname die geen aanwezigheid verzint die er nooit was.
    """
    value = record.get("Aanwezig", False)
    if isinstance(value, dict):
        return {str(name): attendance_value(status) for name, status in value.items()}
    return {name: attendance_value(value) for name in record_events(record)}

def strongest_status(*statuses) -> str:
    """De meest uitgesproken stand wint: aanwezig boven afwezig boven afgemeld."""
    return max(
        (attendance_value(status) for status in statuses),
        key=lambda status: _STATUS_GEWICHT[status],
        default=ONBEKEND,
    )

def attendance_status(record: dict, event_name: str) -> str:
    """De stand bij één evenement; onbekend wanneer er niets is vastgelegd."""
    wanted = normalize(event_name)
    for name, status in attendance_map(record).items():
        if normalize(name) == wanted:
            return status
    return ONBEKEND

def is_present(record: dict, event_name: str = "") -> bool:
    """Aanwezig geweest bij één evenement, of bij welk evenement dan ook."""
    presence = attendance_map(record)
    if not event_name:
        return AANWEZIG in presence.values()
    return attendance_status(record, event_name) == AANWEZIG

def is_no_show(record: dict, event_name: str) -> bool:
    """Aangemeld en niet gekomen. Afgemeld en onbekend tellen hier niet mee."""
    return attendance_status(record, event_name) == AFWEZIG

def is_cancelled(record: dict, event_name: str) -> bool:
    return attendance_status(record, event_name) == AFGEMELD

def attendance_counts(records, event_name: str) -> dict:
    """Hoeveel deelnemers er in elke stand zitten bij dit evenement."""
    counts = {status: 0 for status in ATTENDANCE_STATUSES}
    for record in records:
        counts[attendance_status(record, event_name)] += 1
    return counts

def turnout_percentage(counts: dict) -> float:
    """Aanwezige deelnemers als aandeel van alle aanmeldingen."""
    aangemeld = sum(int(counts.get(status, 0) or 0) for status in ATTENDANCE_STATUSES)
    return round(counts.get(AANWEZIG, 0) / aangemeld * 100, 1) if aangemeld else 0.0

def is_present_in_scope(record: dict, scope_events) -> bool:
    """Aanwezigheid binnen de evenementen die nu in beeld zijn."""
    if not scope_events:
        return is_present(record)
    return any(is_present(record, name) for name in scope_events)

def set_attendance(record: dict, event_name: str, status: str) -> bool:
    """Leg één stand vast bij één evenement. Geeft terug of er iets wijzigde."""
    event_name = str(event_name or "").strip()
    presence = attendance_map(record)
    if not event_name:
        record["Aanwezig"] = presence
        return False
    status = attendance_value(status)
    wanted = normalize(event_name)
    key = next((name for name in presence if normalize(name) == wanted), event_name)
    changed = presence.get(key, ONBEKEND) != status
    presence[key] = status
    record["Aanwezig"] = presence
    return changed

def set_present(record: dict, event_name: str, present: bool) -> bool:
    """Aanwezig of niet gekomen. Voor afgemeld en onbekend: set_attendance."""
    return set_attendance(record, event_name, AANWEZIG if present else AFWEZIG)

def rename_attendance_event(record: dict, old_name: str, new_name: str) -> None:
    """Houd de aanwezigheidsregistratie mee bij het hernoemen van een evenement."""
    presence = attendance_map(record)
    wanted = normalize(old_name)
    moved = {}
    for name, value in presence.items():
        moved[new_name if normalize(name) == wanted else name] = value
    record["Aanwezig"] = moved

def normalize(value) -> str:
    value = unicodedata.normalize("NFD", str(value or "").strip().lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]", "", value)

def text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()
