"""De Browserassistent haalt de presentie rechtstreeks uit EventHub.

De bestaande brug is eenmalig: EventHub opent Rudder zelf met een willekeurige
poort en een token in de URL. Wie in Rudder begint kan die niet vinden en
belandde bij een bestandskiezer - en sinds de JSON-export eruit is, is er niet
eens meer een bestand om te kiezen.

Daarom een vaste loopback-ingang die openstaat zolang EventHub draait. Er gaan
namen en registratie-ID's doorheen, dus hij geeft nooit uit zichzelf iets af:
elke aanvraag wordt eerst in EventHub voorgelegd, en er gaat geen
Access-Control-Allow-Origin mee zodat een gewone webpagina er niet bij kan.
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

APP_SOURCE = desktop_source(ROOT)
EXT = ROOT / "browser_extension"


def haal(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status, response.read().decode("utf-8"), dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace"), dict(error.headers)
    except urllib.error.URLError as error:
        raise AssertionError(f"De luisteraar is niet bereikbaar: {error}") from error


class AttendanceServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        import bezoekerslijst_app

        cls.app = QApplication.instance() or QApplication([])
        cls.service = bezoekerslijst_app.RudderAttendanceService()
        # Een eigen poort: de vaste poort kan bezet zijn door een draaiende
        # EventHub, en een test hoort daar niet mee te vechten.
        cls.service.PORT = 47616
        cls.gevraagd = []

        def beantwoord(request):
            cls.gevraagd.append(request.rudder_event_id)
            if request.rudder_event_id == "5900":
                request.payload = {"format": "EventHub Rudder Attendance", "participants": []}
            else:
                request.status = 404
                request.error = "Geen evenement met dat nummer."
            request.done.set()

        # Rechtstreeks verbonden: in een test is er geen draaiende gebeurtenislus
        # die een wachtrij zou legen.
        cls.service.requested.connect(beantwoord, Qt.ConnectionType.DirectConnection)
        if not cls.service.start():
            raise unittest.SkipTest("De testpoort is bezet.")
        cls.basis = f"http://127.0.0.1:{cls.service.PORT}"

    @classmethod
    def tearDownClass(cls):
        cls.service.stop()

    def test_een_bekend_evenement_levert_de_presentie(self):
        status, body, _ = haal(f"{self.basis}/attendance?event=5900")

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["format"], "EventHub Rudder Attendance")

    def test_geen_enkele_webpagina_mag_erbij(self):
        """Zonder Access-Control-Allow-Origin blokkeert de browser andere sites."""
        _, _, headers = haal(f"{self.basis}/attendance?event=5900")

        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_een_onbekend_nummer_krijgt_een_uitleg(self):
        status, body, _ = haal(f"{self.basis}/attendance?event=9999")

        self.assertEqual(status, 404)
        self.assertIn("Geen evenement", json.loads(body)["error"])

    def test_onzin_bereikt_het_scherm_niet(self):
        """Alleen een nummer wordt doorgezet; de rest wordt meteen afgewezen."""
        eerder = len(self.gevraagd)

        self.assertEqual(haal(f"{self.basis}/attendance?event=kaas")[0], 404)
        self.assertEqual(haal(f"{self.basis}/deelnemers")[0], 404)
        self.assertEqual(len(self.gevraagd), eerder)

    def test_de_poort_komt_weer_vrij(self):
        self.service.stop()
        self.assertTrue(self.service.start())


class TheApplicationAsksFirstTests(unittest.TestCase):
    def _handler(self):
        start = APP_SOURCE.index("def _serve_rudder_attendance")
        return APP_SOURCE[start:APP_SOURCE.index("\n    def ", start + 1)]

    def test_de_luisteraar_start_met_de_app_en_stopt_bij_afsluiten(self):
        """Starten hoort bij het echte opstarten, niet bij elk aangemaakt venster."""
        self.assertIn("window.rudder_attendance_service.start()", APP_SOURCE)
        self.assertIn("self.rudder_attendance_service.stop()", APP_SOURCE)

    def test_er_gaat_niets_uit_zonder_bevestiging(self):
        handler = self._handler()
        vraag = handler.index("QMessageBox.question(")

        self.assertLess(vraag, handler.index("request.payload = payload"))
        self.assertIn("QMessageBox.StandardButton.Cancel,\n            )", handler)

    def test_het_venster_vertelt_wat_er_weggaat(self):
        handler = self._handler()

        self.assertIn("namen en registratie-ID's", handler)
        self.assertIn("aanwezig", handler)

    def test_een_onbekend_rudder_nummer_wordt_netjes_afgewezen(self):
        handler = self._handler()

        self.assertIn("request.status = 404", handler)
        self.assertIn("geen evenement met Rudder-nummer", handler)

    def test_weigeren_levert_geen_gegevens_op(self):
        handler = self._handler()

        self.assertIn("request.status = 403", handler)
        self.assertIn("geweigerd", handler)


class TheExtensionAsksEventHubTests(unittest.TestCase):
    def setUp(self):
        self.content = (EXT / "content.js").read_text(encoding="utf-8")
        self.background = (EXT / "background.js").read_text(encoding="utf-8")

    def test_de_knop_vraagt_het_aan_eventhub(self):
        self.assertIn("requestFromEventHub(pageEventId)", self.content)
        self.assertIn('type:"eventhub-request-attendance"', self.content)

    def test_een_bestand_kiezen_is_alleen_nog_de_uitwijk(self):
        """Niet meer de gewone route: die kostte zoekwerk in de verkenner."""
        self.assertIn("Toch een bestand kiezen", self.content)
        self.assertNotIn('launcher.addEventListener("click", () => { picker.value = ""; picker.click(); });',
                         self.content)

    def test_de_achtergrond_kent_de_vaste_poort(self):
        self.assertIn("const EVENTHUB_PORT = 47615;", self.background)
        self.assertIn("attendance?event=", self.background)

    def test_een_gesloten_eventhub_geeft_een_begrijpelijke_melding(self):
        self.assertIn("EventHub is niet bereikbaar", self.background)

    def test_de_presentie_van_een_ander_evenement_wordt_geweigerd(self):
        self.assertIn("hoort bij Rudder-event", self.content)

    def test_de_extensie_is_opgehoogd(self):
        manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["version"], "1.6.0")
        self.assertIn("http://127.0.0.1/*", manifest["host_permissions"])


if __name__ == "__main__":
    unittest.main()
