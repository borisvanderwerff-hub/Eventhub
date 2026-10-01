"""Applicatiegegevens horen altijd op dezelfde, herkenbare plek te staan."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

import bezoekerslijst_app

SOURCE = desktop_source(ROOT)


class DataLocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_folder_is_named_after_the_app_not_the_interpreter(self):
        """Zonder applicatienaam koos Qt de naam van het draaiende programma.

        Daardoor belandde het foutlogboek in AppData/Local/python, tussen de
        installatiebestanden van Python.
        """
        root = bezoekerslijst_app.application_data_root()
        self.assertEqual(root.name, "EventHub")
        self.assertEqual(root.parent.name, "DCPL")
        self.assertNotIn("python", str(root).casefold().replace("recruiterwest", ""))

    def test_the_location_does_not_depend_on_when_it_is_asked(self):
        eerst = bezoekerslijst_app.application_data_root()
        self.app.setApplicationName("Iets Anders")
        try:
            daarna = bezoekerslijst_app.application_data_root()
        finally:
            self.app.setApplicationName("EventHub")
        self.assertEqual(eerst, daarna, "de naam van de QApplication mag niet meetellen")

    def test_it_no_longer_reads_the_location_from_qt(self):
        start = SOURCE.index("def application_data_root():")
        # Alleen deze functie, tot aan de volgende: de klassen eronder zijn verhuisd.
        block = SOURCE[start:SOURCE.index("\n\ndef ", start + 1)]
        # Op de aanroep matchen, niet op het woord: de toelichting noemt
        # QStandardPaths juist om uit te leggen waarom het weg is.
        self.assertNotIn("QStandardPaths.writableLocation", block)
        self.assertIn("LOCALAPPDATA", block)

    def test_nothing_is_written_to_the_desktop(self):
        """Alles hoort binnen de app-omgeving te blijven."""
        for functie in ("application_data_root", "projects_directory", "exports_directory"):
            with self.subTest(functie=functie):
                pad = str(getattr(bezoekerslijst_app, functie)()).casefold()
                self.assertNotIn("desktop", pad)
                self.assertNotIn("bureaublad", pad)

    def test_exports_live_under_documents_in_their_own_folder(self):
        exports = bezoekerslijst_app.exports_directory()
        self.assertEqual(exports.name, "Exports")
        self.assertEqual(exports.parent.name, "EventHub")


if __name__ == "__main__":
    unittest.main()
