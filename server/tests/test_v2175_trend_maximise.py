"""De grafiek maximaliseren binnen het venster."""
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
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
    """Draait de echte schakellogica zonder Qt."""

    set_maximised = TrendPanel.set_maximised

    def __init__(self, chrome_count=3):
        self.maximised = False
        self.table = FakeWidget()
        self.chrome = [FakeWidget() for _ in range(chrome_count)]
        self.expand_button = FakeButton()


class ToggleTests(unittest.TestCase):
    def test_maximising_hides_the_table_and_the_surrounding_widgets(self):
        panel = FakePanel()
        panel.set_maximised(True)

        self.assertTrue(panel.maximised)
        self.assertTrue(panel.table.hidden)
        self.assertTrue(all(widget.hidden for widget in panel.chrome))

    def test_restoring_brings_everything_back(self):
        panel = FakePanel()
        panel.set_maximised(True)
        panel.set_maximised(False)

        self.assertFalse(panel.maximised)
        self.assertFalse(panel.table.hidden)
        self.assertFalse(any(widget.hidden for widget in panel.chrome))

    def test_button_reflects_the_state(self):
        panel = FakePanel()
        panel.set_maximised(True)
        self.assertTrue(panel.expand_button.checked)
        self.assertEqual(panel.expand_button.label, "⤡")
        self.assertIn("Terug naar", panel.expand_button.tooltip)

        panel.set_maximised(False)
        self.assertFalse(panel.expand_button.checked)
        self.assertEqual(panel.expand_button.label, "⤢")
        self.assertIn("maximaliseren", panel.expand_button.tooltip)

    def test_toggling_twice_is_stable(self):
        panel = FakePanel()
        for _ in range(3):
            panel.set_maximised(True)
            panel.set_maximised(False)
        self.assertFalse(panel.table.hidden)

    def test_panel_without_surrounding_widgets_still_works(self):
        panel = FakePanel(chrome_count=0)
        panel.set_maximised(True)
        self.assertTrue(panel.table.hidden)


class WiringTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "bezoekerslijst_app.py").read_text(encoding="utf-8")

    def _block(self, name, cls_prefix="    def "):
        start = self.source.index(f"{cls_prefix}{name}(self")
        return self.source[start:self.source.index("\n    def ", start + 1)]

    def test_button_is_small_and_carries_no_label_text(self):
        block = self._block("__init__", "    def ")
        self.assertIn('self.expand_button = QPushButton("⤢")', self.source)
        self.assertIn("setFixedWidth(38)", self.source)

    def test_f11_maximises_the_chart_when_trends_is_open(self):
        block = self._block("toggle_event_focus_mode")
        self.assertIn("self.trends_page", block)
        self.assertIn("panel.set_maximised(not panel.maximised)", block)

    def test_f11_is_enabled_when_the_trends_page_opens(self):
        block = self._block("show_trends_page")
        self.assertIn("self.focus_action.setEnabled(True)", block)

    def test_each_workspace_hides_its_own_surroundings(self):
        start = self.source.index("def _build_trends_page(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertIn("self.own_trend_panel.chrome = [", block)
        self.assertIn("self.loose_trend_panel.chrome = [", block)
        # De beheerbalk en het setoverzicht horen alleen bij de losse analyse.
        loose = block[block.index("self.loose_trend_panel.chrome = ["):]
        self.assertIn("manage", loose)
        self.assertIn("self.trend_source_list", loose)

    def test_the_controls_stay_visible_so_you_can_keep_switching(self):
        """Maximaliseren mag de meetwaarde-keuze niet wegnemen."""
        start = self.source.index("def _build_trends_page(self")
        block = self.source[start:self.source.index("\n    def ", start + 1)]
        self.assertNotIn("metric_choice", block.split("chrome = [")[-1].split("]")[0])


if __name__ == "__main__":
    unittest.main()
