"""De grafiek maximaliseren binnen het venster."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from bezoekerslijst_app import TrendPanel


class FakeWidget:
    def __init__(self):
        self.hidden = False

    def setVisible(self, visible):
        self.hidden = not visible


class FakeButton(FakeWidget):
    def __init__(self):
        super().__init__()
        self.checked = False
        self.label = "⤢"
        self.tooltip = ""

    def setChecked(self, value):
        self.checked = bool(value)

    def setText(self, value):
        self.label = value

    def setToolTip(self, value):
        self.tooltip = value


class FakePanel:
    """Draait de compatibiliteitsingang zonder Qt."""

    set_maximised = TrendPanel.set_maximised

    def __init__(self, chrome_count=3):
        self.maximised = False
        self.opened = 0
        self.table = FakeWidget()
        self.chrome = [FakeWidget() for _ in range(chrome_count)]
        self.expand_button = FakeButton()

    def open_chart_window(self):
        self.opened += 1


class FullScreenTests(unittest.TestCase):
    def test_maximising_opens_a_separate_window(self):
        panel = FakePanel()
        panel.set_maximised(True)

        self.assertEqual(panel.opened, 1)
        self.assertFalse(panel.table.hidden)
        self.assertFalse(any(widget.hidden for widget in panel.chrome))

    def test_false_does_not_open_a_window(self):
        panel = FakePanel()
        panel.set_maximised(False)
        self.assertEqual(panel.opened, 0)


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.source = desktop_source(ROOT)

    def _block(self, name, cls_prefix="    def "):
        start = self.source.index(f"{cls_prefix}{name}(self")
        return self.source[start:self.source.index("\n    def ", start + 1)]

    def test_button_is_small_and_carries_no_label_text(self):
        block = self._block("__init__", "    def ")
        self.assertIn('button = QPushButton("⤢")', self.source)
        self.assertIn("button.setFixedSize(38, 38)", self.source)
        self.assertIn("self.expand_button = button", self.source)

    def test_normal_view_keeps_the_old_focused_layout(self):
        self.assertIn("self.summary.setVisible(False)", self.source)
        self.assertIn("self.table.setVisible(False)", self.source)

    def test_full_screen_button_is_overlaid_on_the_chart(self):
        self.assertIn("def _chart_container(self, chart: TrendChart):", self.source)
        self.assertIn("Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight", self.source)
        self.assertIn("self.open_chart_window(source)", self.source)

    def test_f11_opens_the_chart_window_when_trends_is_open(self):
        block = self._block("toggle_event_focus_mode")
        self.assertIn("self.trends_page", block)
        self.assertIn("panel.open_chart_window()", block)

    def test_full_screen_is_a_real_separate_dialog(self):
        self.assertIn("class TrendChartDialog(QDialog):", self.source)
        self.assertIn("dialog.showMaximized()", self.source)
        self.assertIn('QPushButton("Terug naar Trends")', self.source)

    def test_f11_is_enabled_when_the_trends_page_opens(self):
        block = self._block("show_trends_page")
        self.assertIn("self.focus_action.setEnabled(True)", block)

    def test_each_workspace_hides_its_own_surroundings(self):
        start = self.source.index("def _build_trends_page(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("self.own_trend_panel.chrome = [", block)
        self.assertIn("self.loose_trend_panel.chrome = [", block)
        # De compacte beheerknop hoort alleen bij de losse analyse.
        loose = block[block.index("self.loose_trend_panel.chrome = ["):]
        self.assertIn("self.trend_manage_button", loose)
        self.assertNotIn("self.trend_source_list", loose)

    def test_the_controls_stay_visible_so_you_can_keep_switching(self):
        """Maximaliseren mag de meetwaarde-keuze niet wegnemen."""
        start = self.source.index("def _build_trends_page(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertNotIn("metric_choice", block.split("chrome = [")[-1].split("]")[0])


if __name__ == "__main__":
    unittest.main()
