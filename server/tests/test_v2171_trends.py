"""Trendanalyse over evenementen heen."""
from datetime import date
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from emt_trends import (
    anonymous_bundle,
    build_series,
    collect_summaries,
    describe_change,
    event_summary,
    read_bundle,
    series_totals,
)


def snapshot(aangemeld, aanwezig, opleiding=None):
    """Momentopname volgens schema 2: verdelingen splitsen aangemeld/aanwezig."""
    data = {
        "schema": 2,
        "aangemeld": aangemeld,
        "aanwezig": aanwezig,
        "noshows": aangemeld - aanwezig,
        "opkomst_percentage": round(aanwezig / aangemeld * 100, 1) if aangemeld else 0.0,
        "verdeling": {},
    }
    if opleiding:
        data["verdeling"]["Opleidingsniveau"] = opleiding
    return data


def event(name, datum, aangemeld, aanwezig, soort="Meeloopdag", plaats="Den Helder", opleiding=None):
    return {
        "id": name,
        "name": name,
        "date": datum,
        "event_type": soort,
        "place": plaats,
        "statistiek": snapshot(aangemeld, aanwezig, opleiding),
    }


class SummaryTests(unittest.TestCase):
    def test_event_without_a_snapshot_is_skipped(self):
        self.assertIsNone(event_summary({"id": "x", "name": "Zonder cijfers"}))

    def test_summary_carries_no_participant_rows(self):
        summary = event_summary(event("A", "01-03-2026", 10, 8))
        self.assertNotIn("records", summary)
        self.assertEqual(summary["statistiek"]["aangemeld"], 10)

    def test_collect_skips_events_without_snapshots(self):
        events = [event("A", "01-03-2026", 10, 8), {"id": "b", "name": "B"}]
        self.assertEqual(len(collect_summaries(events)), 1)


class TimeSeriesTests(unittest.TestCase):
    def setUp(self):
        self.summaries = collect_summaries([
            event("Maart", "10-03-2026", 100, 60),
            event("April", "10-04-2026", 100, 70),
            event("Mei", "10-05-2026", 100, 90),
        ])

    def test_series_follows_chronological_order(self):
        series = build_series(self.summaries, "aangemeld")
        self.assertEqual([point["label"] for point in series["points"]], ["Maart", "April", "Mei"])

    def test_turnout_rises_over_time(self):
        series = build_series(self.summaries, "opkomst_percentage")
        values = [point["values"]["Totaal"] for point in series["points"]]
        self.assertEqual(values, [60.0, 70.0, 90.0])

    def test_change_is_described_in_words(self):
        series = build_series(self.summaries, "opkomst_percentage")
        self.assertIn("toename", describe_change(series))
        self.assertIn("60", describe_change(series))
        self.assertIn("90", describe_change(series))

    def test_grouping_per_quarter_merges_events(self):
        series = build_series(self.summaries, "aangemeld", period="quarter")
        labels = [point["label"] for point in series["points"]]
        self.assertEqual(labels, ["K1 2026", "K2 2026"])
        self.assertEqual(series["points"][1]["values"]["Totaal"], 200.0)

    def test_percentages_are_recomputed_not_averaged(self):
        """Een klein evenement mag niet even zwaar wegen als een groot."""
        summaries = collect_summaries([
            event("Klein", "10-04-2026", 4, 4),
            event("Groot", "20-04-2026", 200, 100),
        ])
        series = build_series(summaries, "opkomst_percentage", period="month")
        # 104 van 204 aanwezig = 51%, niet het gemiddelde van 100% en 50%.
        self.assertEqual(series["points"][0]["values"]["Totaal"], 51.0)

    def test_date_range_filter(self):
        series = build_series(self.summaries, "aangemeld", since=date(2026, 4, 1))
        self.assertEqual(series["events"], 2)


