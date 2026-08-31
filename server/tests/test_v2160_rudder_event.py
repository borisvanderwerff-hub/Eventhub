import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from emt_models import prepare_event
from emt_rudder import (
    canonical_rudder_url,
    rudder_event_id_from_url,
    rudder_eventhub_updates,
    rudder_export_package,
    sanitize_rudder_event_payload,
)


SAMPLE = {
    "format": "EventHub Rudder Event",
    "version": 1,
    "event_id": "5900",
    "data": {
        "active": True,
        "event_template_id": "415",
        "event_template": "Meeloopdag Marine (Varend)",
        "event_type": "Meeloopdag",
        "form_type": "Uitgebreid",
        "owner_id": "468",
        "owner": "Boris van der Werff",
        "dates": [{"id": "5563", "date": "2026-08-19", "start_time": "09:00", "end_time": "16:00"}],
        "event_location_id": "11",
        "event_location": "Nieuwe Haven Den Helder",
        "location_address": "Rijkszee- en Marinehaven 1, 1781ZZ Den Helder",
        "license_plate_registration": False,
        "allows_invitees": True,
        "invitees_per_registrant": "1",
        "minimal_education": "VMBO Basis",
        "minimal_age": "16",
        "maximal_age": "35",
        "has_emails_enabled": True,
        "csrf_token": "must-never-survive",
    },
}


class RudderEventTests(unittest.TestCase):
    def test_url_validation_and_canonical_urls(self):
        self.assertEqual(rudder_event_id_from_url("https://werkenbijdefensie.nl/rudder/event/events/5900/edit"), "5900")
        self.assertEqual(rudder_event_id_from_url("https://werkenbijdefensie.nl/rudder/event/events/5900/attendance"), "5900")
        self.assertEqual(rudder_event_id_from_url("https://example.com/rudder/event/events/5900/edit"), "")
        self.assertEqual(canonical_rudder_url("5900", "edit"), "https://werkenbijdefensie.nl/rudder/event/events/5900/edit")

    def test_sanitizer_keeps_allowlist_and_drops_email_security_fields(self):
        imported = sanitize_rudder_event_payload(SAMPLE)
        self.assertEqual(imported["event_id"], "5900")
        self.assertEqual(imported["data"]["owner"], "Boris van der Werff")
        self.assertNotIn("has_emails_enabled", imported["data"])
        self.assertNotIn("csrf_token", imported["data"])

    def test_import_maps_core_event_fields(self):
        imported = sanitize_rudder_event_payload(SAMPLE)
        updates = rudder_eventhub_updates(imported)
        self.assertEqual(updates["name"], "Meeloopdag Marine (Varend)")
        self.assertEqual(updates["date"], "19-08-2026")
        self.assertEqual(updates["location"], "Nieuwe Haven Den Helder")

    def test_model_roundtrip_preserves_rudder_snapshot(self):
        imported = sanitize_rudder_event_payload(SAMPLE)
        event = prepare_event({
            "name": "Meeloopdag Marine (Varend) (19_08_2026)",
            "date": "19-08-2026",
            "rudder_event_id": imported["event_id"],
            "rudder_edit_url": imported["edit_url"],
            "rudder_last_synced_at": "2026-08-26T12:34:00",
            "rudder_data": imported["data"],
        })
        self.assertEqual(event["rudder_data"]["event_location_id"], "11")
        package = rudder_export_package(event)
        self.assertEqual(package["event_id"], "5900")
        self.assertEqual(package["data"]["dates"][0]["date"], "2026-08-19")

    def test_extension_supports_edit_page_without_automatic_submit(self):
        manifest = json.loads((ROOT / "browser_extension" / "manifest.json").read_text(encoding="utf-8"))
        matches = [match for script in manifest["content_scripts"] for match in script["matches"]]
        self.assertIn("https://werkenbijdefensie.nl/rudder/event/events/*/edit*", matches)
        source = (ROOT / "browser_extension" / "event_edit.js").read_text(encoding="utf-8")
        self.assertNotIn(".submit()", source)
        self.assertNotIn('setValue("item[event_template_id]"', source)
        self.assertIn("klik zelf op de Rudder-opslagknop", source)

    def test_import_button_uses_one_click_bridge_and_existing_tabs(self):
        source = (ROOT / "browser_extension" / "event_edit.js").read_text(encoding="utf-8")
        self.assertIn('launcher.textContent = "Importeren naar EventHub"', source)
        self.assertIn('launcher.addEventListener("click", sendImportToEventHub)', source)
        self.assertIn('window.addEventListener("hashchange", handleBridge)', source)
        self.assertIn("sessionStorage.setItem(importStorageKey()", source)
        self.assertIn("IMPORT_REFERENCE_LIFETIME_MS = 5 * 60 * 1000", source)
        import_branch = source[source.index("if (importing) {"):source.index('launcher.textContent = "EventHub-evenement ophalen…"')]
        self.assertIn("storeImportReference(importing)", import_branch)
        self.assertNotIn('chrome.runtime.sendMessage({type:"eventhub-send-event"', import_branch)

    def test_browser_assistant_patch_version_is_updated(self):
        manifest = json.loads((ROOT / "browser_extension" / "manifest.json").read_text(encoding="utf-8"))
        # Niet het nummer vastpinnen; dat brak bij elke legitieme ophoging.
        # Wat telt is dat de assistent niet terugvalt naar een oudere versie.
        versie = tuple(int(deel) for deel in manifest["version"].split("."))
        self.assertGreaterEqual(versie, (1, 3, 0))

    def test_manual_link_does_not_clear_unknown_rudder_fields(self):
        package = rudder_export_package({"date": "19-08-2026", "rudder_event_id": "5900", "rudder_data": {}})
        self.assertEqual(package["known_fields"], ["dates"])
        self.assertEqual(package["data"]["dates"][0]["date"], "2026-08-19")


if __name__ == "__main__":
    unittest.main()
