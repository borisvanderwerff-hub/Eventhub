"""Bewaartermijn voor persoonsgegevens van bezoekers.

Na afloop van een evenement blijven de persoonsgegevens van bezoekers nog een
beperkte periode beschikbaar. Daarna worden de deelnemersrijen onomkeerbaar
verwijderd en blijft uitsluitend de geaggregeerde momentopname op het
evenement over: aantallen, opkomstpercentage en verdelingen. Die cijfers zijn
niet naar een persoon herleidbaar.

Bewust Qt- en I/O-vrij gehouden zodat de logica los te testen is; het
opschonen van bestanden en databases gebeurt in de aanroepende laag.
"""
from __future__ import annotations

from datetime import date, timedelta

from bezoekerslijst_core import normalize, record_events
from emt_models import parse_date

# Eén applicatiebrede termijn. Langer dan twee maanden is bewust niet mogelijk:
# de termijn hoort verantwoordbaar te blijven en niet per geval op te rekken.
RETENTION_MAX_DAYS = 60
RETENTION_DEFAULT_DAYS = 21
RETENTION_CHOICES = (7, 14, 21, 30, 60)


def clamp_retention_days(value) -> int:
    """Houd de termijn binnen 1 tot RETENTION_MAX_DAYS dagen."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return RETENTION_DEFAULT_DAYS
    return max(1, min(RETENTION_MAX_DAYS, days))


def event_expiry_date(event: dict, retention_days: int) -> date | None:
    """De dag waarop de persoonsgegevens van dit evenement verlopen."""
    event_date = parse_date(event.get("date", ""))
    if not event_date:
        return None
    return event_date + timedelta(days=clamp_retention_days(retention_days))


def is_event_expired(event: dict, retention_days: int, today: date | None = None) -> bool:
    """Een evenement zonder datum verloopt nooit: de termijn is dan niet vast te stellen."""
    if event.get("persoonsgegevens_gewist"):
        return False
    expiry = event_expiry_date(event, retention_days)
    return bool(expiry and (today or date.today()) >= expiry)


def expired_events(events: list[dict], retention_days: int, today: date | None = None) -> list[dict]:
    return [event for event in events if is_event_expired(event, retention_days, today)]


def plan_retention_cleanup(
    events: list[dict],
    records: list[dict],
    retention_days: int,
    today: date | None = None,
) -> dict:
    """Bepaal wat er zou worden verwijderd, zonder iets te wijzigen.

    Een bezoeker wordt alleen verwijderd wanneer *elk* evenement waaraan die
    gekoppeld is verlopen is. Wie ook op een komend evenement staat, blijft
    volledig staan; anders zouden de gegevens verdwijnen die voor dat komende
    evenement nog nodig zijn.

    Een koppeling aan een onbekend evenement laat de bezoeker eveneens staan:
    zonder datum is de bewaartermijn niet vast te stellen, en bij
    onomkeerbaar verwijderen is niet-verwijderen de veilige uitkomst.
    """
    today = today or date.today()
    retention_days = clamp_retention_days(retention_days)

    due_events = expired_events(events, retention_days, today)
    due_names = {normalize(event.get("name", "")) for event in due_events}
    known_names = {normalize(event.get("name", "")) for event in events}

    removable: list[dict] = []
    kept_upcoming: list[dict] = []
    kept_unknown: list[dict] = []

    for record in records:
        linked = {normalize(name) for name in record_events(record)}
        if not linked or not (linked & due_names):
            continue
        if not linked <= known_names:
            kept_unknown.append(record)
        elif linked <= due_names:
            removable.append(record)
        else:
            kept_upcoming.append(record)

    per_event = []
    removable_ids = {id(record) for record in removable}
    for event in due_events:
        wanted = normalize(event.get("name", ""))
        linked = [
            record for record in records
            if wanted in {normalize(name) for name in record_events(record)}
        ]
        per_event.append({
            "id": event.get("id", ""),
            "name": event.get("name", ""),
            "date": event.get("date", ""),
            "expires_on": (event_expiry_date(event, retention_days) or today).strftime("%d-%m-%Y"),
            "records": len(linked),
            "records_removed": sum(1 for record in linked if id(record) in removable_ids),
        })

    return {
        "retention_days": retention_days,
        "peildatum": today.strftime("%d-%m-%Y"),
        "events": per_event,
        "records_removed": len(removable),
        "records_kept_upcoming": len(kept_upcoming),
        "records_kept_unknown": len(kept_unknown),
        "_removable": removable,
    }


def has_work(plan: dict) -> bool:
    return bool(plan.get("records_removed") or plan.get("events"))


# Zoveel dagen vooraf verschijnt de aankondiging in het meldingenoverzicht.
RETENTION_WARNING_DAYS = 7


def retention_notifications(
    events: list[dict],
    records: list[dict],
    retention_days: int,
    today: date | None = None,
    warning_days: int = RETENTION_WARNING_DAYS,
) -> list[dict]:
    """Kondig aan welke evenementen hun persoonsgegevens binnenkort verliezen.

    Verwijderen gebeurt automatisch; deze meldingen zijn het moment waarop nog
    geëxporteerd kan worden. Alleen evenementen die daadwerkelijk deelnemers
    kwijtraken worden gemeld: een aankondiging zonder gevolgen is ruis.
    """
    today = today or date.today()
    retention_days = clamp_retention_days(retention_days)
    horizon = today + timedelta(days=max(0, warning_days))

    counts: dict[str, int] = {}
    known = {normalize(event.get("name", "")) for event in events}
    for record in records:
        linked = {normalize(name) for name in record_events(record)}
        if not linked or not linked <= known:
            continue
        for name in linked:
            counts[name] = counts.get(name, 0) + 1

    notifications = []
    for event in events:
        if event.get("persoonsgegevens_gewist"):
            continue
        expiry = event_expiry_date(event, retention_days)
        if not expiry or expiry > horizon or expiry <= today:
            continue
        affected = counts.get(normalize(event.get("name", "")), 0)
        if not affected:
            continue
        days_until = (expiry - today).days
        notifications.append({
            "event_id": event.get("id", ""),
            "event_name": event.get("name", "Onbenoemd evenement"),
            "task_id": "",
            "task_title": "Persoonsgegevens worden gewist",
            "due": expiry,
            "severity": "retention",
            "message": (
                f"Morgen: {affected} deelnemer(s) worden verwijderd"
                if days_until == 1
                else f"Over {days_until} dagen: {affected} deelnemer(s) worden verwijderd"
            ),
        })
    return sorted(notifications, key=lambda item: (item["due"], item["event_name"]))


def apply_retention_cleanup(
    events: list[dict],
    records: list[dict],
    retention_days: int,
    today: date | None = None,
    plan: dict | None = None,
) -> dict:
    """Verwijder de verlopen deelnemersrijen. Onomkeerbaar.

    Geeft het uitgevoerde plan terug. De aanroeper is ervoor verantwoordelijk
    dat de momentopname per evenement al is vastgelegd: na deze bewerking is
    die de enige overgebleven bron van cijfers.
    """
    today = today or date.today()
    plan = plan or plan_retention_cleanup(events, records, retention_days, today)
    doomed = {id(record) for record in plan.get("_removable", [])}

    records[:] = [record for record in records if id(record) not in doomed]

    stamp = today.strftime("%d-%m-%Y")
    for summary in plan.get("events", []):
        for event in events:
            if event.get("id", "") == summary["id"] and not event.get("persoonsgegevens_gewist"):
                event["persoonsgegevens_gewist"] = stamp
    return plan


def scrub_payload(payload: dict, retention_days: int, today: date | None = None) -> dict:
    """Pas de bewaartermijn toe op een ingelezen .bvp-payload.

    Gebruikt voor back-ups en herstelkopieën: die bevatten dezelfde
    persoonsgegevens als het hoofddossier en moeten dus mee opgeschoond.
    """
    events = payload.get("events") or []
    records = payload.get("records") or []
    plan = apply_retention_cleanup(events, records, retention_days, today)
    payload["records"] = records
    payload["events"] = events
    return plan
