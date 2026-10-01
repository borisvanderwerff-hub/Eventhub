"""Reusable event defaults. Never carry registrations or session identity."""
from copy import deepcopy

from emt_models import empty_event, prepare_event, prepare_task, parse_date, task_due_date
from bezoekerslijst_core import event_base_name


DEFAULT_FIELDS = (
    "name", "event_type", "location", "location_address", "location_instructions",
    "region", "place", "description", "target_audience", "maximum_registrants",
)


def template_event_data(event, include_tasks=True):
    result = {key: deepcopy(event.get(key, "")) for key in DEFAULT_FIELDS}
    result["name"] = event_base_name(result["name"])
    result["tasks"] = []
    if include_tasks:
        for task in event.get("tasks", []):
            item = prepare_task(task)
            if item["use_rudder_closing_date"]:
                base, due = parse_date(event.get("date")), task_due_date(event, task)
                if base and due:
                    days = (due - base).days
                    item.update(relative="after" if days > 0 else "before", offset_days=abs(days))
            item.update(id="", done=False, completed_on="", use_rudder_closing_date=False)
            result["tasks"].append(item)
    return result


def event_from_template(template):
    source = template_event_data(template.get("event", {}))
    event = empty_event(source.get("name", ""), event_type=source.get("event_type", "Meeloopdag"))
    event.update(source)
    event.update(template_id=str(template["id"]), template_name=str(template["name"]))
    return prepare_event(event)
