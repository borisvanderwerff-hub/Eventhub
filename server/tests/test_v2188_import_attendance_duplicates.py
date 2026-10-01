"""Ook een bezoeker die al in EventHub staat hoort de aanwezigheid mee te krijgen.

Commit 0971fdb verhuisde de aanwezigheid naar het geopende evenement, maar deed
dat alleen voor nieuwe deelnemers. Wie al in de lijst stond werd als duplicaat
aangevuld: de aanwezigheid uit het bestand verdween, en de koppeling landde op
de evenementnaam uit de bronkolom - zonder datum, dus naast het echte evenement.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import import_registration_files, is_present, record_events, set_present

APP_SOURCE = desktop_source(ROOT)

GEOPEND = "Meeloopdag Marine (02-09-'26)"
IN_BESTAND = "Meeloopdag Marine"


class ImportAttendanceForKnownVisitorsTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)

    def _lijst(self, rows):
        path = self.folder / "aanmeldingen.xlsx"
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["Voornaam", "Achternaam", "Email", "Evenement", "Aanwezigheid"])
        for row in rows:
            sheet.append(row)
        workbook.save(path)
        return [str(path)]

    def _bekende_bezoeker(self, eerder_evenement="Open dag (01-01-'26)"):
        record = {"Voornaam": "Jan", "Achternaam": "Jansen", "Email": "jan@x.nl",
                  "Evenement": eerder_evenement, "Aanwezig": {}}
        set_present(record, eerder_evenement, True)
        return record

    def test_de_aanwezigheid_uit_het_bestand_komt_erbij(self):
        bekend = self._bekende_bezoeker()
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", IN_BESTAND, "Yes"]])

        resultaat = import_registration_files(paden, [bekend], target_event=GEOPEND)

        self.assertEqual(resultaat["duplicates"], 1)
        self.assertEqual(resultaat["records"], [])
        self.assertTrue(is_present(bekend, GEOPEND))

    def test_de_koppeling_gebruikt_de_naam_van_het_geopende_evenement(self):
        """Anders maakt _ensure_events_from_records er een tweede evenement bij."""
        bekend = self._bekende_bezoeker()
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", IN_BESTAND, "Yes"]])

        import_registration_files(paden, [bekend], target_event=GEOPEND)

        self.assertIn(GEOPEND, record_events(bekend))
        self.assertNotIn(IN_BESTAND, record_events(bekend))

    def test_afwezig_in_het_bestand_blijft_afwezig(self):
        bekend = self._bekende_bezoeker()
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", IN_BESTAND, "No"]])

        import_registration_files(paden, [bekend], target_event=GEOPEND)

        self.assertFalse(is_present(bekend, GEOPEND))
        self.assertIn(GEOPEND, record_events(bekend))

    def test_een_registratie_in_eventhub_wordt_niet_teruggedraaid(self):
        """Wie hier al aanwezig staat, is gezien; het bestand overschrijft dat niet."""
        bekend = self._bekende_bezoeker()
        set_present(bekend, GEOPEND, True)
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", IN_BESTAND, "No"]])

        import_registration_files(paden, [bekend], target_event=GEOPEND)

        self.assertTrue(is_present(bekend, GEOPEND))

    def test_het_eerdere_evenement_blijft_staan(self):
        bekend = self._bekende_bezoeker()
        paden = self._lijst([["Jan", "Jansen", "jan@x.nl", IN_BESTAND, "Yes"]])

        import_registration_files(paden, [bekend], target_event=GEOPEND)

        self.assertTrue(is_present(bekend, "Open dag (01-01-'26)"))
        self.assertIn("Open dag (01-01-'26)", record_events(bekend))

    def test_een_nieuwe_deelnemer_landt_ook_goed(self):
        """De fix uit 0971fdb, nu via dezelfde weg."""
        paden = self._lijst([["Sanne", "Bakker", "sanne@x.nl", IN_BESTAND, "Yes"]])

        resultaat = import_registration_files(paden, [], target_event=GEOPEND)

        nieuw = resultaat["records"][0]
        self.assertEqual(record_events(nieuw), [GEOPEND])
        self.assertTrue(is_present(nieuw, GEOPEND))

    def test_zonder_evenement_verandert_er_niets_aan_de_bron(self):
        """De trendinvoer leest dezelfde lijsten zonder een geopend evenement."""
        paden = self._lijst([["Sanne", "Bakker", "sanne@x.nl", IN_BESTAND, "Yes"]])

        resultaat = import_registration_files(paden, [])

        self.assertEqual(record_events(resultaat["records"][0]), [IN_BESTAND])


class TheImportHandsOverTheEventTests(unittest.TestCase):
    def test_import_excel_geeft_het_geopende_evenement_door(self):
        self.assertIn(
            'import_registration_files(file_names, self.records, target_event=active_event["name"])',
            APP_SOURCE,
        )


if __name__ == "__main__":
    unittest.main()
