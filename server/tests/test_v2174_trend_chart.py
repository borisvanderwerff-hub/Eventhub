"""Leesbaarheid van de trendgrafiek."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import TrendChart


def _application():
    """Lettertypemetingen hebben een applicatie nodig."""
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])

# Het tekenen is verhuisd naar een gedeelde renderer, zodat het scherm, het
# exportvoorbeeld, de PDF, Excel en een losse PNG dezelfde grafiek opleveren.
CHART_SOURCE = (ROOT / "emt_charts.py").read_text(encoding="utf-8")


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
        self.source = desktop_source(ROOT)

    def _paint_block(self):
        return CHART_SOURCE[CHART_SOURCE.index("def paint_trend_chart("):]

    def test_chart_has_a_dark_mode_switch(self):
        self.assertTrue(hasattr(TrendChart, "set_dark_mode"))
        self.assertTrue(TrendChart.dark, "donker is de standaard van de app")

    def test_background_is_not_hardcoded_white(self):
        self.assertIn('QColor("#111827" if dark else "#ffffff")', CHART_SOURCE)
        self.assertIn('kleuren["surface"]', self._paint_block())

    def test_applying_the_theme_updates_both_charts(self):
        start = self.source.index("def _apply_style(self):")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("own_trend_panel", block)
        self.assertIn("loose_trend_panel", block)
        self.assertIn("set_dark_mode(self.dark_mode_enabled)", block)


class ReadabilityTests(unittest.TestCase):
    def setUp(self):
        self.source = desktop_source(ROOT)
        self.block = CHART_SOURCE[CHART_SOURCE.index("def paint_trend_chart("):]

    def test_values_are_printed_next_to_the_points(self):
        """De laatste waarde blijft als rustig anker zichtbaar."""
        self.assertIn("tekst(value)", self.block)

    def test_the_screen_and_the_export_share_one_renderer(self):
        """Twee tekenimplementaties naast elkaar lopen onvermijdelijk uiteen."""
        self.assertIn("paint_trend_chart(", self.source)
        self.assertNotIn("def paintEvent(self, event):\n        del event\n        surface", self.source)
        self.assertIn("def render_trend_image(", CHART_SOURCE)

    def test_intermediate_values_use_a_hover_tooltip(self):
        self.assertIn("def mouseMoveEvent(self, event):", self.source)
        self.assertIn("QToolTip.showText", self.source)
        self.assertIn("distance <= 12 ** 2", self.source)

    def test_only_the_last_value_is_permanently_labelled(self):
        self.assertIn('value = points[-1]["values"].get(group, 0.0)', self.block)

    def test_labels_are_clamped_inside_the_widget(self):
        self.assertIn("min(max(2, int(x) - 34), int(width) - 70)", self.block)
        self.assertIn("min(max(2, int(x) - 60), int(width) - 122)", self.block)

    def test_legend_height_is_reserved_before_drawing(self):
        self.assertIn("bottom = 34 + legend_rows * LEGEND_ROW_HEIGHT", self.block)
        self.assertLess(self.block.index("bottom = 34 + legend_rows"),
                        self.block.index("plot_height = max("))

    def test_even_a_single_series_has_a_colour_legend(self):
        from PySide6.QtGui import QFont, QFontMetricsF

        from emt_charts import legend_layout

        _app = _application()
        _kolommen, rijen = legend_layout(["Totaal"], QFontMetricsF(QFont("Segoe UI", 9)), 800)

        # Ook bij één reeks staat de betekenis van de kleur er expliciet bij.
        self.assertEqual(rijen, 1)
        self.assertEqual(legend_layout([], QFontMetricsF(QFont("Segoe UI", 9)), 800), (0, 0))

    def test_long_group_names_get_wider_columns(self):
        """Opleidingsniveaus en profielen pasten niet in vier vaste kolommen."""
        from PySide6.QtGui import QFont, QFontMetricsF

        from emt_charts import legend_layout

        _app = _application()
        metrics = QFontMetricsF(QFont("Segoe UI", 9))
        kort = legend_layout(["Mbo", "Hbo", "Wo", "Vmbo"], metrics, 800)
        lang = legend_layout(
            ["Mbo niveau 4 techniek", "Hbo bedrijfskunde en logistiek",
             "Wetenschappelijk onderwijs", "Vmbo basisberoepsgerichte leerweg"],
            metrics, 800,
        )

        self.assertEqual(kort[0], 4)
        self.assertLess(lang[0], kort[0], "lange namen horen bredere kolommen te krijgen")
        self.assertGreater(lang[1], kort[1])

    def test_names_are_elided_instead_of_chopped(self):
        """Afkappen op twintig tekens sneed woorden middendoor."""
        self.assertIn("elidedText(str(group), Qt.TextElideMode.ElideRight", self.block)
        self.assertNotIn("str(group)[:20]", self.block)

    def test_chart_area_is_large_enough_to_read(self):
        self.assertIn("self.setMinimumHeight(180)", self.source)

    def test_panel_resizes_charts_to_the_available_height(self):
        self.assertIn("def resizeEvent(self, event):", self.source)
        self.assertIn("tab_height = self.analysis_tabs.height()", self.source)
        self.assertIn("self.table.setMaximumHeight", self.source)


if __name__ == "__main__":
    unittest.main()
