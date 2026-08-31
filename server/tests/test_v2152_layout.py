from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version2152LayoutTests(unittest.TestCase):
    def test_sidebar_icons_are_cropped_and_centered_on_shared_canvas(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("bounds = QRegion(source.mask()).boundingRect()", source)
        self.assertNotIn("source.mask().boundingRect()", source)
        self.assertIn("canvas_size = 44", source)
        self.assertIn("(pixel_canvas_size - glyph.width()) // 2", source)
        self.assertIn("(pixel_canvas_size - glyph.height()) // 2", source)

    def test_compact_buttons_do_not_expand_horizontally(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed", source)

    def test_major_vertical_action_groups_use_compact_buttons(self):
        """Knoppen in verticale groepen mogen niet over de volle breedte rekken.

        Op losse knoplabels matchen bleek te breekbaar: Live sessie openen en
        Verbonden apparaten bestaan niet meer, en de Server Manager gebruikt
        inmiddels menu's in plaats van knoppenrijen. Getoetst wordt nu dat het
        hulpmiddel bestaat en daadwerkelijk breed wordt toegepast.
        """
        desktop = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("def _make_button_compact(", desktop)
        self.assertIn('_make_button_compact(QPushButton("5WH exporteren naar Word"))', desktop)
        self.assertGreaterEqual(
            desktop.count("_make_button_compact("), 10,
            "verticale actiegroepen gebruiken het hulpmiddel nauwelijks nog",
        )


if __name__ == "__main__":
    unittest.main()
