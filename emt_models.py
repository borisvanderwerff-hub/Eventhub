from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import uuid


DEFAULT_PROFILE = {
    "name": "",
    "function": "",
    "email": "",
    "phone": "",
    "signature_rank": "",
    "signature_first_name": "",
    "signature_department": "",
    "signature_organization": "Ministerie van Defensie",
}


EVENT_STATUSES = ["Concept", "In voorbereiding", "Gereed", "Afgerond", "Geannuleerd"]
EVENT_TYPES = ["Meeloopdag", "Inloopdag", "Voorlichting", "Online voorlichting"]
DEFAULT_EVENT_TYPE = "Meeloopdag"
ONLINE_EXCLUDED_TASK_CATEGORIES = {"security", "transport", "catering"}

# Wie online kijkt hoeft niet langs de poort, hoeft geen vervoer en eet niet mee.
OFFLINE_EVENT_TYPES = [soort for soort in EVENT_TYPES if soort != "Online voorlichting"]


DEFAULT_TASK_TEMPLATES = [
    {
        "title": "Bezoekers aanmelden bij de beveiliging",
        "event_types": list(OFFLINE_EVENT_TYPES),
        "category": "security",
        "offset_days": 7,
        "relative": "before",
        "reminder_days": 3,
    },
    {
        "title": "Vervoer regelen",
        "event_types": list(OFFLINE_EVENT_TYPES),
        "category": "transport",
        "offset_days": 14,
        "relative": "before",
        "reminder_days": 5,
    },
    {
        "title": "Catering regelen",
        "event_types": list(OFFLINE_EVENT_TYPES),
        "category": "catering",
        "offset_days": 10,
        "relative": "before",
        "reminder_days": 4,
    },
    {
        "title": "Laatste informatie versturen",
        "event_types": list(EVENT_TYPES),
        "category": "communication",
        "offset_days": 5,
        "relative": "before",
        "reminder_days": 2,
    },
    {
        "title": "Deelnemerslijst toevoegen",
        "event_types": list(EVENT_TYPES),
        "category": "participants",
        "offset_days": 7,
        "relative": "before",
        "reminder_days": 2,
        # Bij een Rudder-koppeling is de echte inschrijvingssluiting leidend.
        "use_rudder_closing_date": True,
    },
    {
        "title": "Deelnemers registreren in Rudder",
        "event_types": list(EVENT_TYPES),
        "category": "registration",
        "offset_days": 2,
        "relative": "after",
        "reminder_days": 0,
    },
    {
        "title": "Deelnemers registreren in WENS",
        "event_types": list(EVENT_TYPES),
        "category": "registration",
        "offset_days": 2,
        "relative": "after",
        "reminder_days": 0,
    },
]


# Een evenement dat gereed of afgerond is gemeld, is klaar. De taken zeggen
# dan niets meer: wie het vinkje zet, zegt zelf dat de voorbereiding rond is.
AFGERONDE_STATUSSEN = {"Gereed", "Afgerond"}


def event_tasks(event: dict) -> list:
    return [taak for taak in (event.get("tasks") or []) if isinstance(taak, dict)]


def preparation_progress(event: dict) -> float:
    """Hoe ver de voorbereiding is, als getal tussen 0 en 1.

    De takenlijst is de voorbereiding, dus die telt: het aandeel afgevinkte
    taken. Staat het evenement op gereed of afgerond, dan is het per definitie
    100 procent, ook als er nog taken openstaan.
    """
    if str(event.get("status", "") or "").strip() in AFGERONDE_STATUSSEN:
        return 1.0
    taken = event_tasks(event)
    if not taken:
        return 0.0
    return sum(1 for taak in taken if taak.get("done")) / len(taken)


def preparation_summary(event: dict) -> str:
    """Waarom de balk staat waar hij staat, in gewone woorden."""
    status = str(event.get("status", "") or "").strip()
    if status in AFGERONDE_STATUSSEN:
        return f"{status} gemeld"
    taken = event_tasks(event)
    if not taken:
        return "Nog geen taken"
    klaar = sum(1 for taak in taken if taak.get("done"))
    return f"{klaar} van {len(taken)} taken afgerond"


def parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    value = str(value or "").strip()
    for pattern in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    return None


def date_text(value) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%d-%m-%Y") if parsed else str(value or "").strip()


def prepare_task(source: dict | None = None) -> dict:
    source = source or {}
    relative = str(source.get("relative", "before"))
    if relative not in {"before", "after"}:
        relative = "before"
    try:
        offset_days = max(0, int(source.get("offset_days", 0)))
    except (TypeError, ValueError):
        offset_days = 0
    try:
        reminder_days = max(0, int(source.get("reminder_days", 0)))
    except (TypeError, ValueError):
        reminder_days = 0
    return {
        "id": str(source.get("id") or uuid.uuid4().hex),
        "title": str(source.get("title", "Nieuwe taak") or "Nieuwe taak").strip(),
        "category": str(source.get("category", "") or "").strip().lower(),
        "offset_days": offset_days,
        "relative": relative,
        "reminder_days": reminder_days,
        "done": bool(source.get("done", False)),
        "completed_on": str(source.get("completed_on", "") or "").strip(),
        "notes": str(source.get("notes", "") or ""),
        "use_rudder_closing_date": bool(source.get("use_rudder_closing_date", False)),
    }


def _allowed_by_old_rule(task: dict, event_type: str) -> bool:
    """De vaste regel van voor de instelling: online zonder poort, bus en broodjes.

    Alleen nog in gebruik om standaardtaken die van voor deze versie komen om
    te zetten naar een keuze die je kunt zien en aanpassen.
    """
    if event_type != "Online voorlichting":
        return True
    category = str(task.get("category", "") or "").strip().lower()
    if category in ONLINE_EXCLUDED_TASK_CATEGORIES:
        return False
    title = "".join(character for character in str(task.get("title", "") or "").lower() if character.isalnum())
    excluded_titles = {
        "bezoekersaanmeldenbijdebeveiliging",
        "aanmeldenbijdebeveiliging",
        "vervoerregelen",
        "cateringregelen",
    }
    return title not in excluded_titles


def template_event_types(template: dict) -> list[str]:
    """De soorten evenementen waarvoor deze standaardtaak geldt.

    Een lijst die er niet staat betekent: nog geen keuze gemaakt. Die zetten
    we om met de oude vaste regel, zodat bestaande installaties zich precies
    hetzelfde blijven gedragen. Een lege lijst is wel een keuze - dan staat de
    taak uit.
    """
    gekozen = template.get("event_types")
    if isinstance(gekozen, (list, tuple, set)):
        genoemd = {str(soort).strip() for soort in gekozen}
        return [soort for soort in EVENT_TYPES if soort in genoemd]
    return [soort for soort in EVENT_TYPES if _allowed_by_old_rule(template, soort)]


def prepare_template(source: dict | None = None) -> dict:
    """Een standaardtaak: een taak plus de soorten waarvoor hij geldt."""
    source = source or {}
    template = prepare_task(source)
    template["event_types"] = template_event_types(source)
    return template


def template_scope_text(template: dict) -> str:
    """Voor welke soorten deze taak geldt, in een regel."""
    soorten = template_event_types(template)
    if not soorten:
        return "Geen enkel soort"
    if len(soorten) == len(EVENT_TYPES):
        return "Alle soorten"
    return ", ".join(soorten)


def task_allowed_for_event_type(task: dict, event_type: str) -> bool:
    """Hoort deze standaardtaak bij dit soort evenement?"""
    soort = str(event_type or "").strip()
    if soort not in EVENT_TYPES:
        # Een soort dat we niet kennen krijgt alles; beter een taak te veel
        # dan een evenement zonder planning.
        return True
    return soort in template_event_types(task)


