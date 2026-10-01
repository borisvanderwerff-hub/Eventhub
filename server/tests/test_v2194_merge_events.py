"""Evenementen bundelen tot één evenement.

Dezelfde dag staat soms onder meerdere namen online om verschillende
doelgroepen te trekken: Meeloopdag Marine Catering, Administratie en
Logistiek zijn in werkelijkheid één meeloopdag. In EventHub werden dat drie
evenementen met drie deelnemerslijsten, drie statistieken en een
opkomstpercentage over een derde van de mensen.

Na het samenvoegen is het één evenement. De namen blijven per deelnemer
bewaard als inschrijving - dat is juist de informatie waarvoor die aparte
aanmeldpagina's bestaan.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_core import (
    AANWEZIG,
    AFGEMELD,
    AFWEZIG,
    ONBEKEND,
    add_registration,
    attendance_status,
    common_event_name,
    distinctive_labels,
    merge_duplicate_registrations,
    merge_event_into,
    record_events,
    registrations,
    set_attendance,
    strongest_status,
)

APP_SOURCE = desktop_source(ROOT)

CATERING = "Meeloopdag Marine Catering (30-09-'26)"
ADMIN = "Meeloopdag Marine Administratie (30-09-'26)"
LOGISTIEK = "Meeloopdag Marine Logistiek (30-09-'26)"
BUNDEL = "Meeloopdag Marine (30-09-'26)"
ANDER = "Open dag (01-01-'26)"


def deelnemer(voornaam, evenementen, standen=None):
    record = {"_id": voornaam.lower(), "Voornaam": voornaam, "Achternaam": "Jansen",
              "Email": f"{voornaam.lower()}@x.nl", "Evenement": "; ".join(evenementen),
              "Aanwezig": {}}
    for naam, status in (standen or {}).items():
        set_attendance(record, naam, status)
    return record


class NamesAndLabelsTests(unittest.TestCase):
    def test_de_gedeelde_naam_wordt_de_bundelnaam(self):
        self.assertEqual(common_event_name([CATERING, ADMIN, LOGISTIEK]), "Meeloopdag Marine")

    def test_het_onderscheidende_deel_wordt_het_label(self):
        labels = distinctive_labels([CATERING, ADMIN, LOGISTIEK])

        self.assertEqual(labels[CATERING], "Catering")
        self.assertEqual(labels[ADMIN], "Administratie")
        self.assertEqual(labels[LOGISTIEK], "Logistiek")

    def test_zonder_gedeeld_deel_blijft_de_hele_naam_over(self):
        labels = distinctive_labels(["Open dag (01-01-'26)", "Banenmarkt (01-01-'26)"])

        self.assertEqual(labels["Open dag (01-01-'26)"], "Open dag")
        self.assertEqual(labels["Banenmarkt (01-01-'26)"], "Banenmarkt")

    def test_een_enkele_naam_houdt_zichzelf(self):
        self.assertEqual(distinctive_labels([CATERING])[CATERING], "Meeloopdag Marine Catering")


class StrongestStatusTests(unittest.TestCase):
    def test_aanwezig_wint_van_de_rest(self):
        self.assertEqual(strongest_status(ONBEKEND, AFGEMELD, AFWEZIG, AANWEZIG), AANWEZIG)

    def test_een_uitspraak_wint_van_onbekend(self):
        self.assertEqual(strongest_status(ONBEKEND, AFGEMELD), AFGEMELD)
        self.assertEqual(strongest_status(AFWEZIG, ONBEKEND), AFWEZIG)

    def test_zonder_standen_blijft_het_onbekend(self):
        self.assertEqual(strongest_status(), ONBEKEND)


class RegistrationsTests(unittest.TestCase):
    def test_de_aanmeldpagina_wordt_genoteerd(self):
        record = deelnemer("Jan", [CATERING])

        self.assertTrue(add_registration(record, "Catering"))
        self.assertEqual(registrations(record), ["Catering"])

    def test_dezelfde_pagina_komt_er_niet_twee_keer_in(self):
        record = deelnemer("Jan", [CATERING])
        add_registration(record, "Catering")

        self.assertFalse(add_registration(record, "catering"))
        self.assertEqual(registrations(record), ["Catering"])

    def test_twee_aanmeldingen_blijven_allebei_staan(self):
        record = deelnemer("Jan", [CATERING])
        add_registration(record, "Catering")
        add_registration(record, "Logistiek")

        self.assertEqual(registrations(record), ["Catering", "Logistiek"])


class MergeEventIntoTests(unittest.TestCase):
    def test_de_koppeling_verhuist(self):
        record = deelnemer("Jan", [CATERING], {CATERING: AANWEZIG})

        merge_event_into([record], CATERING, BUNDEL, "Catering")

        self.assertEqual(record_events(record), [BUNDEL])
        self.assertEqual(attendance_status(record, BUNDEL), AANWEZIG)

    def test_de_herkomst_blijft_bewaard(self):
        record = deelnemer("Jan", [CATERING], {CATERING: AANWEZIG})

        merge_event_into([record], CATERING, BUNDEL, "Catering")

        self.assertEqual(registrations(record), ["Catering"])

    def test_een_ander_evenement_blijft_ongemoeid(self):
        """Anders sleept het bundelen de rest van iemands dossier mee."""
        record = deelnemer("Jan", [CATERING, ANDER], {CATERING: AFWEZIG, ANDER: AANWEZIG})

        merge_event_into([record], CATERING, BUNDEL, "Catering")

        self.assertEqual(record_events(record), [BUNDEL, ANDER])
        self.assertEqual(attendance_status(record, ANDER), AANWEZIG)
        self.assertEqual(attendance_status(record, BUNDEL), AFWEZIG)

    def test_de_sterkste_uitspraak_wint_bij_twee_lijsten(self):
        record = deelnemer("Jan", [CATERING, BUNDEL], {CATERING: AANWEZIG, BUNDEL: ONBEKEND})

        merge_event_into([record], CATERING, BUNDEL, "Catering")

        self.assertEqual(attendance_status(record, BUNDEL), AANWEZIG)
        self.assertEqual(record_events(record), [BUNDEL])

    def test_afgemeld_verdwijnt_niet_onder_onbekend(self):
        record = deelnemer("Jan", [CATERING], {CATERING: AFGEMELD})

        merge_event_into([record], CATERING, BUNDEL, "Catering")

        self.assertEqual(attendance_status(record, BUNDEL), AFGEMELD)

    def test_het_doelevenement_labelt_ook_zijn_eigen_deelnemers(self):
        """De naam van het doelevenement is zelf ook een aanmeldpagina."""
        record = deelnemer("Jan", [LOGISTIEK], {LOGISTIEK: AANWEZIG})

        merge_event_into([record], LOGISTIEK, LOGISTIEK, "Logistiek")

        self.assertEqual(registrations(record), ["Logistiek"])
        self.assertEqual(attendance_status(record, LOGISTIEK), AANWEZIG)

    def test_wie_er_niet_bij_hoort_wordt_niet_aangeraakt(self):
        record = deelnemer("Els", [ANDER], {ANDER: AANWEZIG})

        self.assertEqual(merge_event_into([record], CATERING, BUNDEL, "Catering"), 0)
        self.assertEqual(record_events(record), [ANDER])
        self.assertEqual(registrations(record), [])


class DuplicateRegistrationTests(unittest.TestCase):
    def test_dezelfde_persoon_uit_twee_lijsten_wordt_een_deelnemer(self):
        eerste = deelnemer("Jan", [BUNDEL], {BUNDEL: AFWEZIG})
        add_registration(eerste, "Catering")
        tweede = deelnemer("Jan", [BUNDEL], {BUNDEL: AANWEZIG})
        add_registration(tweede, "Logistiek")

        overgebleven, dubbel = merge_duplicate_registrations([eerste, tweede], BUNDEL)

        self.assertEqual(dubbel, 1)
        self.assertEqual(len(overgebleven), 1)
        self.assertEqual(registrations(overgebleven[0]), ["Catering", "Logistiek"])
        self.assertEqual(attendance_status(overgebleven[0], BUNDEL), AANWEZIG)

    def test_verschillende_mensen_blijven_apart(self):
        overgebleven, dubbel = merge_duplicate_registrations(
            [deelnemer("Jan", [BUNDEL]), deelnemer("Sanne", [BUNDEL])], BUNDEL
        )

        self.assertEqual(dubbel, 0)
        self.assertEqual(len(overgebleven), 2)

    def test_deelnemers_van_andere_evenementen_tellen_niet_mee(self):
        els = deelnemer("Els", [ANDER])
        tweeling = deelnemer("Els", [ANDER])

        overgebleven, dubbel = merge_duplicate_registrations([els, tweeling], BUNDEL)

        self.assertEqual(dubbel, 0)
        self.assertEqual(len(overgebleven), 2)


class TheWholeMeeloopdagTests(unittest.TestCase):
    """Drie aanmeldpagina's van dezelfde dag worden één evenement."""

    def setUp(self):
        self.records = [
            deelnemer("Jan", [CATERING], {CATERING: AANWEZIG}),
            deelnemer("Sanne", [CATERING], {CATERING: AFWEZIG}),
            deelnemer("Peter", [ADMIN], {ADMIN: AANWEZIG}),
            deelnemer("Lotte", [ADMIN], {ADMIN: AFGEMELD}),
            deelnemer("Youssef", [LOGISTIEK], {LOGISTIEK: ONBEKEND}),
            deelnemer("Els", [ANDER], {ANDER: AANWEZIG}),
        ]
        namen = [LOGISTIEK, CATERING, ADMIN]
        labels = distinctive_labels(namen)
        for naam in namen:
            merge_event_into(self.records, naam, BUNDEL, labels[naam])
        self.records, self.dubbel = merge_duplicate_registrations(self.records, BUNDEL)

    def _van_bundel(self):
        return [r for r in self.records if BUNDEL in record_events(r)]

    def test_iedereen_hangt_aan_het_gebundelde_evenement(self):
        self.assertEqual(len(self._van_bundel()), 5)

    def test_de_aanwezigheid_gaat_ongeschonden_mee(self):
        standen = {r["Voornaam"]: attendance_status(r, BUNDEL) for r in self._van_bundel()}

        self.assertEqual(standen, {
            "Jan": AANWEZIG, "Sanne": AFWEZIG, "Peter": AANWEZIG,
            "Lotte": AFGEMELD, "Youssef": ONBEKEND,
        })

    def test_de_herkomst_is_per_deelnemer_terug_te_vinden(self):
        herkomst = {r["Voornaam"]: registrations(r) for r in self._van_bundel()}

        self.assertEqual(herkomst["Jan"], ["Catering"])
        self.assertEqual(herkomst["Peter"], ["Administratie"])
        self.assertEqual(herkomst["Youssef"], ["Logistiek"])

    def test_een_deelnemer_van_een_ander_evenement_blijft_erbuiten(self):
        els = next(r for r in self.records if r["Voornaam"] == "Els")

        self.assertEqual(record_events(els), [ANDER])
        self.assertEqual(registrations(els), [])

    def test_de_oude_evenementnamen_zijn_nergens_meer_gekoppeld(self):
        for record in self.records:
            for naam in (CATERING, ADMIN, LOGISTIEK):
                self.assertNotIn(naam, record_events(record))


