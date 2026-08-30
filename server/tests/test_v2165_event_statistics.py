"""Geaggregeerde momentopname per evenement (basis voor de bewaartermijn)."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import BezoekerslijstWindow
from bezoekerslijst_core import set_present


EVENT_NAME = "Meeloopdag Marine april 2026"
EVENT_DATE = date(2026, 4, 2)


def deelnemer(voornaam, geboortedatum, opleiding, geslacht, aanwezig, gast_van=""):
    record = {
        "_id": voornaam.lower(),
        "Evenement": EVENT_NAME,
        "Voornaam": voornaam,
        "Geboortedatum": geboortedatum,
        "Opleiding": opleiding,
        "Profiel": "Techniek",
        "Geslacht": geslacht,
        "GastVan": gast_van,
        "Aanwezig": {},
    }
    set_present(record, EVENT_NAME, aanwezig)
    return record


class StubWindow:
    """Draait de statistiekmethodes zonder de Qt-vensterconstructie."""

    _event_statistics_snapshot = BezoekerslijstWindow._event_statistics_snapshot
    _capture_event_statistics = BezoekerslijstWindow._capture_event_statistics
    _refresh_past_event_statistics = BezoekerslijstWindow._refresh_past_event_statistics
    _event_visitors = BezoekerslijstWindow._event_visitors
    _grouped_counts = BezoekerslijstWindow._grouped_counts
    _field_counts = BezoekerslijstWindow._field_counts
    _age_counts = BezoekerslijstWindow._age_counts
    _age_label = BezoekerslijstWindow._age_label
    _age_from_text = BezoekerslijstWindow._age_from_text

    def __init__(self, events, records):
        self.events = events
        self.records = records


def scenario(event_date=EVENT_DATE):
    event = {"id": "e1", "name": EVENT_NAME, "date": event_date.strftime("%d-%m-%Y")}
    records = [
        deelnemer("Jan", "01-06-2008", "VMBO Basis", "Man", True),
        deelnemer("Sanne", "14-11-2004", "HAVO", "Vrouw", True),
        deelnemer("Youssef", "03-02-1999", "MBO", "Man", False),
        deelnemer("Lotte", "20-09-2007", "HAVO", "Vrouw", True, gast_van="Sanne"),
    ]
    return StubWindow([event], records), event


class SnapshotContentTests(unittest.TestCase):
    def setUp(self):
        self.window, self.event = scenario()
        self.snapshot = self.window._event_statistics_snapshot(self.event)

    def test_counts_registrations_attendance_and_noshows(self):
        self.assertEqual(self.snapshot["aangemeld"], 4)
        self.assertEqual(self.snapshot["aanwezig"], 3)
        self.assertEqual(self.snapshot["noshows"], 1)
        self.assertEqual(self.snapshot["opkomst_percentage"], 75.0)
        self.assertEqual(self.snapshot["introducees"], 1)

    def test_age_groups_use_the_event_date_not_today(self):
        """Jan was 17 op 02-04-2026 maar is inmiddels 18: de peildatum telt."""
        self.assertEqual(self.snapshot["peildatum"], "02-04-2026")
        self.assertEqual(
            {group: bucket["aangemeld"]
             for group, bucket in self.snapshot["verdeling"]["Leeftijdsgroep"].items()},
            {"Jonger dan 18": 1, "18–20": 1, "21–24": 1, "25–29": 1},
        )
        self.assertEqual(self.window._age_from_text("01-06-2008", EVENT_DATE), 17)
        self.assertGreater(self.window._age_from_text("01-06-2008"), 17)

    def test_distributions_are_complete_and_not_truncated(self):
        self.assertEqual(
            {group: bucket["aangemeld"]
             for group, bucket in self.snapshot["verdeling"]["Opleidingsniveau"].items()},
            {"HAVO": 2, "MBO": 1, "VMBO Basis": 1},
        )

    def test_distributions_split_attendance_so_noshows_stay_traceable(self):
        """Schema 2: zonder deze splitsing is niet meer te zien wie wegbleef."""
        self.assertEqual(self.snapshot["schema"], 2)
        opleiding = self.snapshot["verdeling"]["Opleidingsniveau"]
        self.assertEqual(opleiding["HAVO"], {"aangemeld": 2, "aanwezig": 2})
        self.assertEqual(opleiding["MBO"], {"aangemeld": 1, "aanwezig": 0})
        self.assertEqual(opleiding["VMBO Basis"], {"aangemeld": 1, "aanwezig": 1})

        geslacht = self.snapshot["verdeling"]["Geslacht"]
        self.assertEqual(geslacht["Man"], {"aangemeld": 2, "aanwezig": 1})
        self.assertEqual(geslacht["Vrouw"], {"aangemeld": 2, "aanwezig": 2})

    def test_snapshot_holds_no_personal_data(self):
        """Niets in de momentopname mag naar een persoon herleidbaar zijn."""
        blob = repr(self.snapshot)
        for personal in ("Jan", "Sanne", "Youssef", "Lotte", "01-06-2008", "14-11-2004"):
            self.assertNotIn(personal, blob)


class SnapshotLifecycleTests(unittest.TestCase):
    def test_past_events_are_captured_automatically(self):
        window, event = scenario(date.today() - timedelta(days=1))
        self.assertTrue(window._refresh_past_event_statistics())
        self.assertEqual(event["statistiek"]["aanwezig"], 3)

    def test_future_events_are_not_captured_yet(self):
        window, event = scenario(date.today() + timedelta(days=10))
        self.assertFalse(window._refresh_past_event_statistics())
        self.assertNotIn("statistiek", event)

    def test_repeated_capture_without_changes_reports_nothing(self):
        window, event = scenario()
        self.assertTrue(window._capture_event_statistics(event))
        self.assertFalse(window._capture_event_statistics(event))

    def test_later_attendance_correction_updates_the_snapshot(self):
        window, event = scenario()
        window._capture_event_statistics(event)
        self.assertEqual(event["statistiek"]["aanwezig"], 3)

        set_present(window.records[2], EVENT_NAME, True)
        self.assertTrue(window._capture_event_statistics(event))
        self.assertEqual(event["statistiek"]["aanwezig"], 4)

    def test_scrubbed_event_freezes_its_snapshot(self):
        """Na het wissen mag herberekenen de cijfers niet vernietigen."""
        window, event = scenario()
        window._capture_event_statistics(event)
        frozen = dict(event["statistiek"])

        event["persoonsgegevens_gewist"] = "23-04-2026"
        window.records = []

        self.assertFalse(window._capture_event_statistics(event))
        self.assertEqual(event["statistiek"], frozen)


if __name__ == "__main__":
    unittest.main()
