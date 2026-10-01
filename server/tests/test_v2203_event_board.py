"""Het evenementenoverzicht als kaartenbord.

De tellerbalk met totalen is vervallen: die vertelde niet welk evenement
aandacht vraagt. Dat staat nu op de kaart van het evenement zelf, met een
balk voor de voorbereiding. De tabel blijft als terugvaloptie bestaan, en
blijft ook onder de kaarten bepalen welk evenement geselecteerd is.
"""
import os
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import (QApplication, QLineEdit, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

import bezoekerslijst_app as app_module
from bezoekerslijst_app import BezoekerslijstWindow as Venster
from bezoekerslijst_app import EventOverviewCard
from bezoekerslijst_core import DUBBELE_INSCHRIJVING
from emt_models import preparation_progress, preparation_summary

APP_SOURCE = desktop_source(ROOT)


def taken(klaar: int, totaal: int):
    return [{"id": str(nummer), "done": nummer < klaar} for nummer in range(totaal)]


def evenement(naam, dagen=7, status="In voorbereiding", **extra):
    moment = date.today() + timedelta(days=dagen)
    event = {
        "id": naam.lower().replace(" ", "-"),
        "name": naam,
        "date": moment.strftime("%d-%m-%Y"),
        "event_type": "Meeloopdag",
        "status": status,
        "tasks": [],
        "attachments": [],
    }
    event.update(extra)
    return event


def deelnemer(naam, event_naam, stand=""):
    record = {"Naam": naam, "Evenement": event_naam}
    if stand:
        record["Aanwezig"] = {event_naam: stand}
    return record


class PreparationTests(unittest.TestCase):
    """De balk telt de takenlijst, tenzij je zelf zegt dat het klaar is."""

    def test_de_helft_van_de_taken_is_de_helft_van_de_balk(self):
        event = evenement("Meeloopdag", tasks=taken(4, 8))

        self.assertAlmostEqual(preparation_progress(event), 0.5)

    def test_gereed_staat_altijd_vol(self):
        event = evenement("Meeloopdag", status="Gereed", tasks=taken(1, 8))

        self.assertEqual(preparation_progress(event), 1.0)

    def test_afgerond_staat_ook_vol(self):
        event = evenement("Meeloopdag", status="Afgerond", tasks=taken(0, 8))

        self.assertEqual(preparation_progress(event), 1.0)

    def test_zonder_taken_valt_er_niets_te_meten(self):
        self.assertEqual(preparation_progress(evenement("Nieuw")), 0.0)

    def test_de_uitleg_vertelt_waarom(self):
        self.assertEqual(
            preparation_summary(evenement("Meeloopdag", tasks=taken(2, 8))),
            "2 van 8 taken afgerond",
        )
        self.assertEqual(
            preparation_summary(evenement("Meeloopdag", status="Gereed")), "Gereed gemeld"
        )
        self.assertEqual(preparation_summary(evenement("Nieuw")), "Nog geen taken")


class BoardWindow:
    """Een venster met alleen wat het bord nodig heeft."""

    _refresh_event_board = Venster._refresh_event_board
    _board_section = Venster._board_section
    _toggle_board_section = Venster._toggle_board_section
    _card_figures = Venster._card_figures
    _card_footnote = Venster._card_footnote
    _visitors_by_event = Venster._visitors_by_event
    _event_listings = Venster._event_listings

    def __init__(self, events, records=()):
        self.events = list(events)
        self.records = list(records)
        self._board_collapsed = {"geweest": True}
        self._board_searching = False
        self._board_selected_id = ""
        self._board_pending = list(events)
        self._event_cards = []
        self.gekozen = []
        self.geopend = []
        self.event_board = QScrollArea()
        self.event_board.setWidgetResizable(True)
        self.body = QWidget()
        self.event_board_layout = QVBoxLayout(self.body)
        self.event_board.setWidget(self.body)

    def _event_by_id(self, event_id):
        return next((item for item in self.events if item.get("id") == event_id), None)

    def _select_event_row(self, event_id):
        self.gekozen.append(event_id)

    def _open_event_from_card(self, event_id):
        self.geopend.append(event_id)

    def _show_card_menu(self, event_id, punt):
        pass

    def _filter_events(self, *_):
        self._refresh_event_board(self.events)

    def kaarten(self):
        return [(kaart.event_id, kaart) for kaart in self._event_cards]


class BoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def _venster(self, events, records=()):
        window = BoardWindow(events, records)
        window._refresh_event_board(events)
        return window

    def test_wat_vandaag_nog_komt_staat_direct_op_het_bord(self):
        straks = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
        window = self._venster([evenement("Vandaag", dagen=0, start_time=straks)])

        self.assertEqual([sleutel for sleutel, _ in window.kaarten()], ["vandaag"])
        self.assertNotIn("VANDAAG", self._koppen(window))

    def test_wat_geweest_is_heeft_geen_aparte_ingeklapte_groep(self):
        window = self._venster([evenement("Vorige week", dagen=-7)])

        self.assertNotIn("GEWEEST", self._koppen(window))
        self.assertEqual([sleutel for sleutel, _ in window.kaarten()], ["vorige-week"])

    def test_een_oude_kaart_is_direct_zichtbaar_wanneer_het_archief_wordt_getoond(self):
        window = self._venster([evenement("Vorige week", dagen=-7)])

        self.assertEqual([sleutel for sleutel, _ in window.kaarten()], ["vorige-week"])

    def test_zoeken_klapt_het_verleden_open(self):
        window = BoardWindow([evenement("Vorige week", dagen=-7)])
        window._board_searching = True

        window._refresh_event_board(window.events)

        self.assertEqual([sleutel for sleutel, _ in window.kaarten()], ["vorige-week"])

    def test_wat_nog_komt_heeft_geen_overbodige_groepskop(self):
        window = self._venster([evenement("Volgende maand", dagen=30)])

        self.assertNotIn("KOMEND", self._koppen(window))
        self.assertEqual([sleutel for sleutel, _ in window.kaarten()], ["volgende-maand"])

    def test_zonder_evenementen_zegt_het_bord_dat(self):
        window = self._venster([])

        self.assertEqual(window.kaarten(), [])
        self.assertTrue(any("Geen evenementen" in knop for knop in self._teksten(window)))

    def test_de_balk_hoort_bij_wat_nog_komt(self):
        window = self._venster([evenement("Komend", tasks=taken(2, 4))])
        _, kaart = window.kaarten()[0]

        self.assertIsNotNone(kaart.preparation_bar)
        self.assertEqual(kaart.preparation_bar.value(), 50)

    def test_een_afgelopen_evenement_krijgt_geen_balk(self):
        window = self._venster([evenement("Geweest", dagen=-7)])
        _, kaart = window.kaarten()[0]

        self.assertIsNone(kaart.preparation_bar)

    def test_dubbelklikken_opent_het_evenement(self):
        window = self._venster([evenement("Komend")])
        _, kaart = window.kaarten()[0]

        kaart.geopend.emit(kaart.event_id)

        self.assertEqual(window.geopend, ["komend"])

    def test_een_klik_kiest_het_evenement(self):
        window = self._venster([evenement("Komend")])
        _, kaart = window.kaarten()[0]

        kaart.aangeklikt.emit(kaart.event_id)

        self.assertEqual(window.gekozen, ["komend"])

    def _koppen(self, window):
        return " ".join(self._teksten(window))

    def _teksten(self, window):
        from PySide6.QtWidgets import QLabel

        return [element.text() for element in
                window.body.findChildren(QPushButton) + window.body.findChildren(QLabel)]


class FiguresTests(unittest.TestCase):
    """De cijfers op een kaart horen bij de fase van het evenement."""

    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def _cijfers(self, event, records, geweest):
        window = BoardWindow([event], records)
        bezoekers = window._visitors_by_event([event])[event["id"]]
        return window._card_figures(event, bezoekers, geweest).replace("<b>", "").replace("</b>", "")

    def test_wat_nog_komt_toont_aanmeldingen_en_open_taken(self):
        event = evenement("Komend", tasks=taken(1, 4))
        tekst = self._cijfers(event, [deelnemer("Jan", "Komend")], False)

        self.assertIn("1 aanmeldingen", tekst)
        self.assertIn("3 taken open", tekst)

    def test_zonder_bijlagen_staat_er_geen_documentenregel(self):
        tekst = self._cijfers(evenement("Komend"), [], False)

        self.assertNotIn("documenten", tekst)

    def test_wat_geweest_is_toont_de_opkomst(self):
        event = evenement("Geweest", dagen=-7)
        records = [
            deelnemer("Jan", "Geweest", app_module.AANWEZIG),
            deelnemer("Piet", "Geweest", app_module.AANWEZIG),
            deelnemer("Klaas", "Geweest", app_module.AFWEZIG),
            deelnemer("Marie", "Geweest", app_module.AFGEMELD),
        ]
        tekst = self._cijfers(event, records, True)

        self.assertIn("4 aangemeld", tekst)
        self.assertIn("2 aanwezig", tekst)
        self.assertIn("1 niet gekomen", tekst)
        self.assertIn("1 afgemeld", tekst)
        self.assertIn("50% opkomst", tekst)

    def test_overgeslagen_dubbelen_tellen_niet_mee(self):
        event = evenement("Komend")
        dubbel = deelnemer("Jan", "Komend")
        dubbel[app_module.OVERGESLAGEN] = DUBBELE_INSCHRIJVING
        tekst = self._cijfers(event, [deelnemer("Jan", "Komend"), dubbel], False)

        self.assertIn("1 aanmeldingen", tekst)


class ViewWindow:
    _set_event_view = Venster._set_event_view
    _toggle_event_view = Venster._toggle_event_view

    class Settings:
        def __init__(self):
            self.waarden = {}

        def setValue(self, sleutel, waarde):
            self.waarden[sleutel] = waarde

    def __init__(self):
        self.settings = self.Settings()
        self.event_view_stack = QStackedWidget()
        self.event_view_stack.addWidget(QWidget())
        self.event_view_stack.addWidget(QWidget())
        self.view_toggle_button = QPushButton()


class ViewToggleTests(unittest.TestCase):
    """Kaarten om te bladeren, de tabel om te vergelijken."""

    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_de_knop_zegt_waar_je_heen_gaat(self):
        window = ViewWindow()

        window._set_event_view("kaarten")
        self.assertEqual(window.view_toggle_button.text(), "Lijst")

        window._toggle_event_view()
        self.assertEqual(window.view_toggle_button.text(), "Kaarten")

    def test_wisselen_verandert_de_weergave(self):
        window = ViewWindow()

        window._set_event_view("kaarten")
        self.assertEqual(window.event_view_stack.currentIndex(), 0)

        window._toggle_event_view()
        self.assertEqual(window.event_view_stack.currentIndex(), 1)

    def test_de_keuze_blijft_bewaard(self):
        window = ViewWindow()

        window._set_event_view("lijst")

        self.assertEqual(window.settings.waarden["event_view_mode"], "lijst")

    def test_het_bord_staat_standaard_voor(self):
        self.assertIn(
            'self.settings.value("event_view_mode", "kaarten")', APP_SOURCE
        )


class LayoutTests(unittest.TestCase):
    """Wat er van het oude startscherm af moest."""

    def test_de_tellerbalk_is_weg(self):
        for verdwenen in ("OPERATIONEEL OVERZICHT", "home_event_count",
                          "home_task_count", "home_visitor_count"):
            with self.subTest(verdwenen=verdwenen):
                self.assertNotIn(verdwenen, APP_SOURCE)

    def test_de_tabel_blijft_bestaan_als_terugvaloptie(self):
        self.assertIn("self.event_view_stack.addWidget(self.home_event_table)", APP_SOURCE)

    def test_de_kaart_kiest_dezelfde_rij_als_de_tabel(self):
        start = APP_SOURCE.index("def _select_event_row")
        blok = APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]

        self.assertIn("table.selectRow(row)", blok)

    def test_beide_weergaven_delen_hetzelfde_menu(self):
        self.assertIn("self._event_actions_menu(event, table).exec(", APP_SOURCE)
        self.assertIn("self._event_actions_menu(event, self).exec(punt)", APP_SOURCE)

    def test_typen_bouwt_niet_bij_elke_aanslag_opnieuw(self):
        """Twintig kaarten opbouwen duurt te lang voor elke toetsaanslag."""
        self.assertIn("self._board_timer.setSingleShot(True)", APP_SOURCE)
        self.assertIn("self._board_timer.start()", APP_SOURCE)

    def test_zoeken_haalt_ook_het_verleden_naar_voren(self):
        self.assertIn(
            "self._board_searching = bool(needle or wanted_status or wanted_type or wanted_date)",
            APP_SOURCE,
        )

    def test_de_filters_staan_er_net_als_in_het_keuzevenster(self):
        for onderdeel in ("self.event_type_filter", "self.event_date_filter",
                          "with_date_picker(self.event_date_filter)"):
            with self.subTest(onderdeel=onderdeel):
                self.assertIn(onderdeel, APP_SOURCE)

    def test_de_kaarten_zijn_doorschijnend(self):
        stijl = (ROOT / "theme" / "styles.py").read_text(encoding="utf-8")
        kaart = stijl[stijl.index("QFrame#eventOverviewCard {{"):]

        self.assertIn("qlineargradient", kaart[:200])
        self.assertIn("rgba(", stijl)

    def test_de_balk_gebruikt_de_huisstijl(self):
        stijl = (ROOT / "theme" / "styles.py").read_text(encoding="utf-8")
        balk = stijl[stijl.index("QProgressBar#preparationBar::chunk"):]

        self.assertIn("qlineargradient", balk[:200])
        self.assertIn("#6c2cff", balk[:200])


