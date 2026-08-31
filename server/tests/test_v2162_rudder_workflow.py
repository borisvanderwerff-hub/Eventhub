import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from emt_rudder import (
    RUDDER_EVENTS_OVERVIEW_URL,
    canonical_rudder_url,
    event_type_for_eventhub,
    is_rudder_event_linked,
    matching_eventhub_template,
    rudder_eventhub_updates,
    sanitize_rudder_event_payload,
)


SAMPLE = {
    "format": "EventHub Rudder Event",
    "version": 1,
    "event_id": "5900",
    "data": {
        "active": True,
        "event_template": "Meeloopdag Marine (Varend)",
        "event_type": "Meeloopdag",
        "dates": [
            {"date": "2026-09-02", "start_time": "09:00", "end_time": "16:00"},
            {"date": "2026-09-01", "start_time": "09:00", "end_time": "16:00"},
        ],
        "event_location": "Nieuwe Haven Den Helder",
        "location_address": "Rijkszee- en Marinehaven 1, 1781 ZZ Den Helder",
        "minimal_education": "VMBO Basis",
        "minimal_age": "16",
        "maximal_age": "35",
    },
}


class RudderWorkflowTests(unittest.TestCase):
    def test_attendance_only_metadata_is_not_an_event_link(self):
        attendance_only = {
            "rudder_event_id": "5900",
            "rudder_attendance_url": canonical_rudder_url("5900", "attendance"),
        }
        self.assertFalse(is_rudder_event_linked(attendance_only))

        imported = sanitize_rudder_event_payload(SAMPLE)
        linked = {
            "rudder_event_id": imported["event_id"],
            "rudder_edit_url": imported["edit_url"],
            "rudder_last_synced_at": "2026-08-27T10:30:00",
            "rudder_data": imported["data"],
        }
        self.assertTrue(is_rudder_event_linked(linked))

    def test_rudder_type_maps_exactly_and_template_can_be_matched(self):
        self.assertEqual(event_type_for_eventhub("Online voorlichting"), "Online voorlichting")
        imported = sanitize_rudder_event_payload(SAMPLE)
        templates = [
            {"name": "Voorlichting"},
            {"name": "Meeloopdag Marine (Varend)", "event": {"tasks": [{"title": "Bus regelen"}]}},
        ]
        self.assertEqual(matching_eventhub_template(imported, templates)["name"], "Meeloopdag Marine (Varend)")

    def test_core_event_info_uses_earliest_date_place_and_audience(self):
        updates = rudder_eventhub_updates(sanitize_rudder_event_payload(SAMPLE))
        self.assertEqual(updates["date"], "01-09-2026")
        self.assertEqual(updates["place"], "Den Helder")
        self.assertEqual(updates["target_audience"], "Opleiding vanaf VMBO Basis · Leeftijd 16–35 jaar")

    def test_desktop_flow_uses_overview_then_linked_update(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertEqual(RUDDER_EVENTS_OVERVIEW_URL, "https://werkenbijdefensie.nl/rudder/event/events")
        self.assertIn('destination_url = canonical_rudder_url(expected_event_id, "edit") if linked else RUDDER_EVENTS_OVERVIEW_URL', source)
        self.assertIn('self.rudder_import_button.setText("Bijwerken uit Rudder" if connected else "Importeren uit Rudder")', source)
        self.assertIn("self.rudder_export_button.setVisible(connected)", source)
        self.assertIn("self.rudder_open_button.setVisible(connected)", source)
        poll = source[source.index("def _poll_rudder_event_import"):source.index("def _apply_rudder_event_import")]
        self.assertNotIn("RudderImportPreviewDialog", poll)

    def test_overview_passes_import_reference_to_selected_event(self):
        manifest = json.loads((ROOT / "browser_extension" / "manifest.json").read_text(encoding="utf-8"))
        # Niet het nummer vastpinnen; dat brak bij elke legitieme ophoging.
        # Wat telt is dat de assistent niet terugvalt naar een oudere versie.
        versie = tuple(int(deel) for deel in manifest["version"].split("."))
        self.assertGreaterEqual(versie, (1, 3, 0))
        scripts = {script for entry in manifest["content_scripts"] for script in entry["js"]}
        self.assertIn("event_list.js", scripts)
        overview = (ROOT / "browser_extension" / "event_list.js").read_text(encoding="utf-8")
        edit = (ROOT / "browser_extension" / "event_edit.js").read_text(encoding="utf-8")
        self.assertIn('sessionStorage.setItem(PENDING_KEY', overview)
        self.assertIn('target.hash = `eventhub-import=', overview)
        self.assertIn("readPendingImportReference", edit)

    def test_import_uses_matching_template_tasks_without_duplicates(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        block = source[source.index("def _apply_rudder_event_import"):source.index("def export_event_to_rudder")]
        self.assertIn("matching_eventhub_template(imported, self.project_templates)", block)
        self.assertIn('existing_titles = {normalize(task.get("title", ""))', block)
        self.assertIn("task_allowed_for_event_type(task, event_type)", block)
        self.assertIn('"done": False, "completed_on": ""', block)


if __name__ == "__main__":
    unittest.main()