class TheOriginSurvivesSavingTests(unittest.TestCase):
    """prepare_record bouwt elk record bij het openen opnieuw op uit vaste velden.

    Een nieuw veld dat daar niet in staat verdwijnt bij het opslaan en opnieuw
    openen, zonder dat je het merkt.
    """

    def test_prepare_record_houdt_de_inschrijving_vast(self):
        self.assertIn("record[INSCHRIJVING] = str(source.get(INSCHRIJVING", APP_SOURCE)

    def test_een_leeg_record_kent_het_veld(self):
        start = APP_SOURCE.index("def empty_record")
        self.assertIn("INSCHRIJVING:", APP_SOURCE[start:start + 900])


class TheMergeIsVisibleTests(unittest.TestCase):
    """Na het samenvoegen moet je kunnen zien waar het evenement uit bestaat.

    Zonder dat is de herkomst wel vastgelegd maar nergens terug te vinden, en
    is het samenvoegen een verlies in plaats van een winst.
    """

    def test_de_inschrijving_is_een_kolom_die_je_kunt_aanzetten(self):
        self.assertIn('"Inschrijving": "Inschrijving",', APP_SOURCE)
        self.assertIn('"Gebruik", "Inschrijving",', APP_SOURCE)

    def test_het_evenementoverzicht_toont_de_onderdelen(self):
        start = APP_SOURCE.index("def _listings_html")
        block = APP_SOURCE[start:start + 700]

        self.assertIn("Samengevoegd uit", block)
        self.assertIn("deelnemer(s)", block)

    def test_een_gewoon_evenement_krijgt_geen_extra_regel(self):
        """Wie niets heeft samengevoegd hoort niets nieuws te zien."""
        start = APP_SOURCE.index("def _event_listings")
        block = APP_SOURCE[start:start + 800]

        self.assertIn("if len(listings) < 2:", block)
        self.assertIn("return []", block)

    def test_de_evenementenlijst_toont_het_aantal_inschrijvingen(self):
        self.assertIn('{len(samengevoegd)} inschrijvingen', APP_SOURCE)

    def test_de_grafiek_per_inschrijving_verschijnt_alleen_als_hij_iets_zegt(self):
        self.assertIn('"listing": ("Inschrijving"', APP_SOURCE)
        self.assertIn('self.statistics_cards["listing"].setVisible(bool(inschrijvingen))', APP_SOURCE)

    def test_de_grafiek_telt_elke_aanmeldpagina(self):
        start = APP_SOURCE.index("def _registration_counts")
        block = APP_SOURCE[start:start + 600]

        self.assertIn("for label in registrations(record):", block)