class ScrollPositionTests(unittest.TestCase):
    """Een status aanpassen mag je plek in de lijst niet afpakken.

    De knop met de focus verdwijnt bij het opnieuw opbouwen; zonder maatregel
    legt Qt de focus op de eerstvolgende knop en scrolt het venster daarheen.
    """

    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def _bord(self):
        events = [evenement(f"Evenement {nummer}", dagen=nummer + 1) for nummer in range(24)]
        window = BoardWindow(events)
        window._refresh_event_board(events)
        window.event_board.resize(760, 320)
        window.event_board.show()
        for _ in range(3):
            self.qt.processEvents()
        return window

    def test_opnieuw_opbouwen_houdt_de_plek_vast(self):
        window = self._bord()
        balk = window.event_board.verticalScrollBar()
        self.assertGreater(balk.maximum(), 0, "er valt niets te scrollen om te toetsen")
        halverwege = balk.maximum() // 2
        balk.setValue(halverwege)
        window._event_cards[4].menu_button.setFocus()

        try:
            window._refresh_event_board(window.events)
            for _ in range(3):
                self.qt.processEvents()
            plek = balk.value()
        finally:
            window.event_board.hide()

        self.assertEqual(plek, halverwege)

    def test_de_focus_blijft_in_het_zoekvak(self):
        """Tijdens het typen mag het bord de focus niet overnemen."""
        window = self._bord()
        zoekvak = QLineEdit()
        zoekvak.show()
        zoekvak.setFocus()

        try:
            window._refresh_event_board(window.events)
            self.qt.processEvents()
            houder = self.qt.focusWidget()
        finally:
            window.event_board.hide()
            zoekvak.hide()

        self.assertIs(houder, zoekvak)