class BreakdownTests(unittest.TestCase):
    def setUp(self):
        self.summaries = collect_summaries([
            event("Maart", "10-03-2026", 30, 20, opleiding={
                "HBO": {"aangemeld": 10, "aanwezig": 9},
                "MBO": {"aangemeld": 20, "aanwezig": 11},
            }),
            event("Mei", "10-05-2026", 30, 22, opleiding={
                "HBO": {"aangemeld": 18, "aanwezig": 16},
                "MBO": {"aangemeld": 12, "aanwezig": 6},
            }),
        ])

    def test_noshows_can_be_traced_to_a_group(self):
        """De vraag: bij welke groep zitten de meeste no-shows?"""
        series = build_series(self.summaries, "noshows", dimension="Opleidingsniveau")
        totals = dict(series_totals(series))
        self.assertEqual(totals["MBO"], 15.0)
        self.assertEqual(totals["HBO"], 3.0)

    def test_growth_within_one_group_is_visible(self):
        """De vraag: nemen de aanmeldingen onder hbo'ers toe?"""
        series = build_series(self.summaries, "aangemeld", dimension="Opleidingsniveau")
        hbo = [point["values"]["HBO"] for point in series["points"]]
        self.assertEqual(hbo, [10.0, 18.0])
        self.assertIn("toename", describe_change(series, "HBO"))

    def test_turnout_per_group_is_recomputed_over_the_whole_period(self):
        series = build_series(self.summaries, "opkomst_percentage", dimension="Opleidingsniveau", period="year")
        # HBO: 25 van 28 aanwezig.
        self.assertEqual(series["points"][0]["values"]["HBO"], 89.3)

    def test_breakdown_by_event_type(self):
        summaries = collect_summaries([
            event("A", "10-03-2026", 100, 50, soort="Meeloopdag"),
            event("B", "11-03-2026", 100, 80, soort="Voorlichting"),
        ])
        series = build_series(summaries, "opkomst_percentage", dimension="event_type", period="month")
        self.assertEqual(series["points"][0]["values"]["Meeloopdag"], 50.0)
        self.assertEqual(series["points"][0]["values"]["Voorlichting"], 80.0)

    def test_groups_are_ordered_by_size(self):
        series = build_series(self.summaries, "aangemeld", dimension="Opleidingsniveau")
        self.assertEqual(series["groups"], ["MBO", "HBO"])


class OldSnapshotTests(unittest.TestCase):
    """Momentopnames van vóór schema 2 kennen geen aanwezigheid per groep."""

    def setUp(self):
        old = event("Oud", "10-03-2026", 30, 20)
        old["statistiek"]["verdeling"] = {"Opleidingsniveau": {"HBO": 10, "MBO": 20}}
        old["statistiek"].pop("schema", None)
        self.summaries = collect_summaries([old])

    def test_registrations_still_work(self):
        series = build_series(self.summaries, "aangemeld", dimension="Opleidingsniveau")
        self.assertEqual(dict(series_totals(series)), {"MBO": 20.0, "HBO": 10.0})
        self.assertFalse(series["incomplete"])

    def test_noshows_are_reported_as_incomplete_rather_than_zero(self):
        series = build_series(self.summaries, "noshows", dimension="Opleidingsniveau")
        self.assertTrue(series["incomplete"], "de gebruiker moet weten dat dit niet te berekenen is")
        self.assertEqual(series["groups"], [])


class SharingTests(unittest.TestCase):
    """Analyses over evenementen van een ander, zonder persoonsgegevens."""

    def test_bundle_contains_only_aggregates(self):
        events = [event("A", "10-03-2026", 10, 8)]
        events[0]["records_hint"] = "mag niet meekomen"
        bundle = anonymous_bundle(events, "Regio Noord")

        self.assertEqual(bundle["format"], "EventHub Trendgegevens")
        self.assertNotIn("records_hint", bundle["events"][0])
        self.assertNotIn("records", repr(bundle))

    def test_bundle_can_be_read_back(self):
        bundle = anonymous_bundle([event("A", "10-03-2026", 10, 8)], "Regio Noord")
        summaries = read_bundle(bundle)
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["source"], "Regio Noord")

    def test_importing_a_full_dossier_takes_only_the_figures(self):
        """Andermans dossier importeren mag nooit deelnemers binnenhalen."""
        dossier = {
            "format": "DCPL Event Management Tool",
            "version": 11,
            "events": [event("A", "10-03-2026", 10, 8)],
            "records": [{"Voornaam": "Jan", "Achternaam": "Jansen"}],
        }
        summaries = read_bundle(dossier, "Collega")

        self.assertEqual(len(summaries), 1)
        self.assertNotIn("Jansen", repr(summaries))
        self.assertEqual(summaries[0]["source"], "Collega")

    def test_own_and_imported_events_combine_into_one_series(self):
        own = collect_summaries([event("Eigen", "10-03-2026", 100, 50)], source="Eigen dossier")
        other = read_bundle(anonymous_bundle([event("Extern", "10-04-2026", 100, 90)], "Regio Noord"))
        series = build_series(own + other, "opkomst_percentage")

        self.assertEqual(series["events"], 2)
        self.assertEqual([point["label"] for point in series["points"]], ["Eigen", "Extern"])

    def test_unreadable_payload_is_harmless(self):
        self.assertEqual(read_bundle({}), [])
        self.assertEqual(read_bundle("geen dict"), [])


if __name__ == "__main__":
    unittest.main()
