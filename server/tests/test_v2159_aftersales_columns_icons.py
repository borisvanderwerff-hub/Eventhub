from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Version2159AfterSalesColumnsAndIconsTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

    def test_each_columns_button_opens_its_own_menu(self):
        self.assertIn('self._columns_button("participants")', self.source)
        self.assertIn('self._columns_button("callbacks")', self.source)
        self.assertIn('self._columns_button("presence")', self.source)
        self.assertIn("def choose_columns(self, initial_view", self.source)
        self.assertIn("menu_tabs.setCurrentIndex(initial_index)", self.source)

    def test_sidebar_icons_offer_high_dpi_pixmaps(self):
        self.assertIn("for scale in (1, 2, 3):", self.source)
        self.assertIn("canvas.setDevicePixelRatio(scale)", self.source)
        self.assertIn("icon.addPixmap(canvas", self.source)

    def test_after_sales_asset_is_tightly_cropped(self):
        data = (ROOT / "assets" / "sidebar" / "nazorg.png").read_bytes()[:24]
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertLess(width / height, 1.2)


if __name__ == "__main__":
    unittest.main()
