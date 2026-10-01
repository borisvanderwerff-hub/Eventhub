"""Na de bewaartermijn blijven alleen controleerbare, anonieme cijfers over."""
from datetime import date
import unittest

from bezoekerslijst_core import AANWEZIG, AFWEZIG, AFGEMELD, ONBEKEND, set_attendance
from emt_history import snapshot_for_event, historical_scope, distribution, cross_table, export_dimensions
from emt_retention import apply_retention_cleanup
from emt_trends import event_summary
from emt_models import prepare_event


EVENT = {"id": "old", "name": "Inloopdag", "date": "01-01-2026"}


def record(name, education, profile, status):
    row = {"_id": name, "Evenement": "Inloopdag", "Voornaam": name, "Geboortedatum": "01-01-2005",
           "Opleiding": education, "Profiel": profile, "Geslacht": "Vrouw", "Aanwezig": {}}
    set_attendance(row, "Inloopdag", status)
    return row


class AnonymousHistoryTests(unittest.TestCase):
    def setUp(self):
        self.records = [record("Anna", "HAVO", "Zorg", AANWEZIG),
                        record("Bas", "MBO", "Techniek", AFWEZIG),
                        record("Chris", "MBO", "Techniek", AFGEMELD),
                        record("Dana", "HAVO", "Zorg", ONBEKEND)]
        self.event = dict(EVENT)

    def test_snapshot_retains_aggregates_but_no_identity(self):
        snapshot = snapshot_for_event(self.event, self.records)
        self.assertEqual((snapshot["aangemeld"], snapshot["aanwezig"], snapshot["noshows"], snapshot["afgemeld"], snapshot["onbekend"]), (4, 1, 1, 1, 1))
        self.assertEqual(dict(distribution(snapshot, "Opleidingsniveau")), {"HAVO": 2, "MBO": 2})
        self.assertEqual(cross_table(snapshot)["total"], 4)
        self.assertNotIn("Anna", repr(snapshot))
        self.assertNotIn("01-01-2005", repr(snapshot))

    def test_cleanup_captures_and_freezes_unknown_attendance(self):
        events, rows = [dict(self.event)], list(self.records)
        apply_retention_cleanup(events, rows, 21, date(2026, 2, 1))
        self.assertEqual(rows, [])
        self.assertEqual(events[0]["persoonsgegevens_gewist"], "01-02-2026")
        snapshot = historical_scope(events[0])
        self.assertEqual(snapshot["onbekend"], 1)
        self.assertTrue(export_dimensions(snapshot))
        self.assertIsNotNone(event_summary(events[0]))

    def test_old_snapshot_without_cross_table_remains_honest(self):
        event = dict(self.event, persoonsgegevens_gewist="01-02-2026", statistiek={"aangemeld": 2, "aanwezig": 1, "verdeling": {}})
        self.assertIsNone(cross_table(historical_scope(event)))

    def test_saved_anonymous_snapshot_survives_reopening_a_project(self):
        snapshot = snapshot_for_event(self.event, self.records)
        restored = prepare_event(dict(self.event, persoonsgegevens_gewist="01-02-2026", statistiek=snapshot), [])
        self.assertEqual(restored["persoonsgegevens_gewist"], "01-02-2026")
        self.assertEqual(restored["statistiek"]["kruistabel"], snapshot["kruistabel"])


if __name__ == "__main__":
    unittest.main()
