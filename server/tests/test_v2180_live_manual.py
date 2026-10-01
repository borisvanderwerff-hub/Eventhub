"""Handleiding livesessies: klopt hij met de werkelijke schermen?"""
from datetime import date
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from emt_live_manual import MANUAL_TITLE, manual_html, manual_sections

CONNECT_PAGE = (ROOT / "server/web/templates/connect.html").read_text(encoding="utf-8")
APP_SOURCE = desktop_source(ROOT)


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.html = manual_html("Boris van der Werff", date(2026, 5, 1))
        self.text = " ".join(
            item for _, items in manual_sections() for item in items
        ).casefold()

    def test_covers_the_whole_flow(self):
        titles = [title for title, _ in manual_sections()]
        self.assertIn("Wat u nodig heeft", titles)
        self.assertTrue(any("sessie starten" in t.casefold() for t in titles))
        self.assertTrue(any("aanmelden" in t.casefold() for t in titles))
        self.assertTrue(any("inchecken" in t.casefold() for t in titles))
        self.assertTrue(any("misgaat" in t.casefold() for t in titles))
        self.assertTrue(any("calamiteiten" in t.casefold() for t in titles))

    def test_warns_that_a_device_starts_as_viewer(self):
        """Zonder rol kan niemand inchecken; dat is de meest gestelde vraag."""
        self.assertIn("viewer", self.text)
        self.assertIn("rol", self.text)

    def test_explains_that_no_internet_is_needed(self):
        self.assertIn("internet is niet nodig", self.text)
        self.assertIn("hetzelfde wifi", self.text)

    def test_mentions_offline_queueing(self):
        self.assertIn("bewaart de handelingen", self.text)

    def test_contains_no_personal_data(self):
        for personal in ("geboortedatum van", "achternaam:", "telefoonnummer:"):
            self.assertNotIn(personal, self.html.casefold())

    def test_names_the_author_and_date(self):
        self.assertIn("Boris van der Werff", self.html)
        self.assertIn("01-05-2026", self.html)

    def test_works_without_an_author(self):
        html = manual_html()
        self.assertIn(MANUAL_TITLE, html)
        self.assertNotIn("opgesteld door", html)


class AccuracyTests(unittest.TestCase):
    """De handleiding moet de echte schermen beschrijven, niet een bedachte."""

    def setUp(self):
        self.text = " ".join(
            item for _, items in manual_sections() for item in items
        )

    def test_device_name_and_session_code_exist_on_the_connect_page(self):
        self.assertIn("apparaatnaam", self.text.casefold())
        self.assertIn("sessiecode", self.text.casefold())
        self.assertIn('id="clientNameInput"', CONNECT_PAGE)
        self.assertIn('id="eventCodeInput"', CONNECT_PAGE)

    def test_search_fields_match_the_client(self):
        self.assertIn("naam, geboortedatum of geboorteplaats", self.text.casefold())
        self.assertIn("Naam, geboortedatum of geboorteplaats", CONNECT_PAGE)

    def test_named_buttons_exist_in_the_client(self):
        for label in ("Nu synchroniseren", "Inchecken pauzeren", "Personen controleren"):
            self.assertIn(label, self.text, f"handleiding noemt {label} niet")
            self.assertIn(label, CONNECT_PAGE, f"{label} bestaat niet meer in de client")

    def test_the_app_offers_the_manual_next_to_the_help_button(self):
        self.assertIn("self.live_manual_button", APP_SOURCE)
        self.assertIn("def open_live_session_manual(self)", APP_SOURCE)

    def _manual_block(self):
        start = APP_SOURCE.index("def open_live_session_manual(self)")
        return APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]

    def test_the_manual_opens_instead_of_asking_where_to_save(self):
        """Een bestand dat vrijwel niemand terugleest hoeft niet bewaard."""
        block = self._manual_block()
        self.assertNotIn("getSaveFileName", block)
        self.assertNotIn("_offer_open_export_folder", block)
        self.assertIn("tempfile.gettempdir()", block)
        self.assertIn("QDesktopServices.openUrl", block)

    def test_a_failure_to_open_still_names_the_file(self):
        self.assertIn("Openen mislukt", self._manual_block())

    def test_the_manual_does_not_warn_about_personal_data(self):
        """Er staan geen bezoekersgegevens in; waarschuwen zou verwarren."""
        self.assertNotIn("_confirm_personal_data_export", self._manual_block())


if __name__ == "__main__":
    unittest.main()
