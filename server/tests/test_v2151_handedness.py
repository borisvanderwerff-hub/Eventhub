from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version2151HandednessTests(unittest.TestCase):
    def test_connect_page_exposes_handedness_and_alphabet_controls(self):
        html = (ROOT / "server/web/templates/connect.html").read_text(encoding="utf-8")
        self.assertIn('id="settingsHandedness"', html)
        self.assertIn('name="handedness" value="right"', html)
        self.assertIn('name="handedness" value="left"', html)
        self.assertIn('id="alphabetIndex"', html)
        self.assertIn('id="alphabetBubble"', html)

    def test_client_persists_preference_and_sorts_index_by_surname(self):
        source = (ROOT / "server/web/static/js/connect.js").read_text(encoding="utf-8")
        self.assertIn('eventhub_handedness', source)
        self.assertIn('participant.achternaam', source)
        # De aanroep kreeg er een argument bij; op de haakjes matchen maakte
        # deze test onnodig breekbaar. De keuze moet toegepast en bewaard.
        self.assertIn('applyHandedness(selectedHand', source)
        self.assertIn('localStorage.setItem(HANDEDNESS_KEY', source)
        self.assertIn('localStorage.getItem(HANDEDNESS_KEY)', source)
        self.assertIn('jumpToLetter', source)

    def test_mobile_layout_can_be_mirrored(self):
        css = (ROOT / "server/web/static/css/style.css").read_text(encoding="utf-8")
        self.assertIn('.roster-shell.hand-left', css)
        self.assertIn('.hand-left .result-row', css)
        self.assertIn('.alphabet-index', css)

    def test_service_worker_cache_is_versioned_and_purges_stale_caches(self):
        """Niet het nummer vastpinnen, maar het mechanisme.

        De oude test eiste een specifieke versie en brak dus bij elke
        legitieme ophoging. Wat telt is dat er een versie is en dat oude
        caches worden opgeruimd, anders blijven clients op verouderde
        bestanden hangen.
        """
        source = (ROOT / "server/web/static/js/service-worker.js").read_text(encoding="utf-8")
        match = re.search(r'const CACHE = "eventhub-live-v(\d+)"', source)
        self.assertIsNotNone(match, "service worker heeft geen genummerde cacheversie")
        self.assertGreaterEqual(int(match.group(1)), 18, "cacheversie mag niet teruglopen")
        self.assertIn('key.startsWith("eventhub-live-")', source)
        self.assertIn("caches.delete(key)", source)


if __name__ == "__main__":
    unittest.main()