class TheApplicationOffersItTests(unittest.TestCase):
    def _handler(self):
        start = APP_SOURCE.index("def merge_selected_events")
        return APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]

    def test_de_actie_staat_in_het_evenementmenu(self):
        self.assertIn('menu.addAction("Samenvoegen met...", self.merge_selected_events)', APP_SOURCE)

    def test_er_komt_een_waarschuwing_met_annuleren_als_standaard(self):
        handler = self._handler()

        self.assertIn("QMessageBox.warning(", handler)
        self.assertIn("QMessageBox.StandardButton.Cancel,\n        )", handler)

    def test_zonder_bevestiging_verandert_er_niets(self):
        handler = self._handler()
        bevestiging = handler.index("if antwoord != QMessageBox.StandardButton.Yes:")

        self.assertLess(bevestiging, handler.index("merge_event_into("))

    def test_evenementen_van_dezelfde_dag_en_plaats_staan_voorgevinkt(self):
        start = APP_SOURCE.index("def _merge_candidates")
        block = APP_SOURCE[start:start + 1200]

        self.assertIn("zelfde_dag", block)
        self.assertIn("zelfde_plek", block)

    def test_een_naam_die_al_bestaat_wordt_geweigerd(self):
        self.assertIn("Naam al in gebruik", self._handler())

    def test_de_aanmeldpagina_s_worden_op_het_evenement_bewaard(self):
        handler = self._handler()

        self.assertIn('event["listings"] = listings', handler)
        self.assertIn('"rudder_event_id"', handler)


if __name__ == "__main__":
    unittest.main()
