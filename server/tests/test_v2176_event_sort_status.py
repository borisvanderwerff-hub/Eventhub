"""Sorteren van de evenementenlijst en het handmatig zetten van een status."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import AUTOMATIC_STATUS, EVENT_SORT_MODES, BezoekerslijstWindow


TODAY = date.today()


def event(name, offset, status="In voorbereiding", **extra):
    data = {
        "id": name,
        "name": name,
        "date": (TODAY + timedelta(days=offset)).strftime("%d-%m-%Y"),
        "status": status,
        "tasks": [],
    }
    data.update(extra)
    return data


class FakeCombo:
    def __init__(self, value):
        self._value = value

    def currentData(self):
        return self._value


class SortWindow:
    _events_in_display_order = BezoekerslijstWindow._events_in_display_order
    _event_sort_key = BezoekerslijstWindow._event_sort_key

    def __init__(self, events, mode="smart"):
        self.events = events
        self.event_sort_mode = FakeCombo(mode)


def sample():
    return [
        event("Vorig jaar", -400, "Afgerond"),
        event("Vorige maand", -30, "Afgerond"),
        event("Volgende week", 7),
        event("Morgen", 1),
        {"id": "x", "name": "Zonder datum", "date": "", "status": "Concept", "tasks": []},
    ]


class SortModeTests(unittest.TestCase):
    def _order(self, mode):
        return [item["name"] for item in SortWindow(sample(), mode)._events_in_display_order()]

    def test_all_modes_are_offered(self):
        self.assertEqual(
            [value for _, value in EVENT_SORT_MODES],
            ["smart", "date_asc", "date_desc", "name"],
        )

    def test_date_ascending_runs_straight_through(self):
        """De klacht: in de slimme volgorde springt de datumkolom terug."""
        order = self._order("date_asc")
        self.assertEqual(order[:4], ["Vorig jaar", "Vorige maand", "Morgen", "Volgende week"])

    def test_date_descending_is_the_exact_reverse(self):
        order = self._order("date_desc")
        self.assertEqual(order[:4], ["Volgende week", "Morgen", "Vorige maand", "Vorig jaar"])

    def test_undated_events_stay_at_the_bottom_in_both_directions(self):
        for mode in ("date_asc", "date_desc"):
            self.assertEqual(self._order(mode)[-1], "Zonder datum", f"bij {mode}")

    def test_smart_mode_still_puts_upcoming_first(self):
        order = self._order("smart")
        self.assertEqual(order[:2], ["Morgen", "Volgende week"])

    def test_name_mode_sorts_alphabetically(self):
        self.assertEqual(self._order("name")[0], "Morgen")

    def test_unknown_mode_falls_back_to_smart(self):
        order = [item["name"] for item in SortWindow(sample(), "onzin")._events_in_display_order()]
        self.assertEqual(order[0], "Morgen")


class ManualStatusTests(unittest.TestCase):
    """Een gekozen status werd bij de eerstvolgende weergave overschreven."""

    def setUp(self):
        self.window = BezoekerslijstWindow.__new__(BezoekerslijstWindow)

    def _sync(self, item):
        return BezoekerslijstWindow._sync_event_status_from_tasks(self.window, item)

    def test_past_event_no_longer_forces_afgerond_when_set_by_hand(self):
        item = event("Verleden", -10, "In voorbereiding", status_manual=True,
                     tasks=[{"done": False}])
        self._sync(item)
        self.assertEqual(item["status"], "In voorbereiding")

    def test_completed_tasks_no_longer_force_gereed_when_set_by_hand(self):
        item = event("Toekomst", 10, "Concept", status_manual=True, tasks=[{"done": True}])
        self._sync(item)
        self.assertEqual(item["status"], "Concept")

    def test_without_the_flag_the_automation_still_works(self):
        past = event("Verleden", -10, "In voorbereiding", tasks=[{"done": False}])
        self._sync(past)
        self.assertEqual(past["status"], "Afgerond")

        ready = event("Toekomst", 10, "Concept", tasks=[{"done": True}])
        self._sync(ready)
        self.assertEqual(ready["status"], "Gereed")

    def test_cancelled_remains_untouched_as_before(self):
        item = event("Afgeblazen", -10, "Geannuleerd")
        self._sync(item)
        self.assertEqual(item["status"], "Geannuleerd")


class StatusReachabilityTests(unittest.TestCase):
    def setUp(self):
        self.source = desktop_source(ROOT)

    def _block(self, name):
        start = self.source.index(f"def {name}(self")
        return self.source[start:self.source.index("\n    def ", start + 1)]

    def test_events_list_offers_a_status_menu(self):
        block = self._block("_event_actions_menu")
        self.assertIn('status_menu = menu.addMenu("Status")', block)
        self.assertIn("AUTOMATIC_STATUS", block)

    def test_menu_ignores_hidden_rows(self):
        self.assertIn("table.isRowHidden(row)", self._block("_show_event_context_menu"))

    def test_choosing_automatic_hands_control_back(self):
        block = self._block("_set_event_status")
        self.assertIn('event.pop("status_manual", None)', block)
        self.assertIn("self._sync_event_status_from_tasks(event)", block)

    def test_choosing_a_status_locks_it(self):
        block = self._block("_set_event_status")
        self.assertIn('event["status_manual"] = True', block)

    def test_edit_dialog_offers_the_automatic_option(self):
        self.assertIn("self.status.addItem(AUTOMATIC_STATUS, AUTOMATIC_STATUS)", self.source)
        self.assertIn('"status_manual": self.status.currentText() != AUTOMATIC_STATUS,', self.source)


if __name__ == "__main__":
    unittest.main()
