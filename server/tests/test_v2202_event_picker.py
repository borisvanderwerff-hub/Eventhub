"""Een evenement kiezen uit kaarten in plaats van uit een lange keuzelijst.

Met tweeentwintig evenementen in een keuzelijst scrol je langs alles wat je
niet zoekt, en zie je van een regel alleen de naam. Het keuzevenster toont
standaard de acht waar je het laatst was en de acht die eraan komen, met datum,
soort, plaats en wanneer je er voor het laatst iets aan deed.
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from emt_models import empty_event, prepare_event

APP_SOURCE = desktop_source(ROOT)

NU = datetime.now()


def evenement(naam, dagen=0, soort="Meeloopdag", plaats="Den Helder", geopend=None, gewijzigd=None,
              start="", eind=""):
    event = empty_event(naam, None, soort)
    event["date"] = (date.today() + timedelta(days=dagen)).strftime("%d-%m-%Y")
    event["place"] = plaats
    event["start_time"], event["end_time"] = start, eind
    if geopend is not None:
        event["last_opened_at"] = (NU - timedelta(hours=geopend)).isoformat(timespec="minutes")
    if gewijzigd is not None:
        event["updated_at"] = (NU - timedelta(hours=gewijzigd)).isoformat(timespec="minutes")
    return event


class ActivityLineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import bezoekerslijst_app

        cls.app_module = bezoekerslijst_app

    def test_gewijzigd_gaat_voor_geopend(self):
        regel = self.app_module.event_activity_line(evenement("X", geopend=10, gewijzigd=1))

        self.assertTrue(regel.startswith("Laatst gewijzigd:"), regel)

    def test_zonder_wijziging_toont_hij_het_openen(self):
        regel = self.app_module.event_activity_line(evenement("X", geopend=3))

        self.assertTrue(regel.startswith("Laatst geopend:"), regel)

    def test_een_onaangeroerd_evenement_zegt_dat_ook(self):
        self.assertEqual(self.app_module.event_activity_line(evenement("X")), "Nog niet geopend")

    def test_onleesbare_tijdstippen_leveren_geen_fout(self):
        event = evenement("X")
        event["updated_at"] = "gisteren ergens"

        self.assertEqual(self.app_module.event_activity_line(event), "Nog niet geopend")

    def test_het_meest_recente_komt_eerst(self):
        oud = evenement("Oud", geopend=100)
        nieuw = evenement("Nieuw", geopend=1)
        nooit = evenement("Nooit")

        gesorteerd = sorted([nooit, oud, nieuw], key=self.app_module.event_recency_key)

        self.assertEqual([e["name"] for e in gesorteerd], ["Nieuw", "Oud", "Nooit"])


class PickerDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        import bezoekerslijst_app

        cls.app_module = bezoekerslijst_app
        cls.qt = QApplication.instance() or QApplication([])

    def _venster(self, events, current=""):
        dialog = self.app_module.EventPickerDialog(events, current)
        self.addCleanup(dialog.deleteLater)
        return dialog

    def _kaarten(self, dialog):
        return dialog.findChildren(self.app_module.EventCard)

    def test_standaard_acht_geopend_en_acht_komende(self):
        events = [evenement(f"Geopend {i}", dagen=-40, geopend=i + 1) for i in range(11)]
        events += [evenement(f"Komt {i}", dagen=i + 1) for i in range(11)]

        dialog = self._venster(events)

        self.assertEqual(len(self._kaarten(dialog)), 16)

    def test_zoeken_op_naam(self):
        events = [evenement("Meeloopdag Catering", dagen=5), evenement("Inloopdag Defensie", dagen=6)]
        dialog = self._venster(events)

        dialog.search_field.setText("catering")

        self.assertEqual(len(self._kaarten(dialog)), 1)

    def test_zoeken_kijkt_ook_naar_de_plaats(self):
        events = [evenement("A", dagen=5, plaats="Amsterdam"), evenement("B", dagen=6, plaats="Den Helder")]
        dialog = self._venster(events)

        dialog.search_field.setText("amsterdam")

        self.assertEqual(len(self._kaarten(dialog)), 1)

    def test_filteren_op_soort(self):
        events = [evenement("A", dagen=5, soort="Meeloopdag"), evenement("B", dagen=6, soort="Inloopdag")]
        dialog = self._venster(events)

        dialog.type_filter.setCurrentIndex(dialog.type_filter.findData("Inloopdag"))

        self.assertEqual(len(self._kaarten(dialog)), 1)

    def test_filteren_op_periode(self):
        events = [evenement("Geweest", dagen=-5), evenement("Komt", dagen=5)]
        dialog = self._venster(events)

        dialog.period_filter.setCurrentIndex(dialog.period_filter.findData("verleden"))

        kaarten = self._kaarten(dialog)
        self.assertEqual(len(kaarten), 1)

    def test_oude_kaarten_blijven_niet_staan(self):
        """Zonder losknippen telde en toonde het venster ze dubbel."""
        events = [evenement(f"Evenement {i}", dagen=i + 1) for i in range(4)]
        dialog = self._venster(events)
        eerst = len(self._kaarten(dialog))

        dialog.search_field.setText("evenement")
        dialog.search_field.clear()

        self.assertEqual(len(self._kaarten(dialog)), eerst)

    def test_een_kaart_kiezen_sluit_het_venster(self):
        events = [evenement("A", dagen=1), evenement("B", dagen=2)]
        dialog = self._venster(events)

        dialog._kies(str(events[1]["id"]))

        self.assertEqual(dialog.chosen_id, str(events[1]["id"]))
        self.assertEqual(dialog.result(), dialog.DialogCode.Accepted)


class PassedTests(unittest.TestCase):
    """Op datum alleen vergelijken hield een afgelopen dag de hele dag 'komend'."""

    @classmethod
    def setUpClass(cls):
        import bezoekerslijst_app

        cls.app_module = bezoekerslijst_app

    def _klok(self, minuten: int) -> str:
        """Een tijdstip van vandaag, een aantal minuten voor of na nu."""
        return (datetime.now() + timedelta(minutes=minuten)).strftime("%H:%M")

    def test_de_eindtijd_telt(self):
        klaar = evenement("Net klaar", dagen=0, start="00:00", eind=self._klok(-3))

        self.assertTrue(self.app_module.event_has_passed(klaar))

    def test_wat_vandaag_nog_komt_is_niet_geweest(self):
        straks = evenement("Straks", dagen=0, start=self._klok(3), eind=self._klok(60))

        self.assertFalse(self.app_module.event_has_passed(straks))

    def test_zonder_eindtijd_telt_de_starttijd(self):
        event = evenement("Begonnen", dagen=0, start=self._klok(-3))

        self.assertTrue(self.app_module.event_has_passed(event))

    def test_zonder_tijden_loopt_de_dag_door_tot_middernacht(self):
        vandaag = evenement("Vandaag", dagen=0)

        self.assertFalse(self.app_module.event_has_passed(vandaag))
        self.assertEqual(self.app_module.event_end_moment(vandaag).strftime("%H:%M"), "23:59")

    def test_gisteren_is_geweest_en_morgen_niet(self):
        self.assertTrue(self.app_module.event_has_passed(evenement("Gisteren", dagen=-1)))
        self.assertFalse(self.app_module.event_has_passed(evenement("Morgen", dagen=1)))

    def test_zonder_datum_is_er_geen_moment(self):
        event = evenement("Ooit", dagen=0)
        event["date"] = ""

        self.assertIsNone(self.app_module.event_end_moment(event))
        self.assertFalse(self.app_module.event_has_passed(event))


class DateFieldTests(unittest.TestCase):
    """Dezelfde kalenderknop als bij het aanpassen van een evenement."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        import bezoekerslijst_app

        cls.app_module = bezoekerslijst_app
        cls.qt = QApplication.instance() or QApplication([])

    def _venster(self, events):
        dialog = self.app_module.EventPickerDialog(events, "")
        self.addCleanup(dialog.deleteLater)
        return dialog

    def test_filteren_op_een_datum(self):
        vandaag = evenement("Vandaag", dagen=0)
        morgen = evenement("Morgen", dagen=1)
        dialog = self._venster([vandaag, morgen])

        dialog.date_field.setText(vandaag["date"])

        kaarten = dialog.findChildren(self.app_module.EventCard)
        self.assertEqual(len(kaarten), 1)
        self.assertEqual(kaarten[0].event_id, str(vandaag["id"]))

    def test_een_halve_datum_filtert_nog_niet(self):
        """Tijdens het typen mag het venster niet leegslaan."""
        dialog = self._venster([evenement("A", dagen=0), evenement("B", dagen=1)])

        dialog.date_field.setText("03-")

        self.assertGreaterEqual(len(dialog.findChildren(self.app_module.EventCard)), 2)

    def test_de_kalenderknop_staat_ernaast(self):
        self.assertIn("filters.addWidget(with_date_picker(self.date_field))", APP_SOURCE)


