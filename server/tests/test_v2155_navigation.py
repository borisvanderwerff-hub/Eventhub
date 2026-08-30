from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version2155NavigationTests(unittest.TestCase):
    def test_mobile_search_uses_full_width_without_card_frame(self):
        css = (ROOT / "server/web/static/css/style.css").read_text(encoding="utf-8")
        self.assertIn(".page-connect .container { width:100%; max-width:none;", css)
        self.assertIn(".page-connect #checkinCard { margin:0; padding:0; border:0;", css)

    def test_after_sales_has_own_sidebar_entry_and_icon(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn('"callbacks": SIDEBAR_ICON_DIR / "nazorg.png"', source)
        self.assertIn('("callbacks", "After sales"', source)
        self.assertIn("self.show_nazorg_page", source)
        self.assertIn("self.page_stack.addWidget(callback_widget)", source)
        self.assertTrue((ROOT / "assets/sidebar/nazorg.png").is_file())

    def test_sidebar_width_and_utility_alignment_are_consistent(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("self.sidebar.setFixedWidth(184 if expanded else 70)", source)
        self.assertIn('button.setProperty("collapsed", not expanded)', source)

    def test_every_dated_event_uses_underscore_date_suffix(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("def event_name_with_date(name: str, event_date: str)", source)
        self.assertIn("strftime('%d_%m_%Y')", source)
        self.assertIn("updated[\"name\"] = event_name_with_date", source)
        self.assertIn("renamed_events = self._ensure_event_date_names()", source)

    def test_duplicate_event_edit_button_is_removed_from_header(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertNotIn('edit_event_button = QPushButton("Evenement aanpassen")', source)


if __name__ == "__main__":
    unittest.main()
