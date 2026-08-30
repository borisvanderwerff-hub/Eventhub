"""Wanneer verschijnt de vraag om verlopen gegevens te verwijderen."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import BezoekerslijstWindow


LONG_AGO = (date.today() - timedelta(days=90)).strftime("%d-%m-%Y")
SOON = (date.today() + timedelta(days=30)).strftime("%d-%m-%Y")


class TriggerWindow:
    """Roept de echte methode aan; de dialoog zelf wordt vervangen."""

    maybe_apply_retention = BezoekerslijstWindow.maybe_apply_retention
    _retention_plan = BezoekerslijstWindow._retention_plan

    def __init__(self, events, records, project_path="dossier.bvp"):
        self.events = events
        self.records = records
        self.project_path = project_path
        self.prompted = False
        self._retention_days = lambda: 21

    def _prompt(self, plan):
        self.prompted = True


def expired_scenario():
    return (
        [{"id": "e1", "name": "Voorlichting", "date": LONG_AGO}],
        [{"_id": "r1", "Evenement": "Voorlichting", "Voornaam": "Jan"}],
    )


class PromptConditionTests(unittest.TestCase):
    """maybe_apply_retention slaat over zolang er niets te verwijderen valt."""

    def _returns_early(self, window):
        # Zonder QMessageBox eindigt de methode in een AttributeError zodra hij
        # de dialoog bereikt; komt hij daar niet, dan is er niets te doen.
        try:
            window.maybe_apply_retention()
        except Exception:
            return False
        return True

    def test_prompts_when_records_have_expired(self):
        events, records = expired_scenario()
        window = TriggerWindow(events, records)
        self.assertFalse(self._returns_early(window), "er had een vraag moeten komen")

    def test_silent_without_an_opened_dossier(self):
        events, records = expired_scenario()
        window = TriggerWindow(events, records, project_path=None)
        self.assertTrue(self._returns_early(window))

    def test_silent_without_events(self):
        window = TriggerWindow([], [])
        self.assertTrue(self._returns_early(window))

    def test_silent_when_nothing_has_expired_yet(self):
        window = TriggerWindow(
            [{"id": "e1", "name": "Open dag", "date": SOON}],
            [{"_id": "r1", "Evenement": "Open dag", "Voornaam": "Lisa"}],
        )
        self.assertTrue(self._returns_early(window))

    def test_silent_when_the_event_was_already_cleared(self):
        events, records = expired_scenario()
        events[0]["persoonsgegevens_gewist"] = "01-01-2026"
        window = TriggerWindow(events, records)
        self.assertTrue(self._returns_early(window))

    def test_silent_when_only_visitors_of_upcoming_events_would_match(self):
        """Wie ook nog moet komen levert geen verwijdervraag op."""
        window = TriggerWindow(
            [
                {"id": "e1", "name": "Voorlichting", "date": LONG_AGO},
                {"id": "e2", "name": "Open dag", "date": SOON},
            ],
            [{"_id": "r1", "Evenement": "Voorlichting; Open dag", "Voornaam": "Sanne"}],
        )
        self.assertTrue(self._returns_early(window))


class TriggerPointTests(unittest.TestCase):
    """De controle hangt aan elk geopend dossier, niet alleen aan het opstarten."""

    def setUp(self):
        self.source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

    def _block(self, name):
        start = self.source.index(f"def {name}(self")
        end = self.source.index("\n    def ", start + 1)
        return self.source[start:end]

    def test_opening_any_dossier_runs_the_check(self):
        block = self._block("_open_project_path")
        self.assertIn("self.maybe_apply_retention()", block)
        self.assertIn('getattr(self, "_starting_up", False)', block)

    def test_startup_defers_the_check_until_after_the_welcome_screens(self):
        block = self._block("run_post_startup")
        self.assertIn("self._starting_up = True", block)
        self.assertIn("self._starting_up = False", block)
        # De vraag komt ná het herstellen en de opstartschermen.
        self.assertGreater(
            block.index("self.maybe_apply_retention()"),
            block.index("maybe_show_startup_welcome"),
        )

    def test_startup_flag_is_cleared_even_when_a_screen_fails(self):
        self.assertIn("finally:\n            self._starting_up = False", self.source)


if __name__ == "__main__":
    unittest.main()
