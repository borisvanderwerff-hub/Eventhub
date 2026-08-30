"""Bezoekerslijsten inladen voor trendanalyse, zonder persoonsgegevens te bewaren."""
from datetime import date
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import set_present
from emt_trends import (
    AGE_GROUPS,
    age_group,
    age_on,
    build_series,
    summaries_from_records,
    summarise_records,
)


EVENT = "Voorlichting Ermelo"


def visitor(voornaam, opleiding, geslacht, geboren, aanwezig, evenement=EVENT, gast_van=""):
    record = {
        "_id": voornaam.lower(),
        "Evenement": evenement,
        "Voornaam": voornaam,
        "Achternaam": f"Van {voornaam}",
        "Geboortedatum": geboren,
        "Opleiding": opleiding,
        "Geslacht": geslacht,
        "GastVan": gast_van,
        "Aanwezig": {},
    }
    set_present(record, evenement, aanwezig)
    return record


def sample():
    return [
        visitor("Jan", "HBO", "Man", "01-06-2005", True),
        visitor("Sanne", "HBO", "Vrouw", "14-11-2004", True),
        visitor("Youssef", "MBO", "Man", "03-02-1999", False),
        visitor("Lotte", "MBO", "Vrouw", "20-09-2007", False),
        visitor("Noor", "MBO", "Vrouw", "20-09-2007", True, gast_van="Lotte"),
    ]


