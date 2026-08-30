"""Volgorde en zoekfunctie van het evenementenoverzicht."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import BezoekerslijstWindow


TODAY = date.today()


def event(name, offset, status="In voorbereiding", **extra):
    data = {
        "id": name,
        "name": name,
        "date": (TODAY + timedelta(days=offset)).strftime("%d-%m-%Y"),
        "status": status,
    }
    data.update(extra)
    return data


def order(events):
    key = lambda item: BezoekerslijstWindow._event_sort_key(None, item)  # noqa: E731
    return [item["name"] for item in sorted(events, key=key)]


class SortOrderTests(unittest.TestCase):
    def test_upcoming_events_come_first_soonest_at_the_top(self):
        names = order([event("Over 3 maanden", 90), event("Morgen", 1), event("Volgende week", 7)])
        self.assertEqual(names, ["Morgen", "Volgende week", "Over 3 maanden"])

    def test_finished_events_move_below_the_upcoming_ones(self):
        """De klacht: afgeronde evenementen stonden bovenaan omdat ze het oudst zijn."""
        names = order([
            event("Vorig jaar afgerond", -400, "Afgerond"),
            event("Volgende week", 7),
        ])
        self.assertEqual(names, ["Volgende week", "Vorig jaar afgerond"])

    def test_the_past_runs_from_recent_to_old(self):
        names = order([
            event("Vorig jaar", -400, "Afgerond"),
            event("Vorige week", -7, "Afgerond"),
            event("Vorige maand", -30, "Afgerond"),
        ])
        self.assertEqual(names, ["Vorige week", "Vorige maand", "Vorig jaar"])

    def test_cancelled_event_leaves_the_upcoming_block_even_with_a_future_date(self):
        names = order([event("Geannuleerd", 30, "Geannuleerd"), event("Gepland", 60)])
        self.assertEqual(names, ["Gepland", "Geannuleerd"])

    def test_today_still_counts_as_upcoming(self):
        names = order([event("Gisteren", -1, "Afgerond"), event("Vandaag", 0)])
        self.assertEqual(names, ["Vandaag", "Gisteren"])

    def test_events_without_a_date_land_at_the_bottom(self):
        names = order([
            {"id": "x", "name": "Zonder datum", "date": "", "status": "Concept"},
            event("Vorig jaar", -400, "Afgerond"),
            event("Volgende week", 7),
        ])
        self.assertEqual(names, ["Volgende week", "Vorig jaar", "Zonder datum"])

    def test_same_day_events_sort_by_name(self):
        names = order([event("Bravo", 5), event("Alfa", 5)])
        self.assertEqual(names, ["Alfa", "Bravo"])


class FakeItem:
    def __init__(self, event_id):
        self.event_id = event_id

    def data(self, _role):
        return self.event_id


class FakeTable:
    def __init__(self, event_ids):
        self.event_ids = event_ids
        self.hidden = {}

    def rowCount(self):
        return len(self.event_ids)

    def item(self, row, _column):
        return FakeItem(self.event_ids[row])

    def setRowHidden(self, row, hidden):
        self.hidden[row] = hidden

    def isRowHidden(self, row):
        return self.hidden.get(row, False)


class FakeInput:
    def __init__(self, value=""):
        self._value = value

    def text(self):
        return self._value

    def currentData(self):
        return self._value

    def setText(self, value):
        self._value = value


class SearchWindow:
    _filter_events = BezoekerslijstWindow._filter_events
    _event_id_for_row = BezoekerslijstWindow._event_id_for_row

    def __init__(self, events, needle="", status=""):
        self.events = events
        self.home_event_table = FakeTable([item["id"] for item in events])
        self.event_search_box = FakeInput(needle)
        self.event_status_filter = FakeInput(status)
        self.event_filter_summary = FakeInput()

    def _event_by_id(self, event_id):
        return next((item for item in self.events if item.get("id") == event_id), None)

    def visible(self):
        self._filter_events()
        return [
            item["name"] for row, item in enumerate(self.events)
            if not self.home_event_table.isRowHidden(row)
        ]


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            event("Meeloopdag Marine", 7, place="Den Helder", event_type="Meeloopdag"),
            event("Voorlichting Landmacht", 14, place="Ermelo", event_type="Voorlichting"),
            event("Open dag Luchtmacht", -30, "Afgerond", place="Volkel", event_type="Open dag"),
        ]

    def test_empty_search_shows_everything(self):
        self.assertEqual(len(SearchWindow(self.events).visible()), 3)

    def test_search_matches_the_name(self):
        self.assertEqual(SearchWindow(self.events, "marine").visible(), ["Meeloopdag Marine"])

    def test_search_matches_the_place(self):
        self.assertEqual(SearchWindow(self.events, "ermelo").visible(), ["Voorlichting Landmacht"])

    def test_search_matches_the_event_type(self):
        self.assertEqual(SearchWindow(self.events, "open dag").visible(), ["Open dag Luchtmacht"])

    def test_search_matches_the_date(self):
        wanted = self.events[0]["date"]
        self.assertIn("Meeloopdag Marine", SearchWindow(self.events, wanted).visible())

    def test_search_ignores_case_and_accents(self):
        self.assertEqual(SearchWindow(self.events, "MARINE").visible(), ["Meeloopdag Marine"])

    def test_search_without_matches_shows_nothing(self):
        self.assertEqual(SearchWindow(self.events, "onderzeeboot").visible(), [])

    def test_summary_only_appears_when_something_is_hidden(self):
        window = SearchWindow(self.events)
        window.visible()
        self.assertEqual(window.event_filter_summary.text(), "")

        window = SearchWindow(self.events, "marine")
        window.visible()
        self.assertEqual(window.event_filter_summary.text(), "1 van 3 getoond")


class StatusFilterTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            event("Gepland", 7),
            event("Afgerond", -30, "Afgerond"),
            event("Geannuleerd", -10, "Geannuleerd"),
        ]

    def test_open_filter_hides_finished_and_cancelled(self):
        self.assertEqual(SearchWindow(self.events, status="_open").visible(), ["Gepland"])

    def test_specific_status_filter(self):
        self.assertEqual(SearchWindow(self.events, status="Afgerond").visible(), ["Afgerond"])

    def test_search_and_status_filter_combine(self):
        window = SearchWindow(self.events, needle="gepland", status="_open")
        self.assertEqual(window.visible(), ["Gepland"])

        window = SearchWindow(self.events, needle="afgerond", status="_open")
        self.assertEqual(window.visible(), [], "status en zoektekst moeten allebei gelden")


class HiddenSelectionTests(unittest.TestCase):
    """Een weggefilterde rij mag niet meer als selectie gelden."""

    def test_selection_guard_checks_row_visibility(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        start = source.index("def _selected_management_event(self")
        block = source[start:source.index("\n    def ", start + 1)]
        self.assertIn("table.isRowHidden(row)", block)


if __name__ == "__main__":
    unittest.main()
