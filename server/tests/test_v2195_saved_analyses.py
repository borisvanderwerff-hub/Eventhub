"""Losse analyses bewaren, en de datum per Rudder-nummer onthouden.

Een losse analyse verdween tot nu toe zodra je EventHub afsloot: de ingeladen
sets stonden alleen in het geheugen. Wie de opkomst van alle inloopdagen wilde
volgen moest elke keer alles opnieuw inladen en elke datum opnieuw intypen.

Een aanmeldlijst bevat de evenementdatum nergens - ook niet in de bestandsnaam,
want de datum daarin is het moment van exporteren. Wat wel vastligt is het
Rudder-nummer, en dat keert terug bij elke volgende export van hetzelfde
evenement.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from emt_models import EVENT_TYPES, empty_event, prepare_event
from emt_rudder import rudder_id_from_filename
from emt_trends import ANALYSIS_FORMAT, analysis_file_name, analysis_payload, read_analysis

APP_SOURCE = desktop_source(ROOT)


def bron(label, aantal=1):
    return {"label": label, "summaries": [{"naam": label, "aangemeld": aantal}]}


class AnalysisFormatTests(unittest.TestCase):
    def test_wat_erin_gaat_komt_eruit(self):
        payload = analysis_payload("Inloopdagen", [bron("lijst-a", 129), bron("lijst-b", 44)])

        naam, sources = read_analysis(payload)

        self.assertEqual(naam, "Inloopdagen")
        self.assertEqual([source["label"] for source in sources], ["lijst-a", "lijst-b"])

    def test_er_staat_bij_wanneer_hij_is_bijgewerkt(self):
        payload = analysis_payload("Inloopdagen", [bron("lijst-a")])

        self.assertEqual(payload["format"], ANALYSIS_FORMAT)
        self.assertTrue(payload["bijgewerkt"])

    def test_een_vreemd_bestand_wordt_niet_ingelezen(self):
        self.assertEqual(read_analysis({"format": "iets anders", "sources": [bron("x")]}), ("", []))
        self.assertEqual(read_analysis({}), ("", []))
        self.assertEqual(read_analysis("geen dict"), ("", []))

    def test_sets_zonder_naam_vallen_af(self):
        payload = analysis_payload("Inloopdagen", [bron("lijst-a"), {"label": "  ", "summaries": []}])

        self.assertEqual(len(read_analysis(payload)[1]), 1)

    def test_de_bestandsnaam_is_overal_toegestaan(self):
        self.assertEqual(analysis_file_name('Inloop/dag: 2026?'), "Inloop-dag- 2026-.json")
        self.assertEqual(analysis_file_name("   "), "Analyse.json")

    def test_er_gaan_geen_persoonsgegevens_in(self):
        """Een analyse werkt op aantallen; de deelnemersrijen zijn al weggegooid."""
        payload = analysis_payload("Inloopdagen", [bron("lijst-a")])

        self.assertEqual(set(payload), {"format", "version", "naam", "bijgewerkt", "sources"})
        self.assertEqual(set(payload["sources"][0]), {"label", "summaries"})


class RudderNumberTests(unittest.TestCase):
    def test_het_nummer_komt_uit_de_bestandsnaam(self):
        self.assertEqual(
            rudder_id_from_filename("meeloopdag-marine-varend-5900-registrations-1-9-2026-4-22-52.xlsx"),
            "5900",
        )

    def test_elke_export_van_hetzelfde_evenement_geeft_hetzelfde_nummer(self):
        """Daarom is het bruikbaar als geheugensleutel; de datum erin is dat niet."""
        eerste = rudder_id_from_filename("inloopdag-defensie-5947-registrations-17-8-2026-8-45-35.xlsx")
        tweede = rudder_id_from_filename("inloopdag-defensie-5947-registrations-2-9-2026-9-01-12.xlsx")

        self.assertEqual(eerste, tweede)
        self.assertEqual(eerste, "5947")

    def test_een_gewone_bestandsnaam_levert_niets_op(self):
        self.assertEqual(rudder_id_from_filename("bezoekers.xlsx"), "")
        self.assertEqual(rudder_id_from_filename(""), "")


class EventTypeTests(unittest.TestCase):
    def test_inloopdag_bestaat(self):
        self.assertIn("Inloopdag", EVENT_TYPES)

    def test_een_inloopdag_is_aan_te_maken(self):
        self.assertEqual(empty_event("Inloopdag Defensie", None, "Inloopdag")["event_type"], "Inloopdag")

    def test_een_bewaard_dossier_houdt_het_type(self):
        self.assertEqual(prepare_event({"name": "Inloopdag", "event_type": "Inloopdag"})["event_type"], "Inloopdag")

    def test_de_bestaande_types_blijven(self):
        for soort in ("Meeloopdag", "Voorlichting", "Online voorlichting"):
            self.assertIn(soort, EVENT_TYPES)


class TheApplicationKeepsAnalysesTests(unittest.TestCase):
    def test_er_is_altijd_een_analyse(self):
        """Anders laad je lijsten in die nergens worden bewaard."""
        self.assertIn('or "Losse analyse"', APP_SOURCE)

    def test_de_keuzelijst_staat_bij_de_losse_analyse(self):
        self.assertIn("self.analysis_picker = ScrollSafeComboBox()", APP_SOURCE)
        self.assertIn('self.analysis_picker.addItem("Nieuwe analyse...", "")', APP_SOURCE)

    def test_elke_wijziging_wordt_meteen_bewaard(self):
        """Geen opslaan-knop: wat je toevoegt of weghaalt staat direct op schijf."""
        self.assertGreaterEqual(APP_SOURCE.count("self._save_current_analysis()"), 3)

    def test_de_laatste_analyse_komt_terug_bij_het_opstarten(self):
        self.assertIn("self._load_analysis(self.current_analysis)", APP_SOURCE)

    def test_analyses_staan_los_van_het_dossier(self):
        """Een analyse loopt over evenementen van meerdere dossiers heen."""
        start = APP_SOURCE.index("def _analyses_dir")
        self.assertIn('self._app_data_root() / "Analyses"', APP_SOURCE[start:start + 300])


class TheDateIsRememberedTests(unittest.TestCase):
    def test_de_datum_wordt_onthouden_per_rudder_nummer(self):
        self.assertIn("def _remembered_trend_dates", APP_SOURCE)
        self.assertIn("def _remember_trend_dates", APP_SOURCE)
        self.assertIn('self.settings.setValue("trend_event_dates"', APP_SOURCE)

    def test_de_vraag_vult_hem_alvast_in(self):
        start = APP_SOURCE.index("def _ask_trend_event_dates")
        block = APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]

        self.assertIn("elif nummer and onthouden.get(nummer):", block)

    def test_het_evenement_uit_het_dossier_gaat_voor(self):
        """Staat het evenement al in EventHub, dan is die datum zekerder."""
        start = APP_SOURCE.index("def _ask_trend_event_dates")
        block = APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]
        eigen = block.index('if known and known.get("date"):')
        onthouden = block.index("elif nummer and onthouden.get(nummer):")

        self.assertLess(eigen, onthouden)

    def test_de_import_weet_welk_bestand_welk_evenement_bevat(self):
        """Zonder die koppeling is het nummer niet aan een evenementnaam te hangen."""
        self.assertIn('"events": sorted({name for record in records for name in record_events(record)}),',
                      (ROOT / "bezoekerslijst_core.py").read_text(encoding="utf-8"))
        self.assertIn("rudder_id_from_filename(report.get(\"file_name\", \"\"))", APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
