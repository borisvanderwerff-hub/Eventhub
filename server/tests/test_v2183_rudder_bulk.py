"""Meerdere Rudder-evenementen in een keer importeren."""
import json
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jslint import check_brackets

EXTENSION = ROOT / "browser_extension"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rudder_events_overview.html"
APP_SOURCE = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")


class ScriptStructureTests(unittest.TestCase):
    """Er is hier geen JS-parser; dit vangt wat handmatig bewerken stukmaakt."""

    def test_every_extension_script_has_balanced_brackets(self):
        for path in sorted(EXTENSION.glob("*.js")):
            with self.subTest(script=path.name):
                self.assertIsNone(check_brackets(path.read_text(encoding="utf-8")))

    def test_the_web_client_scripts_are_checked_too(self):
        for path in sorted((ROOT / "server/web/static/js").glob("*.js")):
            with self.subTest(script=path.name):
                self.assertIsNone(check_brackets(path.read_text(encoding="utf-8")))

    def test_the_checker_actually_catches_an_error(self):
        """Zonder deze test zou een kapotte checker alles laten passeren."""
        self.assertIsNotNone(check_brackets("function x() { if (a) { return 1; }"))
        self.assertIsNotNone(check_brackets("const a = [1, 2;"))
        # Een apostrof in commentaar en // in een url mogen geen vals alarm geven.
        self.assertIsNone(check_brackets("// pagina's tellen\nfetch(`http://x/${y}`);"))


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))

    def test_version_was_raised_for_the_bulk_import(self):
        self.assertEqual(self.manifest["version"], "1.4.0")

    def test_the_shared_scraper_loads_before_the_scripts_that_use_it(self):
        for entry in self.manifest["content_scripts"]:
            scripts = entry["js"]
            if "event_edit.js" in scripts or "event_list.js" in scripts:
                with self.subTest(match=entry["matches"][0]):
                    self.assertEqual(scripts[0], "rudder_scrape.js")

    def test_the_overview_page_also_loads_the_bulk_script(self):
        overview = next(
            entry for entry in self.manifest["content_scripts"]
            if "event_list.js" in entry["js"]
        )
        self.assertIn("event_bulk.js", overview["js"])

    def test_no_new_permissions_were_added(self):
        self.assertEqual(self.manifest["host_permissions"], ["http://127.0.0.1/*"])


class SelectorTests(unittest.TestCase):
    """De selectors moeten passen op de opmaak die Rudder werkelijk levert."""

    def setUp(self):
        self.page = FIXTURE.read_text(encoding="utf-8")
        self.scraper = (EXTENSION / "rudder_scrape.js").read_text(encoding="utf-8")

    def _selectors_used_for(self, function_name):
        start = self.scraper.index(f"function {function_name}(")
        block = self.scraper[start:self.scraper.index("\n  }", start)]
        return re.findall(r'querySelector(?:All)?\(["\']([^"\']+)["\']\)', block)

    def test_event_cards_are_found_by_their_class(self):
        for selector in self._selectors_used_for("scrapeEventList"):
            plain = selector.replace(".", " ").replace("[", " ").split()[0]
            with self.subTest(selector=selector):
                self.assertIn(plain, self.page, f"{selector} komt niet voor in de opmaak")

    def test_the_card_fields_the_scraper_reads_exist(self):
        for klass in ("event-card__title", "event-card__meta", "event-card__byline",
                      "event-card__status"):
            with self.subTest(klass=klass):
                self.assertIn(klass, self.page)

    def test_edit_links_carry_the_event_id(self):
        ids = re.findall(r"/events/(\d+)/edit", self.page)
        self.assertEqual(sorted(set(ids)), ["5814", "5900", "6081"])

    def test_pagination_links_are_present(self):
        pages = sorted({int(n) for n in re.findall(r"[?&]page=(\d+)", self.page)})
        self.assertIn(24, pages, "de paginering moet uitleesbaar zijn")

    def test_rudder_filters_on_owner_itself(self):
        """Daarom hoeft de assistent niet zelf op naam te filteren."""
        self.assertIn('name="user"', self.page)


