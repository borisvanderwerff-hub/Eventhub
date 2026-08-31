from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version2157SidebarAfterSalesTests(unittest.TestCase):
    def test_after_sales_search_and_header_are_compact(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        # De tekst is uitgebreid naar wat er doorzocht wordt; het zoekveld
        # moet vooral een hint tonen.
        self.assertIn("self.callback_search_box.setPlaceholderText(", source)
        self.assertNotIn('callback_back_button = QPushButton("← Evenementen")', source)

    def test_utility_buttons_share_the_navigation_icon_box(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        # De maat is bijgesteld; het punt is dat de beheerknoppen dezelfde
        # icoonmaat delen als de navigatieknoppen, zodat ze uitlijnen.
        navigation = re.search(r"(?<!\w)button\.setIconSize\(QSize\((\d+), (\d+)\)\)", source)
        self.assertIsNotNone(navigation, "navigatieknoppen hebben geen icoonmaat")
        size = f"(QSize({navigation.group(1)}, {navigation.group(2)}))"
        for name in ("file_button", "profile_button", "help_button"):
            self.assertIn(f"{name}.setIconSize{size}", source, f"{name} wijkt af van de navigatie")

    def test_event_counters_fit_on_one_row(self):
        source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        self.assertIn("cards.addWidget(card, 0, index)", source)
        self.assertIn("cards.setSpacing(8)", source)


if __name__ == "__main__":
    unittest.main()