class StrayWindowTests(unittest.TestCase):
    """Een zichtbare widget zonder ouder is een los venster.

    Bij het opnieuw opbouwen van het bord flitste zo'n venster over het
    scherm, precies op het moment dat je ergens anders op klikte.
    """

    class Speurder(QObject):
        def __init__(self):
            super().__init__()
            self.losse = []

        def eventFilter(self, obj, gebeurtenis):
            if (gebeurtenis.type() == QEvent.Type.Show and isinstance(obj, QWidget)
                    and obj.parent() is None and obj.isWindow()):
                self.losse.append(obj.objectName() or type(obj).__name__)
            return False

    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_opnieuw_opbouwen_toont_geen_los_venster(self):
        window = BoardWindow([evenement("Komend"), evenement("Vorige week", dagen=-7)])
        window._refresh_event_board(window.events)
        window.event_board.show()
        self.qt.processEvents()

        speurder = self.Speurder()
        self.qt.installEventFilter(speurder)
        try:
            window._refresh_event_board(window.events)
            window._toggle_board_section("geweest")
            self.qt.processEvents()
            self.qt.processEvents()
        finally:
            self.qt.removeEventFilter(speurder)
            window.event_board.hide()

        self.assertEqual(speurder.losse, [])

    def test_de_speurder_ziet_een_echt_los_venster(self):
        speurder = self.Speurder()
        self.qt.installEventFilter(speurder)
        try:
            los = QWidget()
            los.show()
            self.qt.processEvents()
        finally:
            self.qt.removeEventFilter(speurder)
            los.hide()

        self.assertTrue(speurder.losse)


if __name__ == "__main__":
    unittest.main()
