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


DEFAULT_TASK_TEMPLATES = [
    {
        "title": "Bezoekers aanmelden bij de beveiliging",
        "category": "security",
        "offset_days": 7,
        "relative": "before",
        "reminder_days": 3,
    },
    {
        "title": "Vervoer regelen",
        "category": "transport",
        "offset_days": 14,
        "relative": "before",
        "reminder_days": 5,
    },
    {
        "title": "Catering regelen",
        "category": "catering",
        "offset_days": 10,
        "relative": "before",
        "reminder_days": 4,
    },
    {
        "title": "Laatste informatie versturen",
        "category": "communication",
        "offset_days": 5,
        "relative": "before",
        "reminder_days": 2,
    },
    {
        "title": "Deelnemers registreren in Rudder",
        "category": "registration",
        "offset_days": 2,
        "relative": "after",
        "reminder_days": 0,
    },
    {
        "title": "Deelnemers registreren in WENS",
        "category": "registration",
        "offset_days": 2,
        "relative": "after",
        "reminder_days": 0,
    },
]


EVENT_STATUSES = ["Concept", "In voorbereiding", "Gereed", "Afgerond", "Geannuleerd"]
EVENT_TYPES = ["Meeloopdag", "Voorlichting", "Online voorlichting"]
DEFAULT_EVENT_TYPE = "Meeloopdag"
ONLINE_EXCLUDED_TASK_CATEGORIES = {"security", "transport", "catering"}


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
    }


def task_allowed_for_event_type(task: dict, event_type: str) -> bool:
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
        "whatsapp_template": "",
        "rudder_event_id": "",
        "rudder_attendance_url": "",
        "rudder_edit_url": "",
        "rudder_last_synced_at": "",
        "rudder_data": {},
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
    ):
        if key in source:
            event[key] = str(source.get(key, "") or "").strip()
    if not event["id"]:
        event["id"] = uuid.uuid4().hex
    if event["status"] not in EVENT_STATUSES:
        event["status"] = "Concept"
    if isinstance(source.get("tasks"), list):
        event["tasks"] = [prepare_task(task) for task in source["tasks"] if isinstance(task, dict)]
    event["fivewh"] = deepcopy(source.get("fivewh", {})) if isinstance(source.get("fivewh"), dict) else {}
    event["evaluation"] = deepcopy(source.get("evaluation", {})) if isinstance(source.get("evaluation"), dict) else {}
    event["rudder_data"] = deepcopy(source.get("rudder_data", {})) if isinstance(source.get("rudder_data"), dict) else {}
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
    days = max(0, int(task.get("offset_days", 0) or 0))
    if task.get("relative") == "after":
        return event_date + timedelta(days=days)
    return event_date - timedelta(days=days)


def task_timing_text(task: dict) -> str:
    days = max(0, int(task.get("offset_days", 0) or 0))
    when = "na" if task.get("relative") == "after" else "vóór"
    unit = "dag" if days == 1 else "dagen"
    return f"{days} {unit} {when} het evenement"


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
