"""Historische Trends: filters, KPI's, vergelijkingen en privacyveilige inzichten."""
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
from server.tests.desktop_source import desktop_source
sys.path.insert(0, str(ROOT))

from emt_trends import (
    available_dimensions, build_series, compare_periods, filter_summaries,
    generate_insights, overview_kpis, participant_scope, ranked_events,
    regular_scope_available,
)
from bezoekerslijst_app import TrendPanel


def item(name, day, registered, attended, kind="Meeloopdag", location="Marinebasis"):
    return {
        "id": name, "name": name, "date": day, "event_type": kind,
        "place": "Den Helder", "location": location,
        "statistiek": {
            "schema": 3, "aangemeld": registered, "aanwezig": attended,
            "noshows": registered - attended,
            "verdeling": {"Opleidingsniveau": {
                "MBO": {"aangemeld": registered, "aanwezig": attended,
                        "noshow": registered - attended},
            }},
        },
    }


class HistoricalTrendTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            item("A", "10-01-2025", 100, 50),
            item("B", "10-01-2026", 120, 96, "Voorlichting", "Kazerne"),
            item("C", "10-02-2026", 80, 72, "Voorlichting", "Kazerne"),
        ]

    def test_event_filters_combine(self):
        selected = filter_summaries(self.rows, {
            "since": date(2026, 1, 1), "until": date(2026, 12, 31),
            "event_type": "Voorlichting", "location": "Kazerne",
        })
        self.assertEqual([row["id"] for row in selected], ["B", "C"])

    def test_overview_uses_weighted_turnout(self):
        kpis = overview_kpis(self.rows[1:])
        self.assertEqual(kpis["evenementen"], 2)
        self.assertEqual(kpis["opkomst_percentage"], 84.0)
        self.assertEqual(kpis["noshow_percentage"], 16.0)

    def test_comparison_has_absolute_percent_and_percentage_points(self):
        result = compare_periods(
            self.rows, date(2026, 1, 1), date(2026, 2, 28),
            date(2025, 1, 1), date(2025, 2, 28),
        )
        self.assertEqual(result["changes"]["aanwezig"]["absolute"], 118)
        self.assertEqual(result["changes"]["opkomst_percentage"]["percentage_points"], 34)
        self.assertIsNotNone(result["changes"]["aanwezig"]["percentage"])

    def test_noshow_percentage_is_supported_for_groups(self):
        series = build_series(self.rows, "noshow_percentage", "Opleidingsniveau", "year")
        self.assertEqual(series["points"][1]["values"]["MBO"], 16.0)

    def test_dimensions_only_come_from_real_data(self):
        self.assertIn("Opleidingsniveau", available_dimensions(self.rows))
        self.assertNotIn("Geslacht", available_dimensions(self.rows))

    def test_ranking_and_insights_are_reproducible(self):
        self.assertEqual(ranked_events(self.rows)[0]["id"], "C")
        self.assertTrue(generate_insights(self.rows))

    def test_no_rows_is_a_graceful_empty_state(self):
        self.assertEqual(overview_kpis([])["opkomst_percentage"], 0)
        self.assertEqual(generate_insights([]), [])

    def test_group_values_can_be_expressed_as_share_of_the_selected_status(self):
        row = item("A", "10-01-2026", 10, 5)
        row["statistiek"]["verdeling"]["Opleidingsniveau"] = {
            "MBO-4": {"aangemeld": 4, "aanwezig": 2, "noshow": 2, "afgemeld": 0},
            "HBO": {"aangemeld": 6, "aanwezig": 3, "noshow": 3, "afgemeld": 0},
        }
        series = build_series(
            [row], "noshows", "Opleidingsniveau", "event", percentage_of_total=True
        )
        self.assertEqual(series["points"][0]["values"], {"HBO": 60.0, "MBO-4": 40.0})
        self.assertEqual(series["points"][0]["raw_values"], {"HBO": 3.0, "MBO-4": 2.0})
        self.assertEqual(series["display_metric"], "aandeel_percentage")

    def test_legacy_invitee_data_is_not_presented_as_regular(self):
        legacy = item("Oud", "10-01-2025", 10, 8)
        legacy["statistiek"]["introducees"] = 2
        self.assertFalse(regular_scope_available([legacy]))
        self.assertEqual(participant_scope([legacy], False), [])