def tasks_from_templates(templates=None, event_type: str = DEFAULT_EVENT_TYPE) -> list[dict]:
    tasks = []
    for template in (templates or DEFAULT_TASK_TEMPLATES):
        if not task_allowed_for_event_type(template, event_type):
            continue
        source = dict(template)
        source.update({"id": "", "done": False, "completed_on": ""})
        tasks.append(prepare_task(source))
    return tasks


def empty_event(name: str = "", task_templates=None, event_type: str = DEFAULT_EVENT_TYPE) -> dict:
    event_type = event_type if event_type in EVENT_TYPES else DEFAULT_EVENT_TYPE
    return {
        "id": uuid.uuid4().hex,
        "name": str(name or "").strip(),
        "template_id": "",
        "template_name": "",
        "event_type": event_type,
        "date": "",
        "start_time": "",
        "end_time": "",
        "region": "",
        "place": "",
        "location": "",
        "location_address": "",
        "location_instructions": "",
        "maximum_registrants": "",
        "external_contact": "",
        "external_contact_reachability": "",
        "status": "Concept",
        "description": "",
        "target_audience": "",
        "exclude_from_analysis": False,
        "whatsapp_template": "",
        "rudder_event_id": "",
        "rudder_attendance_url": "",
        "rudder_edit_url": "",
        "rudder_last_synced_at": "",
        "last_opened_at": "",
        "updated_at": "",
        "rudder_data": {},
        # Aanmeldpagina's die bij dit ene evenement horen. Dezelfde dag staat
        # soms onder meerdere namen online; na het bundelen blijven ze hier
        # staan als herkomst van de deelnemers.
        "listings": [],
        "tasks": tasks_from_templates(task_templates, event_type),
        "fivewh": {},
        "evaluation": {},
        "attachments": [],
    }


def prepare_event(source: dict | None, task_templates=None) -> dict:
    source = source or {}
    event_type = str(source.get("event_type", DEFAULT_EVENT_TYPE) or DEFAULT_EVENT_TYPE).strip()
    if event_type not in EVENT_TYPES:
        event_type = DEFAULT_EVENT_TYPE
    event = empty_event(str(source.get("name", "") or ""), task_templates, event_type)
    for key in (
        "id", "name", "event_type", "date", "start_time", "end_time", "region", "place", "location",
        "location_address", "location_instructions", "maximum_registrants", "external_contact", "external_contact_reachability", "status",
        "description", "target_audience", "whatsapp_template", "rudder_event_id", "rudder_attendance_url",
        "rudder_edit_url", "rudder_last_synced_at",
        # Wanneer je hier voor het laatst was en wanneer er iets veranderde;
        # de evenementkiezer sorteert erop.
        "last_opened_at", "updated_at", "template_id", "template_name",
    ):
        if key in source:
            event[key] = str(source.get(key, "") or "").strip()
    event["exclude_from_analysis"] = bool(source.get("exclude_from_analysis", False))
    if isinstance(source.get("statistiek"), dict):
        event["statistiek"] = deepcopy(source["statistiek"])
    if source.get("persoonsgegevens_gewist"):
        event["persoonsgegevens_gewist"] = str(source["persoonsgegevens_gewist"])
    if not event["id"]:
        event["id"] = uuid.uuid4().hex
    if event["status"] not in EVENT_STATUSES:
        event["status"] = "Concept"
    if isinstance(source.get("tasks"), list):
        event["tasks"] = [prepare_task(task) for task in source["tasks"] if isinstance(task, dict)]
    event["fivewh"] = deepcopy(source.get("fivewh", {})) if isinstance(source.get("fivewh"), dict) else {}
    event["evaluation"] = deepcopy(source.get("evaluation", {})) if isinstance(source.get("evaluation"), dict) else {}
    event["rudder_data"] = deepcopy(source.get("rudder_data", {})) if isinstance(source.get("rudder_data"), dict) else {}
    event["listings"] = [
        {
            "label": str(item.get("label", "") or "").strip(),
            "rudder_event_id": str(item.get("rudder_event_id", "") or "").strip(),
        }
        for item in source.get("listings", [])
        if isinstance(item, dict) and str(item.get("label", "") or "").strip()
    ] if isinstance(source.get("listings"), list) else []
    if isinstance(source.get("attachments"), list):
        event["attachments"] = []
        for attachment in source["attachments"]:
            if not isinstance(attachment, dict):
                continue
            name = str(attachment.get("name", "") or "").strip()
            data = str(attachment.get("data", "") or "")
            if not name or not data:
                continue
            try:
                size = max(0, int(attachment.get("size", 0) or 0))
            except (TypeError, ValueError):
                size = 0
            event["attachments"].append({
                "id": str(attachment.get("id") or uuid.uuid4().hex),
                "name": name,
                "mime_type": str(attachment.get("mime_type", "application/octet-stream") or "application/octet-stream"),
                "size": size,
                "added_at": str(attachment.get("added_at", "") or "").strip(),
                "data": data,
            })
    event["date"] = date_text(event["date"])
    return event


