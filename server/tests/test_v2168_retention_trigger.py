"""Wanneer de bewaartermijn automatisch wordt gehandhaafd."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import BezoekerslijstWindow


LONG_AGO = (date.today() - timedelta(days=90)).strftime("%d-%m-%Y")
SOON = (date.today() + timedelta(days=30)).strftime("%d-%m-%Y")


class TriggerWindow:
    """Draait de echte beslislogica; het daadwerkelijk wissen wordt vervangen."""

    maybe_apply_retention = BezoekerslijstWindow.maybe_apply_retention
    _retention_plan = BezoekerslijstWindow._retention_plan

    def __init__(self, events, records, project_path="dossier.bvp"):
        self.events = events
        self.records = records
        self.project_path = project_path
        self.cleaned_with = None

    def _retention_days(self):
        return 21

    def apply_retention_cleanup_now(self, plan=None, announce=True):
        self.cleaned_with = plan
        return plan


def expired_scenario():
    return (
        [{"id": "e1", "name": "Voorlichting", "date": LONG_AGO}],
        [{"_id": "r1", "Evenement": "Voorlichting", "Voornaam": "Jan"}],
    )


class AutomaticCleanupTests(unittest.TestCase):
    """Er wordt niet om bevestiging gevraagd: verlopen is verlopen."""

    def test_expired_records_are_cleaned_without_asking(self):
        window = TriggerWindow(*expired_scenario())
        window.maybe_apply_retention()

        self.assertIsNotNone(window.cleaned_with, "er had gewist moeten worden")
        self.assertEqual(window.cleaned_with["records_removed"], 1)

    def test_the_plan_is_handed_over_so_it_is_not_computed_twice(self):
        window = TriggerWindow(*expired_scenario())
        window.maybe_apply_retention()
        self.assertIn("_removable", window.cleaned_with)


class NoWorkTests(unittest.TestCase):
    """Zonder verlopen gegevens gebeurt er niets."""

    def _stays_quiet(self, window):
        window.maybe_apply_retention()
        return window.cleaned_with is None

    def test_quiet_without_an_opened_dossier(self):
        events, records = expired_scenario()
        self.assertTrue(self._stays_quiet(TriggerWindow(events, records, project_path=None)))

    def test_quiet_without_events(self):
        self.assertTrue(self._stays_quiet(TriggerWindow([], [])))

    def test_quiet_when_nothing_has_expired_yet(self):
        window = TriggerWindow(
            [{"id": "e1", "name": "Open dag", "date": SOON}],
            [{"_id": "r1", "Evenement": "Open dag", "Voornaam": "Lisa"}],
        )
        self.assertTrue(self._stays_quiet(window))

    def test_quiet_when_the_event_was_already_cleared(self):
        events, records = expired_scenario()
        events[0]["persoonsgegevens_gewist"] = "01-01-2026"
        self.assertTrue(self._stays_quiet(TriggerWindow(events, records)))

    def test_quiet_when_only_visitors_of_upcoming_events_would_match(self):
        """Wie ook nog moet komen, blijft volledig bewaard."""
        window = TriggerWindow(
            [
                {"id": "e1", "name": "Voorlichting", "date": LONG_AGO},
                {"id": "e2", "name": "Open dag", "date": SOON},
            ],
            [{"_id": "r1", "Evenement": "Voorlichting; Open dag", "Voornaam": "Sanne"}],
        )
        self.assertTrue(self._stays_quiet(window))


class TriggerPointTests(unittest.TestCase):
    """De handhaving hangt aan drie momenten, niet alleen aan het opstarten."""

    def setUp(self):
        self.source = desktop_source(ROOT)

    def _block(self, name):
        start = self.source.index(f"def {name}(self")
        end = self.source.index("\n    def ", start + 1)
        return self.source[start:end]

    def test_opening_any_dossier_enforces_the_term(self):
        block = self._block("_open_project_path")
        self.assertIn("self.maybe_apply_retention()", block)
        self.assertIn('getattr(self, "_starting_up", False)', block)

    def test_startup_enforces_after_the_welcome_screens(self):
        block = self._block("run_post_startup")
        self.assertIn("self._starting_up = True", block)
        self.assertGreater(
            block.index("self.maybe_apply_retention()"),
            block.index("maybe_show_startup_welcome"),
        )

    def test_an_app_left_open_enforces_at_the_date_rollover(self):
        self.assertIn("self.maybe_apply_retention()", self._block("_daily_refresh_tick"))

    def test_startup_flag_is_cleared_even_when_a_screen_fails(self):
        self.assertIn("finally:\n            self._starting_up = False", self.source)


class AuditTrailTests(unittest.TestCase):
    """Automatisch wissen zonder spoor is niet te verantwoorden."""

    def test_cleanup_writes_a_log_entry(self):
        source = desktop_source(ROOT)
        start = source.index("def apply_retention_cleanup_now(self")
        block = source[start:source.index("\n    def ", start + 1)]
        self.assertIn("self._write_retention_log(", block)
        self.assertIn("self._add_recent_activity(", block)

    def test_log_records_counts_but_no_names(self):
        source = desktop_source(ROOT)
        start = source.index("def _write_retention_log(self")
        block = source[start:source.index("\n    def ", start + 1)]
        self.assertIn("records_removed", block)
        self.assertNotIn("Voornaam", block)
        self.assertNotIn("Achternaam", block)


if __name__ == "__main__":
    unittest.main()
