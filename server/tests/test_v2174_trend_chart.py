"""Leesbaarheid van de trendgrafiek."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import TrendChart


class AxisTests(unittest.TestCase):
    """De as toonde waarden als 17,2 en 5,8 in plaats van ronde stappen."""

    def test_step_is_a_round_number(self):
        for highest, expected in ((23, 10), (100, 25), (8, 2), (4, 1), (1, 0.25)):
            self.assertEqual(TrendChart._nice_step(highest), expected, f"bij {highest}")

    def test_step_never_returns_zero(self):
        self.assertGreater(TrendChart._nice_step(0), 0)
        self.assertGreater(TrendChart._nice_step(-5), 0)
        self.assertGreater(TrendChart._nice_step(0.001), 0)

    def test_step_divides_the_range_into_a_few_readable_ticks(self):
        for highest in (7, 23, 96, 480, 1234):
            step = TrendChart._nice_step(highest)
            ticks = highest / step
            self.assertGreaterEqual(ticks, 1.5, f"te weinig lijnen bij {highest}")
            self.assertLessEqual(ticks, 8, f"te veel lijnen bij {highest}")


class ThemeTests(unittest.TestCase):
    """De grafiek tekent zelf en volgt de stylesheet niet."""

    def setUp(self):
        self.source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

    def _paint_block(self):
        start = self.source.index("    def paintEvent(self, event):\n        del event\n        surface")
        return self.source[start:self.source.index("\nclass ", start)]

    def test_chart_has_a_dark_mode_switch(self):
        self.assertTrue(hasattr(TrendChart, "set_dark_mode"))
        self.assertTrue(TrendChart.dark, "donker is de standaard van de app")

    def test_background_is_not_hardcoded_white(self):
        block = self._paint_block()
        self.assertIn('QColor("#111827" if self.dark else "#ffffff")', block)
        self.assertNotIn('painter.fillRect(self.rect(), QColor("#ffffff"))', block)

    def test_applying_the_theme_updates_both_charts(self):
        start = self.source.index("def _apply_style(self):")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("own_trend_panel", block)
        self.assertIn("loose_trend_panel", block)
        self.assertIn("set_dark_mode(self.dark_mode_enabled)", block)


class ReadabilityTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")
        start = self.source.index("    def paintEvent(self, event):\n        del event\n        surface")
        self.block = self.source[start:self.source.index("\nclass ", start)]

    def test_values_are_printed_next_to_the_points(self):
        """Zonder deze labels moet je de tabel eronder lezen om iets af te lezen."""
        self.assertIn("self._formatted(value)", self.block)

    def test_labels_are_clamped_inside_the_widget(self):
        self.assertIn("min(max(2, int(x) - 34), self.width() - 70)", self.block)
        self.assertIn("min(max(2, int(x) - 60), self.width() - 122)", self.block)

    def test_legend_height_is_reserved_before_drawing(self):
        self.assertIn("bottom = 34 + legend_rows * 20", self.block)

    def test_chart_area_is_large_enough_to_read(self):
        self.assertIn("self.setMinimumHeight(360)", self.source)


if __name__ == "__main__":
    unittest.main()
