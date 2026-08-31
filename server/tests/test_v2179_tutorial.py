"""De rondleiding moet de werkelijke applicatie blijven beschrijven."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

import bezoekerslijst_app


class _CapturingOverlay:
    """Vangt de stappen op in plaats van een venster te tonen."""

    captured: list = []

    def __init__(self, host, steps, finished):
        type(self).captured = steps

    def isVisible(self):
        return False

    def raise_(self):
        pass


class TutorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.original_overlay = bezoekerslijst_app.TutorialOverlay
        bezoekerslijst_app.TutorialOverlay = _CapturingOverlay
        cls.window = bezoekerslijst_app.BezoekerslijstWindow()
        cls.window.start_tutorial()
        cls.steps = _CapturingOverlay.captured

    @classmethod
    def tearDownClass(cls):
        bezoekerslijst_app.TutorialOverlay = cls.original_overlay

    def test_every_step_is_complete(self):
        self.assertTrue(self.steps, "de rondleiding heeft geen stappen")
        for index, step in enumerate(self.steps, 1):
            for key in ("title", "body", "prepare", "target"):
                self.assertIn(key, step, f"stap {index} mist {key}")
            self.assertTrue(str(step["title"]).strip(), f"stap {index} heeft geen titel")
            self.assertGreater(len(str(step["body"])), 40, f"stap {index} legt te weinig uit")

    def test_every_step_can_be_shown(self):
        """Een verwijderd of hernoemd element mag de rondleiding niet breken."""
        for step in self.steps:
            with self.subTest(step=step["title"]):
                step["prepare"]()
                self.assertIsNotNone(step["target"](), "doel niet gevonden")

    def test_every_sidebar_section_is_covered(self):
        """Zo valt een nieuw hoofdonderdeel niet stilletjes buiten de uitleg."""
        titles_and_bodies = " ".join(
            f"{step['title']} {step['body']}" for step in self.steps
        ).casefold()
        expected = {
            "events": "evenement",
            "tasks": "taken",
            "callbacks": "after sales",
            "event_control": "event control",
            "trends": "trends",
        }
        for key, needle in expected.items():
            self.assertIn(key, self.window.sidebar_buttons, f"zijbalkonderdeel {key} bestaat niet meer")
            self.assertIn(needle, titles_and_bodies, f"de rondleiding noemt {key} niet")

    def test_retention_is_explained_with_the_configured_term(self):
        """Gegevens die vanzelf verdwijnen horen niet als verrassing te komen."""
        bodies = " ".join(str(step["body"]) for step in self.steps)
        self.assertIn("bewaartermijn", bodies.casefold())
        self.assertIn(f"{self.window._retention_days()} dagen", bodies)
        self.assertIn("onomkeerbaar", bodies.casefold())

    def test_the_start_screen_is_shown_not_only_the_event_list(self):
        titles = [step["title"] for step in self.steps]
        self.assertIn("Uw startscherm", titles)

    def test_wording_does_not_claim_things_are_new(self):
        """'Nieuw' veroudert; een rondleiding beschrijft wat er is."""
        for step in self.steps:
            self.assertNotIn("de nieuwe ", str(step["title"]).casefold(), step["title"])


if __name__ == "__main__":
    unittest.main()
