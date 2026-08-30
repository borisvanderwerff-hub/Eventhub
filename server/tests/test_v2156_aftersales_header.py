from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version2156AfterSalesHeaderTests(unittest.TestCase):
    def test_header_uses_transparent_artwork_at_both_ends(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "assets/backgrounds/header_wave.png").is_file())
        self.assertIn("class ArtworkHeader(QFrame)", source)
        self.assertIn("QTransform().scale(-1, 1)", source)
        self.assertIn("self.masthead = ArtworkHeader(HEADER_WAVE_PATH)", source)

    def test_sidebar_glyphs_have_readable_individual_sizes(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn('glyph_sizes = {"callbacks": 44, "events": 38, "tasks": 38, "event_control": 38}', source)
        self.assertIn("button.setIconSize(QSize(44, 44))", source)

    def test_after_sales_is_a_standalone_page_with_event_selector(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("self.after_sales_event_combo = QComboBox()", source)
        self.assertIn("self.page_stack.addWidget(callback_widget)", source)
        self.assertIn("self.page_stack.setCurrentWidget(self.callback_tab)", source)
        self.assertIn("self._sync_event_combo(self.after_sales_event_combo)", source)

    def test_summary_indicators_are_visible_and_updated(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("self.event_summary_bar.setVisible(True)", source)
        self.assertIn("self.after_sales_open[1].setText(str(open_callbacks))", source)


if __name__ == "__main__":
    unittest.main()