def task_due_date(event: dict, task: dict) -> date | None:
    event_date = parse_date(event.get("date", ""))
    if not event_date:
        return None
    if task.get("use_rudder_closing_date"):
        rudder = event.get("rudder_data", {}) if isinstance(event.get("rudder_data"), dict) else {}
        # Rudder levert doorgaans het aantal dagen vóór het evenement. Als een
        # concrete vervaldatum aanwezig is, is die een bruikbare terugval.
        try:
            closing_days = int(str(rudder.get("prior_closing_days", "") or "").strip())
        except (TypeError, ValueError):
            closing_days = -1
        if closing_days >= 0:
            return event_date - timedelta(days=closing_days)
        explicit_closing = parse_date(
            rudder.get("registration_closing_date", "") or rudder.get("expiration_date", "")
        )
        if explicit_closing:
            return explicit_closing
    days = max(0, int(task.get("offset_days", 0) or 0))
    if task.get("relative") == "after":
        return event_date + timedelta(days=days)
    return event_date - timedelta(days=days)


def task_timing_text(task: dict) -> str:
    days = max(0, int(task.get("offset_days", 0) or 0))
    when = "na" if task.get("relative") == "after" else "vóór"
    unit = "dag" if days == 1 else "dagen"
    text = f"{days} {unit} {when} het evenement"
    if task.get("use_rudder_closing_date"):
        return f"Rudder-sluitingsdatum, anders {text}"
    return text


def task_state(event: dict, task: dict, today: date | None = None) -> str:
    if task.get("done"):
        return "Afgerond"
    due = task_due_date(event, task)
    if not due:
        return "Geen evenementdatum"
    today = today or date.today()
    if due < today:
        return "Te laat"
    if due == today:
        return "Vandaag"
    days = (due - today).days
    return f"Over {days} dag" if days == 1 else f"Over {days} dagen"


def task_notifications(events: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    notifications = []
    for event in events:
        if event.get("status") in {"Geannuleerd"}:
            continue
        for task in event.get("tasks", []):
            if task.get("done"):
                continue
            due = task_due_date(event, task)
            if not due:
                continue
            reminder_days = max(0, int(task.get("reminder_days", 0) or 0))
            if today < due - timedelta(days=reminder_days):
                continue
            days_until = (due - today).days
            if days_until < 0:
                severity = "overdue"
                message = f"{abs(days_until)} dag(en) te laat"
            elif days_until == 0:
                severity = "today"
                message = "Vandaag uitvoeren"
            else:
                severity = "soon"
                message = f"Binnen {days_until} dag(en) uitvoeren"
            notifications.append({
                "event_id": event.get("id", ""),
                "event_name": event.get("name", "Onbenoemd evenement"),
                "task_id": task.get("id", ""),
                "task_title": task.get("title", "Taak"),
                "due": due,
                "severity": severity,
                "message": message,
            })
    order = {"overdue": 0, "today": 1, "soon": 2}
    return sorted(notifications, key=lambda item: (order[item["severity"]], item["due"], item["event_name"], item["task_title"]))
