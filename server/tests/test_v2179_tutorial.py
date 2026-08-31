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
    finished = staticmethod(lambda *_: None)

    def __init__(self, host, steps, finished):
        type(self).captured = steps
        type(self).finished = staticmethod(finished)

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

    def test_live_session_help_is_separate_from_the_main_tour(self):
        """Live sessies krijgen uitleg op de plek zelf, niet in de hoofdrondleiding."""
        titles = " ".join(step["title"] for step in self.steps).casefold()
        self.assertNotIn("live sessie", titles, "hoort in de losse uitleg te staan")
        self.assertTrue(hasattr(self.window, "live_session_help_button"))
        self.assertTrue(hasattr(self.window, "start_live_session_tour"))

    def test_wording_does_not_claim_things_are_new(self):
        """'Nieuw' veroudert; een rondleiding beschrijft wat er is."""
        for step in self.steps:
            self.assertNotIn("de nieuwe ", str(step["title"]).casefold(), step["title"])


class LiveSessionTourTests(unittest.TestCase):
    """De losse uitleg bij Live sessie."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.original_overlay = bezoekerslijst_app.TutorialOverlay
        bezoekerslijst_app.TutorialOverlay = _CapturingOverlay
        cls.window = bezoekerslijst_app.BezoekerslijstWindow()
        cls.window.start_live_session_tour()
        cls.steps = _CapturingOverlay.captured

    @classmethod
    def tearDownClass(cls):
        bezoekerslijst_app.TutorialOverlay = cls.original_overlay

    def test_help_button_is_just_a_question_mark(self):
        """De volledige tekst paste niet in de kop en was slecht leesbaar."""
        button = self.window.live_session_help_button
        self.assertEqual(button.text(), "?")
        self.assertTrue(button.toolTip(), "zonder tekst moet de tooltip het uitleggen")

    def test_finish_callback_accepts_the_result_argument(self):
        """De overlay roept de callback aan met wel of niet afgerond."""
        finish = _CapturingOverlay.finished
        finish(True)
        finish(False)
        self.assertIsNone(self.window._tutorial_overlay)

    def test_a_destroyed_overlay_does_not_block_a_new_tour(self):
        """Qt vernietigt de overlay terwijl de verwijzing blijft bestaan."""

        class Destroyed:
            def isVisible(self):
                raise RuntimeError("Internal C++ object (TutorialOverlay) already deleted.")

        self.window._tutorial_overlay = Destroyed()
        self.window.start_live_session_tour()
        self.assertIsNot(self.window._tutorial_overlay, None)

    def test_the_live_session_tab_is_reachable_by_name(self):
        """De knop Live sessie op het startscherm schakelt hier naartoe."""
        self.assertTrue(hasattr(self.window, "live_session_tab"))
        self.assertGreaterEqual(
            self.window.event_control_tabs.indexOf(self.window.live_session_tab), 0
        )

    def test_every_step_can_be_shown(self):
        for step in self.steps:
            with self.subTest(step=step["title"]):
                step["prepare"]()
                self.assertIsNotNone(step["target"](), "doel niet gevonden")

    def test_it_covers_what_the_interface_does_not_show(self):
        """Juist het niet-zichtbare hoort uitgelegd: netwerk, apparaten, herstel."""
        bodies = " ".join(step["body"] for step in self.steps).casefold()
        for needle in ("netwerk", "qr-code", "sessiecode", "herstelkopie", "dashboard"):
            self.assertIn(needle, bodies, f"de uitleg noemt {needle} niet")

    def test_it_stays_short(self):
        self.assertLessEqual(len(self.steps), 8, "een contextuele uitleg hoort kort te zijn")
        self.assertGreaterEqual(len(self.steps), 4)


if __name__ == "__main__":
    unittest.main()
