"""Scrollen over een gesloten keuzelijst mag de keuze niet veranderen."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

SOURCE = desktop_source(ROOT)


class ScrollSafeDropdownTests(unittest.TestCase):
    def test_de_keuzelijst_negeert_het_muiswiel(self):
        start = SOURCE.index("class ScrollSafeComboBox")
        # Tot het eerstvolgende blok; de klasse staat sinds de opsplitsing in emt_widgets.
        block = SOURCE[start:SOURCE.index("\n\nclass ", start + 1)]
        self.assertIn("def wheelEvent", block)
        self.assertIn("event.ignore()", block)

    def test_alle_dropdowns_gebruiken_de_scrollveilige_variant(self):
        self.assertNotIn("= QComboBox()", SOURCE)
        self.assertGreater(SOURCE.count("ScrollSafeComboBox()"), 20)


if __name__ == "__main__":
    unittest.main()
