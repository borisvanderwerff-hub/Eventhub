"""Aanwezigheid uit oudere imports staat onder de naam van de aanmeldlijst.

Die naam is geen evenement: hij mist de datum die EventHub erbij zet, en soms
heet de lijst zelfs heel anders dan het evenement waarin hij is ingelezen.
Zolang die sleutel nergens bij hoort telt de aanwezigheid niet mee en staat een
afgelopen evenement vol no-shows, met een filter dat niets lijkt te doen.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import (
    event_base_name,
    is_present,
    record_events,
    repair_orphan_attendance,
    set_present,
)

APP_SOURCE = desktop_source(ROOT)

EVENEMENT = "Meeloopdag Defensie (26-08-'26)"
ANDER = "Meeloopdag Defensie (25-11-'26)"


def bezoeker(gekoppeld, aanwezigheid):
    record = {"Voornaam": "Jan", "Achternaam": "Jansen",
              "Evenement": "; ".join(gekoppeld), "Aanwezig": {}}
    for naam, aanwezig in aanwezigheid.items():
        set_present(record, naam, aanwezig)
    return record


class EventBaseNameTests(unittest.TestCase):
    def test_de_datum_gaat_eraf(self):
        self.assertEqual(event_base_name(EVENEMENT), "Meeloopdag Defensie")
        self.assertEqual(event_base_name("Meeloopdag Marine (26-08-2026)"), "Meeloopdag Marine")

    def test_een_naam_zonder_datum_blijft_heel(self):
        self.assertEqual(event_base_name("Ladies Day"), "Ladies Day")


class RepairOrphanAttendanceTests(unittest.TestCase):
    def test_de_lijstnaam_zonder_datum_komt_thuis(self):
        record = bezoeker([EVENEMENT], {"Meeloopdag Defensie": True})

        self.assertEqual(repair_orphan_attendance([record], [EVENEMENT]), 1)
        self.assertTrue(is_present(record, EVENEMENT))
        self.assertEqual(list(record["Aanwezig"]), [EVENEMENT])

    def test_een_lijst_met_een_eigen_naam_komt_ook_thuis(self):
        """De lijst Ladies Day is ingelezen in de Meeloopdag; iets anders kan het niet zijn."""
        record = bezoeker([EVENEMENT], {"Ladies Day": True})

        repair_orphan_attendance([record], [EVENEMENT])

        self.assertTrue(is_present(record, EVENEMENT))

    def test_afwezig_blijft_afwezig(self):
        record = bezoeker([EVENEMENT], {"Ladies Day": False})

        repair_orphan_attendance([record], [EVENEMENT])

        self.assertFalse(is_present(record, EVENEMENT))
        self.assertIn(EVENEMENT, record["Aanwezig"])

    def test_een_bestaande_registratie_wordt_niet_teruggedraaid(self):
        record = bezoeker([EVENEMENT], {EVENEMENT: True, "Ladies Day": False})

        repair_orphan_attendance([record], [EVENEMENT])

        self.assertTrue(is_present(record, EVENEMENT))

    def test_bij_meerdere_evenementen_beslist_de_basisnaam(self):
        record = bezoeker([EVENEMENT, "Open dag (01-01-'26)"], {"Meeloopdag Defensie": True})

        repair_orphan_attendance([record], [EVENEMENT, "Open dag (01-01-'26)"])

        self.assertTrue(is_present(record, EVENEMENT))
        self.assertFalse(is_present(record, "Open dag (01-01-'26)"))

    def test_zonder_duidelijk_tehuis_blijft_het_staan(self):
        """Twee keer dezelfde basisnaam: gokken zou aanwezigheid verzinnen."""
        record = bezoeker([EVENEMENT, ANDER], {"Meeloopdag Defensie": True})

        self.assertEqual(repair_orphan_attendance([record], [EVENEMENT, ANDER]), 0)
        self.assertIn("Meeloopdag Defensie", record["Aanwezig"])
        self.assertFalse(is_present(record, EVENEMENT))

    def test_een_gezond_dossier_blijft_ongemoeid(self):
        record = bezoeker([EVENEMENT], {EVENEMENT: True})

        self.assertEqual(repair_orphan_attendance([record], [EVENEMENT]), 0)
        self.assertEqual(list(record["Aanwezig"]), [EVENEMENT])

    def test_een_tweede_keer_draaien_verandert_niets(self):
        records = [bezoeker([EVENEMENT], {"Ladies Day": True}),
                   bezoeker([EVENEMENT], {"Meeloopdag Defensie": False})]

        self.assertEqual(repair_orphan_attendance(records, [EVENEMENT]), 2)
        self.assertEqual(repair_orphan_attendance(records, [EVENEMENT]), 0)

    def test_de_koppeling_aan_het_evenement_verandert_niet(self):
        record = bezoeker([EVENEMENT], {"Ladies Day": True})

        repair_orphan_attendance([record], [EVENEMENT])

        self.assertEqual(record_events(record), [EVENEMENT])


class TheProjectLoadRepairsTests(unittest.TestCase):
    def test_een_geopend_dossier_wordt_hersteld(self):
        start = APP_SOURCE.index("def _apply_project_payload")
        block = APP_SOURCE[start:start + 2000]
        self.assertIn("repair_orphan_attendance(", block)

    def test_de_gebruiker_hoort_dat_het_is_gebeurd(self):
        self.assertIn("_repaired_attendance", APP_SOURCE)


if __name__ == "__main__":
    unittest.main()
