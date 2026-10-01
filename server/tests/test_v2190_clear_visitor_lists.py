"""Bezoekerslijst(en) wissen bij een evenement, zodat ze opnieuw ingelezen kunnen worden.

Het evenement zelf blijft staan met zijn taken en documenten; alleen de
gekoppelde bezoekers en hun aanwezigheid bij dit evenement verdwijnen.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import detach_event_from_records, is_present, record_events, set_present

APP_SOURCE = desktop_source(ROOT)

EVENEMENT = "Meeloopdag Defensie (26-08-'26)"
ANDER = "Open dag (01-01-'26)"


def bezoeker(naam, gekoppeld, aanwezig_bij=()):
    record = {"Voornaam": naam, "Achternaam": "Jansen",
              "Evenement": "; ".join(gekoppeld), "Aanwezig": {}}
    for event_name in aanwezig_bij:
        set_present(record, event_name, True)
    return record


class ClearingUnlinksTheVisitorsTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            bezoeker("Jan", [EVENEMENT], [EVENEMENT]),
            bezoeker("Sanne", [EVENEMENT]),
            bezoeker("Peter", [EVENEMENT, ANDER], [EVENEMENT, ANDER]),
            bezoeker("Els", [ANDER], [ANDER]),
        ]

    def test_de_bezoekers_van_dit_evenement_zijn_weg(self):
        overgebleven = detach_event_from_records(self.records, EVENEMENT)

        namen = [record["Voornaam"] for record in overgebleven]
        self.assertNotIn("Jan", namen)
        self.assertNotIn("Sanne", namen)

    def test_wie_ook_elders_hoort_blijft_daar_staan(self):
        overgebleven = detach_event_from_records(self.records, EVENEMENT)

        peter = next(record for record in overgebleven if record["Voornaam"] == "Peter")
        self.assertEqual(record_events(peter), [ANDER])
        self.assertTrue(is_present(peter, ANDER))
        self.assertFalse(is_present(peter, EVENEMENT))

    def test_een_ander_evenement_blijft_ongemoeid(self):
        overgebleven = detach_event_from_records(self.records, EVENEMENT)

        els = next(record for record in overgebleven if record["Voornaam"] == "Els")
        self.assertTrue(is_present(els, ANDER))

    def test_de_aanwezigheid_bij_dit_evenement_blijft_niet_hangen(self):
        """Anders duikt hij op zodra de lijst opnieuw wordt ingelezen."""
        overgebleven = detach_event_from_records(self.records, EVENEMENT)

        for record in overgebleven:
            self.assertNotIn(EVENEMENT, record["Aanwezig"])


class TheMenuOffersItTests(unittest.TestCase):
    def _handler(self):
        """Alleen deze methode, ongeacht wat er verderop in de klasse bijkomt."""
        start = APP_SOURCE.index("def clear_event_visitor_lists")
        return APP_SOURCE[start:APP_SOURCE.index('\n    def ', start + 1)]

    def test_de_actie_staat_onder_meer_acties_bij_de_deelnemers(self):
        self.assertIn(
            'participant_clear_action = participant_more_menu.addAction("Bezoekerslijst(en) wissen")',
            APP_SOURCE,
        )
        self.assertIn(
            "participant_clear_action.triggered.connect(self.clear_event_visitor_lists)",
            APP_SOURCE,
        )

    def test_de_actie_geldt_voor_het_geopende_evenement(self):
        self.assertIn("event = self._active_event()", self._handler())

    def test_er_komt_eerst_een_waarschuwing(self):
        handler = self._handler()
        self.assertIn("QMessageBox.warning(", handler)
        self.assertIn("StandardButton.Cancel,", handler)
        # Afbreken is de standaardkeuze; enter mag geen lijst wissen.
        self.assertIn("QMessageBox.StandardButton.Cancel,\n        )", handler)

    def test_zonder_bevestiging_gebeurt_er_niets(self):
        handler = self._handler()
        bevestiging = handler.index("if answer != QMessageBox.StandardButton.Yes:")
        self.assertLess(bevestiging, handler.index("detach_event_from_records"))

    def test_het_evenement_zelf_blijft_staan(self):
        """Alleen de records worden aangeraakt, self.events niet."""
        handler = self._handler()
        self.assertIn("self.records = detach_event_from_records(self.records, event_name)", handler)
        self.assertNotIn("self.events = ", handler)

    def test_de_wijziging_wordt_als_onopgeslagen_gemarkeerd(self):
        self.assertIn("self._mark_dirty()", self._handler())


if __name__ == "__main__":
    unittest.main()
