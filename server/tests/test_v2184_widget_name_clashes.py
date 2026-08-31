"""Eigen attributen mogen geen Qt-methodes overschrijven.

Een widgetattribuut dat toevallig zo heet als een bestaande Qt-methode
vervangt die methode. Qt roept hem daarna alsnog aan en de applicatie valt om
met 'object is not callable'. Dat gebeurde met self.metric in TrendPanel:
QPaintDevice heeft al een metric(), die Qt tijdens het tekenen gebruikt.

De fout kwam pas naar boven bij het opslaan van instellingen, ver van de
plek waar hij was gemaakt. Deze test wijst hem meteen aan.
"""
import os
import re
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QFrame, QMainWindow, QWidget

SOURCE = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

# Namen die de app zelf bewust definieert of die Qt juist verwacht.
TOEGESTAAN = {"event", "close", "show", "update", "raise_"}

BASISKLASSEN = {
    "QWidget": QWidget,
    "QFrame": QFrame,
    "QMainWindow": QMainWindow,
}


def _eigen_klassen():
    """Klassen in de app die van een Qt-widget erven, met hun basisklasse."""
    for match in re.finditer(r"^class (\w+)\((Q\w+)\):", SOURCE, re.M):
        naam, basis = match.group(1), match.group(2)
        if basis in BASISKLASSEN:
            yield naam, BASISKLASSEN[basis]


def _toegewezen_attributen(klasse_naam):
    start = SOURCE.index(f"class {klasse_naam}(")
    volgende = SOURCE.find("\nclass ", start + 1)
    blok = SOURCE[start:volgende if volgende > 0 else len(SOURCE)]
    return set(re.findall(r"self\.([a-z_][a-z0-9_]*)\s*=(?!=)", blok))


class WidgetAttributeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_no_widget_attribute_shadows_a_qt_method(self):
        gevonden = []
        for klasse_naam, basis in _eigen_klassen():
            bestaand = set(dir(basis))
            for attribuut in sorted(_toegewezen_attributen(klasse_naam)):
                if attribuut in bestaand and attribuut not in TOEGESTAAN:
                    gevonden.append(f"{klasse_naam}.{attribuut} overschrijft {basis.__name__}.{attribuut}")
        self.assertEqual(gevonden, [], "; ".join(gevonden))

    def test_the_known_offender_is_renamed(self):
        """self.metric brak de applicatie zodra de stylesheet werd toegepast."""
        self.assertNotIn("self.metric = QComboBox()", SOURCE)
        self.assertIn("self.metric_choice = QComboBox()", SOURCE)

    def test_metric_really_is_a_qt_method(self):
        """Zonder deze controle zou de test hierboven niets bewijzen."""
        self.assertIn("metric", dir(QWidget))

    def test_applying_the_stylesheet_twice_does_not_crash(self):
        """De fout kwam pas bij het opnieuw toepassen van de stylesheet."""
        from bezoekerslijst_app import TrendPanel

        panel = TrendPanel(lambda: [])
        panel.setStyleSheet("QWidget { color: #fff; }")
        panel.setStyleSheet("QWidget { color: #000; }")
        self.assertTrue(hasattr(panel, "metric_choice"))


if __name__ == "__main__":
    unittest.main()
