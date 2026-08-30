from pathlib import Path
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
        self.assertIn('applyHandedness(selectedHand)', source)
        self.assertIn('jumpToLetter', source)

    def test_mobile_layout_can_be_mirrored(self):
        css = (ROOT / "server/web/static/css/style.css").read_text(encoding="utf-8")
        self.assertIn('.roster-shell.hand-left', css)
        self.assertIn('.hand-left .result-row', css)
        self.assertIn('.alphabet-index', css)

    def test_service_worker_cache_was_advanced(self):
        source = (ROOT / "server/web/static/js/service-worker.js").read_text(encoding="utf-8")
        self.assertIn('eventhub-live-v18', source)


if __name__ == "__main__":
    unittest.main()