class TrendWorkspaceLayoutTests(unittest.TestCase):
    def setUp(self):
        self.source = desktop_source(ROOT)

    def test_analysis_functions_have_separate_tabs(self):
        for label in ("Overzicht", "Opkomst", "Demografie & opleiding", "Vergelijken", "Evenementen", "Inzichten"):
            self.assertIn(f'addTab(', self.source)
            self.assertIn(f'"{label}"', self.source)

    def test_custom_comparison_dates_are_not_in_the_shared_filter_grid(self):
        filters_start = self.source.index('filters = QFrame()')
        tabs_start = self.source.index('self.analysis_tabs = QTabWidget()', filters_start)
        filters_block = self.source[filters_start:tabs_start]
        self.assertNotIn('filter_layout.addWidget(widget, 3, column)', filters_block)
        self.assertIn('comparison_dates_layout.addWidget(widget, 1, column)', self.source[tabs_start:])

    def test_overview_and_detail_have_independent_charts(self):
        self.assertIn('self.overview_chart = TrendChart()', self.source)
        self.assertIn('self.demographic_chart = TrendChart()', self.source)

    def test_overview_uses_a_chart_with_a_vertical_kpi_rail(self):
        self.assertIn('kpi_row = QVBoxLayout(self.kpi_bar)', self.source)
        self.assertIn('self.kpi_bar.setMaximumWidth(320)', self.source)
        self.assertIn('overview_body.addWidget(overview_left, 3)', self.source)
        self.assertIn('overview_body.addWidget(self.kpi_bar, 1, Qt.AlignmentFlag.AlignTop)', self.source)

    def test_selector_bars_are_not_collapsible(self):
        self.assertNotIn('def _collapse_button(self, widgets, name: str):', self.source)

    def test_filters_share_one_compact_inline_row(self):
        self.assertIn('self.filter_bar_layout = QHBoxLayout(filter_bar)', self.source)
        self.assertIn('(self.range_choice, 125, "Periode")', self.source)
        self.assertIn('(self.event_filter, 155, "Evenement")', self.source)
        self.assertIn('controls.setVisible(False)', self.source)
        self.assertIn('demographic_controls.setVisible(False)', self.source)
        self.assertIn('def _update_inline_filters(self, *_):', self.source)

    def test_exporting_sits_above_the_filters_next_to_the_workspaces(self):
        """De knop hoort bij de werkgebieden, niet tussen de filters.

        Exporteren geldt voor het werkgebied dat openstaat, dus staat er één
        knop rechtsboven in de balk van de tabbladen in plaats van een knop in
        de filterrij van elk paneel afzonderlijk.
        """
        self.assertIn('self.trend_export_button = QPushButton("Exporteren")', self.source)
        self.assertIn("self.trend_tabs.setCornerWidget(", self.source)
        self.assertIn("Qt.Corner.TopRightCorner", self.source)
        self.assertNotIn("self.export_button", self.source)

    def test_time_unit_is_automatic_instead_of_a_selector(self):
        start = self.source.index("def _update_inline_filters(self")
        blok = self.source[start:self.source.index(chr(10) + "    def ", start + 1)]
        self.assertIn("self.overview_period.setVisible(False)", blok)
        self.assertIn("self.period.setVisible(False)", blok)
        self.assertIn("self.demographic_period.setVisible(False)", blok)
        self.assertIn("def _automatic_timeline_period", self.source)
        self.assertIn('f"Tijdlijn: {timeline_labels[timeline_period]}"', self.source)

    def test_a_year_is_shown_as_monthly_development(self):
        rows = [{"date": "10-01-2026"}, {"date": "10-05-2026"}, {"date": "10-09-2026"}]
        self.assertEqual(
            TrendPanel._automatic_timeline_period(rows, date(2026, 1, 1), date(2026, 12, 31)),
            "month",
        )

    def test_automatic_time_unit_falls_back_to_events_to_keep_a_trend(self):
        rows = [{"date": "10-01-2026"}, {"date": "20-01-2026"}]
        self.assertEqual(
            TrendPanel._automatic_timeline_period(rows, date(2026, 1, 1), date(2026, 12, 31)),
            "event",
        )

    def test_filters_are_only_shown_when_the_source_has_a_real_choice(self):
        self.assertIn('meaningful = len(values) > 1', self.source)
        self.assertIn('"period": period_available', self.source)
        self.assertIn('self.event_type_filter.setVisible(bool(available.get("event_type")))', self.source)
        self.assertIn('self.event_filter.setVisible(bool(available.get("event")))', self.source)
        self.assertIn('self.clear_filters_button.setVisible(bool(active))', self.source)

    def test_participant_scope_and_percentage_are_contextual_controls(self):
        self.assertIn('self.participant_scope.addItem("Reguliere deelnemers", False)', self.source)
        self.assertIn('self.participant_scope.addItem("Inclusief introducees", True)', self.source)
        self.assertIn('QCheckBox("Als percentage van totaal")', self.source)
        self.assertIn('percentage_dimension in TREND_GROUP_DIMENSIONS', self.source)
        self.assertIn('self.participant_scope.setEnabled(True)', self.source)
        self.assertIn('def _participant_scope_changed(self, *_):', self.source)

    def test_kpi_values_have_enough_vertical_room(self):
        self.assertIn('card_layout = QHBoxLayout(card)', self.source)
        self.assertIn('value.setMinimumHeight(34)', self.source)
        self.assertIn('Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter', self.source)

    def test_custom_period_opens_a_date_selector(self):
        self.assertIn('widget.currentIndexChanged.connect(self._range_changed)', self.source)
        self.assertIn('def _choose_custom_range(self)', self.source)
        self.assertIn('dialog.setWindowTitle("Zelf periode kiezen")', self.source)
        self.assertIn('form.addRow("Van:", since_picker)', self.source)
        self.assertIn('form.addRow("Tot en met:", until_picker)', self.source)

    def test_loose_analysis_controls_open_in_one_compact_dialog(self):
        self.assertIn('QPushButton("✎  Analyse beheren")', self.source)
        self.assertIn('self.loose_trend_panel.filter_bar_layout.insertWidget(0, self.trend_manage_button)', self.source)
        self.assertIn('self.trend_source_list.setVisible(False)', self.source)
        self.assertIn('self.trend_manage_button.setMaximumWidth(190)', self.source)
        self.assertIn('def _open_trend_source_management(self)', self.source)
        self.assertIn('dialog.setWindowTitle("Losse analyse instellen")', self.source)
        self.assertIn('options.addRow("Analyse:", analysis_choice)', self.source)
        self.assertIn('options.addRow("Meetellen:", source_choice)', self.source)
        self.assertIn('QPushButton("Bezoekerslijsten inladen")', self.source)


if __name__ == "__main__":
    unittest.main()
