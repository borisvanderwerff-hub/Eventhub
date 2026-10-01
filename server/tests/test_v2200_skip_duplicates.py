"""Een dubbele inschrijving overslaan, zodat er nog een persoon overblijft.

Vijf bezoekers van de vaardag stonden twee keer in de lijst: zelfde naam,
zelfde geboortedatum, twee aanmeldingen. Daardoor telde het evenement 102
aanmeldingen terwijl er 97 mensen waren, waren er vijf no-shows te veel, en
kon de livesessie hun incheck niet koppelen omdat hij niet wil raden welke van
de twee bedoeld is.

Overslaan in plaats van wissen: de regel blijft in het dossier staan, want een
verwijderde regel komt bij de volgende Rudder-import gewoon terug.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import (
    AANWEZIG,
    AFWEZIG,
    DUBBELE_INSCHRIJVING,
    ONBEKEND,
    OVERGESLAGEN,
    absorb_duplicate,
    attendance_status,
    counting_records,
    include_again,
    is_skipped,
    registrations,
    richest_record,
    set_attendance,
    skip_reason,
)

APP_SOURCE = desktop_source(ROOT)

VAARDAG = "Meeloopdag Marine (Varend) (02-09-'26)"


def deelnemer(voornaam="Jelmer", stand=None, **velden):
    record = {"Voornaam": voornaam, "Achternaam": "Bezemer", "Geboortedatum": "12-10-2005",
              "Evenement": VAARDAG, "Aanwezig": {}, OVERGESLAGEN: ""}
    record.update(velden)
    if stand:
        set_attendance(record, VAARDAG, stand)
    return record


class SkippingTests(unittest.TestCase):
    def test_de_overgeslagen_regel_telt_niet_meer_mee(self):
        blijft, dubbel = deelnemer(), deelnemer()

        absorb_duplicate(blijft, dubbel)

        self.assertTrue(is_skipped(dubbel))
        self.assertFalse(is_skipped(blijft))
        self.assertEqual(counting_records([blijft, dubbel]), [blijft])

    def test_de_reden_blijft_bewaard(self):
        blijft, dubbel = deelnemer(), deelnemer()

        absorb_duplicate(blijft, dubbel)

        self.assertEqual(skip_reason(dubbel), DUBBELE_INSCHRIJVING)

    def test_de_aanwezigheid_gaat_niet_verloren(self):
        """Het probleem van Jelmer: zijn aanwezigheid stond op de andere regel."""
        blijft = deelnemer(stand=AFWEZIG)
        dubbel = deelnemer(stand=AANWEZIG)

        absorb_duplicate(blijft, dubbel)

        self.assertEqual(attendance_status(blijft, VAARDAG), AANWEZIG)

    def test_een_afwezigheid_overschrijft_geen_aanwezigheid(self):
        blijft = deelnemer(stand=AANWEZIG)
        dubbel = deelnemer(stand=AFWEZIG)

        absorb_duplicate(blijft, dubbel)

        self.assertEqual(attendance_status(blijft, VAARDAG), AANWEZIG)

    def test_lege_velden_worden_aangevuld(self):
        blijft = deelnemer(Email="", Telefoonnummer="0612345678")
        dubbel = deelnemer(Email="jelmer@x.nl", Telefoonnummer="0699999999")

        absorb_duplicate(blijft, dubbel)

        self.assertEqual(blijft["Email"], "jelmer@x.nl")
        self.assertEqual(blijft["Telefoonnummer"], "0612345678", "ingevulde gegevens blijven staan")

    def test_beide_inschrijvingen_blijven_zichtbaar(self):
        blijft, dubbel = deelnemer(), deelnemer()
        dubbel["Inschrijving"] = "Catering"

        absorb_duplicate(blijft, dubbel)

        self.assertEqual(registrations(blijft), ["Catering"])

    def test_het_kan_worden_teruggedraaid(self):
        blijft, dubbel = deelnemer(), deelnemer()
        absorb_duplicate(blijft, dubbel)

        self.assertTrue(include_again(dubbel))
        self.assertFalse(is_skipped(dubbel))
        self.assertEqual(len(counting_records([blijft, dubbel])), 2)

    def test_terugdraaien_van_een_gewone_regel_doet_niets(self):
        self.assertFalse(include_again(deelnemer()))

    def test_een_regel_slaat_zichzelf_niet_over(self):
        record = deelnemer(stand=AANWEZIG)

        absorb_duplicate(record, record)

        self.assertFalse(is_skipped(record))


class WhichRecordStaysTests(unittest.TestCase):
    def test_de_regel_met_aanwezigheid_wint(self):
        kaal = deelnemer(stand=AANWEZIG)
        vol = deelnemer(stand=ONBEKEND, Email="jelmer@x.nl", Telefoonnummer="0612345678",
                        Geboorteplaats="Den Helder")

        self.assertIs(richest_record([vol, kaal]), kaal)

    def test_anders_wint_de_best_gevulde(self):
        kaal = deelnemer()
        vol = deelnemer(Email="jelmer@x.nl", Telefoonnummer="0612345678")

        self.assertIs(richest_record([kaal, vol]), vol)

    def test_zonder_regels_geen_keuze(self):
        self.assertIsNone(richest_record([]))


class TheApplicationHidesThemTests(unittest.TestCase):
    def test_overgeslagen_regels_vallen_uit_de_lijsten_en_tellingen(self):
        start = APP_SOURCE.index("def _filtered_records")
        block = APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]

        self.assertIn("if include_skipped else [record for record in rows if not is_skipped(record)]", block)

    def test_ook_uit_de_deelnemers_van_een_evenement(self):
        start = APP_SOURCE.index("def _event_visitors")
        block = APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]

        self.assertIn("if not is_skipped(r)", block)

    def test_gegevenscontrole_toont_ze_juist_wel(self):
        """Anders kun je nergens meer zien wat je hebt overgeslagen."""
        self.assertIn("self._quality_issues(self._filtered_records(include_skipped=True))", APP_SOURCE)
        self.assertIn("— overgeslagen", APP_SOURCE)

    def test_het_staat_bij_de_statistieken_vermeld(self):
        """Een telling die niet bij de lijst past hoort zichzelf te verklaren."""
        self.assertIn("dubbele inschrijving(en) tellen niet mee.", APP_SOURCE)

    def test_de_acties_staan_in_het_rijmenu(self):
        self.assertIn('("Dubbele inschrijving overslaan", self.skip_duplicate_registration)', APP_SOURCE)
        self.assertIn('("Weer meetellen", self.include_record_again)', APP_SOURCE)

    def test_er_wordt_eerst_bevestigd(self):
        start = APP_SOURCE.index("def skip_duplicate_registration")
        block = APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]
        bevestiging = block.index("if antwoord != QMessageBox.StandardButton.Yes:")

        self.assertLess(bevestiging, block.index("absorb_duplicate(blijft, other)"))
        self.assertIn("QMessageBox.StandardButton.Cancel,\n        )", block)

    def test_het_veld_overleeft_opslaan_en_openen(self):
        """Dezelfde valkuil als bij Inschrijving: prepare_record bouwt alles opnieuw op."""
        self.assertIn("record[OVERGESLAGEN] = str(source.get(OVERGESLAGEN", APP_SOURCE)
        start = APP_SOURCE.index("def empty_record")
        self.assertIn("OVERGESLAGEN:", APP_SOURCE[start:start + 900])


if __name__ == "__main__":
    unittest.main()
