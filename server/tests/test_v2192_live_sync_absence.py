"""Een livesessie bevestigt aanwezigheid, maar verklaart niemand stilzwijgend afwezig.

De server kent present, checked_out en not_checked_in. Die laatste is ook de
beginstand van iedereen die wordt ingelezen: hij betekent 'nog niet gescand',
niet 'was er niet'. De sync nam hem over als afwezig, waardoor het openen van
een evenement met een aangemaakte maar ongebruikte livesessie de aanwezigheid
uit de aanmeldlijst wiste - van 87 aanwezigen bleven er 2 over, precies de
twee die niet op naam te matchen waren.
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bezoekerslijst_core import is_present, set_present

APP_SOURCE = desktop_source(ROOT)

EVENEMENT = "Meeloopdag Defensie (26-08-'26)"


def bezoeker(record_id, voornaam, aanwezig):
    record = {"_id": record_id, "Voornaam": voornaam, "Achternaam": "Jansen",
              "Geboortedatum": "01-01-2008", "Evenement": EVENEMENT, "Aanwezig": {}}
    set_present(record, EVENEMENT, aanwezig)
    return record


def deelnemer(participant_id, voornaam, status, checkin=None):
    return {"id": participant_id, "voornaam": voornaam, "achternaam": "Jansen",
            "geboortedatum": "01-01-2008", "attendance_status": status, "checkin_time": checkin}


class LiveSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bezoekerslijst_app

        cls.sync = staticmethod(bezoekerslijst_app.apply_live_attendance)

    def test_een_incheck_wordt_overgenomen(self):
        record = bezoeker("a", "Jan", False)

        self.sync([record], [deelnemer("a", "Jan", "present", "2026-08-26T09:00:00")], EVENEMENT)

        self.assertTrue(is_present(record, EVENEMENT))

    def test_uitchecken_telt_ook_als_aanwezig(self):
        record = bezoeker("a", "Jan", False)

        self.sync([record], [deelnemer("a", "Jan", "checked_out")], EVENEMENT)

        self.assertTrue(is_present(record, EVENEMENT))

    def test_niet_gescand_wist_de_aanwezigheid_niet(self):
        """De kern: not_checked_in is geen uitspraak over aanwezigheid."""
        record = bezoeker("a", "Jan", True)

        self.sync([record], [deelnemer("a", "Jan", "not_checked_in")], EVENEMENT)

        self.assertTrue(is_present(record, EVENEMENT))

    def test_een_ongebruikte_sessie_verandert_niets(self):
        """Een sessie met de hele lijst en nul inchecks maakte iedereen afwezig."""
        records = [bezoeker(str(index), f"Deelnemer {index}", index % 2 == 0) for index in range(20)]
        deelnemers = [deelnemer(str(index), f"Deelnemer {index}", "not_checked_in") for index in range(20)]

        gewijzigd = self.sync(records, deelnemers, EVENEMENT)

        self.assertEqual(gewijzigd, 0)
        self.assertEqual(sum(is_present(record, EVENEMENT) for record in records), 10)

    def test_een_teruggedraaide_incheck_zet_wel_afwezig(self):
        """Dat is wel een uitspraak: iemand is bewust weer uitgeboekt."""
        record = bezoeker("a", "Jan", True)

        self.sync([record], [deelnemer("a", "Jan", "not_checked_in")], EVENEMENT, reverted_ids={"a"})

        self.assertFalse(is_present(record, EVENEMENT))

    def test_inchecken_stoppen_maakt_de_rest_niet_gekomen(self):
        """Serverbeheer > Inchecken stoppen zet iedereen die niet scande op absent."""
        from bezoekerslijst_core import AFWEZIG, attendance_status

        record = bezoeker("a", "Jan", False)

        self.sync([record], [deelnemer("a", "Jan", "absent")], EVENEMENT)

        self.assertEqual(attendance_status(record, EVENEMENT), AFWEZIG)

    def test_een_vastgelegde_aanwezigheid_overleeft_het_stoppen(self):
        """De balie zegt absent omdat daar niet is gescand; EventHub weet beter.

        Een sessie waar niemand doorheen is gegaan zet iedereen op absent. Dat
        overnemen wiste 57 aanwezigen en 19 afmeldingen in een keer.
        """
        from bezoekerslijst_core import AANWEZIG, AFGEMELD, attendance_status, set_attendance

        aanwezig = bezoeker("a", "Jan", True)
        afgemeld = bezoeker("b", "Sanne", False)
        set_attendance(afgemeld, EVENEMENT, AFGEMELD)

        self.sync(
            [aanwezig, afgemeld],
            [deelnemer("a", "Jan", "absent"), deelnemer("b", "Sanne", "absent")],
            EVENEMENT,
        )

        self.assertEqual(attendance_status(aanwezig, EVENEMENT), AANWEZIG)
        self.assertEqual(attendance_status(afgemeld, EVENEMENT), AFGEMELD)

    def test_een_ingecheckte_bezoeker_blijft_aanwezig_na_het_stoppen(self):
        """De stopactie raakt alleen wie nog niet was ingecheckt."""
        record = bezoeker("a", "Jan", False)

        self.sync([record], [deelnemer("a", "Jan", "present", "2026-09-02T09:00:00")], EVENEMENT)

        self.assertTrue(is_present(record, EVENEMENT))

    def test_een_latere_live_incheck_overschrijft_handmatig_afwezig(self):
        """Afronden in EventHub mag een latere scan nooit blokkeren."""
        from bezoekerslijst_core import AFWEZIG, attendance_status, set_attendance

        record = bezoeker("a", "Jan", False)
        set_attendance(record, EVENEMENT, AFWEZIG)

        self.sync([record], [deelnemer("a", "Jan", "present", "2026-09-02T09:15:00")], EVENEMENT)

        self.assertNotEqual(attendance_status(record, EVENEMENT), AFWEZIG)
        self.assertTrue(is_present(record, EVENEMENT))

    def test_de_aanwezigheid_landt_bij_het_juiste_evenement(self):
        record = bezoeker("a", "Jan", False)
        record["Evenement"] = f"{EVENEMENT}; Open dag (01-01-'26)"

        self.sync([record], [deelnemer("a", "Jan", "present")], EVENEMENT)

        self.assertTrue(is_present(record, EVENEMENT))
        self.assertFalse(is_present(record, "Open dag (01-01-'26)"))

    def test_matchen_op_naam_werkt_nog(self):
        record = bezoeker("eigen-id", "Jan", False)

        self.sync([record], [deelnemer("server-id", "Jan", "present")], EVENEMENT)

        self.assertTrue(is_present(record, EVENEMENT))


class UnmatchedCheckinsAreReportedTests(unittest.TestCase):
    """Staat iemand twee keer in de lijst, dan weigert de koppeling te raden.

    Terecht, maar het gebeurde zonder een woord: de incheck van drie bezoekers
    van de vaardag verdween spoorloos omdat zij twee aanmeldingen hadden.
    """

    @classmethod
    def setUpClass(cls):
        import bezoekerslijst_app

        cls.sync = staticmethod(bezoekerslijst_app.apply_live_attendance)

    def test_een_dubbele_naam_wordt_gemeld(self):
        tweeling = [bezoeker("x1", "Lisanne", False), bezoeker("x2", "Lisanne", False)]
        niet_gekoppeld = []

        self.sync(tweeling, [deelnemer("server-id", "Lisanne", "present")], EVENEMENT,
                  unmatched=niet_gekoppeld)

        self.assertEqual(niet_gekoppeld, ["Lisanne Jansen"])

    def test_de_aanwezigheid_wordt_niet_gegokt(self):
        """Raden zou de aanwezigheid bij de verkeerde persoon kunnen zetten."""
        tweeling = [bezoeker("x1", "Lisanne", False), bezoeker("x2", "Lisanne", False)]

        gewijzigd = self.sync(tweeling, [deelnemer("server-id", "Lisanne", "present")], EVENEMENT)

        self.assertEqual(gewijzigd, 0)
        self.assertFalse(any(is_present(record, EVENEMENT) for record in tweeling))

    def test_op_id_koppelen_gaat_gewoon_door(self):
        """Matcht het id wel, dan is er niets te raden en telt de dubbele naam niet."""
        tweeling = [bezoeker("x1", "Lisanne", False), bezoeker("x2", "Lisanne", False)]
        niet_gekoppeld = []

        self.sync(tweeling, [deelnemer("x1", "Lisanne", "present")], EVENEMENT,
                  unmatched=niet_gekoppeld)

        self.assertEqual(niet_gekoppeld, [])
        self.assertTrue(is_present(tweeling[0], EVENEMENT))

    def test_wie_niet_is_ingecheckt_hoeft_niet_gemeld(self):
        """Alleen een verloren incheck is een probleem; de rest is ruis."""
        tweeling = [bezoeker("x1", "Lisanne", False), bezoeker("x2", "Lisanne", False)]
        niet_gekoppeld = []

        self.sync(tweeling, [deelnemer("server-id", "Lisanne", "not_checked_in")], EVENEMENT,
                  unmatched=niet_gekoppeld)

        self.assertEqual(niet_gekoppeld, [])

    def test_de_app_toont_het(self):
        self.assertIn("def _report_unmatched_checkins", APP_SOURCE)
        self.assertEqual(APP_SOURCE.count("self._report_unmatched_checkins(ongekoppeld, event)"), 2)
        self.assertIn("twee keer in de deelnemerslijst staat", APP_SOURCE)


class TheSyncAsksForRevertedCheckinsTests(unittest.TestCase):
    def test_beide_synchronisatiepunten_geven_ze_door(self):
        self.assertIn("reverted_ids=teruggedraaid,", APP_SOURCE)
        self.assertIn("reverted_ids=self._reverted_checkins(window.connection, window.event_id),", APP_SOURCE)

    def test_de_uitvraag_kijkt_naar_de_juiste_actie(self):
        start = APP_SOURCE.index("def _reverted_checkins")
        block = APP_SOURCE[start:start + 900]

        self.assertIn("action='checkin_undone'", block)


if __name__ == "__main__":
    unittest.main()
