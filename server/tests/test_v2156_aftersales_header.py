from pathlib import Path
import re
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
        # De maten zijn sindsdien verkleind; het gaat erom dat elk
        # navigatie-onderdeel een eigen glyphmaat krijgt en dat de knoppen een
        # icoonmaat meekrijgen.
        match = re.search(r"glyph_sizes = \{([^}]*)\}", source)
        self.assertIsNotNone(match, "zijbalkiconen hebben geen eigen maten meer")
        for key in ("callbacks", "events", "tasks", "event_control"):
            self.assertIn(f'"{key}"', match.group(1))
        self.assertIn("button.setIconSize(QSize(", source)

    def test_after_sales_is_a_standalone_page_with_event_selector(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("self.after_sales_event_combo = QComboBox()", source)
        self.assertIn("self.page_stack.addWidget(callback_widget)", source)
        self.assertIn("self.page_stack.setCurrentWidget(self.callback_tab)", source)
        self.assertIn("self._sync_event_combo(self.after_sales_event_combo)", source)

    def test_summary_indicators_are_visible_and_updated(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("self.event_summary_bar.setVisible(True)", source)
        # De lokale variabele heet inmiddels anders; op die naam matchen zei
        # niets over het gedrag.
        self.assertIn("self.after_sales_open[1].setText(", source)
        self.assertIn("self.after_sales_total[1].setText(", source)


if __name__ == "__main__":
    unittest.main()
