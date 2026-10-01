"""Het scherm Trends en de grafiekonderdelen die daarbij horen: de lijngrafiek, de
kruistabel als heatmap en de staaf- en donutdiagrammen bij Statistieken.

De panelen krijgen hun cijfers kant en klaar binnen; rekenen gebeurt in emt_trends.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date

from PySide6.QtCore import QDate, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit as CalendarDateInput, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QMenu, QMessageBox, QPushButton, QSizePolicy, QTabWidget,
    QTableWidget, QTableWidgetItem, QToolTip, QVBoxLayout, QWidget,
)

from bezoekerslijst_core import normalize
from emt_base import exports_directory
from emt_charts import (
    TREND_PALETTE,
    format_value as format_chart_value,
    has_values as chart_has_values,
    nice_step as chart_nice_step,
    paint_trend_chart,
    render_trend_image,
)
from emt_models import parse_date
from emt_report_export import ExportError, export_chart_png
from emt_trend_selection_ui import TrendGroupDialog
from emt_trends import (
    EVENT_DIMENSIONS as TREND_EVENT_DIMENSIONS,
    GROUP_DIMENSIONS as TREND_GROUP_DIMENSIONS,
    METRICS as TREND_METRICS,
    PERIODS as TREND_PERIODS,
    available_dimensions as trend_available_dimensions,
    build_series as build_trend_series,
    compare_periods as compare_trend_periods,
    describe_change as describe_trend_change,
    filter_summaries as filter_trend_summaries,
    generate_insights as generate_trend_insights,
    overview_kpis as trend_overview_kpis,
    participant_scope as trend_participant_scope,
    ranked_events as ranked_trend_events,
    regular_scope_available as trend_regular_scope_available,
    select_series_groups,
    series_totals as trend_series_totals,
)
from emt_widgets import ScrollSafeComboBox, _fit_dialog_to_screen, _make_button_compact
from emt_trend_charts_ui import (
    STATISTICS_CHART_TYPES, StatisticsChart, CrosstabHeatmap, TrendChart, TrendChartDialog,
)


class TrendPanel(QWidget):
    """Bediening, grafiek, samenvatting en tabel voor één trendweergave.

    Bestaat als eigen widget omdat er twee werkgebieden zijn — de eigen
    evenementen en een losse analyse van ingeladen bezoekerslijsten — die
    dezelfde bediening horen te hebben zonder die code te dupliceren.
    """

    def __init__(self, provider, open_event_callback=None, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.open_event_callback = open_event_callback
        self._updating_filters = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(10)

        filters = QFrame()
        filters.setObjectName("toolbar")
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(14, 10, 14, 10)
        filter_layout.setSpacing(8)
        self.range_choice = ScrollSafeComboBox()
        for label, value in (
            ("Alle perioden", "all"), ("Afgelopen 6 maanden", "6m"),
            ("Dit jaar", "year"), ("Dit kwartaal", "quarter"), ("Zelf kiezen", "custom"),
        ):
            self.range_choice.addItem(label, value)
        self._last_range_value = "all"
        self.event_type_filter = ScrollSafeComboBox()
        self.location_filter = ScrollSafeComboBox()
        self.template_filter = ScrollSafeComboBox()
        self.template_filter.currentIndexChanged.connect(self.refresh)
        self.event_filter = ScrollSafeComboBox()
        self.participant_scope = ScrollSafeComboBox()
        self.participant_scope.addItem("Reguliere deelnemers", False)
        self.participant_scope.addItem("Inclusief introducees", True)
        self._regular_scope_supported = True
        self.participant_scope.currentIndexChanged.connect(self._participant_scope_changed)
        self.percentage_of_total = QCheckBox("Als percentage van totaal")
        self.percentage_of_total.setToolTip(
            "Toon per groep welk aandeel deze vormt van de gekozen meetwaarde"
        )
        self.percentage_of_total.stateChanged.connect(self.refresh)
        for widget in (self.event_type_filter, self.location_filter, self.event_filter):
            widget.setMinimumWidth(145)
        self.since_date = CalendarDateInput()
        self.until_date = CalendarDateInput()
        self.compare_since = CalendarDateInput()
        self.compare_until = CalendarDateInput()
        today = QDate.currentDate()
        for widget in (self.since_date, self.until_date, self.compare_since, self.compare_until):
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("dd-MM-yyyy")
        self.until_date.setDate(today)
        self.since_date.setDate(today.addMonths(-6).addDays(1))
        self.compare_until.setDate(self.since_date.date().addDays(-1))
        self.compare_since.setDate(self.compare_until.date().addMonths(-6).addDays(1))
        for column, (caption, widget) in enumerate((
            ("Periode", self.range_choice), ("Evenementsoort", self.event_type_filter),
            ("Locatie", self.location_filter), ("Evenement", self.event_filter),
        )):
            label = QLabel(caption)
            label.setObjectName("hintLabel")
            filter_layout.addWidget(label, 0, column)
            filter_layout.addWidget(widget, 1, column)
            if widget is self.range_choice:
                widget.currentIndexChanged.connect(self._range_changed)
            else:
                widget.currentIndexChanged.connect(self.refresh)
        clear_filters = _make_button_compact(QPushButton("Filters wissen"))
        clear_filters.setObjectName("secondaryButton")
        clear_filters.clicked.connect(self._clear_filters)
        self.clear_filters_button = clear_filters
        filter_layout.addWidget(clear_filters, 1, 4)
        for widget in (self.since_date, self.until_date, self.compare_since, self.compare_until):
            widget.dateChanged.connect(self._manual_date_changed)
        filters.setVisible(False)
        layout.addWidget(filters)

        filter_bar = QWidget()
        self.filter_bar_layout = QHBoxLayout(filter_bar)
        self.filter_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_bar_layout.setSpacing(8)
        self.timeline_granularity = QLabel("")
        self.timeline_granularity.setObjectName("hintLabel")
        layout.addWidget(filter_bar)
        chart_filter_bar = QWidget()
        self.chart_filter_layout = QHBoxLayout(chart_filter_bar)
        self.chart_filter_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_filter_layout.setSpacing(8)
        layout.addWidget(chart_filter_bar)
        self.group_selections = {}
        self.display_choice = ScrollSafeComboBox()
        self.display_choice.addItem("Verloop", "verloop")
        self.display_choice.addItem("Statistieken", "statistieken")
        self.time_choice = ScrollSafeComboBox()
        for title, key in (("Automatisch", "auto"), ("Per evenement", "event"),
                           ("Per maand", "month"), ("Per kwartaal", "quarter"), ("Per jaar", "year")):
            self.time_choice.addItem(title, key)
        self.display_choice.currentIndexChanged.connect(self.refresh)
        self.time_choice.currentIndexChanged.connect(self.refresh)
        self.groups_button = QPushButton("Groepen kiezen…")
        self.groups_button.setObjectName("secondaryButton")
        self.groups_button.clicked.connect(self._choose_trend_groups)
        for widget in (self.display_choice, self.time_choice, self.groups_button):
            self.chart_filter_layout.addWidget(widget)

        self.kpi_labels = {}
        self.kpi_bar = QWidget()
        self.kpi_bar.setMinimumWidth(240)
        self.kpi_bar.setMaximumWidth(320)
        kpi_row = QVBoxLayout(self.kpi_bar)
        kpi_row.setContentsMargins(0, 0, 0, 0)
        kpi_row.setSpacing(8)
        for key, title in (("evenementen", "Evenementen"), ("aangemeld", "Aanmeldingen"),
                           ("aanwezig", "Aanwezigen"), ("noshows", "No-shows"),
                           ("opkomst_percentage", "Gem. opkomst")):
            card = QFrame()
            card.setObjectName("compactSummaryCard")
            card.setMinimumHeight(48)
            card.setMaximumHeight(58)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 6, 12, 6)
            caption = QLabel(title)
            caption.setObjectName("cardCaption")
            value = QLabel("—")
            value.setObjectName("statisticsTitle")
            value.setMinimumHeight(34)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            card_layout.addWidget(caption)
            card_layout.addStretch()
            card_layout.addWidget(value, 0, Qt.AlignmentFlag.AlignVCenter)
            self.kpi_labels[key] = value
            kpi_row.addWidget(card, 1)

        controls = QFrame()
        controls.setObjectName("toolbar")
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(14, 10, 14, 10)
        controls_layout.setSpacing(10)

        # Niet 'metric': QWidget heeft al een metric()-methode, en Qt roept die
        # tijdens het tekenen aan. Een combobox op die naam laat de applicatie
        # omvallen zodra de stylesheet opnieuw wordt toegepast.
        self.metric_choice = ScrollSafeComboBox()
        for label, value in TREND_METRICS:
            self.metric_choice.addItem(label, value)
        self.dimension = ScrollSafeComboBox()
        for label, value in TREND_EVENT_DIMENSIONS:
            self.dimension.addItem(label, value)
        for label in TREND_GROUP_DIMENSIONS:
            self.dimension.addItem(label, label)
        self.overview_period = ScrollSafeComboBox()
        for label, value in TREND_PERIODS:
            self.overview_period.addItem(label, value)
        self.overview_period.setCurrentIndex(
            max(0, self.overview_period.findData("month"))
        )
        self.overview_period.currentIndexChanged.connect(self.refresh)
        self.period = ScrollSafeComboBox()
        for label, value in TREND_PERIODS:
            self.period.addItem(label, value)
        self.period.setCurrentIndex(2)

        for caption_text, widget in (
            ("Meetwaarde:", self.metric_choice),
            ("Uitsplitsen naar:", self.dimension),
            ("Periode:", self.period),
        ):
            caption = QLabel(caption_text)
            caption.setObjectName("hintLabel")
            controls_layout.addWidget(caption)
            widget.setMinimumWidth(150)
            widget.currentIndexChanged.connect(self.refresh)
            controls_layout.addWidget(widget)
        controls_layout.addStretch()
        self.summary = QLabel("")
        self.summary.setObjectName("statusLabel")
        self.summary.setWordWrap(True)
        self.summary.setVisible(False)

        self.chart = TrendChart()
        self.chart.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Periode", "Groep", "Waarde"])
        self.table.setObjectName("dashboardTable")
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        value_header = self.table.horizontalHeader()
        value_header.setStretchLastSection(False)
        value_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        value_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        value_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setMaximumHeight(122)
        self.table.setToolTip("Dubbelklik op een periode om de onderliggende evenementen te tonen.")
        self.table.cellDoubleClicked.connect(self._drill_period)
        self.table.setVisible(False)

        self.comparison = QLabel("")
        self.comparison.setObjectName("statusLabel")
        self.comparison.setWordWrap(True)

        self.insights = QLabel("")
        self.insights.setObjectName("statusLabel")
        self.insights.setWordWrap(True)
        self.insights.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.event_table = QTableWidget(0, 6)
        self.event_table.setHorizontalHeaderLabels(
            ["Evenement", "Datum", "Type / locatie", "Aanmeldingen", "Aanwezig", "Opkomst"]
        )
        self.event_table.setObjectName("dashboardTable")
        self.event_table.verticalHeader().setVisible(False)
        self.event_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.event_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        event_header = self.event_table.horizontalHeader()
        event_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        event_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for column in (1, 3, 4, 5):
            event_header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.event_table.setMaximumHeight(145)
        self.event_table.cellDoubleClicked.connect(self._open_event_row)
        self.analysis_tabs = QTabWidget()
        self.analysis_tabs.setDocumentMode(True)

        overview_tab = QWidget()
        overview_layout = QVBoxLayout(overview_tab)
        overview_layout.setContentsMargins(10, 12, 10, 10)
        overview_body = QHBoxLayout()
        overview_body.setSpacing(14)
        overview_left = QWidget()
        overview_left_layout = QVBoxLayout(overview_left)
        overview_left_layout.setContentsMargins(0, 0, 0, 0)
        overview_left_layout.setSpacing(8)
        self.overview_summary = QLabel("")
        self.overview_summary.setObjectName("statusLabel")
        self.overview_summary.setWordWrap(True)
        overview_left_layout.addWidget(self.overview_summary)
        self.overview_chart = TrendChart()
        overview_left_layout.addWidget(self._chart_container(self.overview_chart), 1)
        overview_body.addWidget(overview_left, 3)
        overview_body.addWidget(self.kpi_bar, 1, Qt.AlignmentFlag.AlignTop)
        overview_layout.addLayout(overview_body, 1)
        self.analysis_tabs.addTab(overview_tab, "Overzicht")

        turnout_tab = QWidget()
        turnout_layout = QVBoxLayout(turnout_tab)
        turnout_layout.setContentsMargins(10, 12, 10, 10)
        controls.setVisible(False)
        turnout_layout.addWidget(controls)
        turnout_layout.addWidget(self.summary)
        turnout_layout.addWidget(self._chart_container(self.chart), 1)
        turnout_layout.addWidget(self.table)
        self.analysis_tabs.addTab(turnout_tab, "Opkomst")

        demographic_tab = QWidget()
        demographic_layout = QVBoxLayout(demographic_tab)
        demographic_layout.setContentsMargins(10, 12, 10, 10)
        demographic_controls = QFrame()
        demographic_controls.setObjectName("toolbar")
        demographic_controls_layout = QHBoxLayout(demographic_controls)
        self.demographic_metric = ScrollSafeComboBox()
        for label, value in TREND_METRICS:
            self.demographic_metric.addItem(label, value)
        self.demographic_dimension = ScrollSafeComboBox()
        self.demographic_period = ScrollSafeComboBox()
        for label, value in TREND_PERIODS:
            self.demographic_period.addItem(label, value)
        self.demographic_period.setCurrentIndex(2)
        for caption, widget in (("Meetwaarde:", self.demographic_metric),
                                ("Verdeling:", self.demographic_dimension),
                                ("Periode:", self.demographic_period)):
            label = QLabel(caption)
            label.setObjectName("hintLabel")
            demographic_controls_layout.addWidget(label)
            widget.setMinimumWidth(170)
            widget.currentIndexChanged.connect(self.refresh)
            demographic_controls_layout.addWidget(widget)
        demographic_controls_layout.addStretch()
        demographic_controls.setVisible(False)
        demographic_layout.addWidget(demographic_controls)
        self.demographic_note = QLabel("")
        self.demographic_note.setObjectName("statusLabel")
        self.demographic_note.setWordWrap(True)
        demographic_layout.addWidget(self.demographic_note)
        self.demographic_chart = TrendChart()
        demographic_layout.addWidget(self._chart_container(self.demographic_chart), 1)
        self.analysis_tabs.addTab(demographic_tab, "Demografie & opleiding")

        # Eén gedeelde, lage regel. Algemene filters blijven staan; alleen de
        # drie weergavekeuzes van het actieve analysetabblad wisselen mee.
        for widget, width, tooltip in (
            (self.range_choice, 125, "Periode"),
            (self.template_filter, 155, "Evenementtemplate"),
            (self.event_type_filter, 125, "Evenementsoort"),
            (self.location_filter, 125, "Locatie"),
            (self.event_filter, 155, "Evenement"),
            (self.participant_scope, 155, "Deelnemers"),
            (self.metric_choice, 120, "Meetwaarde"),
            (self.dimension, 125, "Uitsplitsing"),
            (self.demographic_metric, 120, "Meetwaarde"),
            (self.demographic_dimension, 135, "Verdeling"),
            (self.percentage_of_total, 165, "Percentageweergave"),
        ):
            widget.setMinimumWidth(width)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            widget.setToolTip(tooltip)
            target_layout = (self.chart_filter_layout if widget in (
                self.metric_choice, self.dimension, self.demographic_metric,
                self.demographic_dimension, self.percentage_of_total) else self.filter_bar_layout)
            target_layout.addWidget(widget)
        self.chart_filter_layout.addWidget(self.timeline_granularity)
        self.chart_filter_layout.addStretch(1)
        self.clear_filters_button.setText("Wissen")
        self.clear_filters_button.setMaximumWidth(78)
        self.filter_bar_layout.addWidget(self.clear_filters_button)

        comparison_tab = QWidget()
        comparison_layout = QVBoxLayout(comparison_tab)
        comparison_layout.setContentsMargins(10, 12, 10, 10)
        comparison_dates = QFrame()
        comparison_dates.setObjectName("toolbar")
        comparison_dates_layout = QGridLayout(comparison_dates)
        for column, (caption, widget) in enumerate((
            ("Periode A van", self.since_date), ("tot", self.until_date),
            ("Periode B van", self.compare_since), ("tot", self.compare_until),
        )):
            label = QLabel(caption)
            label.setObjectName("hintLabel")
            comparison_dates_layout.addWidget(label, 0, column)
            comparison_dates_layout.addWidget(widget, 1, column)
        comparison_layout.addWidget(comparison_dates)
        comparison_layout.addWidget(self.comparison)
        self.comparison_table = QTableWidget(0, 4)
        self.comparison_table.setHorizontalHeaderLabels(["KPI", "Periode A", "Periode B", "Verandering"])
        self.comparison_table.setObjectName("dashboardTable")
        self.comparison_table.verticalHeader().setVisible(False)
        self.comparison_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.comparison_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        comparison_layout.addWidget(self.comparison_table, 1)
        self.analysis_tabs.addTab(comparison_tab, "Vergelijken")

        events_tab = QWidget()
        events_layout = QVBoxLayout(events_tab)
        events_layout.setContentsMargins(10, 12, 10, 10)
        event_hint = QLabel("Gesorteerd op opkomst. Dubbelklik op een eigen evenement om de bestaande Statistieken te openen.")
        event_hint.setObjectName("statusLabel")
        events_layout.addWidget(event_hint)
        self.event_table.setMaximumHeight(16777215)
        events_layout.addWidget(self.event_table, 1)
        self.analysis_tabs.addTab(events_tab, "Evenementen")

        insights_tab = QWidget()
        insights_layout = QVBoxLayout(insights_tab)
        insights_layout.setContentsMargins(18, 18, 18, 18)
        insights_title = QLabel("Inzichten uit de geselecteerde gegevens")
        insights_title.setObjectName("statisticsTitle")
        insights_layout.addWidget(insights_title)
        insights_layout.addWidget(self.insights)
        insights_layout.addStretch()
        self.analysis_tabs.addTab(insights_tab, "Inzichten")
        self.analysis_tabs.currentChanged.connect(self._update_inline_filters)
        self._update_inline_filters()

        layout.addWidget(self.analysis_tabs, 1)

        self.empty_message = "Nog geen cijfers beschikbaar."
        # Widgets buiten dit paneel die bij maximaliseren mee moeten verdwijnen;
        # de pagina vult deze aan, want het paneel kent zijn omgeving niet.
        self.chrome: list = []
        self.maximised = False

    def _chart_container(self, chart: TrendChart):
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(chart, 0, 0)
        button = QPushButton("⤢")
        button.setObjectName("secondaryButton")
        button.setProperty("picker", "true")
        button.setFixedSize(38, 38)
        button.setToolTip("Deze grafiek openen op volledig scherm (F11)")
        button.clicked.connect(lambda _checked=False, source=chart: self.open_chart_window(source))
        grid.addWidget(button, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        button.raise_()
        if not hasattr(self, "expand_button"):
            self.expand_button = button
        return container

    def resizeEvent(self, event):
        """Laat grafieken, detailtabel en KPI-rail met het venster meeschalen."""
        super().resizeEvent(event)
        tab_height = self.analysis_tabs.height() if hasattr(self, "analysis_tabs") else self.height()
        usable = max(180, tab_height - 90)
        overview_height = max(220, min(520, usable - 10))
        detail_height = max(220, min(520, usable - 55))
        self.overview_chart.setMinimumHeight(overview_height)
        self.demographic_chart.setMinimumHeight(overview_height)
        self.chart.setMinimumHeight(detail_height)
        self.table.setMaximumHeight(max(64, min(122, int(usable * 0.22))))
        # De rechterkolom blijft compact, maar gebruikt op een breed scherm de
        # extra ruimte iets royaler.
        self.kpi_bar.setMaximumWidth(320 if self.width() >= 1200 else 270)

    @staticmethod
    def _dialog_combo(source: QComboBox) -> ScrollSafeComboBox:
        combo = ScrollSafeComboBox()
        for index in range(source.count()):
            combo.addItem(source.itemText(index), source.itemData(index))
        combo.setCurrentIndex(max(0, combo.findData(source.currentData())))
        combo.setEnabled(source.isEnabled())
        return combo

    @staticmethod
    def _apply_dialog_combo(target: QComboBox, source: QComboBox):
        index = target.findData(source.currentData())
        if index >= 0:
            target.setCurrentIndex(index)

    def _open_filter_dialog(self):
        """Toon algemene en tabgebonden instellingen zonder grafiekhoogte op te offeren."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Trendsfilters")
        _fit_dialog_to_screen(dialog, 560, 560, 480, 390)
        layout = QVBoxLayout(dialog)
        intro = QLabel("Deze instellingen gelden samen voor alle cijfers en grafieken in Trends.")
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        range_choice = self._dialog_combo(self.range_choice)
        event_type = self._dialog_combo(self.event_type_filter)
        template_choice = self._dialog_combo(self.template_filter)
        location = self._dialog_combo(self.location_filter)
        event_choice = self._dialog_combo(self.event_filter)
        form.addRow("Periode:", range_choice)
        form.addRow("Evenementsoort:", event_type)
        form.addRow("Template:", template_choice)
        form.addRow("Locatie:", location)
        form.addRow("Evenement:", event_choice)

        since_picker = CalendarDateInput()
        until_picker = CalendarDateInput()
        for picker, value in ((since_picker, self.since_date.date()),
                              (until_picker, self.until_date.date())):
            picker.setCalendarPopup(True)
            picker.setDisplayFormat("dd-MM-yyyy")
            picker.setDate(value)
        since_label = QLabel("Van:")
        until_label = QLabel("Tot en met:")
        form.addRow(since_label, since_picker)
        form.addRow(until_label, until_picker)

        def show_custom_dates():
            visible = str(range_choice.currentData() or "") == "custom"
            for widget in (since_label, since_picker, until_label, until_picker):
                widget.setVisible(visible)

        range_choice.currentIndexChanged.connect(show_custom_dates)
        show_custom_dates()

        tab_index = self.analysis_tabs.currentIndex()
        tab_controls = []
        if tab_index == 1:
            metric = self._dialog_combo(self.metric_choice)
            dimension = self._dialog_combo(self.dimension)
            period = self._dialog_combo(self.time_choice)
            form.addRow("Meetwaarde:", metric)
            form.addRow("Uitsplitsen naar:", dimension)
            form.addRow("Tijdseenheid:", period)
            tab_controls = [(self.metric_choice, metric), (self.dimension, dimension), (self.time_choice, period)]
        elif tab_index == 2:
            metric = self._dialog_combo(self.demographic_metric)
            dimension = self._dialog_combo(self.demographic_dimension)
            period = self._dialog_combo(self.time_choice)
            form.addRow("Meetwaarde:", metric)
            form.addRow("Verdeling:", dimension)
            form.addRow("Tijdseenheid:", period)
            tab_controls = [
                (self.demographic_metric, metric),
                (self.demographic_dimension, dimension),
                (self.time_choice, period),
            ]
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Toepassen")
        clear_button = buttons.addButton("Wissen", QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        def clear_dialog_filters():
            range_choice.setCurrentIndex(range_choice.findData("all"))
            for combo in (event_type, location, event_choice, template_choice):
                combo.setCurrentIndex(0)

        clear_button.clicked.connect(clear_dialog_filters)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if range_choice.currentData() == "custom" and since_picker.date() > until_picker.date():
            QMessageBox.information(self, "Ongeldige periode", "De begindatum moet op of vóór de einddatum liggen.")
            return
        self._updating_filters = True
        try:
            for target, source in (
                (self.range_choice, range_choice), (self.event_type_filter, event_type),
                (self.template_filter, template_choice),
                (self.location_filter, location), (self.event_filter, event_choice),
                *tab_controls,
            ):
                self._apply_dialog_combo(target, source)
            self._last_range_value = str(range_choice.currentData() or "all")
            if self._last_range_value == "custom":
                self.since_date.setDate(since_picker.date())
                self.until_date.setDate(until_picker.date())
        finally:
            self._updating_filters = False
        self.refresh()

    def _update_inline_filters(self, *_):
        if not hasattr(self, "analysis_tabs"):
            return
        tab_index = self.analysis_tabs.currentIndex()
        available = getattr(self, "_filter_availability", {})
        group_dimension = str((self.demographic_dimension if tab_index == 2 else self.dimension).currentData() or "")
        self.groups_button.setVisible(tab_index in {1, 2} and bool(group_dimension))
        selected_groups = self.group_selections.get(group_dimension)
        self.groups_button.setText("Alle groepen…" if selected_groups is None else f"{len(selected_groups)} groepen gekozen…")
        self.range_choice.setVisible(bool(available.get("period")))
        self.event_type_filter.setVisible(bool(available.get("event_type")))
        self.template_filter.setVisible(self.template_filter.count() > 1)
        self.location_filter.setVisible(bool(available.get("location")))
        self.event_filter.setVisible(bool(available.get("event")))
        self.participant_scope.setVisible(bool(available.get("introducees")))
        self.overview_period.setVisible(False)
        self.metric_choice.setVisible(tab_index == 1)
        self.dimension.setVisible(tab_index == 1 and self.dimension.count() > 1)
        self.period.setVisible(False)
        self.demographic_metric.setVisible(tab_index == 2)
        self.demographic_dimension.setVisible(
            tab_index == 2 and self.demographic_dimension.count() > 0
        )
        self.demographic_period.setVisible(False)
        self.timeline_granularity.setVisible(tab_index in {0, 1, 2})
        if tab_index == 1:
            percentage_dimension = str(self.dimension.currentData() or "")
            percentage_metric = str(self.metric_choice.currentData() or "")
        elif tab_index == 2:
            percentage_dimension = str(self.demographic_dimension.currentData() or "")
            percentage_metric = str(self.demographic_metric.currentData() or "")
        else:
            percentage_dimension = percentage_metric = ""
        self.percentage_of_total.setVisible(
            percentage_dimension in TREND_GROUP_DIMENSIONS
            and percentage_metric in {"aangemeld", "aanwezig", "noshows", "afgemeld"}
        )
        active = (
            str(self.range_choice.currentData() or "all") != "all"
            or any(combo.currentData() for combo in (
                self.event_type_filter, self.location_filter, self.event_filter, self.template_filter
            ))
        )
        self.clear_filters_button.setVisible(bool(active))

    def _participant_scope_changed(self, *_):
        if self._updating_filters:
            return
        if not bool(self.participant_scope.currentData()) and not self._regular_scope_supported:
            self.participant_scope.blockSignals(True)
            self.participant_scope.setCurrentIndex(self.participant_scope.findData(True))
            self.participant_scope.blockSignals(False)
            QMessageBox.information(
                self,
                "Reguliere deelnemers niet afzonderlijk beschikbaar",
                "Deze analyse bevat oudere geaggregeerde cijfers. Daarin is alleen het totale aantal "
                "introducees bewaard, niet hun afzonderlijke aanwezigheid of verdeling.\n\n"
                "Laad de oorspronkelijke bezoekerslijst opnieuw in om introducees betrouwbaar te kunnen uitsluiten.",
            )
            return
        self.refresh()

    def _clear_filters(self):
        self.group_selections.clear()
        self._updating_filters = True
        try:
            self.range_choice.setCurrentIndex(self.range_choice.findData("all"))
            self._last_range_value = "all"
            for combo in (self.event_type_filter, self.location_filter, self.event_filter, self.template_filter):
                combo.setCurrentIndex(0)
        finally:
            self._updating_filters = False
        self.refresh()

    def _range_changed(self, *_):
        value = str(self.range_choice.currentData() or "all")
        if self._updating_filters:
            return
        if value != "custom":
            self._last_range_value = value
            self.refresh()
            return
        if self._choose_custom_range():
            self._last_range_value = "custom"
            self.refresh()
            return
        # Annuleren verandert het actieve filter niet.
        self.range_choice.blockSignals(True)
        previous = self.range_choice.findData(self._last_range_value)
        self.range_choice.setCurrentIndex(previous if previous >= 0 else 0)
        self.range_choice.blockSignals(False)

    def _choose_custom_range(self) -> bool:
        dialog = QDialog(self)
        dialog.setWindowTitle("Zelf periode kiezen")
        dialog.setModal(True)
        dialog.setMinimumWidth(410)
        layout = QVBoxLayout(dialog)
        intro = QLabel("Kies de eerste en laatste dag die in alle Trends-onderdelen moeten meetellen.")
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        since_picker = CalendarDateInput()
        until_picker = CalendarDateInput()
        for picker in (since_picker, until_picker):
            picker.setCalendarPopup(True)
            picker.setDisplayFormat("dd-MM-yyyy")
        since_picker.setDate(self.since_date.date())
        until_picker.setDate(self.until_date.date())
        form.addRow("Van:", since_picker)
        form.addRow("Tot en met:", until_picker)
        layout.addLayout(form)
        error = QLabel("")
        error.setObjectName("statusLabel")
        error.setWordWrap(True)
        layout.addWidget(error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Periode toepassen")

        def accept_valid_range():
            if since_picker.date() > until_picker.date():
                error.setText("De begindatum moet op of vóór de einddatum liggen.")
                return
            dialog.accept()

        buttons.accepted.connect(accept_valid_range)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        for target, source in ((self.since_date, since_picker), (self.until_date, until_picker)):
            target.blockSignals(True)
            target.setDate(source.date())
            target.blockSignals(False)
        return True

    @staticmethod
    def _python_date(value: QDate) -> date:
        return date(value.year(), value.month(), value.day())

    def _manual_date_changed(self, *_):
        if not self._updating_filters:
            self.range_choice.blockSignals(True)
            self.range_choice.setCurrentIndex(self.range_choice.findData("custom"))
            self.range_choice.blockSignals(False)
            self._last_range_value = "custom"
            self.refresh()

    def _date_ranges(self):
        today = date.today()
        preset = str(self.range_choice.currentData() or "all")
        since = until = None
        if preset == "6m":
            until = today
            qdate = QDate(today.year, today.month, today.day).addMonths(-6).addDays(1)
            since = self._python_date(qdate)
        elif preset == "year":
            since, until = date(today.year, 1, 1), today
        elif preset == "quarter":
            month = ((today.month - 1) // 3) * 3 + 1
            since, until = date(today.year, month, 1), today
        elif preset == "custom":
            since, until = self._python_date(self.since_date.date()), self._python_date(self.until_date.date())
        if since and until:
            previous_since = self._python_date(self.compare_since.date()) if preset == "custom" else None
            previous_until = self._python_date(self.compare_until.date()) if preset == "custom" else None
            return since, until, previous_since, previous_until
        return None, None, None, None

    @staticmethod
    def _automatic_timeline_period(summaries, since=None, until=None) -> str:
        """Kies een leesbare tijdlijn die binnen de analyseperiode verloop houdt."""
        dates = sorted({
            parsed for item in summaries
            if (parsed := parse_date(str(item.get("date", "") or ""))) is not None
        })
        if len(dates) < 2:
            return "event"
        start = since or dates[0]
        end = until or dates[-1]
        days = max(0, (end - start).days)
        if days <= 45:
            preferred = "event"
        elif days <= 550:
            preferred = "month"
        elif days <= 1460:
            preferred = "quarter"
        else:
            preferred = "year"

        def bucket_count(period):
            if period == "year":
                return len({value.year for value in dates})
            if period == "quarter":
                return len({(value.year, (value.month - 1) // 3) for value in dates})
            if period == "month":
                return len({(value.year, value.month) for value in dates})
            return len(dates)

        fallbacks = {
            "year": ("year", "quarter", "month", "event"),
            "quarter": ("quarter", "month", "event"),
            "month": ("month", "event"),
            "event": ("event",),
        }
        return next(
            (period for period in fallbacks[preferred] if bucket_count(period) >= 2),
            "event",
        )

    def _sync_filter_options(self, summaries):
        self._updating_filters = True
        try:
            option_counts = {}
            for combo, label, key in ((self.event_type_filter, "Alle typen", "event_type"),
                                      (self.template_filter, "Alle templates", "template_id"),
                                      (self.location_filter, "Alle locaties", "location"),
                                      (self.event_filter, "Alle evenementen", "id")):
                current = str(combo.currentData() or "")
                combo.blockSignals(True)
                combo.clear()
                combo.addItem(label, "")
                if key == "id":
                    unique_events = {
                        str(item.get("id", "") or item.get("name", "")): str(
                            item.get("name", "") or "Onbenoemd"
                        )
                        for item in summaries
                        if str(item.get("id", "") or item.get("name", "")).strip()
                    }
                    values = sorted(
                        ((name, event_id) for event_id, name in unique_events.items()),
                        key=lambda item: normalize(item[0]),
                    )
                elif key == "template_id":
                    names = {str(item["template_id"]): str(item.get("template_name") or "Template")
                             for item in summaries if item.get("template_id")}
                    values = sorted(((name, ident) for ident, name in names.items()), key=lambda item: normalize(item[0]))
                else:
                    values = [(value, value) for value in sorted(
                        {str(item.get(key, "") or "") for item in summaries if str(item.get(key, "") or "").strip() not in {"", "Onbekend"}},
                        key=normalize)]
                for text, value in values:
                    combo.addItem(text, value)
                meaningful = len(values) > 1
                if key == "template_id":
                    meaningful = bool(values)  # One template can coexist with unlinked events.
                combo.setCurrentIndex(max(0, combo.findData(current)) if meaningful else 0)
                combo.setEnabled(meaningful)
                combo.blockSignals(False)
                option_counts[key] = len(values)

            dated_events = {
                parsed for item in summaries
                if (parsed := parse_date(str(item.get("date", "") or ""))) is not None
            }
            period_available = len(dated_events) > 1
            if not period_available:
                self.range_choice.blockSignals(True)
                self.range_choice.setCurrentIndex(self.range_choice.findData("all"))
                self.range_choice.blockSignals(False)
                self._last_range_value = "all"
            self._filter_availability = {
                "period": period_available,
                "event_type": option_counts.get("event_type", 0) > 1,
                "location": option_counts.get("location", 0) > 1,
                "event": option_counts.get("id", 0) > 1,
            }

            allowed = set(trend_available_dimensions(summaries))
            current_dimension = str(self.dimension.currentData() or "")
            self.dimension.blockSignals(True)
            self.dimension.clear()
            for label, value in TREND_EVENT_DIMENSIONS:
                if value in allowed:
                    self.dimension.addItem(label, value)
            for label in TREND_GROUP_DIMENSIONS:
                if label in allowed:
                    self.dimension.addItem(label, label)
            self.dimension.setCurrentIndex(max(0, self.dimension.findData(current_dimension)))
            self.dimension.blockSignals(False)

            current_demographic = str(self.demographic_dimension.currentData() or "")
            self.demographic_dimension.blockSignals(True)
            self.demographic_dimension.clear()
            for label in TREND_GROUP_DIMENSIONS:
                if label in allowed:
                    self.demographic_dimension.addItem(label, label)
            self.demographic_dimension.setCurrentIndex(max(0, self.demographic_dimension.findData(current_demographic)))
            self.demographic_dimension.blockSignals(False)
            demographic_index = self.analysis_tabs.indexOf(self.demographic_chart.parentWidget())
            if demographic_index < 0:
                demographic_index = 2
            self.analysis_tabs.setTabEnabled(demographic_index, self.demographic_dimension.count() > 0)
        finally:
            self._updating_filters = False

    def _open_event_row(self, row, _column):
        item = self.event_table.item(row, 0)
        event_id = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        if event_id and self.open_event_callback:
            self.open_event_callback(event_id)

    def _drill_period(self, row, _column):
        item = self.table.item(row, 0)
        wanted = set(item.data(Qt.ItemDataRole.UserRole) or []) if item else set()
        if not wanted:
            return
        for event_row in range(self.event_table.rowCount()):
            event_item = self.event_table.item(event_row, 0)
            self.event_table.setRowHidden(
                event_row, not event_item or str(event_item.data(Qt.ItemDataRole.UserRole) or "") not in wanted
            )
        self.summary.setText(
            f"Drill-down: {item.text()} · {len(wanted)} onderliggende evenement(en). "
            "Dubbelklik op een evenement om de bestaande Statistieken te openen."
        )

    def open_chart_window(self, source_chart=None):
        tab = self.analysis_tabs.currentIndex()
        source_chart = source_chart or (
            self.overview_chart if tab == 0 else self.demographic_chart if tab == 2 else self.chart
        )
        dialog = TrendChartDialog(source_chart.series, source_chart.dark, self)
        dialog.showMaximized()
        dialog.exec()

    def set_maximised(self, maximised: bool):
        """Compatibiliteitsingang voor bestaande sneltoetsen."""
        if maximised:
            self.open_chart_window()

    def current_filters(self) -> dict:
        """De filters zoals ze nu op het scherm staan.

        De Report Builder begint met precies deze selectie, zodat het rapport
        gaat over wat de gebruiker op dat moment bekijkt.
        """
        since, until, _vorige_since, _vorige_until = self._date_ranges()
        tab_index = self.analysis_tabs.currentIndex()
        active_series = (self.demographic_chart.series if tab_index == 2 else
                         self.overview_chart.series if tab_index == 0 else self.chart.series)
        return {
            "since": since, "until": until,
            "template_id": str(self.template_filter.currentData() or ""),
            "template_name": self.template_filter.currentText() if self.template_filter.currentData() else "",
            "event_type": str(self.event_type_filter.currentData() or ""),
            "location": str(self.location_filter.currentData() or ""),
            "event_id": str(self.event_filter.currentData() or ""),
            "periode": str(self.period.currentData() or "event"),
            "weergave": str(self.display_choice.currentData()),
            "group_selections": deepcopy(self.group_selections),
            "analysis_metric": active_series.get("metric", "opkomst_percentage"),
            "analysis_dimension": active_series.get("dimension", ""),
            "include_introducees": bool(self.participant_scope.currentData()),
            "percentage_of_total": self.percentage_of_total.isChecked(),
        }

    def _choose_trend_groups(self):
        demographic = self.analysis_tabs.currentIndex() == 2
        dimension = str((self.demographic_dimension if demographic else self.dimension).currentData() or "")
        if not dimension:
            return
        rows = filter_trend_summaries(trend_participant_scope(self.provider() or [], bool(self.participant_scope.currentData())), self.current_filters())
        groups = build_trend_series(rows, "aangemeld", dimension, "total").get("groups", [])
        dialog = TrendGroupDialog(self, dimension, groups, self.group_selections.get(dimension))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.selected()
            if set(selected) == set(groups):
                self.group_selections.pop(dimension, None)
            else:
                self.group_selections[dimension] = selected
            self.refresh()

    def current_series(self) -> dict:
        return self.chart.series

    def value_text(self, value: float) -> str:
        metric = self.chart.series.get("display_metric", self.chart.series.get("metric"))
        return f"{value:g}%" if metric in {"opkomst_percentage", "noshow_percentage", "aandeel_percentage"} else f"{value:g}"

    def refresh(self, *_):
        summaries = self.provider() or []
        if self._updating_filters:
            return
        has_introducees = any(
            int(item.get("statistiek", {}).get("introducees", 0) or 0) > 0
            for item in summaries
        )
        was_supported = self._regular_scope_supported
        regular_supported = trend_regular_scope_available(summaries)
        self._regular_scope_supported = regular_supported
        if has_introducees and regular_supported and not was_supported:
            self.participant_scope.blockSignals(True)
            self.participant_scope.setCurrentIndex(self.participant_scope.findData(False))
            self.participant_scope.blockSignals(False)
        if has_introducees and not regular_supported and not bool(self.participant_scope.currentData()):
            self.participant_scope.blockSignals(True)
            self.participant_scope.setCurrentIndex(self.participant_scope.findData(True))
            self.participant_scope.blockSignals(False)
        include_introducees = bool(self.participant_scope.currentData())
        self.participant_scope.setEnabled(True)
        self.participant_scope.setToolTip(
            "Oudere cijfers bevatten geen betrouwbare scheiding tussen reguliere deelnemers en introducees."
            if has_introducees and not regular_supported else
            "Bepaal of introducees in aantallen, percentages en verdelingen meetellen."
        )
        summaries = trend_participant_scope(summaries, include_introducees)
        self._sync_filter_options(summaries)
        self._filter_availability["introducees"] = has_introducees
        self._update_inline_filters()
        since, until, previous_since, previous_until = self._date_ranges()
        filters = {
            "since": since, "until": until,
            "template_id": str(self.template_filter.currentData() or ""),
            "event_type": str(self.event_type_filter.currentData() or ""),
            "location": str(self.location_filter.currentData() or ""),
            "event_id": str(self.event_filter.currentData() or ""),
        }
        base_filters = dict(filters)
        base_filters["since"] = base_filters["until"] = None
        comparable = filter_trend_summaries(summaries, base_filters)
        filtered = filter_trend_summaries(comparable, filters)
        timeline_period = str(self.time_choice.currentData() or "auto")
        if timeline_period == "auto":
            timeline_period = self._automatic_timeline_period(filtered, since, until)
        statistics = self.display_choice.currentData() == "statistieken"
        self.time_choice.setEnabled(not statistics)
        if statistics:
            timeline_period = "total"
        timeline_labels = {
            "event": "per evenement", "month": "per maand",
            "quarter": "per kwartaal", "year": "per jaar",
            "total": "hele selectie",
        }
        self.timeline_granularity.setText(
            f"Tijdlijn: {timeline_labels[timeline_period]}"
        )
        for combo in (self.overview_period, self.period, self.demographic_period):
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(timeline_period)))
            combo.blockSignals(False)
        overview_series = build_trend_series(
            filtered, metric="opkomst_percentage", dimension="",
            period=timeline_period,
        )
        self.overview_chart.set_series(overview_series)
        series = build_trend_series(
            filtered,
            metric=str(self.metric_choice.currentData() or "aangemeld"),
            dimension=str(self.dimension.currentData() or ""),
            period=timeline_period,
            percentage_of_total=self.percentage_of_total.isChecked(),
        )
        series = select_series_groups(series, self.group_selections)
        self.chart.set_series(series)

        demographic_dimension = str(self.demographic_dimension.currentData() or "")
        demographic_series = build_trend_series(
            filtered,
            metric=str(self.demographic_metric.currentData() or "aangemeld"),
            dimension=demographic_dimension,
            period=timeline_period,
            percentage_of_total=self.percentage_of_total.isChecked(),
        ) if demographic_dimension else {"groups": [], "points": [], "metric": "aangemeld"}
        demographic_series = select_series_groups(demographic_series, self.group_selections)
        self.demographic_chart.set_series(demographic_series)
        self.demographic_note.setText(
            describe_trend_change(demographic_series)
            if demographic_dimension else
            "Deze werkruimte verschijnt zodra opleiding, profiel, geslacht of leeftijdsgroep in de brondata aanwezig is."
        )

        rows = [
            (
                point["label"], group,
                (f"{value:g}% ({float(point.get('raw_values', {}).get(group, 0) or 0):g})"
                 if series.get("percentage_of_total") else self.value_text(value)),
            )
            for point in series["points"] for group, value in point["values"].items()
        ]
        self.table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                point = series["points"][row_index // max(1, len(series["groups"]))]
                item.setData(Qt.ItemDataRole.UserRole, point.get("event_ids", []))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row_index, column, item)

        kpis = trend_overview_kpis(filtered)
        for key, label in self.kpi_labels.items():
            value = kpis[key]
            label.setText(f"{value:g}%" if key.endswith("percentage") else f"{value:g}")
        self.overview_summary.setText(
            f"{kpis['evenementen']} evenement(en) · {kpis['aanwezig']} van {kpis['aangemeld']} aanmeldingen aanwezig · "
            f"{kpis['noshows']} no-show(s). De tijdlijn toont het gewogen opkomstpercentage {timeline_labels[timeline_period]}."
            if filtered else "Geen historische gegevens binnen de gekozen filters."
        )

        ranked = ranked_trend_events(filtered)
        self.event_table.setRowCount(len(ranked))
        for row_index, event in enumerate(ranked):
            stats = event.get("statistiek", {})
            values = (event.get("name", ""), event.get("date", ""),
                      " · ".join(filter(None, [event.get("event_type", ""), event.get("location", "")])),
                      stats.get("aangemeld", 0), stats.get("aanwezig", 0), f"{event['turnout']:g}%")
            for column, text in enumerate(values):
                item = QTableWidgetItem(str(text or ""))
                item.setData(Qt.ItemDataRole.UserRole, event.get("id", ""))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.event_table.setItem(row_index, column, item)
            self.event_table.setRowHidden(row_index, False)

        insights = generate_trend_insights(filtered)
        self.insights.setText(
            "Inzichten\n" + "\n".join(f"• {item['title']} — {item['detail']}" for item in insights)
            if insights else "Inzichten\nNog te weinig vergelijkbare gegevens voor een betrouwbaar inzicht."
        )
        if since and until:
            comparison = compare_trend_periods(comparable, since, until, previous_since, previous_until)
            change = comparison["changes"]
            attendance = change["aanwezig"]
            turnout = change["opkomst_percentage"]
            attendance_pct = "n.v.t." if attendance["percentage"] is None else f"{attendance['percentage']:+g}%"
            self.comparison.setText(
                f"Periodevergelijking · aanwezigen {attendance['absolute']:+g} ({attendance_pct}) · "
                f"opkomst {turnout['percentage_points']:+g} procentpunt."
            )
            labels = {
                "evenementen": "Evenementen", "aangemeld": "Aanmeldingen", "aanwezig": "Aanwezigen",
                "noshows": "No-shows", "opkomst_percentage": "Opkomst", "noshow_percentage": "No-showpercentage",
            }
            self.comparison_table.setRowCount(len(labels))
            for row_index, (key, label) in enumerate(labels.items()):
                current, previous, delta = comparison["current"][key], comparison["previous"][key], comparison["changes"][key]
                percentage_metric = key.endswith("percentage")
                suffix = "%" if percentage_metric else ""
                if percentage_metric:
                    change_text = f"{delta['percentage_points']:+g} procentpunt"
                else:
                    relative = "n.v.t." if delta["percentage"] is None else f"{delta['percentage']:+g}%"
                    change_text = f"{delta['absolute']:+g} ({relative})"
                for column, text in enumerate((label, f"{current:g}{suffix}", f"{previous:g}{suffix}", change_text)):
                    item = QTableWidgetItem(text)
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    self.comparison_table.setItem(row_index, column, item)
        else:
            self.comparison.setText("Kies een periode om deze met de direct voorafgaande, even lange periode te vergelijken.")
            self.comparison_table.setRowCount(0)

        if not summaries:
            self.summary.setText(self.empty_message)
            return
        if not filtered:
            self.summary.setText("Geen evenementen voldoen aan de gecombineerde filters.")
            return
        parts = [f"{series['events']} evenement(en)"]
        if len(series["groups"]) > 1:
            biggest = max(trend_series_totals(series), key=lambda item: item[1], default=None)
            if biggest:
                parts.append(f"grootste groep: {biggest[0]} ({self.value_text(biggest[1])})")
        parts.append(describe_trend_change(series))
        if series.get("incomplete"):
            parts.append(
                "Let op: voor een deel van de evenementen is de aanwezigheid per groep niet "
                "vastgelegd; die tellen niet mee."
            )
        self.summary.setText("  ·  ".join(parts))
