from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source


class Version2155NavigationTests(unittest.TestCase):
    def test_mobile_search_uses_full_width_without_card_frame(self):
        css = (ROOT / "server/web/static/css/style.css").read_text(encoding="utf-8")
        self.assertIn(".page-connect .container { width:100%; max-width:none;", css)
        self.assertIn(".page-connect #checkinCard { margin:0; padding:0; border:0;", css)

    def test_after_sales_has_own_sidebar_entry_and_icon(self):
        source = desktop_source(ROOT)
        self.assertIn('"callbacks": SIDEBAR_ICON_DIR / "nazorg.png"', source)
        self.assertIn('("callbacks", "After sales"', source)
        self.assertIn("self.show_nazorg_page", source)
        self.assertIn("self.page_stack.addWidget(callback_widget)", source)
        self.assertTrue((ROOT / "assets/sidebar/nazorg.png").is_file())

    def test_sidebar_width_and_utility_alignment_are_consistent(self):
        source = desktop_source(ROOT)
        # Niet de exacte pixels vastpinnen; die zijn sindsdien bijgesteld. Wat
        # telt is dat de zijbalk inklapt naar een smallere vaste breedte.
        match = re.search(
            r"self\.sidebar\.setFixedWidth\((\d+) if expanded else (\d+)\)", source
        )
        self.assertIsNotNone(match, "zijbalk heeft geen in- en uitgeklapte breedte")
        self.assertGreater(int(match.group(1)), int(match.group(2)))
        self.assertIn('button.setProperty("collapsed", not expanded)', source)

    def test_every_dated_event_carries_its_date_in_the_name(self):
        """De notatie is van 15_04_2026 naar (15-04-'26) gegaan.

        De oude test pinde het onderstreepte formaat vast. Wat blijft tellen is
        dat elk evenement zijn datum in de naam draagt en dat die naam via
        dezelfde functie wordt opgebouwd.
        """
        source = desktop_source(ROOT)
        self.assertIn("def event_name_with_date(name: str, event_date: str)", source)
        self.assertIn("parsed.strftime(", source)
        self.assertIn("updated[\"name\"] = event_name_with_date", source)
        self.assertIn("renamed_events = self._ensure_event_date_names()", source)

    def test_duplicate_event_edit_button_is_removed_from_header(self):
        source = desktop_source(ROOT)
        self.assertNotIn('edit_event_button = QPushButton("Evenement aanpassen")', source)


if __name__ == "__main__":
    unittest.main()
