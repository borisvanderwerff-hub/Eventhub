from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version2157SidebarAfterSalesTests(unittest.TestCase):
    def test_after_sales_search_and_header_are_compact(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn('self.callback_search_box.setPlaceholderText("Zoeken")', source)
        self.assertNotIn('callback_back_button = QPushButton("← Evenementen")', source)

    def test_utility_buttons_share_the_navigation_icon_box(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("file_button.setIconSize(QSize(44, 44))", source)
        self.assertIn("help_button.setIconSize(QSize(44, 44))", source)

    def test_event_counters_fit_on_one_row(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("cards.addWidget(card, 0, index)", source)
        self.assertIn("cards.setSpacing(8)", source)


if __name__ == "__main__":
    unittest.main()