class AgeGroupTests(unittest.TestCase):
    """Eén indeling, gedeeld met de app, anders zijn groepen niet vergelijkbaar."""

    def test_boundaries(self):
        self.assertEqual(age_group(17), "Jonger dan 18")
        self.assertEqual(age_group(18), "18–20")
        self.assertEqual(age_group(20), "18–20")
        self.assertEqual(age_group(21), "21–24")
        self.assertEqual(age_group(40), "40 en ouder")
        self.assertEqual(age_group(None), "Onbekend")

    def test_age_is_measured_on_the_reference_date(self):
        self.assertEqual(age_on("01-06-2008", date(2026, 4, 2)), 17)
        self.assertEqual(age_on("01-06-2008", date(2026, 7, 2)), 18)

    def test_unusable_birthdate_gives_none(self):
        self.assertIsNone(age_on("", date(2026, 4, 2)))
        self.assertIsNone(age_on("geen datum", date(2026, 4, 2)))

    def test_app_uses_the_same_definition(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        start = source.index("def _age_label(self")
        block = source[start:source.index("\n    def ", start + 1)]
        self.assertIn("trend_age_group(", block)

    def test_group_names_are_declared_once(self):
        self.assertEqual(len(AGE_GROUPS), 7)


class SummariseTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = summarise_records(sample(), EVENT, "15-01-2026")

    def test_totals(self):
        self.assertEqual(self.snapshot["aangemeld"], 5)
        self.assertEqual(self.snapshot["aanwezig"], 3)
        self.assertEqual(self.snapshot["noshows"], 2)
        self.assertEqual(self.snapshot["opkomst_percentage"], 60.0)

    def test_introducees_are_counted(self):
        self.assertEqual(self.snapshot["introducees"], 1)

    def test_distribution_splits_attendance(self):
        opleiding = self.snapshot["verdeling"]["Opleidingsniveau"]
        self.assertEqual(opleiding["HBO"], {"aangemeld": 2, "aanwezig": 2})
        self.assertEqual(opleiding["MBO"], {"aangemeld": 3, "aanwezig": 1})

    def test_uses_schema_two_like_the_app(self):
        self.assertEqual(self.snapshot["schema"], 2)

    def test_summary_holds_no_personal_data(self):
        blob = repr(self.snapshot)
        for personal in ("Jan", "Sanne", "Youssef", "Van Jan", "01-06-2005"):
            self.assertNotIn(personal, blob)

    def test_empty_list_does_not_divide_by_zero(self):
        empty = summarise_records([], EVENT, "15-01-2026")
        self.assertEqual(empty["aangemeld"], 0)
        self.assertEqual(empty["opkomst_percentage"], 0.0)


class GroupingTests(unittest.TestCase):
    """Eén bestand kan deelnemers van meerdere evenementen bevatten."""

    def setUp(self):
        self.records = sample() + [
            visitor("Pim", "HBO", "Man", "01-01-2000", True, evenement="Meeloopdag Den Helder"),
            visitor("Eva", "HBO", "Vrouw", "01-01-2001", False, evenement="Meeloopdag Den Helder"),
        ]

    def test_each_event_becomes_its_own_summary(self):
        summaries = summaries_from_records(self.records)
        self.assertEqual([item["name"] for item in summaries], ["Meeloopdag Den Helder", EVENT])
        self.assertEqual(summaries[0]["statistiek"]["aangemeld"], 2)
        self.assertEqual(summaries[1]["statistiek"]["aangemeld"], 5)

    def test_supplied_dates_land_on_the_summaries(self):
        summaries = summaries_from_records(self.records, {EVENT: "15-01-2026"})
        by_name = {item["name"]: item for item in summaries}
        self.assertEqual(by_name[EVENT]["date"], "15-01-2026")
        self.assertEqual(by_name["Meeloopdag Den Helder"]["date"], "")

    def test_undated_events_still_count_in_totals(self):
        summaries = summaries_from_records(self.records)
        series = build_series(summaries, "aangemeld")
        self.assertEqual(series["events"], 2)

    def test_records_without_an_event_get_a_placeholder(self):
        summaries = summaries_from_records([{"Evenement": "", "Voornaam": "X", "Aanwezig": {}}])
        self.assertEqual(summaries[0]["name"], "Onbekend evenement")

    def test_source_label_is_carried_through(self):
        summaries = summaries_from_records(self.records, source="2 bezoekerslijsten")
        self.assertTrue(all(item["source"] == "2 bezoekerslijsten" for item in summaries))

    def test_imported_summaries_combine_with_own_events_in_one_series(self):
        summaries = summaries_from_records(
            self.records, {EVENT: "15-01-2026", "Meeloopdag Den Helder": "15-04-2026"}
        )
        series = build_series(summaries, "opkomst_percentage", period="quarter")
        self.assertEqual([point["label"] for point in series["points"]], ["K1 2026", "K2 2026"])


class ImportFlowTests(unittest.TestCase):
    """De inlaadroutine mag geen deelnemersrijen achterlaten."""

    def setUp(self):
        self.source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

    def _block(self, name):
        start = self.source.index(f"def {name}(self")
        return self.source[start:self.source.index("\n    def ", start + 1)]

    def test_multiple_files_can_be_selected(self):
        self.assertIn("getOpenFileNames", self._block("import_trend_data"))

    def test_spreadsheets_are_summarised_not_stored(self):
        block = self._block("import_trend_data")
        self.assertIn("trend_summaries_from_records(", block)
        self.assertIn("existing_records=[]", block)
        # De ingelezen rijen mogen nooit in het dossier belanden.
        self.assertNotIn("self.records.extend", block)
        self.assertNotIn("self.records +=", block)

    def test_dates_are_requested_because_a_list_has_none(self):
        self.assertIn("_ask_trend_event_dates", self._block("import_trend_data"))

    def test_cancelling_the_date_dialog_aborts_the_import(self):
        block = self._block("import_trend_data")
        self.assertIn("if dates is None:", block)

    def test_known_events_prefill_their_date(self):
        self.assertIn("self._event_by_name(name)", self._block("_ask_trend_event_dates"))


class PdfExportTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

    def test_export_writes_a_pdf(self):
        start = self.source.index("def export_trend_data(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("QPrinter.OutputFormat.PdfFormat", block)
        self.assertIn(".pdf", block)

    def test_pdf_embeds_the_chart_and_states_it_is_anonymous(self):
        start = self.source.index("def _trend_pdf_document(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("ImageResource", block)
        self.assertIn("geen namen", block)


if __name__ == "__main__":
    unittest.main()