class BridgeBatchTests(unittest.TestCase):
    """De brug was eenmalig; voor een reeks moet hij openblijven."""

    def _post(self, port, token, payload):
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/event?token={token}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read())

    def setUp(self):
        from bezoekerslijst_app import RudderLocalBridge
        self.factory = RudderLocalBridge

    def test_batch_mode_collects_every_event(self):
        bridge = self.factory(receive_event=True, batch=True, lifetime_seconds=30)
        port, token = bridge.start()
        try:
            for index in range(3):
                answer = self._post(port, token, {"event_id": str(index), "data": {}})
                self.assertEqual(answer["received"], index + 1)
            received = bridge.take_received_batch()
            self.assertEqual([item["event_id"] for item in received], ["0", "1", "2"])
            self.assertEqual(bridge.take_received_batch(), [], "de lijst moet leeg achterblijven")
        finally:
            bridge.stop()

    def test_single_use_mode_still_closes_after_one_event(self):
        bridge = self.factory(receive_event=True, lifetime_seconds=30)
        port, token = bridge.start()
        try:
            self._post(port, token, {"event_id": "1", "data": {}})
            threading.Event().wait(0.5)
            with self.assertRaises(urllib.error.URLError):
                self._post(port, token, {"event_id": "2", "data": {}})
        finally:
            bridge.stop()

    def test_a_wrong_token_is_refused(self):
        bridge = self.factory(receive_event=True, batch=True, lifetime_seconds=30)
        port, _token = bridge.start()
        try:
            with self.assertRaises(urllib.error.HTTPError):
                self._post(port, "0" * 64, {"event_id": "1", "data": {}})
        finally:
            bridge.stop()


class PreviewTests(unittest.TestCase):
    """Bestaande evenementen bijwerken in plaats van dupliceren."""

    def setUp(self):
        from bezoekerslijst_app import BezoekerslijstWindow
        self.window = BezoekerslijstWindow.__new__(BezoekerslijstWindow)
        self.window.events = [
            {"id": "a", "name": "Meeloopdag Marine", "rudder_event_id": "5900"},
            {"id": "b", "name": "Los evenement"},
        ]

    def test_known_rudder_events_are_marked_for_update(self):
        nieuw, bijwerken = self.window._rudder_bulk_preview([
            {"event_id": "5900", "data": {}},
            {"event_id": "6081", "data": {}},
        ])
        self.assertEqual([item["event_id"] for item, _ in nieuw], ["6081"])
        self.assertEqual([item["event_id"] for item, _ in bijwerken], ["5900"])
        self.assertEqual(bijwerken[0][1]["id"], "a")

    def test_events_without_a_rudder_link_never_match(self):
        nieuw, bijwerken = self.window._rudder_bulk_preview([{"event_id": "", "data": {}}])
        self.assertEqual(len(nieuw), 1)
        self.assertEqual(bijwerken, [])


class WiringTests(unittest.TestCase):
    def test_the_events_page_offers_the_bulk_import(self):
        self.assertIn("self.bulk_import_button", APP_SOURCE)
        self.assertIn("def import_rudder_events_bulk(self", APP_SOURCE)

    def test_the_bulk_import_opens_the_overview_not_a_single_event(self):
        start = APP_SOURCE.index("def import_rudder_events_bulk(self")
        block = APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]
        self.assertIn("RUDDER_EVENTS_OVERVIEW_URL", block)
        self.assertIn("eventhub-import-all=", block)
        self.assertIn("batch=True", block)

    def test_a_done_signal_closes_the_batch(self):
        start = APP_SOURCE.index("def _poll_rudder_bulk_import(self")
        block = APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]
        self.assertIn('"done"', block)

    def test_the_assistant_only_reads_from_rudder(self):
        """De bulkimport mag niets in Rudder wijzigen."""
        bulk = (EXTENSION / "event_bulk.js").read_text(encoding="utf-8")
        self.assertIn('credentials: "same-origin"', bulk)
        for verb in ('method: "POST"', 'method: "PUT"', 'method: "DELETE"'):
            self.assertNotIn(verb, bulk, "de assistent hoort alleen te lezen")


if __name__ == "__main__":
    unittest.main()
