"""Aankondiging van de bewaartermijn in het meldingenoverzicht."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from emt_retention import RETENTION_WARNING_DAYS, retention_notifications


TODAY = date(2026, 5, 1)


def event_expiring_in(days, name="Voorlichting", retention_days=21, **extra):
    """Evenement waarvan de termijn over `days` dagen verloopt."""
    event_date = TODAY + timedelta(days=days) - timedelta(days=retention_days)
    data = {"id": name.lower(), "name": name, "date": event_date.strftime("%d-%m-%Y")}
    data.update(extra)
    return data


def visitor(name, *events):
    return {"_id": name.lower(), "Voornaam": name, "Evenement": "; ".join(events)}


class WarningWindowTests(unittest.TestCase):
    def _notify(self, events, records):
        return retention_notifications(events, records, 21, TODAY)

    def test_warning_starts_seven_days_ahead(self):
        self.assertEqual(RETENTION_WARNING_DAYS, 7)
        self.assertEqual(len(self._notify([event_expiring_in(7)], [visitor("Jan", "Voorlichting")])), 1)

    def test_nothing_yet_at_eight_days(self):
        self.assertEqual(self._notify([event_expiring_in(8)], [visitor("Jan", "Voorlichting")]), [])

    def test_message_counts_down(self):
        for days, expected in ((7, "Over 7 dagen"), (3, "Over 3 dagen"), (1, "Morgen")):
            notes = self._notify([event_expiring_in(days)], [visitor("Jan", "Voorlichting")])
            self.assertTrue(notes[0]["message"].startswith(expected), notes[0]["message"])

    def test_message_names_the_number_of_visitors(self):
        records = [visitor("Jan", "Voorlichting"), visitor("Sanne", "Voorlichting")]
        notes = self._notify([event_expiring_in(3)], records)
        self.assertIn("2 deelnemer(s)", notes[0]["message"])

    def test_expired_event_no_longer_announces(self):
        """Na het verstrijken is er niets meer aan te kondigen."""
        self.assertEqual(self._notify([event_expiring_in(0)], [visitor("Jan", "Voorlichting")]), [])
        self.assertEqual(self._notify([event_expiring_in(-5)], [visitor("Jan", "Voorlichting")]), [])

    def test_already_cleared_event_is_quiet(self):
        event = event_expiring_in(3, persoonsgegevens_gewist="20-04-2026")
        self.assertEqual(self._notify([event], [visitor("Jan", "Voorlichting")]), [])

    def test_event_without_visitors_is_not_announced(self):
        """Een aankondiging zonder gevolgen is ruis."""
        self.assertEqual(self._notify([event_expiring_in(3)], []), [])


class NotificationShapeTests(unittest.TestCase):
    def setUp(self):
        self.note = retention_notifications(
            [event_expiring_in(5)], [visitor("Jan", "Voorlichting")], 21, TODAY
        )[0]

    def test_matches_the_shape_of_a_task_notification(self):
        for key in ("event_id", "event_name", "task_id", "task_title", "due", "severity", "message"):
            self.assertIn(key, self.note)

    def test_due_is_the_expiry_date(self):
        self.assertEqual(self.note["due"], date(2026, 5, 6))

    def test_has_its_own_severity_so_it_can_be_coloured_apart(self):
        self.assertEqual(self.note["severity"], "retention")

    def test_carries_no_task_id_because_it_cannot_be_completed(self):
        self.assertEqual(self.note["task_id"], "")

    def test_contains_no_personal_data(self):
        self.assertNotIn("Jan", repr(self.note))


class SortingTests(unittest.TestCase):
    def test_earliest_expiry_comes_first(self):
        events = [
            event_expiring_in(6, name="Laat"),
            event_expiring_in(2, name="Vroeg"),
        ]
        records = [visitor("Jan", "Laat"), visitor("Sanne", "Vroeg")]
        notes = retention_notifications(events, records, 21, TODAY)
        self.assertEqual([note["event_name"] for note in notes], ["Vroeg", "Laat"])


class LongerTermTests(unittest.TestCase):
    def test_window_follows_the_configured_term(self):
        """Bij 60 dagen schuift de aankondiging mee, hij blijft 7 dagen vooraf."""
        event = event_expiring_in(5, retention_days=60)
        notes = retention_notifications([event], [visitor("Jan", "Voorlichting")], 60, TODAY)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["due"], date(2026, 5, 6))


if __name__ == "__main__":
    unittest.main()
