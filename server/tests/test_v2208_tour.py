"""De rondleiding moet blijven kloppen met de app.

Een rondleiding veroudert stilletjes: een widget wordt hernoemd of een scherm
wordt vervangen, en de stap wijst nergens meer naar zonder dat iets klaagt.
Deze tests controleren dat elke stap een bestaand doel heeft en dat de tekst
de onderdelen noemt die EventHub inmiddels heeft.
"""
import os
import re
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from bezoekerslijst_app import BezoekerslijstWindow

APP_SOURCE = desktop_source(ROOT)


def _tour_source() -> str:
    start = APP_SOURCE.index("def start_tutorial")
    return APP_SOURCE[start:APP_SOURCE.index("def finish_tutorial", start)]


class TourTargetTests(unittest.TestCase):
    """Elke stap wijst een onderdeel aan dat er ook echt is."""

    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])
        cls.window = BezoekerslijstWindow()
        cls.tour = _tour_source()

    def test_every_highlighted_widget_exists(self):
        # De lokale hulpfunctie voor tabbladen is geen widget van het venster.
        lokaal = {"event_tab_label"}
        namen = set(re.findall(r'"target": lambda: (?:self\.)?([a-z_]+)', self.tour)) - lokaal

        self.assertGreater(len(namen), 10, "de rondleiding wijst nauwelijks iets aan")
        for naam in sorted(namen):
            with self.subTest(widget=naam):
                self.assertTrue(hasattr(self.window, naam))

    def test_every_prepared_tab_exists(self):
        for naam in sorted(set(re.findall(r"show_event_tab\(self\.([a-z_]+)\)", self.tour))):
            with self.subTest(tab=naam):
                self.assertTrue(hasattr(self.window, naam))

    def test_every_step_has_a_title_and_a_body(self):
        titels = re.findall(r'"title": "([^"]+)"', self.tour)
        lichamen = self.tour.count('"body":')

        self.assertEqual(len(titels), lichamen)
        self.assertEqual(len(titels), len(set(titels)), "twee stappen met dezelfde titel")


class TourSideEffectTests(unittest.TestCase):
    """Een rondleiding toont; hij verandert niets en vraagt niets.

    Een dossier openen synchroniseert normaal de live presentie, en dat kan
    een waarschuwing tonen. Tijdens de rondleiding ligt de laag daaroverheen:
    dat venster valt erachter en de app lijkt vast te lopen.
    """

    def setUp(self):
        self.tour = _tour_source()

    def test_the_tour_opens_events_quietly(self):
        self.assertIn("self.open_event(tutorial_event, tab, stil=True)", self.tour)

    def test_restoring_the_users_own_event_is_quiet_too(self):
        start = APP_SOURCE.index("def finish_tutorial")
        blok = APP_SOURCE[start:APP_SOURCE.index(chr(10) + "    def ", start)]

        self.assertIn("self.open_event(original_event, original_tab, stil=True)", blok)

    def test_a_quiet_open_skips_the_syncing_and_the_timestamp(self):
        start = APP_SOURCE.index("    def open_event(self")
        blok = APP_SOURCE[start:APP_SOURCE.index(chr(10) + "    def ", start + 1)]

        self.assertIn("def open_event(self, event: dict, tab: QWidget | None = None, stil: bool = False)",
                      APP_SOURCE)
        self.assertIn("if not stil:", blok)
        self.assertIn("self._sync_latest_live_attendance_for_event(event)", blok)
        # De synchronisatie hoort binnen die voorwaarde te staan.
        self.assertLess(blok.index("if not stil:"),
                        blok.index("self._sync_latest_live_attendance_for_event(event)"))

    def test_opening_an_event_normally_still_syncs(self):
        """Buiten de rondleiding moet het gedrag onveranderd zijn."""
        start = APP_SOURCE.index("    def open_event(self")
        blok = APP_SOURCE[start:APP_SOURCE.index(chr(10) + "    def ", start + 1)]

        self.assertIn("self._touch_event(event, opened=True)", blok)


class TourContentTests(unittest.TestCase):
    """De tekst hoort de app van vandaag te beschrijven."""

    def setUp(self):
        self.tour = _tour_source()

    def test_it_covers_the_event_board(self):
        """Het overzicht is een kaartenbord, geen tabel met rechtermuisknop."""
        self.assertIn("kaart", self.tour)
        self.assertIn("Vandaag", self.tour)
        self.assertIn("Geweest", self.tour)

    def test_it_covers_the_report_builder(self):
        self.assertIn("Een rapport samenstellen", self.tour)
        self.assertIn("PDF of Excel", self.tour)
        self.assertIn("sjabloon", self.tour)

    def test_it_covers_switching_events(self):
        self.assertIn("Ander evenement", self.tour)

    def test_it_covers_standard_tasks_per_event_kind(self):
        self.assertIn("per soort evenement", self.tour)

    def test_it_covers_the_rudder_attendance_button(self):
        self.assertIn("EventHub aanwezigheid", self.tour)

    def test_it_covers_skipping_duplicate_registrations(self):
        self.assertIn("dubbelen", self.tour)

    def test_it_no_longer_describes_the_old_overview(self):
        """De tabel met sorteerkeuze en rechtermuisknop bestaat niet meer zo."""
        self.assertNotIn("kies zelf de sortering", self.tour)


if __name__ == "__main__":
    unittest.main()
