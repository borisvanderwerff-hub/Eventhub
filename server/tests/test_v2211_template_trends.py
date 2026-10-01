import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import date
import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from bezoekerslijst_app import TrendPanel
from emt_event_templates_ui import LinkEventsDialog
from emt_trends import event_summary, filter_summaries
import emt_report as report


def sample(ident, template, day, count):
    return {"id": ident, "name": ident, "date": day, "template_id": template,
            "template_name": "Marine" if template else "", "event_type": "Meeloopdag",
            "statistiek": {"aangemeld": count, "aanwezig": count, "noshows": 0, "afgemeld": 0}}


class TemplateTrendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_summary_carries_stable_link(self):
        source = sample("one", "t", "01-01-2025", 5)
        result = event_summary(source)
        self.assertIsNotNone(result)
        self.assertEqual(result["template_id"], "t")

    def test_template_filter_excludes_unlinked_and_other_templates(self):
        rows = [sample("one", "t", "01-01-2025", 5), sample("two", "", "01-01-2025", 7), sample("three", "u", "01-01-2025", 99)]
        self.assertEqual([r["id"] for r in filter_summaries(rows, {"template_id": "t"})], ["one"])

    def test_single_template_remains_selectable_and_reaches_export(self):
        rows = [sample("one", "t", "01-01-2025", 5), sample("two", "", "02-01-2025", 7)]
        panel = TrendPanel(lambda: rows)
        panel.refresh()
        panel.template_filter.setCurrentIndex(panel.template_filter.findData("t"))
        self.assertEqual(panel.current_filters()["template_id"], "t")
        self.assertEqual(panel.kpi_labels["aangemeld"].text(), "5")
        model = report.build_report_model(rows, dict(report.default_config(), selectie=panel.current_filters()))
        self.assertEqual(model["kpis"]["aangemeld"], 5)
        panel._clear_filters()
        self.assertEqual(panel.kpi_labels["aangemeld"].text(), "12")
        panel.close()

    def test_comparison_uses_same_template_for_both_periods(self):
        rows = [sample("now", "t", "10-02-2025", 20), sample("before", "t", "25-01-2025", 10), sample("other", "u", "25-01-2025", 1000)]
        config = report.default_config("volledig")
        config["selectie"].update(template_id="t", template_name="Marine", since=date(2025, 2, 1), until=date(2025, 2, 28))
        model = report.build_report_model(rows, config)
        self.assertEqual(model["vergelijking"]["previous"]["aangemeld"], 10)
        self.assertIn("Marine", dict(model["filters"])["Selectie"])

    def test_bulk_selection_keeps_hidden_checks_explicit(self):
        events = [sample("one", "", "01-01-2025", 5), sample("two", "", "02-01-2025", 7)]
        dialog = LinkEventsDialog(None, events, [{"id": "t", "name": "Marine"}], "one")
        dialog.events.item(1).setCheckState(Qt.CheckState.Checked)
        dialog.search.setText("two")
        self.assertEqual(set(dialog.selected_ids()), {"one", "two"})
        self.assertIn("1 buiten", dialog.count.text())
        dialog.close()

    def test_builder_preserves_template_and_can_change_selection(self):
        from emt_report_ui import ReportBuilderDialog
        class Settings:
            def value(self, key, default=None, **kwargs):
                return default
        rows = [sample("one", "t", "01-01-2025", 5), sample("two", "", "02-01-2025", 7)]
        dialog = ReportBuilderDialog(rows, {"template_id": "t", "template_name": "Marine"}, Settings())
        self.assertEqual(dialog.event_template_filter.currentData(), "t")
        self.assertEqual(report.build_report_model(rows, dialog.config)["kpis"]["aangemeld"], 5)
        dialog.event_template_filter.setCurrentIndex(0)
        self.assertEqual(report.build_report_model(rows, dialog.config)["kpis"]["aangemeld"], 12)
        dialog.close()