class PagingTests(unittest.TestCase):
    """Bij veel resultaten blader je, in plaats van eindeloos te scrollen."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        import bezoekerslijst_app

        cls.app_module = bezoekerslijst_app
        cls.qt = QApplication.instance() or QApplication([])

    def _venster(self, aantal):
        events = [evenement(f"Evenement {i:02d}", dagen=i + 1) for i in range(aantal)]
        dialog = self.app_module.EventPickerDialog(events, "")
        self.addCleanup(dialog.deleteLater)
        dialog.search_field.setText("evenement")
        return dialog

    def _kaarten(self, dialog):
        return dialog.findChildren(self.app_module.EventCard)

    def test_acht_kaarten_per_pagina(self):
        dialog = self._venster(20)

        self.assertEqual(len(self._kaarten(dialog)), 8)
        self.assertIn("Pagina 1 van 3", dialog.result_label.text())

    def test_bladeren_toont_de_volgende(self):
        dialog = self._venster(20)

        dialog._blader(1)

        self.assertIn("Pagina 2 van 3", dialog.result_label.text())
        self.assertEqual(len(self._kaarten(dialog)), 8)

    def test_de_laatste_pagina_kan_korter_zijn(self):
        dialog = self._venster(20)

        dialog._blader(1)
        dialog._blader(1)

        self.assertIn("Pagina 3 van 3", dialog.result_label.text())
        self.assertEqual(len(self._kaarten(dialog)), 4)

    def test_voorbij_het_einde_bladeren_kan_niet(self):
        dialog = self._venster(20)

        for _ in range(6):
            dialog._blader(1)

        self.assertIn("Pagina 3 van 3", dialog.result_label.text())

    def test_zonder_tweede_pagina_geen_bladerregel(self):
        dialog = self._venster(5)

        self.assertNotIn("Pagina", dialog.result_label.text())

    def test_een_nieuw_filter_begint_bij_het_begin(self):
        """Anders kijk je na het typen naar pagina drie van een andere zoekopdracht."""
        dialog = self._venster(20)
        dialog._blader(1)

        dialog._filters_changed()

        self.assertIn("Pagina 1 van 3", dialog.result_label.text())


class CardAppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        import bezoekerslijst_app

        cls.app_module = bezoekerslijst_app
        cls.qt = QApplication.instance() or QApplication([])

    def test_de_kaart_draagt_zijn_status(self):
        """De gekleurde rand links komt uit deze eigenschap."""
        event = evenement("X", dagen=1)
        event["status"] = "In voorbereiding"

        kaart = self.app_module.EventCard(event)
        self.addCleanup(kaart.deleteLater)

        self.assertEqual(kaart.property("eventStatus"), "invoorbereiding")

    def test_zonder_status_valt_hij_terug_op_concept(self):
        event = evenement("X", dagen=1)
        event["status"] = ""

        kaart = self.app_module.EventCard(event)
        self.addCleanup(kaart.deleteLater)

        self.assertEqual(kaart.property("eventStatus"), "concept")

    def test_elke_status_heeft_een_eigen_kleur(self):
        """De opmaak hoort in theme/styles.py; in _apply_style staat dode code."""
        from emt_models import EVENT_STATUSES
        from bezoekerslijst_core import normalize
        from theme.styles import build_stylesheet

        for donker in (False, True):
            stijl = build_stylesheet(donker)
            for status in EVENT_STATUSES:
                self.assertIn(f'eventStatus="{normalize(status)}"', stijl, f"{status} ({donker})")

    def test_de_opmaak_staat_niet_in_de_dode_code(self):
        """Daar deed hij niets; _apply_style keert terug voor die blokken."""
        start = APP_SOURCE.index("def _apply_style")
        blok = APP_SOURCE[start:APP_SOURCE.index('\n    def ', start + 1)]

        self.assertIn("dode code", blok)
        self.assertNotIn("QFrame#eventCard", blok)

    def test_de_naam_staat_vet(self):
        kaart = self.app_module.EventCard(evenement("Meeloopdag", dagen=1))
        self.addCleanup(kaart.deleteLater)
        from PySide6.QtWidgets import QLabel

        titel = next(label for label in kaart.findChildren(QLabel)
                     if label.objectName() == "eventCardTitle")

        self.assertTrue(titel.font().bold())


class PickerButtonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        import bezoekerslijst_app

        cls.app_module = bezoekerslijst_app
        cls.qt = QApplication.instance() or QApplication([])

    def test_de_knop_toont_naam_en_datum(self):
        event = evenement("Meeloopdag Marine", dagen=3)
        knop = self.app_module.EventPickerButton()
        self.addCleanup(knop.deleteLater)

        knop.set_events([event], str(event["id"]))

        self.assertIn("Meeloopdag Marine", knop.text())
        self.assertIn(event["date"], knop.text())

    def test_zonder_evenementen_vraagt_hij_erom(self):
        knop = self.app_module.EventPickerButton()
        self.addCleanup(knop.deleteLater)

        self.assertIn("kiezen", knop.text())

    def test_een_verdwenen_evenement_valt_terug_op_het_eerste(self):
        events = [evenement("A", dagen=1), evenement("B", dagen=2)]
        knop = self.app_module.EventPickerButton()
        self.addCleanup(knop.deleteLater)

        knop.set_events(events, "bestaat-niet")

        self.assertEqual(knop.current_id(), str(events[0]["id"]))


class SwitchFromInsideTheEventTests(unittest.TestCase):
    """Wisselen zonder eerst terug naar het evenementenoverzicht."""

    def _handler(self):
        start = APP_SOURCE.index("def switch_event")
        return APP_SOURCE[start:APP_SOURCE.index(chr(10) + "    def ", start + 1)]

    def test_de_knop_staat_in_de_balk_bij_de_status(self):
        kop = APP_SOURCE.index('self.switch_event_button = QPushButton("Ander evenement")')
        badge = APP_SOURCE.index('self.event_status_badge = QLabel("Status onbekend")')

        self.assertLess(kop, badge, "de knop hoort in dezelfde rij als de status")
        self.assertIn("event_title_row.addWidget(self.switch_event_button", APP_SOURCE)

    def test_hij_gebruikt_hetzelfde_keuzevenster(self):
        self.assertIn("EventPickerDialog(", self._handler())

    def test_het_huidige_evenement_staat_gemarkeerd(self):
        handler = self._handler()

        self.assertIn('str(huidig.get("id", ""))', handler)

    def test_dezelfde_keuze_verandert_niets(self):
        handler = self._handler()

        self.assertIn('if dialog.chosen_id == str(huidig.get("id", "")):', handler)

    def test_kiezen_opent_het_dossier(self):
        self.assertIn("self.open_event(gekozen)", self._handler())


class TheWorkspacesUseItTests(unittest.TestCase):
    def test_after_sales_en_event_control_gebruiken_de_kaartkiezer(self):
        self.assertIn("self.after_sales_event_combo = EventPickerButton(allow_none=True)", APP_SOURCE)
        self.assertIn("self.event_control_event_combo = EventPickerButton(allow_none=True)", APP_SOURCE)

    def test_de_tijdstippen_overleven_opslaan_en_openen(self):
        """Dezelfde valkuil als bij Inschrijving: prepare_event bouwt alles opnieuw op."""
        bewaard = prepare_event({"name": "X", "last_opened_at": "2026-09-02T08:00",
                                 "updated_at": "2026-09-02T09:00"})

        self.assertEqual(bewaard["last_opened_at"], "2026-09-02T08:00")
        self.assertEqual(bewaard["updated_at"], "2026-09-02T09:00")

    def test_openen_wordt_genoteerd(self):
        self.assertIn("self._touch_event(event, opened=True)", APP_SOURCE)

    def test_wijzigen_wordt_genoteerd(self):
        self.assertGreaterEqual(APP_SOURCE.count("self._touch_event(event)"), 3)


if __name__ == "__main__":
    unittest.main()
