"""Bewaartermijn: welke bezoekers verdwijnen, en vooral welke niet."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from emt_retention import (
    RETENTION_DEFAULT_DAYS,
    RETENTION_MAX_DAYS,
    apply_retention_cleanup,
    clamp_retention_days,
    expired_events,
    is_event_expired,
    plan_retention_cleanup,
    scrub_payload,
)


TODAY = date(2026, 5, 1)


def day(offset):
    return (TODAY + timedelta(days=offset)).strftime("%d-%m-%Y")


def event(name, offset, **extra):
    data = {"id": name.lower().replace(" ", "-"), "name": name, "date": day(offset)}
    data.update(extra)
    return data


def visitor(name, *events):
    return {"_id": name.lower(), "Voornaam": name, "Evenement": "; ".join(events)}


class RetentionSettingTests(unittest.TestCase):
    def test_default_is_three_weeks(self):
        self.assertEqual(RETENTION_DEFAULT_DAYS, 21)

    def test_termijn_never_exceeds_two_months(self):
        self.assertEqual(RETENTION_MAX_DAYS, 60)
        self.assertEqual(clamp_retention_days(90), 60)
        self.assertEqual(clamp_retention_days(365), 60)

    def test_nonsense_falls_back_to_the_default(self):
        self.assertEqual(clamp_retention_days(None), 21)
        self.assertEqual(clamp_retention_days("veel"), 21)
        self.assertEqual(clamp_retention_days(0), 1)


class ExpiryTests(unittest.TestCase):
    def test_event_expires_exactly_after_the_term(self):
        self.assertFalse(is_event_expired(event("A", -20), 21, TODAY))
        self.assertTrue(is_event_expired(event("A", -21), 21, TODAY))
        self.assertTrue(is_event_expired(event("A", -60), 21, TODAY))

    def test_future_events_never_expire(self):
        self.assertFalse(is_event_expired(event("A", 10), 21, TODAY))

    def test_event_without_a_date_never_expires(self):
        """Zonder datum is de termijn niet vast te stellen; dan niet verwijderen."""
        self.assertFalse(is_event_expired({"name": "A", "date": ""}, 21, TODAY))

    def test_already_scrubbed_event_is_not_offered_again(self):
        done = event("A", -30, persoonsgegevens_gewist="01-04-2026")
        self.assertFalse(is_event_expired(done, 21, TODAY))
        self.assertEqual(expired_events([done], 21, TODAY), [])


class WhoGetsRemovedTests(unittest.TestCase):
    def setUp(self):
        self.events = [
            event("Voorlichting maart", -40),
            event("Meeloopdag april", -25),
            event("Open dag juni", +30),
        ]

    def _plan(self, records):
        return plan_retention_cleanup(self.events, records, 21, TODAY)

    def test_visitor_of_only_expired_events_is_removed(self):
        jan = visitor("Jan", "Voorlichting maart", "Meeloopdag april")
        plan = self._plan([jan])
        self.assertEqual(plan["records_removed"], 1)
        self.assertIn(jan, plan["_removable"])

    def test_visitor_with_an_upcoming_event_is_kept_entirely(self):
        """De kern: wie nog moet komen, mag zijn gegevens niet kwijtraken."""
        sanne = visitor("Sanne", "Voorlichting maart", "Open dag juni")
        plan = self._plan([sanne])
        self.assertEqual(plan["records_removed"], 0)
        self.assertEqual(plan["records_kept_upcoming"], 1)

    def test_visitor_of_an_unknown_event_is_kept(self):
        """Onbekend evenement betekent onbekende termijn; niet verwijderen."""
        wim = visitor("Wim", "Voorlichting maart", "Braderie 2019")
        plan = self._plan([wim])
        self.assertEqual(plan["records_removed"], 0)
        self.assertEqual(plan["records_kept_unknown"], 1)

    def test_visitor_of_only_future_events_is_untouched(self):
        lisa = visitor("Lisa", "Open dag juni")
        plan = self._plan([lisa])
        self.assertEqual(plan["records_removed"], 0)
        self.assertEqual(plan["records_kept_upcoming"], 0)

    def test_plan_reports_per_event_counts(self):
        records = [
            visitor("Jan", "Voorlichting maart"),
            visitor("Sanne", "Voorlichting maart", "Open dag juni"),
        ]
        plan = self._plan(records)
        maart = next(e for e in plan["events"] if e["name"] == "Voorlichting maart")
        self.assertEqual(maart["records"], 2)
        self.assertEqual(maart["records_removed"], 1)
        self.assertEqual(maart["expires_on"], "12-04-2026")

    def test_planning_changes_nothing(self):
        records = [visitor("Jan", "Voorlichting maart")]
        self._plan(records)
        self.assertEqual(len(records), 1, "een dry-run mag niets verwijderen")
        self.assertNotIn("persoonsgegevens_gewist", self.events[0])


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.events = [event("Voorlichting maart", -40), event("Open dag juni", +30)]
        self.records = [
            visitor("Jan", "Voorlichting maart"),
            visitor("Sanne", "Voorlichting maart", "Open dag juni"),
            visitor("Lisa", "Open dag juni"),
        ]

    def test_only_the_expired_visitors_disappear(self):
        apply_retention_cleanup(self.events, self.records, 21, TODAY)
        remaining = sorted(record["Voornaam"] for record in self.records)
        self.assertEqual(remaining, ["Lisa", "Sanne"])

    def test_cleared_event_is_marked_and_not_repeated(self):
        apply_retention_cleanup(self.events, self.records, 21, TODAY)
        self.assertEqual(self.events[0]["persoonsgegevens_gewist"], "01-05-2026")
        self.assertNotIn("persoonsgegevens_gewist", self.events[1])

        second = apply_retention_cleanup(self.events, self.records, 21, TODAY)
        self.assertEqual(second["records_removed"], 0)

    def test_statistics_snapshot_survives_the_cleanup(self):
        self.events[0]["statistiek"] = {"aangemeld": 2, "aanwezig": 1}
        apply_retention_cleanup(self.events, self.records, 21, TODAY)
        self.assertEqual(self.events[0]["statistiek"], {"aangemeld": 2, "aanwezig": 1})

    def test_no_personal_data_of_removed_visitors_remains(self):
        apply_retention_cleanup(self.events, self.records, 21, TODAY)
        self.assertNotIn("Jan", repr(self.records) + repr(self.events))


class BackupScrubTests(unittest.TestCase):
    """Back-ups en herstelkopieën bevatten dezelfde gegevens en gaan mee."""

    def test_payload_is_cleaned_in_place(self):
        payload = {
            "version": 11,
            "events": [event("Voorlichting maart", -40)],
            "records": [visitor("Jan", "Voorlichting maart")],
        }
        plan = scrub_payload(payload, 21, TODAY)

        self.assertEqual(plan["records_removed"], 1)
        self.assertEqual(payload["records"], [])
        self.assertEqual(payload["events"][0]["persoonsgegevens_gewist"], "01-05-2026")

    def test_empty_payload_is_harmless(self):
        payload = {"version": 11}
        plan = scrub_payload(payload, 21, TODAY)
        self.assertEqual(plan["records_removed"], 0)


if __name__ == "__main__":
    unittest.main()
