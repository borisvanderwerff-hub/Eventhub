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
        desktop = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        manager = (ROOT / "server/manager/manager_window.py").read_text(encoding="utf-8")
        self.assertIn('_make_button_compact(QPushButton("Live sessie openen"))', desktop)
        self.assertIn('_make_button_compact(QPushButton("5WH exporteren naar Word"))', desktop)
        self.assertIn('_compact(QPushButton("Verbonden apparaten"))', manager)
        self.assertIn('_compact(QPushButton("Dossier synchroniseren"))', manager)


if __name__ == "__main__":
    unittest.main()
