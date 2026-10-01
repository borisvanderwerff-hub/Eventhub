from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date, datetime, timedelta
from html import escape
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import tempfile
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PySide6.QtCore import QEvent, QItemSelectionModel, QMarginsF, QSettings, QSize, QStandardPaths, Qt, QTimer, QUrl, QUrlQuery
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QDesktopServices,
    QFont,
    QIcon,
    QPageLayout,
    QPageSize,
    QPainter,
    QPixmap,
    QRegion,
    QTextDocument,
    QTransform,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QSystemTrayIcon,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from emt_documents import export_evaluation, export_fivewh
from emt_history import (snapshot_for_event, historical_scope, bucket_value,
                         distribution as historical_distribution, cross_table as historical_crosstab,
                         export_dimensions as historical_export_dimensions)
from emt_event_templates import template_event_data, event_from_template
from emt_event_templates_ui import TemplateEditor, TemplateManager, LinkEventsDialog
from emt_models import (
    DEFAULT_PROFILE,
    DEFAULT_TASK_TEMPLATES,
    EVENT_STATUSES,
    EVENT_TYPES,
    empty_event,
    event_tasks,
    parse_date,
    prepare_template,
    template_scope_text,
    prepare_event,
    prepare_task,
    task_allowed_for_event_type,
    tasks_from_templates,
    task_due_date,
    task_notifications,
    task_state,
    task_timing_text,
)
from emt_rudder import (
    RUDDER_EVENTS_OVERVIEW_URL,
    canonical_rudder_url,
    human_sync_time,
    is_rudder_event_linked,
    matching_eventhub_template,
    rudder_eventhub_updates,
    rudder_export_package,
    rudder_id_from_filename,
    sanitize_rudder_event_payload,
)

from bezoekerslijst_core import (
    AANWEZIG,
    AFGEMELD,
    AFWEZIG,
    ATTENDANCE_LABELS,
    ATTENDANCE_STATUSES,
    CALLBACK_DONE_STATUSES,
    CALLBACK_STATUSES,
    EVENT_NAME_DATE_SUFFIX,
    ONBEKEND,
    STRING_FIELDS,
    apply_attendance_conflicts,
    attendance_counts,
    attendance_map,
    attendance_status,
    callback_is_done,
    callback_status,
    clear_absence_for_events,
    common_event_name,
    detach_event_from_records,
    distinctive_labels,
    event_base_name,
    export_participant_template,
    export_statistics_workbook,
    export_workbook,
    has_status_in_scope,
    INSCHRIJVING,
    OVERGESLAGEN,
    absorb_duplicate,
    import_registration_files,
    include_again,
    is_introducee,
    is_cancelled,
    is_skipped,
    is_no_show,
    is_present,
    is_present_in_scope,
    matches_event_filter,
    merge_duplicate_registrations,
    merge_event_into,
    normalize,
    primary_visitor_name,
    record_events,
    registration_lookup,
    registrations,
    rename_attendance_event,
    repair_orphan_attendance,
    richest_record,
    set_attendance,
    skip_reason,
    turnout_percentage,
    visitor_type,
)
from emt_report_ui import ReportBuilderDialog
from emt_education import (
    collapse_columns as education_collapse,
    crosstab as education_crosstab,
    education_level,
    profile_label,
)
from emt_live_manual import manual_html
from emt_retention import (
    RETENTION_DEFAULT_DAYS,
    RETENTION_WARNING_DAYS,
    apply_retention_cleanup,
    clamp_retention_days,
    has_work,
    plan_retention_cleanup,
    retention_notifications,
    scrub_payload,
)
from emt_trends import (
    age_group as trend_age_group,
    analysis_file_name,
    analysis_payload,
    collect_summaries as collect_trend_summaries,
    participant_scope as trend_participant_scope,
    read_analysis,
    read_bundle as read_trend_bundle,
    summaries_from_records as trend_summaries_from_records,
)
from theme.styles import build_stylesheet
# De schermonderdelen staan in eigen modules (emt_widgets, emt_dialogs, ...).
# Ze worden hier opnieuw
# beschikbaar gesteld, zodat bestaande code en tests ze via bezoekerslijst_app
# kunnen blijven gebruiken.
from emt_base import (  # noqa: F401
    APP_DATA_ORGANISATION,
    APP_ICON_PATH,
    APP_NAME,
    APP_VERSION,
    HEADER_WAVE_PATH,
    LOGO_PATH,
    NEON_WAVES_PATH,
    SETTINGS_ICON_PATH,
    SIDEBAR_ICON_DIR,
    application_data_root,
    bundled_resource,
    documents_directory,
    event_activity_line,
    event_end_moment,
    event_has_passed,
    event_last_seen,
    event_last_touched,
    event_recency_key,
    exports_directory,
    parse_timestamp,
    program_directory,
    projects_directory,
)
from emt_widgets import (  # noqa: F401
    EventCard,
    EventOverviewCard,
    EventPickerButton,
    EventPickerDialog,
    FitWidthScrollArea,
    NeonEdgeOverlay,
    ScrollSafeComboBox,
    StartupSplash,
    _center_on_screen_near,
    _fit_dialog_to_screen,
    _make_button_compact,
    _picker_button,
    _picker_dialog,
    _style_calendar,
    valid_time_text,
    with_date_picker,
    with_time_picker,
)
from emt_whatsapp_ui import (  # noqa: F401
    CALLBACK_STATUS_COLOURS,
    WHATSAPP_DEFAULT_TEMPLATE,
    WHATSAPP_LEGACY_SIGNATURE_SUFFIXES,
    WHATSAPP_PLACEHOLDER_HINT,
    WHATSAPP_STATUSES,
    WHATSAPP_TEMPLATES_SETTING,
    WHATSAPP_TEMPLATE_NAME_MAX,
    WHATSAPP_TEMPLATE_PICKER_ROWS,
    WhatsAppQueueDialog,
    WhatsAppTemplatesDialog,
    _profile_signature,
    _whatsapp_phone,
    callback_status_colour,
    callback_status_icon,
    default_whatsapp_templates,
    load_whatsapp_templates,
    normalize_whatsapp_templates,
    save_whatsapp_templates,
    whatsapp_event_name,
)
from emt_dialogs import (  # noqa: F401
    AUTOMATIC_STATUS,
    ApplicationSettingsDialog,
    EVALUATION_TARGET_GROUPS,
    EvaluationDialog,
    EventDialog,
    FIVEWH_FIELDS,
    FiveWhDialog,
    NewEventSourceDialog,
    NewProjectDialog,
    ProfileDetailsDialog,
    ProfileDialog,
    TaskDialog,
    _scroll_form_page,
)
from emt_live_ui import (  # noqa: F401
    LiveCheckinDialog,
    LiveSessionSetupDialog,
    RudderAttendanceService,
    RudderLocalBridge,
    _AttendanceRequest,
    apply_live_attendance,
)
from emt_tutorial import (  # noqa: F401
    TutorialOverlay,
)
from emt_trends_panel import (  # noqa: F401
    CrosstabHeatmap,
    STATISTICS_CHART_TYPES,
    StatisticsChart,
    TrendChart,
    TrendChartDialog,
    TrendPanel,
)


from emt_event_board import EventBoardMixin, event_name_with_date

FILE_FILTER = "EventHub-bestand (*.bvp)"
EXCEL_FILTER = "Excel-bestanden (*.xlsx *.xlsm *.xls)"


SIDEBAR_ICON_PATHS = {
    "events": SIDEBAR_ICON_DIR / "evenementen.png",
    "tasks": SIDEBAR_ICON_DIR / "taken.png",
    "event_control": SIDEBAR_ICON_DIR / "event_control.png",
    # Nog geen eigen asset; valt terug op een Qt-standaardicoon.
    "trends": SIDEBAR_ICON_DIR / "trends.png",
    "callbacks": SIDEBAR_ICON_DIR / "nazorg.png",
    "file": SIDEBAR_ICON_DIR / "bestanden.png",
    "profile": SIDEBAR_ICON_DIR / "profiel.png",
    "help": SIDEBAR_ICON_DIR / "help.png",
    "settings": SIDEBAR_ICON_DIR / "instellingen.png",
}
TEMPLATE_DIR = Path(__file__).with_name("templates")
FIVEWH_TEMPLATE = TEMPLATE_DIR / "5WH - Leeg.docx"
EVALUATION_TEMPLATE = TEMPLATE_DIR / "Evaluatieformulier Blanco.docx"
PARTICIPANT_TEMPLATE = TEMPLATE_DIR / "Bezoekerslijst (DCPL) - Leeg.xlsx"
MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024


def _centered_sidebar_icon(path: Path, fallback: QIcon, glyph_size: int = 32) -> QIcon:
    """Crop transparent margins and provide sharp, centred high-DPI icon variants."""
    if not path or not path.exists():
        return fallback
    source = QPixmap(str(path))
    if source.isNull():
        return fallback
    bounds = QRegion(source.mask()).boundingRect()
    if bounds.isEmpty():
        bounds = source.rect()
    cropped = source.copy(bounds)
    canvas_size = 44
    icon = QIcon()
    # One 44 px bitmap becomes visibly soft on scaled Windows displays. Supplying
    # several device-pixel variants preserves the same layout and sharp edges.
    for scale in (1, 2, 3):
        pixel_canvas_size = canvas_size * scale
        pixel_glyph_size = glyph_size * scale
        glyph = cropped.scaled(
            pixel_glyph_size,
            pixel_glyph_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        canvas = QPixmap(pixel_canvas_size, pixel_canvas_size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawPixmap(
            (pixel_canvas_size - glyph.width()) // 2,
            (pixel_canvas_size - glyph.height()) // 2,
            glyph,
        )
        painter.end()
        canvas.setDevicePixelRatio(scale)
        icon.addPixmap(canvas, QIcon.Mode.Normal, QIcon.State.Off)
    return icon




class ArtworkHeader(QFrame):
    """Header met één golfasset, gespiegeld aan beide uiteinden."""

    def __init__(self, image_path: Path, parent=None):
        super().__init__(parent)
        self._pixmap = QPixmap(str(image_path)) if image_path.exists() else QPixmap()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setOpacity(0.34)
        target_height = max(1, self.height())
        scaled = self._pixmap.scaledToHeight(
            target_height, Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(0, 0, scaled)
        mirrored = scaled.transformed(QTransform().scale(-1, 1))
        painter.drawPixmap(max(0, self.width() - mirrored.width()), 0, mirrored)


FIELD_LABELS = {
    "Evenement": "Evenement", "Identifier": "Identifier", "Voornaam": "Voornaam",
    "Tussenvoegsel": "Tussenvoegsel", "Achternaam": "Achternaam", "Email": "E-mail",
    "Telefoonnummer": "Telefoonnummer", "Geboortedatum": "Geboortedatum",
    "Geboorteplaats": "Geboorteplaats", "Geslacht": "Geslacht", "Opleiding": "Opleidingsniveau",
    "Profiel": "Profiel / opleidingsrichting", "Type": "Type",
    "Aanwezigheid": "Aanwezigheid (bron)", "Gebruik": "Gebruik",
    "Bezoekerstype": "Type bezoeker", "IntroduceeVan": "Introducé van",
    "Inschrijving": "Inschrijving",
}

ALL_VISITOR_FIELDS = [
    "Evenement", "Bezoekerstype", "IntroduceeVan", "Achternaam", "Tussenvoegsel", "Voornaam", "Geboortedatum",
    "Geboorteplaats", "Telefoonnummer", "Email", "Opleiding", "Profiel", "Geslacht",
    "Identifier", "Type", "Aanwezigheid", "Gebruik", "Inschrijving",
]

VIEW_LABELS = {
    "participants": "Deelnemers",
    "callbacks": "After sales",
    "presence": "Presentie",
}


# Vaste volgorde van de leeftijdsgroepen: op het scherm en in de export
# dezelfde, en oplopend in plaats van op aantal.
AGE_GROUPS = ["Jonger dan 18", "18–20", "21–24", "25–29", "30–39", "40 en ouder", "Onbekend"]

CROSSTAB_VIEWS = [
    ("Grafiek", "grafiek"),
    ("Tabel", "tabel"),
]
CROSSTAB_VALUES = [
    ("Aantallen", "aantallen"),
    ("Percentage per niveau", "percentage"),
]
# Boven dit aantal profielen wordt de staart gebundeld tot een kolom Overig.
# Met achtentwintig kolommen naast elkaar is het raster onleesbaar.
CROSSTAB_COLUMN_LIMIT = 8
_NO_HISTORICAL_CROSSTAB = object()

STATISTICS_CHART_DEFAULTS = {
    "education": "horizontal",
    "profile": "horizontal",
    "gender": "donut",
    "age": "vertical",
    "listing": "donut",
}

EVENT_SORT_MODES = [
    ("Slim: eerst wat komt", "smart"),
    ("Datum — oudste eerst", "date_asc"),
    ("Datum — nieuwste eerst", "date_desc"),
    ("Naam A–Z", "name"),
]

STATISTICS_PRESENCE_FILTERS = [
    ("Alle bezoekers", "all"),
    ("Alleen aanwezig geweest", AANWEZIG),
    ("Alleen no-shows (niet gekomen)", AFWEZIG),
    ("Alleen afgemeld", AFGEMELD),
    ("Alleen onbekend", ONBEKEND),
]

DEFAULT_VISIBLE_FIELDS_BY_VIEW = {
    "participants": [
        "Evenement", "Bezoekerstype", "Achternaam", "Tussenvoegsel", "Voornaam", "Geboortedatum",
        "Geboorteplaats", "Telefoonnummer", "Opleiding", "Profiel",
    ],
    "callbacks": [
        "Evenement", "Voornaam", "Tussenvoegsel", "Achternaam", "Telefoonnummer",
        "Opleiding", "Profiel",
    ],
    "presence": [
        "Voornaam", "Tussenvoegsel", "Achternaam", "Geboortedatum", "Geboorteplaats",
    ],
}

EDITABLE_VISITOR_FIELDS = {
    "Evenement", "Voornaam", "Tussenvoegsel", "Achternaam", "Telefoonnummer",
    "Geboortedatum", "Geboorteplaats", "Opleiding", "Profiel", "Geslacht",
}

UPDATE_LOG_HTML = """
<h2>Nieuw in EventHub 0.2.1 Beta</h2>
<ul>
  <li><b>WhatsApp-sjablonen:</b> beheer via Instellingen een eigen lijst met berichten en kies er één in de WhatsApp-wachtrij.</li>
  <li><b>Contactstatus in kleur:</b> After sales toont per kandidaat een gekleurde stip: groen afgehandeld, oranje opnieuw proberen, rood niet meer benaderen, grijs nog bellen.</li>
  <li><b>Opgelost:</b> de datum van het evenement stond twee keer in een WhatsApp-bericht.</li>
  <li><b>Aanmeldingen in het evenementkeuzevenster:</b> bij After sales, Event Control en Ander evenement toont elke kaart hoeveel aanmeldingen er zijn, en hoeveel daarvan introducé.</li>
  <li><b>Kalender in een eigen venster:</b> datum- en tijdkeuze openen als klein venster midden in beeld, met Vandaag, Leegmaken en Nederlandse dagnamen, en vallen niet meer buiten het scherm.</li>
  <li><b>Opgelost:</b> het kandidaatpaneel in After sales viel op kleine of geschaalde schermen deels weg. Velden blijven nu leesbaar, de kalenderknop blijft in beeld en het paneel scrolt als de ruimte op is.</li>
  <li><b>Rondleiding bijgewerkt:</b> templatebeheer en installatie van de browserextensie komen nu aan bod, met aparte uitleg voor Trends en exporteren.</li>
  <li><b>Browserextensie installeren:</b> de installatiehulp staat nu bij Algemene instellingen.</li>
  <li><b>Kleiner installatiepakket:</b> onnodige testonderdelen en dubbele browseronderdelen worden niet meer meegeleverd.</li>
</ul>
<h3>Eerder in 0.2.0 Beta</h3>
<ul>
  <li><b>EventControl veiliger:</b> livesessies, dashboards en incheckpunten blijven gekoppeld aan het gekozen evenement.</li>
  <li><b>Aanwezigheid afronden:</b> EventHub toont vooraf wat er met nog onbeoordeelde deelnemers gebeurt.</li>
  <li><b>Compactere livesessie:</b> de actuele sessiestatus en het dashboard staan voortaan bij elkaar.</li>
</ul>
"""


def empty_record() -> dict:
    record = {field: "" for field in STRING_FIELDS}
    record.update({
        "_id": uuid.uuid4().hex,
        "Teruggebeld": False,
        "Terugbelstatus": "Nog bellen",
        "LaatsteContact": "",
        "TerugbellenOp": "",
        "Opmerkingen": "",
        "WhatsAppStatus": "Nog te sturen",
        "WhatsAppGeopendOp": "",
        "WhatsAppVerzondenOp": "",
        # Via welke aanmeldpagina deze deelnemer binnenkwam; gevuld zodra
        # evenementen worden samengevoegd.
        INSCHRIJVING: "",
        # Reden waarom deze regel nergens meer meetelt; leeg is gewoon meetellen.
        OVERGESLAGEN: "",
        # Aanwezigheid per evenementnaam; zie attendance_map() voor de migratie
        # van de losse boolean uit bestandsversie 10 en ouder.
        "Aanwezig": {},
    })
    return record


def prepare_record(source: dict) -> dict:
    record = empty_record()
    for field in STRING_FIELDS:
        record[field] = str(source.get(field, "") or "").strip()
    record["_id"] = str(source.get("_id") or uuid.uuid4().hex)
    record["Terugbelstatus"] = callback_status(source)
    record["Teruggebeld"] = record["Terugbelstatus"] in CALLBACK_DONE_STATUSES
    record["LaatsteContact"] = str(source.get("LaatsteContact", "") or "").strip()
    record["TerugbellenOp"] = str(source.get("TerugbellenOp", "") or "").strip()
    record["Opmerkingen"] = str(source.get("Opmerkingen", "") or "")
    whatsapp_status = str(source.get("WhatsAppStatus", "Nog te sturen") or "Nog te sturen").strip()
    record["WhatsAppStatus"] = whatsapp_status if whatsapp_status in WHATSAPP_STATUSES else "Nog te sturen"
    record["WhatsAppGeopendOp"] = str(source.get("WhatsAppGeopendOp", "") or "").strip()
    record["WhatsAppVerzondenOp"] = str(source.get("WhatsAppVerzondenOp", "") or "").strip()
    record[INSCHRIJVING] = str(source.get(INSCHRIJVING, "") or "").strip()
    record[OVERGESLAGEN] = str(source.get(OVERGESLAGEN, "") or "").strip()
    # attendance_map() leest zowel het oude boolean-formaat als de dict en
    # levert altijd een dict; hiermee migreert een bestaand dossier bij openen.
    # De evenementnamen komen uit het al opgeschoonde record, niet uit de bron.
    record["Aanwezig"] = attendance_map({
        "Aanwezig": source.get("Aanwezig", False),
        "Evenement": record["Evenement"],
    })
    return record


class StatisticsCard(QFrame):
    def __init__(self, title: str, description: str, chart_type: str = "horizontal", change_callback=None, parent=None):
        super().__init__(parent)
        self.setObjectName("statisticsCard")
        self.change_callback = change_callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)
        heading_row = QHBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("statisticsTitle")
        self.chart_type_picker = ScrollSafeComboBox()
        for label, value in STATISTICS_CHART_TYPES:
            self.chart_type_picker.addItem(label, value)
        selected = self.chart_type_picker.findData(chart_type)
        self.chart_type_picker.setCurrentIndex(selected if selected >= 0 else 0)
        self.chart_type_picker.setToolTip("Kies de grafieksoort voor alleen deze statistiek.")
        heading_row.addWidget(heading, 1)
        heading_row.addWidget(self.chart_type_picker)
        caption = QLabel(description)
        caption.setObjectName("statisticsCaption")
        caption.setWordWrap(True)
        self.chart = StatisticsChart()
        self.chart.set_chart_type(str(self.chart_type_picker.currentData() or "horizontal"))
        self.chart_type_picker.currentIndexChanged.connect(self._chart_type_changed)
        layout.addLayout(heading_row)
        layout.addWidget(caption)
        layout.addWidget(self.chart, 1)

    def _chart_type_changed(self, *_):
        value = str(self.chart_type_picker.currentData() or "horizontal")
        self.chart.set_chart_type(value)
        if self.change_callback:
            self.change_callback(value)


class BezoekerslijstWindow(EventBoardMixin, QMainWindow):
    def __init__(self, progress_callback=None):
        super().__init__()
        self._progress_callback = progress_callback or (lambda value, message: None)
        self._progress_callback(18, "Instellingen laden…")
        self.records: list[dict] = []
        self.events: list[dict] = []
        self.selected_events: set[str] = set()
        self.active_event_id = ""
        self.project_path: Path | None = None
        self.dirty = False
        self.presence_changes_pending = False
        self._presence_render_signature = None
        self.loading_tables = False
        self._identifier_lookup: dict[str, dict] = {}
        # Keep the legacy QSettings namespace so existing profiles/preferences
        # survive the branding change to EventHub.
        self.settings = QSettings("DCPL", "DCPL Event Management Tool")
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.timeout.connect(self._perform_autosave)
        self._autosave_in_progress = False
        self._autosave_error_reported = False
        self._live_server_windows = []
        self._rudder_bridge = None
        # Zo kan de Browserassistent de presentie opvragen vanuit Rudder zelf,
        # in plaats van dat jij een bestand moet aanwijzen.
        self.rudder_attendance_service = RudderAttendanceService(self)
        self.rudder_attendance_service.requested.connect(self._serve_rudder_attendance)
        self._allow_application_exit = False
        self._tray_icon = None
        self.event_focus_mode = True
        self.dark_mode_enabled = self.settings.value("dark_mode", True, type=bool)
        self._previous_excepthook = sys.excepthook
        sys.excepthook = self._handle_unexpected_exception
        self.profile = self._load_profile()
        self.task_templates = self._load_task_templates()
        self.project_templates = self._load_project_templates()
        self.recent_project_paths = self._load_recent_project_paths()
        self.visible_fields_by_view = self._load_visible_fields()

        self._progress_callback(38, "Hoofdvenster voorbereiden…")
        self.setWindowTitle("EventHub | Cohentra Digital")
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH if APP_ICON_PATH.exists() else LOGO_PATH)))
        self.resize(1480, 860)
        self.setMinimumSize(1060, 650)
        saved_geometry = self.settings.value("window_geometry")
        if saved_geometry:
            self.restoreGeometry(saved_geometry)
        self._build_ui()
        self._build_menu()
        self._setup_system_tray()
        self._progress_callback(72, "Vormgeving en tabbladen laden…")
        self._apply_style()
        self._load_analysis(self.current_analysis)
        self._render_all()
        self._progress_callback(94, "Gegevenscontroles voorbereiden…")

    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_sidebar()
        root.addWidget(self.sidebar)

        main_shell = QWidget()
        main_shell.setObjectName("mainShell")
        main_layout = QVBoxLayout(main_shell)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.masthead = ArtworkHeader(HEADER_WAVE_PATH)
        self.masthead.setObjectName("masthead")
        self.masthead_layout = QHBoxLayout(self.masthead)
        self.masthead_layout.setContentsMargins(24, 10, 24, 10)
        self.masthead_layout.setSpacing(12)
        self.app_logo = None
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.app_title = QLabel("Overzicht")
        self.app_title.setObjectName("appTitle")
        self.app_subtitle = QLabel("Operations, connected.")
        self.app_subtitle.setObjectName("appSubtitle")
        title_box.addWidget(self.app_title)
        title_box.addWidget(self.app_subtitle)
        self.masthead_layout.addLayout(title_box)
        self.masthead_layout.addStretch()
        self.workspace_status = QLabel("●  Lokaal actief")
        self.workspace_status.setObjectName("workspaceStatus")
        self.workspace_status.setToolTip("EventHub werkt lokaal op deze computer")
        self.masthead_layout.addWidget(self.workspace_status)
        self.notification_button = QPushButton("🔔  0")
        self.notification_button.setObjectName("notificationButton")
        self.notification_button.setToolTip("Open taken en meldingen")
        self.notification_button.clicked.connect(self.show_notifications)
        self.masthead_layout.addWidget(self.notification_button)
        self.settings_button = QPushButton()
        self.settings_button.setObjectName("iconButton")
        settings_icon_path = SIDEBAR_ICON_PATHS["settings"]
        if settings_icon_path.exists():
            self.settings_button.setIcon(QIcon(str(settings_icon_path)))
            self.settings_button.setIconSize(QSize(26, 26))
        self.settings_button.setFixedSize(36, 36)
        self.settings_button.setToolTip("Open instellingen")
        self.settings_button.setAccessibleName("Instellingen")
        settings_menu = QMenu(self.settings_button)
        settings_menu.addAction("Algemene instellingen", self.show_application_settings)
        settings_menu.addAction("Standaardtaken", self.show_standard_tasks_page)
        settings_menu.addAction("Templatebeheer", self.manage_project_templates)
        settings_menu.addAction("WhatsApp-sjablonen", self.manage_whatsapp_templates)
        settings_menu.addSeparator()
        settings_menu.addAction("Opslaglocaties", self.show_storage_locations)
        settings_menu.addAction("Herstelbestanden beheren", self.manage_recovery_files)
        settings_menu.aboutToShow.connect(lambda: self._set_settings_active(True))
        settings_menu.aboutToHide.connect(lambda: self._set_settings_active(False))
        self.settings_button.setMenu(settings_menu)
        self.masthead_layout.addWidget(self.settings_button)
        self.privacy_label = QLabel(f"Versie {APP_VERSION}   •   Dossiers lokaal opgeslagen")
        self.privacy_label.setObjectName("privacyLabel")
        self.masthead_layout.addWidget(self.privacy_label)
        main_layout.addWidget(self.masthead)

        body = QWidget()
        body.setObjectName("bodyCanvas")
        body_stack = QStackedLayout(body)
        body_stack.setContentsMargins(0, 0, 0, 0)
        body_stack.setStackingMode(QStackedLayout.StackingMode.StackAll)
        body_content = QWidget()
        body_content.setObjectName("bodyContent")
        self.body_layout = QVBoxLayout(body_content)
        self.body_layout.setContentsMargins(24, 12, 24, 12)
        self.body_layout.setSpacing(10)
        self.page_stack = QStackedWidget()
        self._build_home_page()
        self._build_events_page()
        self._build_open_tasks_page()
        self._build_standard_tasks_page()
        self._build_event_control_page()
        self._build_trends_page()
        self._build_profile_page()

        self.event_page = QWidget()
        self.event_page_layout = QVBoxLayout(self.event_page)
        self.event_page_layout.setContentsMargins(0, 0, 0, 0)
        self.event_page_layout.setSpacing(12)

        self.event_header = QFrame()
        self.event_header.setObjectName("eventWorkspaceHeader")
        self.event_header_layout = QVBoxLayout(self.event_header)
        self.event_header_layout.setContentsMargins(18, 12, 18, 12)
        self.event_header_layout.setSpacing(7)
        event_title_row = QHBoxLayout()
        event_title_row.setSpacing(12)
        back_button = QPushButton("← Evenementen")
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(self.back_to_home)
        event_title_row.addWidget(back_button, 0, Qt.AlignmentFlag.AlignTop)
        event_heading = QVBoxLayout()
        event_heading.setSpacing(2)
        event_eyebrow = QLabel("EVENEMENTDOSSIER")
        event_eyebrow.setObjectName("eyebrowLabel")
        self.event_title_label = QLabel("Evenement")
        self.event_title_label.setObjectName("eventWorkspaceTitle")
        self.event_meta_label = QLabel("")
        self.event_meta_label.setObjectName("hintLabel")
        event_heading.addWidget(event_eyebrow)
        event_heading.addWidget(self.event_title_label)
        event_heading.addWidget(self.event_meta_label)
        event_title_row.addLayout(event_heading, 1)
        self.switch_event_button = QPushButton("Ander evenement")
        self.switch_event_button.setObjectName("secondaryButton")
        self.switch_event_button.setToolTip("Snel naar een ander evenementdossier")
        self.switch_event_button.clicked.connect(self.switch_event)
        event_title_row.addWidget(self.switch_event_button, 0, Qt.AlignmentFlag.AlignTop)
        self.event_status_badge = QLabel("Status onbekend")
        self.event_status_badge.setObjectName("eventStatusBadge")
        event_title_row.addWidget(self.event_status_badge, 0, Qt.AlignmentFlag.AlignTop)
        self.event_header_layout.addLayout(event_title_row)
        self.event_page_layout.addWidget(self.event_header)

        self.event_summary_bar = QWidget()
        cards = QGridLayout(self.event_summary_bar)
        cards.setContentsMargins(0, 0, 0, 0)
        cards.setSpacing(8)
        self.count_total = self._summary_card("Deelnemers", "0", "Totaal ingeladen", compact=True)
        self.count_tasks = self._summary_card("Open taken", "0", "Geen openstaande acties", compact=True)
        self.count_callbacks = self._summary_card("After sales open", "0", "Nog te behandelen", compact=True)
        self.count_present = self._summary_card("Aanwezig", "0", "Presentiestatus", compact=True)
        summary_cards = (
            self.count_total[0], self.count_tasks[0], self.count_callbacks[0], self.count_present[0],
        )
        for index, card in enumerate(summary_cards):
            cards.addWidget(card, 0, index)
        for column in range(len(summary_cards)):
            cards.setColumnStretch(column, 1)
        self.event_page_layout.addWidget(self.event_summary_bar)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        event_overview = QWidget()
        self.event_overview_tab = event_overview
        event_overview_layout = QVBoxLayout(event_overview)
        event_overview_layout.setContentsMargins(16, 16, 16, 16)
        event_overview_layout.setSpacing(14)

        overview_heading_row = QHBoxLayout()
        overview_heading = QVBoxLayout()
        overview_heading.setSpacing(2)
        overview_title = QLabel("Overzicht")
        overview_title.setObjectName("sectionTitle")
        overview_hint = QLabel("Kerngegevens van dit evenement op één rustige plek.")
        overview_hint.setObjectName("hintLabel")
        overview_heading.addWidget(overview_title)
        overview_heading.addWidget(overview_hint)
        overview_heading_row.addLayout(overview_heading, 1)
        self.edit_event_button = QPushButton("Gegevens aanpassen")
        self.edit_event_button.setObjectName("secondaryButton")
        self.edit_event_button.clicked.connect(self.edit_active_event)
        overview_heading_row.addWidget(self.edit_event_button, 0, Qt.AlignmentFlag.AlignBottom)
        template_actions = QPushButton("•••")
        template_actions.setObjectName("secondaryButton")
        template_actions.setToolTip("Meer acties")
        template_menu = QMenu(template_actions)
        template_menu.addAction("Opslaan als template", self.save_active_event_as_template)
        template_actions.setMenu(template_menu)
        overview_heading_row.addWidget(template_actions, 0, Qt.AlignmentFlag.AlignBottom)
        event_overview_layout.addLayout(overview_heading_row)

        details_card = QFrame()
        details_card.setObjectName("eventDetailsCard")
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(18, 16, 18, 16)
        details_layout.setSpacing(10)
        details_title = QLabel("Evenementgegevens")
        details_title.setObjectName("statisticsTitle")
        details_layout.addWidget(details_title)
        self.event_details_label = QLabel("")
        self.event_details_label.setObjectName("eventDetailsText")
        self.event_details_label.setWordWrap(True)
        self.event_details_label.setTextFormat(Qt.TextFormat.RichText)
        details_layout.addWidget(self.event_details_label)
        details_layout.addStretch()
        event_overview_layout.addWidget(details_card, 1)
        event_overview_layout.addStretch()
        self.tabs.addTab(event_overview, "Overzicht")

        self.participant_table = self._new_table(self._participant_headers())
        self.participant_table.setObjectName("participants")
        self.participant_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.participant_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        participant_header = self.participant_table.horizontalHeader()
        participant_header.setStretchLastSection(False)
        participant_header.setMinimumSectionSize(72)
        participant_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        participant_header.setSectionsMovable(True)
        participant_header.sectionResized.connect(self._remember_participant_column_width)
        participant_header.sectionMoved.connect(self._remember_participant_column_order)
        self.participant_table.itemSelectionChanged.connect(self._participant_selection_changed)
        self.participant_table.viewport().installEventFilter(self)
        self.callback_table = self._new_table(self._callback_headers())
        self.callback_table.setObjectName("callbacks")
        self.callback_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.callback_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.callback_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        callback_header = self.callback_table.horizontalHeader()
        callback_header.setStretchLastSection(False)
        callback_header.setMinimumSectionSize(72)
        callback_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        callback_header.sectionResized.connect(self._remember_callback_column_width)
        self.callback_table.itemSelectionChanged.connect(self._callback_selection_changed)
        self.callback_table.cellDoubleClicked.connect(self._send_whatsapp_for_callback_row)
        # Een gewone tweede klik op een geselecteerde kandidaat deselecteert die rij.
        # Ctrl/Shift behouden de standaard meervoudige-selectielogica van Qt.
        self.callback_table.viewport().installEventFilter(self)
        self.access_table = self._new_table(self._presence_headers())
        self.access_table.setObjectName("presence")
        self.access_table.installEventFilter(self)
        self.access_table.viewport().installEventFilter(self)
        # Vier standen passen niet in een vinkje; ze worden per rij gekozen.
        self._attach_row_menu(self.access_table, [
            (f"Aanwezigheid: {ATTENDANCE_LABELS[status]}",
             lambda status=status: self._set_presence_status(status))
            for status in ATTENDANCE_STATUSES
        ])
        self.participant_table.itemChanged.connect(self._participant_changed)
        self.callback_table.itemChanged.connect(self._callback_changed)
        self.access_table.itemChanged.connect(self._presence_changed)

        participant_widget = QWidget()
        self.participant_tab = participant_widget
        participant_layout = QVBoxLayout(participant_widget)
        participant_layout.setContentsMargins(14, 14, 14, 14)
        participant_layout.setSpacing(10)
        participant_top = QHBoxLayout()
        self.participant_search_box = QLineEdit()
        self.participant_search_box.setPlaceholderText("Zoeken op naam, telefoonnummer, opleiding…")
        self.participant_search_box.setClearButtonEnabled(True)
        self.participant_search_box.setMinimumWidth(300)
        self.participant_search_box.textChanged.connect(self._filter_participants)
        participant_top.addWidget(self.participant_search_box, 1)
        self.participant_selection_label = QLabel("0 geselecteerd")
        self.participant_selection_label.setObjectName("hintLabel")
        participant_top.addWidget(self.participant_selection_label)
        self.participant_include_introducees = QCheckBox("Introducees tonen")
        self.participant_include_introducees.setChecked(True)
        self.settings.setValue("participants_include_introducees", True)
        self.participant_include_introducees.stateChanged.connect(self._participant_scope_changed)
        self.participant_import_button = QPushButton("Bezoekerslijst importeren")
        self.participant_import_button.setObjectName("primaryButton")
        self.participant_import_button.setToolTip("Voeg één of meer Excel-aanmeldlijsten toe aan dit evenement.")
        self.participant_import_button.clicked.connect(self.import_excel)
        self.participant_columns_button = self._columns_button("participants")
        self.participant_more_button = QPushButton("•••  Meer acties")
        self.participant_more_button.setObjectName("secondaryButton")
        participant_more_menu = QMenu(self.participant_more_button)
        participant_excel_action = participant_more_menu.addAction("Excel exporteren")
        participant_excel_action.triggered.connect(self.export_participant_list)
        self.participant_preview_action = participant_more_menu.addAction("Afdrukvoorbeeld")
        self.participant_preview_action.triggered.connect(self.preview_participant_list)
        participant_pdf_action = participant_more_menu.addAction("Exporteren als PDF")
        participant_pdf_action.triggered.connect(self.export_participant_pdf)
        participant_more_menu.addSeparator()
        participant_clear_action = participant_more_menu.addAction("Bezoekerslijst(en) wissen")
        participant_clear_action.setToolTip(
            "Koppel alle bezoekers los van dit evenement, bijvoorbeeld om de aanmeldlijsten opnieuw in te lezen."
        )
        participant_clear_action.triggered.connect(self.clear_event_visitor_lists)
        self.participant_more_button.setMenu(participant_more_menu)
        participant_top.addWidget(self.participant_include_introducees)
        participant_top.addWidget(self.participant_import_button)
        participant_top.addWidget(self.participant_columns_button)
        participant_top.addWidget(self.participant_more_button)
        participant_layout.addLayout(participant_top)
        self.participant_history_notice = QLabel("Geanonimiseerd — persoonsgegevens zijn verwijderd. Historische cijfers vindt u bij Statistieken.")
        self.participant_history_notice.setObjectName("statusLabel")
        self.participant_history_notice.setWordWrap(True)
        self.participant_history_notice.hide()
        participant_layout.addWidget(self.participant_history_notice)
        participant_layout.addWidget(self.participant_table, 1, Qt.AlignmentFlag.AlignLeft)
        # Houd de totale tabelbreedte dynamisch, maar laat hem nooit smaller
        # worden dan de beschikbare werkruimte wanneer de zichtbare kolommen
        # samen breder zijn. In dat geval neemt de tabel de beschikbare breedte
        # en verschijnt de horizontale scrollbar voor de resterende kolommen.
        participant_widget.installEventFilter(self)
        self.tabs.addTab(participant_widget, "Deelnemers")

        callback_widget = QWidget()
        self.callback_tab = callback_widget
        callback_layout = QVBoxLayout(callback_widget)
        callback_layout.setContentsMargins(14, 14, 14, 14)
        callback_layout.setSpacing(10)
        callback_heading = QHBoxLayout()
        callback_title_box = QVBoxLayout()
        callback_title_box.setSpacing(2)
        callback_title = QLabel("After sales")
        callback_title.setObjectName("sectionTitle")
        callback_subtitle = QLabel("Werk kandidaten snel af en leg alleen vast wat voor de volgende opvolging nodig is.")
        callback_subtitle.setObjectName("hintLabel")
        callback_title_box.addWidget(callback_title)
        callback_title_box.addWidget(callback_subtitle)
        callback_heading.addLayout(callback_title_box, 1)
        callback_heading.addWidget(QLabel("Evenement:"))
        self.after_sales_event_combo = EventPickerButton(allow_none=True)
        self.after_sales_event_combo.set_registration_counter(self._registration_lines)
        self.after_sales_event_combo.setMinimumWidth(320)
        self.after_sales_event_combo.changed.connect(self._after_sales_event_changed)
        callback_heading.addWidget(self.after_sales_event_combo)
        callback_layout.addLayout(callback_heading)

        self.after_sales_context_hint = QLabel(
            "Selecteer eerst een evenement om After sales te gebruiken."
        )
        self.after_sales_context_hint.setObjectName("statusLabel")
        self.after_sales_context_hint.setWordWrap(True)
        self.after_sales_context_hint.setVisible(False)
        callback_layout.addWidget(self.after_sales_context_hint)

        after_sales_cards = QGridLayout()
        after_sales_cards.setSpacing(10)
        self.after_sales_total = self._summary_card("Kandidaten", "0", "Reguliere kandidaten", compact=True)
        self.after_sales_open = self._summary_card("Nog te behandelen", "0", "Actie nodig", compact=True)
        self.after_sales_followup = self._summary_card("Opvolging", "0", "Terugbellen gepland", compact=True)
        self.after_sales_done = self._summary_card("Afgehandeld", "0", "Geen actie meer nodig", compact=True)
        for index, summary in enumerate((self.after_sales_total, self.after_sales_open, self.after_sales_followup, self.after_sales_done)):
            after_sales_cards.addWidget(summary[0], 0, index)
            after_sales_cards.setColumnStretch(index, 1)
        callback_layout.addLayout(after_sales_cards)

        callback_top = QHBoxLayout()
        self.callback_search_box = QLineEdit()
        self.callback_search_box.setPlaceholderText("Zoek op naam, telefoonnummer of notitie…")
        self.callback_search_box.setClearButtonEnabled(True)
        self.callback_search_box.setMinimumWidth(300)
        self.callback_search_box.textChanged.connect(self._filter_callbacks)
        self.callback_status_filter = ScrollSafeComboBox()
        self.callback_status_filter.addItems(["Alle statussen", "Actie nodig", "Opvolging gepland", "Afgehandeld"])
        for status in CALLBACK_STATUSES:
            self.callback_status_filter.addItem(callback_status_icon(status), status)
        self.callback_status_filter.currentTextChanged.connect(self._filter_callbacks)
        callback_columns_button = self._columns_button("callbacks")
        callback_top.addWidget(self.callback_search_box, 1)
        callback_top.addWidget(self.callback_status_filter)
        callback_top.addWidget(callback_columns_button)
        callback_layout.addLayout(callback_top)
        callback_actions = QHBoxLayout()
        self.callback_selection_label = QLabel("0 kandidaten geselecteerd")
        self.callback_selection_label.setObjectName("hintLabel")
        self.select_all_callbacks_button = QPushButton("Alles selecteren")
        self.select_all_callbacks_button.setObjectName("secondaryButton")
        self.select_all_callbacks_button.setToolTip("Selecteert alle kandidaten. Zodra alles geselecteerd is, deselecteert deze knop alles weer.")
        self.select_all_callbacks_button.clicked.connect(self._toggle_all_callbacks)
        self.select_visible_callbacks_button = QPushButton("Gefilterde kandidaten selecteren")
        self.select_visible_callbacks_button.setObjectName("secondaryButton")
        self.select_visible_callbacks_button.setToolTip("Selecteert alleen de kandidaten die na de huidige zoekopdracht/filter zichtbaar zijn.")
        self.select_visible_callbacks_button.clicked.connect(self._select_visible_callbacks)
        self.whatsapp_queue_button = QPushButton("Stuur WhatsApp")
        self.whatsapp_queue_button.setObjectName("primaryButton")
        self.whatsapp_queue_button.clicked.connect(self._start_whatsapp_queue)
        callback_actions.addWidget(self.callback_selection_label, 1)
        callback_actions.addWidget(self.select_all_callbacks_button)
        callback_actions.addWidget(self.select_visible_callbacks_button)
        callback_actions.addWidget(self.whatsapp_queue_button)
        callback_layout.addLayout(callback_actions)

        self.callback_workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.callback_workspace_splitter.setObjectName("callbackWorkspaceSplitter")
        self.callback_workspace_splitter.setChildrenCollapsible(False)
        self.callback_workspace_splitter.setHandleWidth(8)
        self.callback_workspace_splitter.addWidget(self.callback_table)

        self.callback_detail_card = QFrame()
        self.callback_detail_card.setObjectName("eventDetailsCard")
        self.callback_detail_card.setMaximumWidth(560)
        card_layout = QVBoxLayout(self.callback_detail_card)
        card_layout.setContentsMargins(3, 2, 2, 2)
        card_layout.setSpacing(0)
        self.callback_detail_scroll = FitWidthScrollArea(minimum_width=300)
        self.callback_detail_scroll.setObjectName("callbackDetailScroll")
        self.callback_detail_scroll.viewport().setObjectName("callbackDetailBody")
        detail_body = QWidget()
        detail_body.setObjectName("callbackDetailBody")
        self.callback_detail_scroll.setWidget(detail_body)
        card_layout.addWidget(self.callback_detail_scroll)
        detail_layout = QVBoxLayout(detail_body)
        detail_layout.setContentsMargins(13, 10, 12, 10)
        detail_layout.setSpacing(6)
        self.callback_detail_name = QLabel("Selecteer een kandidaat")
        self.callback_detail_name.setObjectName("sectionTitle")
        self.callback_detail_name.setWordWrap(True)
        detail_layout.addWidget(self.callback_detail_name)
        self.callback_detail_person = QLabel("Klik op een rij om de contactgegevens en opvolging te bekijken.")
        self.callback_detail_person.setObjectName("hintLabel")
        self.callback_detail_person.setWordWrap(True)
        detail_layout.addWidget(self.callback_detail_person)

        detail_form = QGridLayout()
        detail_form.setHorizontalSpacing(14)
        detail_form.setVerticalSpacing(7)
        detail_form.setColumnStretch(0, 0)
        detail_form.setColumnStretch(1, 1)

        self.callback_detail_status = ScrollSafeComboBox()
        self.callback_detail_status.setMinimumHeight(30)
        self.callback_detail_status.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.callback_detail_status.setMinimumContentsLength(12)
        for status in CALLBACK_STATUSES:
            self.callback_detail_status.addItem(callback_status_icon(status), status)
        self.callback_detail_status.currentTextChanged.connect(self._callback_detail_status_changed)

        self.callback_detail_last_contact = QLabel("—")
        self.callback_detail_last_contact.setObjectName("hintLabel")
        self.callback_detail_last_contact.setMinimumHeight(30)
        self.callback_detail_last_contact.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.callback_detail_followup = QLineEdit()
        # Geen vaste hoogte: op een geschaalde Windows-weergave viel de tekst dan half weg.
        self.callback_detail_followup.setMinimumWidth(120)
        self.callback_detail_followup.setPlaceholderText("dd-mm-jjjj")
        self.callback_detail_followup.editingFinished.connect(self._save_callback_detail)

        self.callback_detail_whatsapp = QLabel("—")
        self.callback_detail_whatsapp.setObjectName("hintLabel")
        self.callback_detail_whatsapp.setMinimumHeight(30)
        self.callback_detail_whatsapp.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        detail_rows = (
            ("Contactstatus", self.callback_detail_status),
            ("Laatste contact", self.callback_detail_last_contact),
            ("Opnieuw contact", with_date_picker(self.callback_detail_followup)),
            ("WhatsApp", self.callback_detail_whatsapp),
        )
        for row_index, (label_text, field_widget) in enumerate(detail_rows):
            row_label = QLabel(label_text)
            row_label.setObjectName("hintLabel")
            row_label.setMinimumHeight(30)
            row_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            # Velden houden hun eigen hoogte; bij te weinig ruimte scrolt het paneel.
            field_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            detail_form.addWidget(row_label, row_index, 0)
            detail_form.addWidget(field_widget, row_index, 1)

        detail_layout.addLayout(detail_form)
        notes_label = QLabel("Opmerkingen")
        notes_label.setObjectName("hintLabel")
        detail_layout.addWidget(notes_label)
        self.callback_detail_notes = QPlainTextEdit()
        self.callback_detail_notes.setPlaceholderText("Notities over het contact of de volgende actie…")
        self.callback_detail_notes.setMinimumHeight(
            max(72, self.callback_detail_notes.fontMetrics().lineSpacing() * 3 + 28)
        )
        self.callback_detail_notes.textChanged.connect(self._callback_detail_notes_changed)
        # De notities vullen de resterende ruimte; is die er niet, dan scrolt het paneel.
        detail_layout.addWidget(self.callback_detail_notes, 1)
        self.callback_workspace_splitter.addWidget(self.callback_detail_card)
        # Het detailpaneel verschijnt pas zodra er daadwerkelijk een selectie is.
        # Zonder selectie gebruikt de kandidatentabel de volledige werkruimte.
        self.callback_detail_card.setVisible(False)
        self.callback_workspace_splitter.setStretchFactor(0, 1)
        self.callback_workspace_splitter.setStretchFactor(1, 0)
        saved_splitter_state = self.settings.value("after_sales_workspace_splitter")
        if saved_splitter_state:
            try:
                self.callback_workspace_splitter.restoreState(saved_splitter_state)
            except (TypeError, ValueError):
                self.callback_workspace_splitter.setSizes([760, 380])
        else:
            self.callback_workspace_splitter.setSizes([760, 380])
        self.callback_workspace_splitter.splitterMoved.connect(
            lambda *_: self.settings.setValue(
                "after_sales_workspace_splitter", self.callback_workspace_splitter.saveState()
            )
        )
        callback_layout.addWidget(self.callback_workspace_splitter, 1)
        self._callback_detail_record_id = None
        self._callback_detail_loading = False
        self.page_stack.addWidget(callback_widget)

        access_widget = QWidget()
        self.presence_tab = access_widget
        access_layout = QVBoxLayout(access_widget)
        access_layout.setContentsMargins(14, 14, 14, 14)
        access_layout.setSpacing(10)
        access_top = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Zoek op naam, geboortedatum of geboorteplaats…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(self._filter_presence)
        print_button = QPushButton("Presentielijst afdrukken")
        print_button.setObjectName("primaryButton")
        print_button.clicked.connect(self.print_presence_list)
        self.presence_save_button = QPushButton("Registratie afronden")
        self.presence_save_button.setObjectName("primaryButton")
        self.presence_save_button.setToolTip(
            "Rond de registratie af. Nog onbeoordeelde deelnemers worden pas na uw bevestiging als afwezig vastgelegd."
        )
        self.presence_save_button.clicked.connect(self._finish_presence_registration)
        self.presence_save_button.setVisible(False)
        presence_columns_button = self._columns_button("presence")
        access_top.addWidget(self.search_box, 1)
        access_top.addWidget(presence_columns_button)
        access_top.addWidget(print_button)
        access_top.addWidget(self.presence_save_button)
        access_layout.addLayout(access_top)
        access_hint = QLabel(
            "Gebruik de pijltjestoetsen om door de deelnemers te gaan en de spatiebalk om Aanwezig aan of uit te vinken. "
            "De zoekopdracht beperkt alleen het scherm; de afdruk negeert de zoektekst."
        )
        access_hint.setObjectName("hintLabel")
        access_layout.addWidget(access_hint)
        self.presence_live_lock_label = QLabel(
            "Live registratie is actief voor dit evenement. Aanwezigheid wordt via de livesessie bijgehouden."
        )
        self.presence_live_lock_label.setObjectName("statusLabel")
        self.presence_live_lock_label.setWordWrap(True)
        self.presence_live_lock_label.setVisible(False)
        access_layout.addWidget(self.presence_live_lock_label)
        access_layout.addWidget(self.access_table, 1)
        self.event_control_tabs.insertTab(0, access_widget, "Aanwezigheid")
        self.event_control_tabs.setCurrentWidget(access_widget)

        self.statistics_cards = {}
        statistics_definitions = {
            "education": ("Opleidingsniveau", "Verdeling van het opgegeven opleidingsniveau"),
            "profile": ("Profiel", "Meest voorkomende profielen en opleidingsrichtingen"),
            "gender": ("Geslacht", "Verdeling op basis van de aangeleverde registratiegegevens"),
            "age": ("Leeftijd", "Automatisch berekend uit de geboortedatum"),
            "listing": ("Inschrijving", "Via welke aanmeldpagina de deelnemers binnenkwamen"),
        }
        for chart_key, (title, description) in statistics_definitions.items():
            chart_type = str(self.settings.value(
                f"statistics_chart_type/{chart_key}", STATISTICS_CHART_DEFAULTS[chart_key]
            ) or STATISTICS_CHART_DEFAULTS[chart_key])
            self.statistics_cards[chart_key] = StatisticsCard(
                title,
                description,
                chart_type,
                lambda value, chart_key=chart_key: self._statistics_chart_type_changed(chart_key, value),
            )
        statistics_tab = QWidget()
        self.statistics_tab = statistics_tab
        statistics_tab_layout = QVBoxLayout(statistics_tab)
        statistics_tab_layout.setContentsMargins(14, 14, 14, 14)
        statistics_tab_layout.setSpacing(10)
        statistics_top = QHBoxLayout()
        self.statistics_scope_label = QLabel("Grafieken op basis van reguliere bezoekers.")
        self.statistics_scope_label.setObjectName("hintLabel")
        presence_filter_label = QLabel("Aanwezigheid:")
        self.statistics_presence_filter = ScrollSafeComboBox()
        for label, value in STATISTICS_PRESENCE_FILTERS:
            self.statistics_presence_filter.addItem(label, value)
        stored_presence_filter = str(self.settings.value("statistics_presence_filter", "all") or "all")
        selected_presence = self.statistics_presence_filter.findData(stored_presence_filter)
        self.statistics_presence_filter.setCurrentIndex(selected_presence if selected_presence >= 0 else 0)
        self.statistics_presence_filter.setToolTip(
            "Beperk de statistieken tot bijvoorbeeld alleen de no-shows na afloop van het evenement."
        )
        self.statistics_presence_filter.currentIndexChanged.connect(self._statistics_scope_changed)
        self.statistics_show_all = QCheckBox("Alle waarden tonen")
        self.statistics_show_all.setChecked(self.settings.value("statistics_show_all", False, type=bool))
        self.statistics_show_all.setToolTip(
            "Standaard tonen de grafieken de grootste waarden en gaat de staart samen onder Overig. "
            "Hiermee komt elke waarde apart in beeld, ook in de export."
        )
        self.statistics_show_all.stateChanged.connect(self._statistics_scope_changed)
        self.statistics_include_introducees = QCheckBox("Introducees meetellen in grafieken")
        self.statistics_include_introducees.setChecked(
            self.settings.value("statistics_include_introducees_v2", True, type=bool)
        )
        self.statistics_include_introducees.stateChanged.connect(self._statistics_scope_changed)
        statistics_export_button = QPushButton("Exporteren")
        statistics_export_button.setToolTip("Statistieken exporteren naar Excel, inclusief de kruistabel")
        statistics_export_button.setObjectName("secondaryButton")
        statistics_export_button.clicked.connect(self.export_statistics)
        statistics_top.addWidget(self.statistics_scope_label, 1)
        statistics_top.addWidget(presence_filter_label)
        statistics_top.addWidget(self.statistics_presence_filter)
        statistics_top.addWidget(self.statistics_show_all)
        statistics_top.addWidget(self.statistics_include_introducees)
        statistics_top.addWidget(statistics_export_button)
        statistics_tab_layout.addLayout(statistics_top)

        statistics_content = QWidget()
        statistics_grid = QGridLayout(statistics_content)
        statistics_grid.setContentsMargins(0, 0, 0, 0)
        statistics_grid.setSpacing(12)
        statistics_grid.addWidget(self.statistics_cards["education"], 0, 0)
        statistics_grid.addWidget(self.statistics_cards["profile"], 0, 1)
        statistics_grid.addWidget(self.statistics_cards["gender"], 1, 0)
        statistics_grid.addWidget(self.statistics_cards["age"], 1, 1)
        statistics_grid.addWidget(self.statistics_cards["listing"], 2, 0, 1, 2)

        # Extra weergave onder de bestaande grafieken; die blijven ongewijzigd.
        crosstab_box = QGroupBox("Opleidingsniveau x profiel")
        crosstab_box.setObjectName("statisticsCard")
        crosstab_layout = QVBoxLayout(crosstab_box)
        crosstab_layout.setContentsMargins(16, 14, 16, 14)
        crosstab_layout.setSpacing(6)
        crosstab_caption = QLabel(
            "Welke profielen komen bij welk opleidingsniveau. Schrijfwijzen als MBO 4, "
            "mbo-4 en MBO niveau 4 worden als een groep geteld; de aangeleverde gegevens "
            "blijven ongewijzigd."
        )
        crosstab_caption.setObjectName("statisticsCaption")
        crosstab_caption.setWordWrap(True)
        crosstab_layout.addWidget(crosstab_caption)

        crosstab_controls = QHBoxLayout()
        self.crosstab_view_picker = ScrollSafeComboBox()
        for label, value in CROSSTAB_VIEWS:
            self.crosstab_view_picker.addItem(label, value)
        self._restore_picker(self.crosstab_view_picker, "crosstab_view", "grafiek")
        self.crosstab_view_picker.setToolTip("Wissel tussen de heatmap en de tabel met exacte getallen.")
        self.crosstab_view_picker.currentIndexChanged.connect(self._crosstab_options_changed)
        self.crosstab_value_picker = ScrollSafeComboBox()
        for label, value in CROSSTAB_VALUES:
            self.crosstab_value_picker.addItem(label, value)
        self._restore_picker(self.crosstab_value_picker, "crosstab_value", "aantallen")
        self.crosstab_value_picker.setToolTip(
            "Aantallen tellen personen; percentage toont het aandeel binnen een opleidingsniveau."
        )
        self.crosstab_value_picker.currentIndexChanged.connect(self._crosstab_options_changed)
        crosstab_controls.addWidget(QLabel("Weergave:"))
        crosstab_controls.addWidget(self.crosstab_view_picker)
        crosstab_controls.addWidget(QLabel("Waarde:"))
        crosstab_controls.addWidget(self.crosstab_value_picker)
        crosstab_controls.addStretch()
        crosstab_layout.addLayout(crosstab_controls)

        self.crosstab_heatmap = CrosstabHeatmap()
        self.crosstab_table = QTableWidget(0, 0)
        self.crosstab_table.setObjectName("dashboardTable")
        self.crosstab_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.crosstab_table.setMinimumHeight(200)
        # Beide weergaven tonen dezelfde gegevens; de tabel blijft bereikbaar
        # voor wie de exacte getallen naast elkaar wil zien.
        self.crosstab_stack = QStackedWidget()
        self.crosstab_stack.addWidget(self.crosstab_heatmap)
        self.crosstab_stack.addWidget(self.crosstab_table)
        crosstab_layout.addWidget(self.crosstab_stack)
        self.crosstab_note = QLabel("")
        self.crosstab_note.setObjectName("hintLabel")
        self.crosstab_note.setWordWrap(True)
        crosstab_layout.addWidget(self.crosstab_note)
        statistics_grid.addWidget(crosstab_box, 3, 0, 1, 2)
        statistics_scroll = QScrollArea()
        statistics_scroll.setWidgetResizable(True)
        statistics_scroll.setFrameShape(QFrame.Shape.NoFrame)
        statistics_scroll.setWidget(statistics_content)
        statistics_tab_layout.addWidget(statistics_scroll, 1)
        self.tabs.addTab(statistics_tab, "Statistieken")

        quality_tab = QWidget()
        self.quality_tab = quality_tab
        quality_layout = QVBoxLayout(quality_tab)
        quality_layout.setContentsMargins(14, 14, 14, 14)
        quality_layout.setSpacing(10)
        quality_top = QHBoxLayout()
        self.quality_scope_label = QLabel("EventHub controleert het geopende evenement automatisch op ontbrekende of verdachte gegevens.")
        self.quality_scope_label.setObjectName("hintLabel")
        edit_quality_button = QPushButton("Gegevens aanpassen")
        edit_quality_button.setObjectName("primaryButton")
        edit_quality_button.clicked.connect(self.edit_selected_quality_record)
        quality_top.addWidget(self.quality_scope_label, 1)
        quality_top.addWidget(edit_quality_button)
        quality_layout.addLayout(quality_top)
        self.quality_table = self._new_table(["Probleem", "Deelnemer", "Evenement", "Waarde / advies"])
        self.quality_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.quality_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.quality_table.cellDoubleClicked.connect(lambda *_: self.edit_selected_quality_record())
        self._attach_row_menu(self.quality_table, [
            ("Gegevens aanpassen", self.edit_selected_quality_record),
            (None, None),
            ("Dubbele inschrijving overslaan", self.skip_duplicate_registration),
            ("Weer meetellen", self.include_record_again),
        ])
        quality_layout.addWidget(self.quality_table, 1)
        self.tabs.addTab(quality_tab, "Gegevenscontrole")

        self._build_event_support_tabs()
        self.event_page_layout.addWidget(self.tabs, 1)
        self.page_stack.addWidget(self.event_page)
        self.body_layout.addWidget(self.page_stack, 1)
        self.page_stack.setCurrentWidget(self.home_page)
        self.page_stack.currentChanged.connect(self._sync_navigation_indicator)
        self.tabs.currentChanged.connect(self._sync_navigation_indicator)
        self.status_label = QLabel("Klaar — maak een evenement of open een bestaand EventHub-bestand.")
        self.status_label.setObjectName("statusLabel")
        footer = QWidget()
        footer.setObjectName("appFooter")
        footer.setFixedHeight(26)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(12)
        footer_layout.addWidget(self.status_label, 1)
        self.powered_by_label = QLabel("Powered by Cohentra Digital")
        self.powered_by_label.setObjectName("poweredByLabel")
        self.powered_by_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer_layout.addWidget(self.powered_by_label, 0)
        self.body_layout.addWidget(footer)
        body_stack.addWidget(body_content)
        self.neon_edge_overlay = NeonEdgeOverlay(NEON_WAVES_PATH, self.dark_mode_enabled, body)
        body_stack.addWidget(self.neon_edge_overlay)
        body_stack.setCurrentWidget(self.neon_edge_overlay)
        main_layout.addWidget(body, 1)
        root.addWidget(main_shell, 1)
        self.setCentralWidget(central)
        self._set_project_context_ui(False)
        self._refresh_recent_projects_ui()
        QTimer.singleShot(0, self._update_event_workspace_header)

    def _build_sidebar(self):
        # EventHub 2 starts once with the full navigation visible. Older builds
        # could persist a collapsed sidebar, which made a fresh UI update look
        # broken on first launch. After this one-time migration the user's
        # collapse/expand choice is remembered normally again.
        sidebar_layout_version = "2.17.3"
        if self.settings.value("sidebar_layout_version", "") != sidebar_layout_version:
            self.sidebar_expanded = True
            self.settings.setValue("sidebar_expanded", True)
            self.settings.setValue("sidebar_layout_version", sidebar_layout_version)
        else:
            self.sidebar_expanded = self.settings.value("sidebar_expanded", True, type=bool)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 14, 10, 12)
        self.sidebar_layout.setSpacing(7)

        brand = QWidget()
        brand.setObjectName("sidebarBrand")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(2, 0, 2, 10)
        brand_layout.setSpacing(10)
        self.sidebar_logo = QLabel()
        self.sidebar_logo.setObjectName("sidebarLogo")
        if LOGO_PATH.exists():
            self.sidebar_logo.setPixmap(QPixmap(str(LOGO_PATH)).scaled(
                44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
        self.sidebar_logo.setFixedSize(48, 48)
        self.sidebar_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_logo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_logo.setToolTip("Home")
        self.sidebar_logo.installEventFilter(self)
        brand_layout.addWidget(self.sidebar_logo)
        self.sidebar_brand_text = QWidget()
        self.sidebar_brand_text.setObjectName("sidebarBrandText")
        brand_text_layout = QVBoxLayout(self.sidebar_brand_text)
        brand_text_layout.setContentsMargins(0, 2, 0, 2)
        brand_text_layout.setSpacing(0)
        brand_title = QLabel("EVENTHUB")
        brand_title.setObjectName("sidebarBrandTitle")
        brand_subtitle = QLabel("Events, connected.")
        brand_subtitle.setObjectName("sidebarBrandSubtitle")
        brand_text_layout.addWidget(brand_title)
        brand_text_layout.addWidget(brand_subtitle)
        brand_layout.addWidget(self.sidebar_brand_text, 1)
        self.sidebar_layout.addWidget(brand)

        self.sidebar_buttons = {}
        style = QApplication.style()
        def sidebar_icon(name, fallback):
            path = SIDEBAR_ICON_PATHS.get(name)
            glyph_sizes = {"callbacks": 28, "events": 28, "tasks": 28, "event_control": 28, "file": 27, "profile": 27, "help": 27}
            return _centered_sidebar_icon(path, style.standardIcon(fallback), glyph_sizes.get(name, 32))

        self.sidebar_workspace_label = QLabel("WERKRUIMTE")
        self.sidebar_workspace_label.setObjectName("sidebarSectionLabel")
        self.sidebar_layout.addWidget(self.sidebar_workspace_label)

        navigation = [
            ("events", "Evenementen", QStyle.StandardPixmap.SP_FileDialogListView, self.back_to_home,
             "Alle evenementen en evenementdossiers"),
            ("tasks", "Taken", QStyle.StandardPixmap.SP_DialogApplyButton, self.show_open_tasks_page,
             "Alle onafgeronde taken"),
            ("callbacks", "After sales", QStyle.StandardPixmap.SP_MessageBoxInformation, self.show_nazorg_page,
             "Bellen, WhatsApp-contact en vervolgafspraken"),
            ("event_control", "Event Control", QStyle.StandardPixmap.SP_ComputerIcon, self.show_event_control_page,
             "Presentie, live sessies en Rudder"),
            ("trends", "Trends", QStyle.StandardPixmap.SP_FileDialogDetailedView, self.show_trends_page,
             "Ontwikkeling over evenementen heen: opkomst, no-shows en doelgroep"),
        ]
        for key, label, pixmap, handler, tooltip in navigation:
            button = QPushButton(label)
            button.setObjectName("sidebarButton")
            button.setProperty("navigationKey", key)
            button.setIcon(sidebar_icon(key, pixmap))
            button.setIconSize(QSize(30, 30))
            button.setFixedHeight(46)
            button.setToolTip(tooltip)
            button.setAccessibleName(label)
            button.clicked.connect(handler)
            self.sidebar_layout.addWidget(button)
            self.sidebar_buttons[key] = button

        self.sidebar_layout.addStretch()
        self.sidebar_manage_label = QLabel("BEHEER")
        self.sidebar_manage_label.setObjectName("sidebarSectionLabel")
        self.sidebar_layout.addWidget(self.sidebar_manage_label)

        file_button = QPushButton("Bestand")
        file_button.setObjectName("sidebarButton")
        file_button.setIcon(sidebar_icon("file", QStyle.StandardPixmap.SP_DialogOpenButton))
        file_button.setIconSize(QSize(30, 30))
        file_button.setFixedHeight(46)
        file_button.setToolTip("EventHub-bestanden openen, opslaan en terugvinden")
        file_menu = QMenu(file_button)
        file_menu.addAction("Bestand openen", self.open_project)
        file_menu.addAction("Bestand opslaan", self.save_project)
        file_menu.addSeparator()
        file_menu.addAction("Deelnemerslijst exporteren", self.export_participant_list)
        file_menu.addAction("Volledige Excel-export", self.export_excel)
        file_menu.addSeparator()
        file_menu.addAction("Recent openen", self.open_recent_project)
        file_menu.addSeparator()
        file_menu.addAction("Vorige versie herstellen", self.restore_previous_version)
        file_button.setMenu(file_menu)
        self.sidebar_layout.addWidget(file_button)

        profile_button = QPushButton("Mijn profiel")
        profile_button.setObjectName("sidebarButton")
        profile_button.setIcon(sidebar_icon("profile", QStyle.StandardPixmap.SP_DirIcon))
        profile_button.setIconSize(QSize(30, 30))
        profile_button.setFixedHeight(46)
        profile_button.setToolTip("Uw profielgegevens beheren")
        profile_button.clicked.connect(self.show_profile_page)
        self.sidebar_layout.addWidget(profile_button)
        self.sidebar_buttons["profile"] = profile_button

        help_button = QPushButton("Help")
        help_button.setObjectName("sidebarButton")
        help_button.setIcon(sidebar_icon("help", QStyle.StandardPixmap.SP_MessageBoxQuestion))
        help_button.setIconSize(QSize(30, 30))
        help_button.setFixedHeight(46)
        help_button.setToolTip("Rondleiding, versie-informatie en uitleg over EventHub")
        help_menu = QMenu(help_button)
        help_menu.addAction("Rondleiding door EventHub", self.start_tutorial)
        help_menu.addSeparator()
        help_menu.addAction("Nieuw in deze versie", self.show_changelog)
        help_menu.addAction("Over EventHub", self.show_about_dialog)
        help_button.setMenu(help_menu)
        self.sidebar_layout.addWidget(help_button)

        self.sidebar_utility_buttons = [file_button, help_button]
        self.sidebar_utility_labels = ["Bestand", "Help"]
        self.sidebar_collapse_button = QPushButton()
        self.sidebar_collapse_button.setObjectName("sidebarCollapseButton")
        self.sidebar_collapse_button.setToolTip("Zijbalk in- of uitklappen")
        self.sidebar_collapse_button.setFixedSize(38, 34)
        self.sidebar_collapse_button.clicked.connect(self.toggle_sidebar)
        collapse_row = QHBoxLayout()
        collapse_row.setContentsMargins(0, 2, 0, 0)
        collapse_row.addStretch()
        collapse_row.addWidget(self.sidebar_collapse_button)
        self.sidebar_layout.addLayout(collapse_row)
        self._apply_sidebar_state()

    def toggle_sidebar(self):
        self.sidebar_expanded = not self.sidebar_expanded
        self.settings.setValue("sidebar_expanded", self.sidebar_expanded)
        self._apply_sidebar_state()

    def _apply_sidebar_state(self):
        expanded = bool(self.sidebar_expanded)
        self.sidebar.setFixedWidth(204 if expanded else 72)
        self.sidebar_brand_text.setVisible(expanded)
        if hasattr(self, "sidebar_workspace_label"):
            self.sidebar_workspace_label.setVisible(expanded)
        if hasattr(self, "sidebar_manage_label"):
            self.sidebar_manage_label.setVisible(expanded)
        labels = {"events": "Evenementen", "tasks": "Taken", "callbacks": "After sales", "event_control": "Event Control", "trends": "Trends", "profile": "Mijn profiel"}
        for key, button in self.sidebar_buttons.items():
            button.setText(labels[key] if expanded else "")
            button.setProperty("collapsed", not expanded)
            button.style().unpolish(button)
            button.style().polish(button)
        for button, label in zip(self.sidebar_utility_buttons, self.sidebar_utility_labels):
            button.setText(label if expanded else "")
            button.setProperty("collapsed", not expanded)
            button.style().unpolish(button)
            button.style().polish(button)
        self.sidebar_collapse_button.setText("‹" if expanded else "›")

    def _build_home_page(self):
        home = QWidget()
        self.home_page = home
        layout = QVBoxLayout(home)
        layout.setContentsMargins(18, 4, 18, 12)
        layout.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("dashboardHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 14, 20, 14)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        self.start_welcome = QLabel("Welkom bij EventHub")
        self.start_welcome.setObjectName("heroTitle")
        self.start_date_label = QLabel("")
        self.start_date_label.setObjectName("heroSubtitle")
        copy.addWidget(self.start_welcome)
        copy.addWidget(self.start_date_label)
        hero_layout.addLayout(copy, 1)
        events_button = QPushButton("Evenementen openen →")
        events_button.setObjectName("secondaryButton")
        events_button.clicked.connect(self.back_to_home)
        hero_layout.addWidget(events_button)
        layout.addWidget(hero)

        top = QHBoxLayout()
        top.setSpacing(10)

        continue_box = QGroupBox("Verder waar je was")
        continue_box.setObjectName("dashboardPanel")
        continue_layout = QVBoxLayout(continue_box)
        self.home_continue_title = QLabel("Nog geen recente werkcontext")
        self.home_continue_title.setObjectName("sectionTitle")
        self.home_continue_meta = QLabel("Open een evenement om hier later direct verder te gaan.")
        self.home_continue_meta.setObjectName("hintLabel")
        self.home_continue_meta.setWordWrap(True)
        self.home_continue_button = QPushButton("Doorgaan →")
        self.home_continue_button.setObjectName("primaryButton")
        self.home_continue_button.clicked.connect(self._continue_home_context)
        continue_layout.addWidget(self.home_continue_title)
        continue_layout.addWidget(self.home_continue_meta)
        continue_layout.addStretch()
        continue_layout.addWidget(self.home_continue_button, 0, Qt.AlignmentFlag.AlignLeft)
        top.addWidget(continue_box, 1)

        attention_box = QGroupBox("Aandacht nodig")
        attention_box.setObjectName("dashboardPanel")
        attention_layout = QVBoxLayout(attention_box)
        self.home_attention_label = QLabel("✓ Alles op orde\nEventHub ziet op dit moment geen bijzonderheden.")
        self.home_attention_label.setObjectName("hintLabel")
        self.home_attention_label.setWordWrap(True)
        attention_layout.addWidget(self.home_attention_label)
        attention_layout.addStretch()
        tasks_button = QPushButton("Open taken bekijken →")
        tasks_button.setObjectName("secondaryButton")
        tasks_button.clicked.connect(self.show_open_tasks_page)
        attention_layout.addWidget(tasks_button, 0, Qt.AlignmentFlag.AlignLeft)
        top.addWidget(attention_box, 1)
        layout.addLayout(top, 1)

        today_box = QGroupBox("Vandaag")
        today_box.setObjectName("dashboardPanel")
        today_layout = QVBoxLayout(today_box)
        today_layout.setContentsMargins(14, 14, 14, 14)
        self.home_today_title = QLabel("Geen evenementen vandaag")
        self.home_today_title.setObjectName("sectionTitle")
        self.home_today_meta = QLabel("Je planning is vandaag leeg.")
        self.home_today_meta.setObjectName("hintLabel")
        today_layout.addWidget(self.home_today_title)
        today_layout.addWidget(self.home_today_meta)

        today_actions = QHBoxLayout()
        today_actions.setSpacing(10)
        self.home_today_button = QPushButton("Evenement openen →")
        self.home_today_button.setObjectName("primaryButton")
        self.home_today_button.setMinimumWidth(160)
        self.home_today_button.clicked.connect(self._open_home_today_event)
        today_actions.addWidget(self.home_today_button)
        self.home_today_live_button = QPushButton("Live sessie →")
        self.home_today_live_button.setObjectName("primaryButton")
        self.home_today_live_button.setMinimumWidth(160)
        self.home_today_live_button.clicked.connect(self._open_home_today_live_session)
        today_actions.addWidget(self.home_today_live_button)
        today_actions.addStretch(1)
        today_layout.addLayout(today_actions)
        layout.addWidget(today_box)

        activity_box = QGroupBox("Recente activiteit")
        activity_box.setObjectName("dashboardPanel")
        activity_layout = QVBoxLayout(activity_box)
        activity_layout.setContentsMargins(14, 12, 14, 12)
        self.home_activity_label = QLabel("Nog geen recente activiteit.")
        self.home_activity_label.setObjectName("hintLabel")
        self.home_activity_label.setWordWrap(True)
        activity_layout.addWidget(self.home_activity_label)
        layout.addWidget(activity_box)

        self._home_today_event_id = ""
        self.page_stack.addWidget(home)

    def _build_events_page(self):
        home = QWidget()
        self.events_page = home
        home_layout = QVBoxLayout(home)
        self.home_layout = home_layout
        home_layout.setContentsMargins(0, 0, 0, 0)
        home_layout.setSpacing(8)

        home_content = QWidget()
        home_content_layout = QVBoxLayout(home_content)
        home_content_layout.setContentsMargins(18, 4, 18, 6)
        home_content_layout.setSpacing(8)

        # Command-center hero: one clear welcome area with the actions used most.
        hero = QFrame()
        hero.setObjectName("dashboardHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 10, 20, 10)
        hero_layout.setSpacing(12)
        hero.setMaximumHeight(88)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(4)
        self.home_welcome = QLabel("Welkom bij EventHub")
        self.home_welcome.setObjectName("heroTitle")
        hero_subtitle = QLabel("Beheer evenementen, deelnemers, taken en live operaties vanuit één werkruimte.")
        hero_subtitle.setObjectName("heroSubtitle")
        hero_subtitle.setWordWrap(True)
        hero_copy.addWidget(self.home_welcome)
        hero_copy.addWidget(hero_subtitle)
        hero_layout.addLayout(hero_copy, 1)

        hero_actions = QHBoxLayout()
        hero_actions.setSpacing(8)
        self.new_event_button = QPushButton("＋  Nieuw evenement")
        self.new_event_button.setObjectName("primaryButton")
        self.new_event_button.clicked.connect(lambda _checked=False: self.new_project())
        hero_actions.addWidget(self.new_event_button)
        event_control_button = QPushButton("Event Control")
        event_control_button.setObjectName("secondaryButton")
        event_control_button.clicked.connect(self.show_event_control_page)
        hero_actions.addWidget(event_control_button)
        hero_layout.addLayout(hero_actions)
        home_content_layout.addWidget(hero)

        # De tellerbalk met evenementen, open taken en bezoekers is vervallen.
        # Een totaal over alle evenementen zegt niet welk evenement aandacht
        # vraagt; dat staat nu op de kaart van het evenement zelf.
        upcoming_box = QGroupBox("Evenementen")
        upcoming_box.setObjectName("dashboardPanel")
        upcoming_box.setMinimumHeight(300)
        upcoming_layout = QVBoxLayout(upcoming_box)
        upcoming_layout.setContentsMargins(14, 14, 14, 12)
        upcoming_layout.setSpacing(8)
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.event_search_box = QLineEdit()
        self.event_search_box.setPlaceholderText("Zoeken op naam, plaats, locatie, soort of datum…")
        self.event_search_box.setClearButtonEnabled(True)
        self.event_search_box.setMinimumWidth(220)
        self.event_search_box.textChanged.connect(self._filter_events)
        search_row.addWidget(self.event_search_box, 1)
        self.event_status_filter = ScrollSafeComboBox()
        self.event_status_filter.addItem("Alle statussen", "")
        self.event_status_filter.addItem("Alleen lopend en gepland", "_open")
        for status in EVENT_STATUSES:
            self.event_status_filter.addItem(status, status)
        # Standaard alles tonen: de nieuwe sortering zet lopende evenementen al
        # bovenaan, dus verbergen is niet nodig en zou verwarrend zijn.
        self.event_status_filter.setCurrentIndex(0)
        self.event_status_filter.currentIndexChanged.connect(self._filter_events)
        search_row.addWidget(self.event_status_filter)
        # Dezelfde filters als in het keuzevenster, zodat beide schermen zich
        # hetzelfde laten bedienen.
        self.event_type_filter = ScrollSafeComboBox()
        self.event_type_filter.addItem("Alle soorten", "")
        for soort in EVENT_TYPES:
            self.event_type_filter.addItem(soort, soort)
        self.event_type_filter.currentIndexChanged.connect(self._filter_events)
        search_row.addWidget(self.event_type_filter)
        self.event_date_filter = QLineEdit()
        self.event_date_filter.setPlaceholderText("dd-mm-jjjj")
        self.event_date_filter.setClearButtonEnabled(True)
        self.event_date_filter.setMaximumWidth(140)
        self.event_date_filter.textChanged.connect(self._filter_events)
        search_row.addWidget(with_date_picker(self.event_date_filter))
        self.show_archived_events = QCheckBox("Gearchiveerd")
        self.show_archived_events.setChecked(
            self.settings.value("show_archived_events", False, type=bool)
        )
        self.show_archived_events.toggled.connect(self._show_archived_events_changed)
        search_row.addWidget(self.show_archived_events)
        self.event_sort_mode = ScrollSafeComboBox()
        for label, value in EVENT_SORT_MODES:
            self.event_sort_mode.addItem(label, value)
        stored = str(self.settings.value("event_sort_mode", "smart") or "smart")
        self.event_sort_mode.setCurrentIndex(max(0, self.event_sort_mode.findData(stored)))
        self.event_sort_mode.setToolTip(
            "Slim zet eerst wat eraan komt en daarna het verleden; de datumopties sorteren "
            "de hele lijst doorlopend."
        )
        self.event_sort_mode.currentIndexChanged.connect(self._event_sort_changed)
        search_row.addWidget(self.event_sort_mode)
        self.event_filter_summary = QLabel("")
        self.event_filter_summary.setObjectName("hintLabel")
        search_row.addWidget(self.event_filter_summary)
        search_row.addStretch(1)
        self.view_toggle_button = QPushButton("Lijst")
        self.view_toggle_button.setObjectName("viewToggleButton")
        self.view_toggle_button.clicked.connect(self._toggle_event_view)
        search_row.addWidget(self.view_toggle_button)
        upcoming_layout.addLayout(search_row)

        # De knoppen Openen, Aanpassen en Verwijderen zijn vervallen: dubbelklikken
        # opent een evenement, en de acties staan onder de knop met de drie
        # puntjes op de kaart. Een permanent zichtbare verwijderknop naast een
        # lijst is bovendien een ongeluk dat op zijn beurt wacht.
        self._board_collapsed = {"geweest": True}
        self._board_searching = False
        self._board_selected_id = ""
        self._event_cards = []
        # Twintig kaarten opbouwen kost een fractie van een seconde. Bij elke
        # toetsaanslag in het zoekvak is dat merkbaar, dus wachten we tot de
        # vingers even stilstaan.
        self._board_pending = []
        self._board_timer = QTimer(self)
        self._board_timer.setSingleShot(True)
        self._board_timer.setInterval(120)
        self._board_timer.timeout.connect(
            lambda: self._refresh_event_board(self._board_pending)
        )
        self.event_board = QScrollArea()
        self.event_board.setObjectName("eventBoard")
        self.event_board.setWidgetResizable(True)
        self.event_board.setFrameShape(QFrame.Shape.NoFrame)
        self.event_board.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        board_body = QWidget()
        board_body.setObjectName("eventBoardBody")
        self.event_board_layout = QVBoxLayout(board_body)
        self.event_board_layout.setContentsMargins(0, 4, 6, 4)
        self.event_board_layout.setSpacing(4)
        self.event_board.setWidget(board_body)

        self.home_event_table = self._new_table(["Datum", "Evenement", "Soort", "Plaats / locatie", "Status", "Bezoekers"])
        self.home_event_table.setObjectName("dashboardTable")
        # Het evenementenoverzicht is het primaire werkvlak: toon op normale laptops
        # meerdere evenementen tegelijk in plaats van één gigantische rij.
        self.home_event_table.setMinimumHeight(210)
        self.home_event_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.home_event_table.verticalHeader().setDefaultSectionSize(42)
        header = self.home_event_table.horizontalHeader()
        header.setStretchLastSection(False)
        # Fit the complete dashboard table inside the available width. The two
        # descriptive columns consume leftover space; compact metadata columns
        # size to their contents. This prevents a horizontal scrollbar from
        # appearing inside the primary event list.
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.home_event_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.home_event_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.home_event_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.home_event_table.cellDoubleClicked.connect(lambda *_: self.activate_selected_event())
        # De status stond alleen onderaan een lang formulier; hier is hij met
        # twee klikken te wijzigen.
        self.home_event_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.home_event_table.customContextMenuRequested.connect(self._show_event_context_menu)

        # Kaarten om te bladeren, de tabel om te vergelijken. De tabel blijft
        # ook onder de kaarten de bron voor de selectie, zodat Openen,
        # Aanpassen en Verwijderen ongewijzigd blijven werken.
        self.event_view_stack = QStackedWidget()
        self.event_view_stack.addWidget(self.event_board)
        self.event_view_stack.addWidget(self.home_event_table)
        upcoming_layout.addWidget(self.event_view_stack)
        self._set_event_view(str(self.settings.value("event_view_mode", "kaarten") or "kaarten"))
        home_content_layout.addWidget(upcoming_box, 1)
        home_layout.addWidget(home_content, 1)
        self.event_table = self.home_event_table
        self.page_stack.addWidget(home)

    def _build_event_control_page(self):
        page = QWidget()
        self.event_control_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 4, 18, 18)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading = QLabel("Event Control")
        heading.setObjectName("sectionTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch()
        heading_row.addWidget(QLabel("Evenement:"))
        self.event_control_event_combo = EventPickerButton(allow_none=True)
        self.event_control_event_combo.set_registration_counter(self._registration_lines)
        self.event_control_event_combo.setMinimumWidth(300)
        self.event_control_event_combo.changed.connect(self._event_control_event_changed)
        heading_row.addWidget(self.event_control_event_combo)
        back_button = QPushButton("← Evenementen")
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(self.back_to_home)
        heading_row.addWidget(back_button)
        layout.addLayout(heading_row)

        intro = QLabel(
            "Registreer lokale presentie of start een gedeelde sessie waarmee meerdere laptops, "
            "tablets en telefoons tegelijk bezoekers kunnen inchecken via hetzelfde lokale netwerk."
        )
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.event_control_context_hint = QLabel(
            "Selecteer eerst een evenement om EventControl te gebruiken."
        )
        self.event_control_context_hint.setObjectName("statusLabel")
        self.event_control_context_hint.setWordWrap(True)
        self.event_control_context_hint.setVisible(False)
        layout.addWidget(self.event_control_context_hint)

        self.event_control_tabs = QTabWidget()
        self.event_control_tabs.setDocumentMode(True)

        # Als attribuut bewaren: de knop Live sessie op het startscherm en de
        # losse uitleg schakelen hier naartoe.
        self.live_session_tab = live_session_tab = QWidget()
        live_session_layout = QVBoxLayout(live_session_tab)
        live_session_layout.setContentsMargins(18, 18, 18, 18)
        live_session_heading = QHBoxLayout()
        live_session_title = QLabel("Live sessies")
        live_session_title.setObjectName("sectionTitle")
        live_session_heading.addWidget(live_session_title)
        live_session_heading.addStretch()
        # Losse uitleg naast de hoofdrondleiding: live sessies vragen om context
        # op de plek zelf, en de algemene rondleiding zou er te lang van worden.
        self.live_session_help_button = QPushButton("?")
        self.live_session_help_button.setObjectName("secondaryButton")
        self.live_session_help_button.setProperty("picker", "true")
        self.live_session_help_button.setFixedWidth(34)
        self.live_session_help_button.setToolTip(
            "Korte uitleg over samen inchecken met meerdere apparaten."
        )
        self.live_session_help_button.clicked.connect(self.start_live_session_tour)
        live_session_heading.addWidget(self.live_session_help_button)
        self.live_manual_button = _make_button_compact(QPushButton("Handleiding"))
        self.live_manual_button.setObjectName("secondaryButton")
        self.live_manual_button.setToolTip(
            "Open de handleiding voor medewerkers op locatie."
        )
        self.live_manual_button.clicked.connect(self.open_live_session_manual)
        live_session_heading.addWidget(self.live_manual_button)
        live_session_text = QLabel(
            "Het gekozen evenement is leidend. Start een nieuwe livesessie voor dit evenement of verbind dit apparaat "
            "met een actieve livesessie op het lokale netwerk."
        )
        live_session_text.setObjectName("hintLabel")
        live_session_text.setWordWrap(True)
        self.live_session_status_label = QLabel("Er is vanuit dit venster nog geen live sessie geopend.")
        self.live_session_status_label.setObjectName("statusLabel")

        self.live_choices_widget = QWidget()
        choices = QHBoxLayout(self.live_choices_widget)
        choices.setContentsMargins(0, 0, 0, 0)
        choices.setSpacing(16)

        self.live_start_card = start_card = QFrame()
        start_card.setObjectName("liveChoiceCardPrimary")
        start_card.setMinimumHeight(210)
        start_layout = QVBoxLayout(start_card)
        start_layout.setContentsMargins(22, 20, 22, 20)
        start_layout.setSpacing(8)
        start_eyebrow = QLabel("HOST")
        start_eyebrow.setObjectName("choiceEyebrow")
        start_title = QLabel("＋  Livesessie hosten")
        start_title.setObjectName("choiceTitle")
        start_text = QLabel("Start een nieuwe livesessie. Naam, datum, locatie en deelnemers worden uit het gekozen evenement overgenomen.")
        start_text.setObjectName("choiceText")
        start_text.setWordWrap(True)
        self.start_live_button = start_live_button = QPushButton("Live sessie starten  →")
        start_live_button.setObjectName("primaryButton")
        start_live_button.clicked.connect(self.open_live_session_manager)
        self.reopen_previous_live_button = QPushButton("Vorige sessie opnieuw openen")
        self.reopen_previous_live_button.setObjectName("secondaryButton")
        self.reopen_previous_live_button.clicked.connect(self.reopen_previous_live_session)
        start_layout.addWidget(start_eyebrow)
        start_layout.addWidget(start_title)
        start_layout.addWidget(start_text)
        start_layout.addStretch()
        start_layout.addWidget(start_live_button)
        start_layout.addWidget(self.reopen_previous_live_button)
        choices.addWidget(start_card, 1)

        self.live_join_card = join_card = QFrame()
        join_card.setObjectName("liveChoiceCard")
        join_card.setMinimumHeight(210)
        join_layout = QVBoxLayout(join_card)
        join_layout.setContentsMargins(22, 20, 22, 20)
        join_layout.setSpacing(8)
        join_eyebrow = QLabel("DEELNEMEN")
        join_eyebrow.setObjectName("choiceEyebrow")
        join_title = QLabel("⇄  Verbinden met livesessie")
        join_title.setObjectName("choiceTitle")
        join_text = QLabel(
            "Open de EventHub-webclient om vanaf dit apparaat deel te nemen aan een actieve sessie."
        )
        join_text.setObjectName("choiceText")
        join_text.setWordWrap(True)
        self.connect_page_button = connect_page_button = QPushButton("Verbinden als incheckpunt  →")
        connect_page_button.setObjectName("secondaryButton")
        connect_page_button.clicked.connect(self.open_live_webclient)
        join_layout.addWidget(join_eyebrow)
        join_layout.addWidget(join_title)
        join_layout.addWidget(join_text)
        join_layout.addStretch()
        join_layout.addWidget(connect_page_button)
        choices.addWidget(join_card, 1)

        live_session_layout.addLayout(live_session_heading)
        live_session_layout.addWidget(live_session_text)
        live_session_layout.addSpacing(8)
        live_session_layout.addWidget(self.live_choices_widget)

        self.live_active_card = QFrame()
        self.live_active_card.setObjectName("liveChoiceCardPrimary")
        active_layout = QHBoxLayout(self.live_active_card)
        active_layout.setContentsMargins(22, 18, 22, 18)
        active_text = QVBoxLayout()
        active_text.setSpacing(4)
        self.live_active_title_label = QLabel("Livesessie actief")
        self.live_active_title_label.setObjectName("choiceTitle")
        self.live_active_event_label = QLabel("")
        self.live_active_event_label.setObjectName("choiceText")
        self.live_active_meta_label = QLabel("")
        self.live_active_meta_label.setObjectName("statusLabel")
        active_text.addWidget(self.live_active_title_label)
        active_text.addWidget(self.live_active_event_label)
        active_text.addWidget(self.live_active_meta_label)
        active_layout.addLayout(active_text, 1)
        self.live_manage_button = QPushButton("Beheer openen")
        self.live_manage_button.setObjectName("primaryButton")
        self.live_manage_button.clicked.connect(self._open_selected_live_manager)
        self.live_dashboard_button = QPushButton("Dashboard openen")
        self.live_dashboard_button.setObjectName("secondaryButton")
        self.live_dashboard_button.clicked.connect(self.open_live_dashboard)
        active_layout.addWidget(self.live_manage_button)
        active_layout.addWidget(self.live_dashboard_button)
        self.live_active_card.setVisible(False)
        live_session_layout.addWidget(self.live_active_card)
        live_session_layout.addWidget(self.live_session_status_label)
        live_session_layout.addStretch()
        self.event_control_tabs.addTab(live_session_tab, "Live sessie")

        rudder_tab = QWidget()
        rudder_layout = QVBoxLayout(rudder_tab)
        rudder_layout.setContentsMargins(18, 18, 18, 18)
        rudder_title = QLabel("Rudder aanwezigheidsregistratie")
        rudder_title.setObjectName("sectionTitle")
        rudder_text = QLabel(
            "Exporteer de gekozen EventHub-presentie rechtstreeks naar de Rudder-pagina Registratie opkomst. "
            "De browserassistent toont eerst een controleoverzicht en vult daarna Yes en No in. Bestaande "
            "Canceled-statussen blijven behouden; resterende Unknown-statussen worden na controle op No gezet."
        )
        rudder_text.setObjectName("hintLabel")
        rudder_text.setWordWrap(True)
        self.rudder_status_label = QLabel("Er is nog geen Rudder-export gestart.")
        self.rudder_status_label.setObjectName("statusLabel")
        direct_rudder_button = _make_button_compact(QPushButton("Exporteren naar Rudder"))
        direct_rudder_button.setObjectName("primaryButton")
        direct_rudder_button.clicked.connect(self.export_directly_to_rudder)
        open_rudder_button = _make_button_compact(QPushButton("Rudder-link instellen / openen"))
        open_rudder_button.setObjectName("secondaryButton")
        open_rudder_button.clicked.connect(self.open_rudder_attendance_page)
        rudder_layout.addWidget(rudder_title)
        rudder_layout.addWidget(rudder_text)
        rudder_layout.addSpacing(8)
        rudder_layout.addWidget(self.rudder_status_label)
        rudder_layout.addWidget(direct_rudder_button)
        rudder_layout.addWidget(open_rudder_button)
        rudder_layout.addStretch()
        self.event_control_tabs.addTab(rudder_tab, "Rudder")

        layout.addWidget(self.event_control_tabs, 1)
        self.page_stack.addWidget(page)

        self.event_control_live_timer = QTimer(self)
        self.event_control_live_timer.setInterval(1000)
        self.event_control_live_timer.timeout.connect(self._refresh_event_control_live_state)
        self.event_control_live_timer.start()

    def _build_trends_page(self):
        page = QWidget()
        self.trends_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 4, 18, 18)
        layout.setSpacing(10)

        self.trend_sources: list[dict] = []
        self.current_analysis = str(self.settings.value("current_analysis", "") or "") or "Losse analyse"
        self.trend_tabs = QTabWidget()
        self.trend_tabs.setDocumentMode(True)
        self.trend_tabs.currentChanged.connect(lambda _index: self._render_trends())
        # Exporteren geldt voor het werkgebied dat openstaat, dus hoort de knop
        # bij de tabbladen en niet tussen de filters van één van beide.
        self.trend_export_button = QPushButton("Exporteren")
        self.trend_export_button.setObjectName("primaryButton")
        self.trend_export_button.setToolTip(
            "Stel een rapport samen: kies de inhoud, bekijk het voorbeeld en "
            "exporteer naar PDF of Excel"
        )
        self.trend_export_button.clicked.connect(lambda: self.export_trend_data())
        trend_actions = QWidget()
        trend_actions_layout = QHBoxLayout(trend_actions)
        trend_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.trend_help_button = QPushButton("?")
        self.trend_help_button.setObjectName("secondaryButton")
        self.trend_help_button.setFixedWidth(32)
        self.trend_help_button.setToolTip("Uitleg over Trends en exporteren")
        self.trend_help_button.setAccessibleName("Rondleiding door Trends")
        self.trend_help_button.clicked.connect(self.start_trends_tour)
        trend_actions_layout.addWidget(self.trend_help_button)
        trend_actions_layout.addWidget(self.trend_export_button)
        self.trend_tabs.setCornerWidget(trend_actions, Qt.Corner.TopRightCorner)

        # Werkgebied 1: de evenementen uit het geopende dossier.
        own_tab = QWidget()
        own_layout = QVBoxLayout(own_tab)
        own_layout.setContentsMargins(0, 0, 0, 0)
        self.trend_incomplete_notice = QLabel()
        self.trend_incomplete_notice.setObjectName("hintLabel")
        self.trend_incomplete_notice.setWordWrap(True)
        self.trend_incomplete_notice.hide()
        own_layout.addWidget(self.trend_incomplete_notice)
        self.own_trend_panel = TrendPanel(
            self._own_trend_summaries,
            self._open_trend_event,
        )
        self.own_trend_panel.empty_message = (
            "Nog geen cijfers. Een evenement krijgt cijfers zodra de datum is geweest."
        )
        own_layout.addWidget(self.own_trend_panel)
        self.own_trend_panel.chrome = [self.own_trend_panel.summary]
        self.trend_tabs.addTab(own_tab, "Eigen evenementen")

        # Werkgebied 2: uitsluitend wat hier is ingeladen. Bewust gescheiden van
        # het dossier, zodat een losse analyse de eigen cijfers niet vertroebelt.
        loose_tab = QWidget()
        loose_layout = QVBoxLayout(loose_tab)
        loose_layout.setContentsMargins(0, 8, 0, 0)
        loose_layout.setSpacing(8)

        # De bediening van een losse analyse staat bewust in een apart venster:
        # zo neemt bronbeheer geen permanente horizontale ruimte in beslag.
        self.analysis_picker = ScrollSafeComboBox()
        self.analysis_picker.setToolTip(
            "Een analyse blijft bewaard. Voeg na elk evenement de nieuwe lijst toe zonder alles opnieuw in te laden."
        )
        self.analysis_picker.currentIndexChanged.connect(self._analysis_picked)
        self.trend_manage_button = _make_button_compact(QPushButton("✎  Analyse beheren"))
        self.trend_manage_button.setObjectName("primaryButton")
        self.trend_manage_button.setMaximumWidth(190)
        self.trend_manage_button.setToolTip("Analyse kiezen, lijsten inladen en sets beheren")
        self.trend_manage_button.clicked.connect(self._open_trend_source_management)
        self.trend_source = ScrollSafeComboBox()
        self.trend_source.currentIndexChanged.connect(lambda _index: self._render_trends())

        self.trend_source_list = QTableWidget(0, 3)
        self.trend_source_list.setHorizontalHeaderLabels(["Ingeladen set", "Evenementen", "Deelnemers"])
        self.trend_source_list.setObjectName("dashboardTable")
        self.trend_source_list.verticalHeader().setVisible(False)
        self.trend_source_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.trend_source_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.trend_source_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.trend_source_list.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.trend_source_list.setMaximumHeight(92)
        self.trend_source_list.setVisible(False)

        self.loose_trend_panel = TrendPanel(self._loose_trend_summaries)
        self.loose_trend_panel.open_event_callback = self._open_trend_event
        self.loose_trend_panel.empty_message = (
            "Nog niets ingeladen. Kies Bezoekerslijsten inladen om een losse analyse te maken, "
            "bijvoorbeeld over evenementen van een collega. De eigen evenementen tellen hier niet mee."
        )
        self.loose_trend_panel.filter_bar_layout.insertWidget(0, self.trend_manage_button)
        loose_layout.addWidget(self.loose_trend_panel, 1)
        self.loose_trend_panel.chrome = [
            self.trend_manage_button, self.loose_trend_panel.summary,
        ]
        self.trend_tabs.addTab(loose_tab, "Losse analyse")

        layout.addWidget(self.trend_tabs, 1)
        self.page_stack.addWidget(page)

    def _build_profile_page(self):
        page = QWidget()
        self.profile_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 4, 18, 18)
        layout.setSpacing(16)
        heading = QLabel("Mijn profiel")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        intro = QLabel(
            "Uw persoonlijke gegevens worden uitsluitend lokaal bewaard en automatisch gebruikt in 5WH's en evaluatieformulieren."
        )
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        card = QFrame()
        card.setObjectName("toolbar")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(22, 22, 22, 22)
        icon_label = QLabel()
        profile_icon = SIDEBAR_ICON_PATHS.get("profile")
        if profile_icon and profile_icon.exists():
            icon_label.setPixmap(QPixmap(str(profile_icon)).scaled(
                96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
        icon_label.setFixedSize(112, 112)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon_label)
        details = QFormLayout()
        self.profile_name_label = QLabel("—")
        self.profile_function_label = QLabel("—")
        self.profile_email_label = QLabel("—")
        self.profile_phone_label = QLabel("—")
        self.profile_signature_label = QLabel("—")
        self.profile_signature_label.setWordWrap(True)
        details.addRow("Naam:", self.profile_name_label)
        details.addRow("Functie:", self.profile_function_label)
        details.addRow("E-mailadres:", self.profile_email_label)
        details.addRow("06-nummer:", self.profile_phone_label)
        details.addRow("Handtekening:", self.profile_signature_label)
        card_layout.addLayout(details, 1)
        edit_button = QPushButton("Profiel aanpassen")
        edit_button.setObjectName("primaryButton")
        edit_button.clicked.connect(self.edit_profile)
        card_layout.addWidget(edit_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(card)
        profile_note = QLabel("De handtekening wordt desgewenst automatisch onder WhatsApp-berichten geplaatst.")
        profile_note.setObjectName("hintLabel")
        profile_note.setWordWrap(True)
        layout.addWidget(profile_note)
        layout.addStretch()
        self.page_stack.addWidget(page)

    def _build_standard_tasks_page(self):
        page = QWidget()
        self.standard_tasks_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 4, 18, 18)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading = QLabel("Standaardtaken")
        heading.setObjectName("sectionTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch()
        back_button = QPushButton("← Evenementen")
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(self.back_to_home)
        heading_row.addWidget(back_button)
        layout.addLayout(heading_row)

        intro = QLabel(
            "Deze taken worden automatisch toegevoegd aan nieuwe evenementen. Per taak "
            "kiest u voor welke soorten evenementen hij meekomt; deadlines en "
            "meldtermijnen blijven daarna per evenement aanpasbaar."
        )
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.standard_tasks_table = self._new_table(["Taak", "Geldt voor", "Planning", "Melding"])
        self.standard_tasks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.standard_tasks_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.standard_tasks_table.cellDoubleClicked.connect(lambda *_: self.edit_standard_task())
        self._attach_row_menu(self.standard_tasks_table, [
            ("Taak bewerken", self.edit_standard_task),
            (None, None),
            ("Taak verwijderen", self.remove_standard_task),
        ])
        layout.addWidget(self.standard_tasks_table, 1)

        actions = QHBoxLayout()
        add_button = QPushButton("Taak toevoegen")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self.add_standard_task)
        for button in (add_button,):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.page_stack.addWidget(page)

    def _build_open_tasks_page(self):
        page = QWidget()
        self.open_tasks_page = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 10, 22, 18)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        heading = QLabel("Taken")
        heading.setObjectName("sectionTitle")
        subtitle = QLabel("Werk openstaande acties af over alle evenementen.")
        subtitle.setObjectName("hintLabel")
        title_box.addWidget(heading)
        title_box.addWidget(subtitle)
        heading_row.addLayout(title_box)
        heading_row.addStretch()
        back_button = QPushButton("← Evenementen")
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(self.back_to_home)
        heading_row.addWidget(back_button)
        layout.addLayout(heading_row)

        # Compacte statusregel: informatie, geen verzameling decoratieve cards.
        summary = QFrame()
        summary.setObjectName("subtlePanel")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 10, 16, 10)
        summary_layout.setSpacing(18)
        self.task_summary_total = QLabel("0 open")
        self.task_summary_overdue = QLabel("0 te laat")
        self.task_summary_today = QLabel("0 vandaag")
        self.task_summary_upcoming = QLabel("0 binnenkort")
        for label in (self.task_summary_total, self.task_summary_overdue,
                      self.task_summary_today, self.task_summary_upcoming):
            label.setObjectName("taskSummaryLabel")
            summary_layout.addWidget(label)
        summary_layout.addStretch()
        summary_layout.addWidget(QLabel("Weergave:"))
        self.open_tasks_filter = ScrollSafeComboBox()
        self.open_tasks_filter.addItems(["Alle open taken", "Te laat", "Vandaag", "Binnenkort", "Later"])
        self.open_tasks_filter.setMinimumWidth(165)
        self.open_tasks_filter.currentIndexChanged.connect(self._render_open_tasks_page)
        summary_layout.addWidget(self.open_tasks_filter)
        layout.addWidget(summary)

        self.open_tasks_table = self._new_table(["Deadline", "Evenement", "Taak", "Status"])
        self.open_tasks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.open_tasks_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.open_tasks_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.open_tasks_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.open_tasks_table.verticalHeader().setDefaultSectionSize(42)
        header = self.open_tasks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.open_tasks_table.cellDoubleClicked.connect(lambda *_: self.open_selected_open_task())
        self._attach_row_menu(self.open_tasks_table, [
            ("Taak openen", self.open_selected_open_task),
            ("Markeren als afgerond", self.complete_selected_open_task),
        ])
        layout.addWidget(self.open_tasks_table, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        layout.addLayout(actions)
        self.page_stack.addWidget(page)

    def _open_task_rows(self):
        rows = []
        for event in self.events:
            if event.get("status") == "Geannuleerd":
                continue
            for task in event.get("tasks", []):
                if bool(task.get("done", False)):
                    continue
                due = task_due_date(event, task)
                rows.append((due or date.max, normalize(event.get("name", "")),
                             normalize(task.get("title", "")), event, task))
        return sorted(rows, key=lambda row: row[:3])

    def _task_bucket(self, due):
        if not due or due == date.max:
            return "Later"
        today = date.today()
        if due < today:
            return "Te laat"
        if due == today:
            return "Vandaag"
        if due <= today + timedelta(days=7):
            return "Binnenkort"
        return "Later"

    def _render_open_tasks_page(self):
        if not hasattr(self, "open_tasks_table"):
            return
        rows = self._open_task_rows()
        buckets = Counter(self._task_bucket(due) for due, *_ in rows)
        if hasattr(self, "task_summary_total"):
            self.task_summary_total.setText(f"{len(rows)} open")
            self.task_summary_overdue.setText(f"{buckets.get('Te laat', 0)} te laat")
            self.task_summary_today.setText(f"{buckets.get('Vandaag', 0)} vandaag")
            self.task_summary_upcoming.setText(f"{buckets.get('Binnenkort', 0)} binnenkort")

        selected_filter = self.open_tasks_filter.currentText() if hasattr(self, "open_tasks_filter") else "Alle open taken"
        if selected_filter != "Alle open taken":
            rows = [row for row in rows if self._task_bucket(row[0]) == selected_filter]

        self.open_tasks_table.clearSpans()
        self.open_tasks_table.setRowCount(len(rows))
        for row_index, (due_key, _event_key, _task_key, event, task) in enumerate(rows):
            due = None if due_key == date.max else due_key
            state = task_state(event, task)
            values = [due.strftime("%d-%m-%Y") if due else "—", event.get("name", ""),
                      task.get("title", ""), state]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.ItemDataRole.UserRole, (event.get("id", ""), task.get("id", "")))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                # Geen volledige alarmkleur over de hele rij; status blijft leesbaar zonder kermis.
                if column == 3 and state == "Te laat":
                    item.setForeground(QColor("#ff6b81"))
                elif column == 3 and state == "Vandaag":
                    item.setForeground(QColor("#f6c453"))
                self.open_tasks_table.setItem(row_index, column, item)
        if not rows:
            self.open_tasks_table.setRowCount(1)
            message = "Geen taken in deze weergave."
            if selected_filter == "Alle open taken":
                message = "Geen onafgeronde taken. De administratie heeft zich uitzonderlijk overgegeven."
            item = QTableWidgetItem(message)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.open_tasks_table.setSpan(0, 0, 1, 4)
            self.open_tasks_table.setItem(0, 0, item)

    def _selected_open_task(self):
        row = self.open_tasks_table.currentRow()
        item = self.open_tasks_table.item(row, 0) if row >= 0 else None
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(data, (tuple, list)) or len(data) != 2:
            return None, None
        event = self._event_by_id(data[0])
        task = next((task for task in event.get("tasks", []) if task.get("id") == data[1]), None) if event else None
        return event, task

    def show_open_tasks_page(self):
        self.page_stack.setCurrentWidget(self.open_tasks_page)
        self._set_project_context_ui(False)
        self._set_navigation_active("tasks")
        self._render_open_tasks_page()

    def open_selected_open_task(self):
        event, task = self._selected_open_task()
        if not event or not task:
            QMessageBox.information(self, "Geen taak gekozen", "Selecteer eerst een onafgeronde taak.")
            return
        self.open_event(event, self.tasks_tab)
        self._select_task(task.get("id", ""))

    def complete_selected_open_task(self):
        event, task = self._selected_open_task()
        if not task:
            QMessageBox.information(self, "Geen taak gekozen", "Selecteer eerst een onafgeronde taak.")
            return
        task["done"] = True
        task["completed_on"] = date.today().strftime("%d-%m-%Y")
        self._sync_event_status_from_tasks(event)
        self._mark_dirty()
        self._render_all()
        self._render_open_tasks_page()

    def show_standard_tasks_page(self):
        self.page_stack.setCurrentWidget(self.standard_tasks_page)
        self._set_project_context_ui(False)
        self._set_navigation_active(None)
        self._render_standard_tasks_page()

    def show_event_control_page(self):
        self._sync_event_combo(self.event_control_event_combo)
        # De gedeelde evenementcontext en de keuzelijst worden tegelijk
        # bijgehouden. Zo kan een oude schermkeuze nooit stilletjes leidend zijn.
        event = self._combo_event(self.event_control_event_combo)
        if event is not None:
            self.active_event_id = event.get("id", "")
            self.selected_events = {event.get("name", "")}
        else:
            self.active_event_id = ""
            self.selected_events = set()
        self.page_stack.setCurrentWidget(self.event_control_page)
        self._set_project_context_ui(False)
        self._set_navigation_active("event_control")
        # Dit scherm wordt vaak tijdens de ontvangst geopend. Bouw daarom
        # alleen de presentielijst opnieuw op, niet alle tabellen en grafieken
        # van de volledige applicatie.
        self._render_presence_table()
        self._update_previous_live_session_action()
        self._update_presence_registration_availability()
        self._refresh_event_control_live_state()
        self._set_live_session_context_status()

    def _after_sales_event_changed(self, _index=None):
        event = self._combo_event(self.after_sales_event_combo)
        if event is None:
            self.active_event_id = ""
            self.selected_events = set()
        else:
            self._touch_event(event, opened=True)
            self.active_event_id = event.get("id", "")
            self.selected_events = {event.get("name", "")}
            self._sync_latest_live_attendance_for_event(event)
        self._sync_event_context_pickers()
        self._render_all()

    def _event_control_event_changed(self, _index=None):
        event = self._combo_event(self.event_control_event_combo)
        if event is None:
            self.active_event_id = ""
            self.selected_events = set()
        else:
            self._touch_event(event, opened=True)
            self.active_event_id = event.get("id", "")
            self.selected_events = {event.get("name", "")}
        self._sync_event_context_pickers()
        self._render_event_control_scope()
        self._refresh_event_control_live_state()
        self._set_live_session_context_status()

    def _event_control_selected_event(self):
        """Het evenement bovenaan EventControl is voor alle acties leidend."""
        if not hasattr(self, "event_control_event_combo"):
            return None
        return self._combo_event(self.event_control_event_combo)

    def _set_live_session_context_status(self):
        if not hasattr(self, "live_session_status_label"):
            return
        event = self._event_control_selected_event()
        if not event:
            self.live_session_status_label.setText("Kies eerst een evenement.")
            return
        event_name = str(event.get("name", "") or "het gekozen evenement")
        window = self._active_live_server_window(event)
        if window is not None:
            state = "actief" if getattr(window, "server_thread", None) is not None else "voorbereid"
            self.live_session_status_label.setText(
                f"De livesessie van {event_name} is {state} en kan hierboven worden geopend."
            )
        elif self._previous_live_session_for_event(event):
            self.live_session_status_label.setText(
                f"Voor {event_name} is een opgeslagen livesessie beschikbaar."
            )
        else:
            self.live_session_status_label.setText(
                f"Voor {event_name} is nog geen livesessie geopend."
            )

    def _previous_live_session_for_event(self, event=None):
        event = event or self._event_control_selected_event()
        if not event:
            return None
        try:
            from server.services import session_service as live_session_service
        except Exception:
            return None
        source_event_id = str(event.get("id", "") or "").strip()
        event_name = str(event.get("name", "") or "").strip().casefold()
        event_date = str(event.get("date", "") or "").strip()
        for session in live_session_service.list_recent_sessions():
            linked_id = str(session.get("source_event_id", "") or "").strip()
            if source_event_id and linked_id == source_event_id:
                return session
            # Compatibiliteit met sessies van vóór de expliciete evenementkoppeling.
            if not linked_id and event_name and event_date \
                    and str(session.get("name", "") or "").strip().casefold() == event_name \
                    and str(session.get("date", "") or "").strip() == event_date:
                return session
        return None

    def _update_previous_live_session_action(self):
        button = getattr(self, "reopen_previous_live_button", None)
        if button is None:
            return
        previous = self._previous_live_session_for_event()
        button.setEnabled(previous is not None)
        button.setToolTip(
            "Open de meest recente livesessie van dit evenement zonder een nieuwe run te starten."
            if previous else "Voor dit evenement is nog geen eerdere livesessie opgeslagen."
        )

    def reopen_previous_live_session(self):
        event = self._event_control_selected_event()
        if not event:
            QMessageBox.information(self, "Geen evenement", "Kies eerst een evenement.")
            return
        previous = self._previous_live_session_for_event(event)
        if not previous:
            QMessageBox.information(self, "Geen vorige sessie", "Voor dit evenement is nog geen eerdere livesessie opgeslagen.")
            self._update_previous_live_session_action()
            return
        session_id = str(previous.get("id", "") or "").strip()
        for existing_window in list(self._live_server_windows):
            if existing_window is not None and str(getattr(existing_window, "event_id", "") or "") == session_id:
                existing_window.show()
                existing_window.raise_()
                existing_window.activateWindow()
                self.live_session_status_label.setText("Vorige livesessie opnieuw geopend.")
                return
        try:
            from server.logging_setup import configure_logging
            from server.manager.manager_window import ManagerWindow
            from server.services import session_service as live_session_service
            configure_logging()
            db_path = live_session_service.resume_session(session_id)
            resumed = type("ResumedSession", (), {"id": session_id, "db_path": db_path})()
            window = ManagerWindow(resumed)
        except Exception as exc:
            QMessageBox.warning(self, "Vorige sessie kan niet openen", f"De vorige livesessie kon niet worden geopend.\n\nDetails: {exc}")
            return
        source_event_id = str(event.get("id", "") or "").strip()
        window.linked_event_id = source_event_id
        window.attendance_changed.connect(
            lambda window=window, event_id=source_event_id: self._sync_live_attendance(window, event_id)
        )
        window.server_state_changed.connect(self._live_server_state_changed)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._live_server_windows.append(window)
        window.destroyed.connect(
            lambda *_args, window=window, event_id=source_event_id:
            self._forget_live_server_window(window, event_id, offer_completion=True)
        )
        window.show()
        window.raise_()
        window.activateWindow()
        self.live_session_status_label.setText(
            f"Vorige livesessie van {event.get('name', 'het gekozen evenement')} opnieuw geopend. "
            "Er is geen nieuwe run aangemaakt."
        )
        self._refresh_event_control_live_state()

    def _active_live_server_window(self, event=None):
        self._live_server_windows = [window for window in self._live_server_windows if window is not None]
        candidates = self._live_server_windows
        if event is not None:
            event_id = str(event.get("id", "") or "").strip()
            candidates = [
                window for window in candidates
                if str(getattr(window, "linked_event_id", "") or "").strip() == event_id
            ]
        for window in reversed(candidates):
            if getattr(window, "server_thread", None) is not None:
                return window
        return candidates[-1] if candidates else None

    def _open_selected_live_manager(self):
        event = self._event_control_selected_event()
        window = self._active_live_server_window(event)
        if window is None:
            QMessageBox.information(
                self, "Geen livesessie",
                "Voor het gekozen evenement is vanuit dit venster geen livesessie geopend."
            )
            self._refresh_event_control_live_state()
            return
        window.show()
        window.raise_()
        window.activateWindow()

    def _live_server_state_changed(self, _active=False):
        self._update_presence_registration_availability()
        self._refresh_event_control_live_state()
        self._set_live_session_context_status()

    def _refresh_event_control_live_state(self):
        if not hasattr(self, "live_active_card"):
            return
        event = self._event_control_selected_event()
        window = self._active_live_server_window(event) if event else None
        has_window = window is not None
        self.live_choices_widget.setVisible(not has_window)
        self.live_active_card.setVisible(has_window)
        if not has_window:
            return

        event_name = str(event.get("name", "") or "Onbenoemd evenement")
        event_date = str(event.get("date", "") or "Datum niet opgegeven")
        running = getattr(window, "server_thread", None) is not None
        self.live_active_title_label.setText(
            "Livesessie actief" if running else "Livesessie voorbereid"
        )
        self.live_active_event_label.setText(f"{event_name}  •  {event_date}")
        meta = "Nog niet beschikbaar voor andere apparaten"
        try:
            manager_meta = str(window.session_meta_label.text() or "").strip()
            if manager_meta:
                meta = manager_meta if running else f"Server gestopt  •  {manager_meta.split('•')[-1].strip()}"
        except RuntimeError:
            pass
        self.live_active_meta_label.setText(meta)
        self.live_dashboard_button.setEnabled(running)
        self.live_dashboard_button.setToolTip(
            "Open het actuele dashboard van dit evenement."
            if running else "Start eerst de server in het sessiebeheervenster."
        )

    def open_live_session_manager(self):
        """Start één nieuwe live-run voor het gekozen EventHub-evenement.

        Het evenement is het vaste dossier; iedere keer dat dit dossier opnieuw
        live wordt gezet krijgt de uitvoering een eigen sessiedatabase. Een
        servervenster dat in deze app-run al voor hetzelfde evenement openstaat
        wordt alleen naar voren gehaald, zodat dubbel starten door dubbelklikken
        wordt voorkomen.
        """
        try:
            from server import importer as live_importer
            from server.logging_setup import configure_logging
            from server.manager.manager_window import ManagerWindow
            from server.services import participant_service as live_participant_service
            from server.services import session_service as live_session_service
        except Exception as exc:
            self._show_runtime_error("Event Control openen", exc)
            return

        active_event = self._event_control_selected_event()
        if not active_event:
            QMessageBox.information(self, "Geen evenement", "Kies eerst het evenement dat u live wilt zetten.")
            return

        source_event_id = str(active_event.get("id", "") or "").strip()
        for existing_window in list(self._live_server_windows):
            if existing_window is None:
                continue
            if str(getattr(existing_window, "linked_event_id", "") or "") == source_event_id:
                existing_window.show()
                existing_window.raise_()
                existing_window.activateWindow()
                self.live_session_status_label.setText(
                    f"Livesessie voor {active_event.get('name', 'dit evenement')} is al geopend."
                )
                return

        # Per evenement hoort er precies een livesessie te bestaan. Zeven
        # sessies voor dezelfde dag leverden zeven verschillende waarheden op -
        # van nul tot vierenvijftig inchecks - en welke daarvan werd
        # gesynchroniseerd hing af van de volgorde in de sessielijst.
        bestaande = self._previous_live_session_for_event(active_event)
        if bestaande:
            QMessageBox.information(
                self,
                "Er is al een livesessie",
                f"Voor '{active_event.get('name', 'dit evenement')}' bestaat al een livesessie.\n\n"
                "Per evenement kan er maar een zijn: met meerdere sessies raakt de "
                "aanwezigheidsregistratie verdeeld over sessies die elkaar tegenspreken.\n\n"
                "De bestaande sessie wordt geopend.",
            )
            self.reopen_previous_live_session()
            return

        configure_logging()
        default_location = " — ".join(filter(None, [
            str(active_event.get("place", "") or "").strip(),
            str(active_event.get("location", "") or "").strip(),
            str(active_event.get("location_address", "") or "").strip(),
        ]))
        if not default_location:
            default_location = "Online" if active_event.get("event_type") == "Online voorlichting" else "Niet opgegeven"

        setup_dialog = LiveSessionSetupDialog(active_event, default_location, self)
        if setup_dialog.exec() != QDialog.DialogCode.Accepted:
            self.live_session_status_label.setText("Nieuwe livesessie geannuleerd.")
            return

        try:
            session_result = live_session_service.create_session(
                str(active_event.get("name", "") or "Onbenoemd evenement"),
                str(active_event.get("date", "") or ""),
                default_location,
                setup_dialog.checkout_required,
                source_event_id,
            )
        except live_session_service.SessionValidationError as exc:
            QMessageBox.warning(
                self,
                "Livesessie kan niet starten",
                "De livesessie gebruikt de gegevens uit het evenementdossier. "
                "Vul de ontbrekende evenementgegevens aan en probeer opnieuw.\n\n"
                f"Details: {exc}",
            )
            return

        window = ManagerWindow(session_result)
        window.linked_event_id = source_event_id
        window.attendance_changed.connect(
            lambda window=window, event_id=source_event_id: self._sync_live_attendance(window, event_id)
        )
        window.server_state_changed.connect(self._live_server_state_changed)

        visitors = self._event_visitors(active_event)
        if visitors:
            try:
                rows = live_importer.records_to_participants(visitors, window.event_id)
                live_participant_service.add_participants(window.connection, window.event_id, rows)
                window.refresh_status()
                self._sync_live_attendance(window, source_event_id)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Deelnemers niet automatisch gekoppeld",
                    "De livesessie is aangemaakt, maar de deelnemers konden niet automatisch worden overgenomen. "
                    f"Gebruik in Serverbeheer de knop Bezoekerslijst importeren.\n\nDetails: {exc}",
                )

        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._live_server_windows.append(window)
        window.destroyed.connect(
            lambda *_args, window=window, event_id=source_event_id:
            self._forget_live_server_window(window, event_id, offer_completion=True)
        )
        window.show()
        window.raise_()
        window.activateWindow()
        self.live_session_status_label.setText(
            f"Nieuwe livesessie gestart voor {active_event.get('name', 'het gekozen evenement')}. "
            "Start de server om apparaten te verbinden."
        )
        self._refresh_event_control_live_state()

    def _sync_latest_live_attendance_for_event(self, event) -> int:
        """Refresh the EventHub participant records from the latest live run for this event."""
        if not event:
            return 0
        event_id = str(event.get("id", "") or "").strip()
        if not event_id:
            return 0
        # Prefer an already-open manager window so we use its live connection.
        for window in list(self._live_server_windows):
            try:
                if str(getattr(window, "linked_event_id", "") or "").strip() == event_id:
                    return self._sync_live_attendance(window, event_id)
            except RuntimeError:
                continue
        previous = self._previous_live_session_for_event(event)
        if not previous:
            return 0
        session_id = str(previous.get("id", "") or "").strip()
        if not session_id:
            return 0
        connection = None
        try:
            from server.paths import database_path as live_database_path
            db_path = live_database_path(session_id)
            if not Path(db_path).is_file():
                return 0
            connection = sqlite3.connect(str(db_path), timeout=2)
            connection.row_factory = sqlite3.Row
            participants = [dict(row) for row in connection.execute(
                "SELECT id, voornaam, achternaam, geboortedatum, attendance_status, checkin_time "
                "FROM participant WHERE event_id=?", (session_id,)
            ).fetchall()]
            teruggedraaid = self._reverted_checkins(connection, session_id)
        except Exception:
            return 0
        finally:
            if connection is not None:
                connection.close()
        ongekoppeld: list = []
        changed = apply_live_attendance(
            self._event_visitors(event), participants, event.get("name", ""),
            reverted_ids=teruggedraaid, unmatched=ongekoppeld,
        )
        self._report_unmatched_checkins(ongekoppeld, event)
        if changed:
            self._mark_dirty()
            self.status_label.setText(
                f"Live presentie gesynchroniseerd: {changed} wijziging(en) automatisch verwerkt."
            )
        return changed

    def _ask_about_attendance_conflicts(self, conflicts) -> int:
        """Vraag wie voorgaat als het bestand iets anders zegt dan EventHub.

        Zonder die vraag koos EventHub stilzwijgend, en dat is precies waar
        aanwezigheid ongemerkt verdween of juist bleef staan.
        """
        if not conflicts:
            return 0
        voorbeeld = ", ".join(sorted({
            f"{ATTENDANCE_LABELS[status].lower()} in het bestand" for _, _, status in conflicts
        })[:3])
        answer = QMessageBox.question(
            self,
            "Aanwezigheid wijkt af",
            f"Voor {len(conflicts)} deelnemer(s) zegt het bestand iets anders over de aanwezigheid "
            f"dan wat er in EventHub staat ({voorbeeld}).\n\n"
            "Wilt u de gegevens uit het bestand overnemen? Kiest u Nee, dan blijft de registratie "
            "staan zoals hij nu is; de rest van de import gaat gewoon door.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return 0
        return apply_attendance_conflicts(conflicts)

    def _report_unmatched_checkins(self, namen, event):
        """Vertel het wanneer een incheck nergens op paste.

        Dat gebeurt als iemand twee keer in de deelnemerslijst staat: de
        koppeling op naam weigert dan te raden. Zonder deze melding raak je die
        aanwezigheid kwijt zonder dat iets het zegt.
        """
        if not namen:
            return
        lijst = ", ".join(sorted(set(namen))[:6])
        if len(set(namen)) > 6:
            lijst += f" en {len(set(namen)) - 6} andere"
        QMessageBox.warning(
            self,
            "Inchecks niet gekoppeld",
            f"Van {len(set(namen))} ingecheckte bezoeker(s) kon de aanwezigheid niet aan een deelnemer "
            f"in '{event.get('name', '')}' worden gekoppeld: {lijst}."
            "\n\nDat gebeurt wanneer iemand twee keer in de deelnemerslijst staat. Zet hun "
            "aanwezigheid met de hand goed, of haal de dubbele regel weg.",
        )

    def _reverted_checkins(self, connection, session_id: str) -> set:
        """Deelnemers bij wie een incheck bewust is teruggedraaid.

        Alleen die stap is een uitspraak dat iemand er niet was; de gewone
        beginstand not_checked_in betekent enkel dat er niet gescand is.
        """
        try:
            rows = connection.execute(
                "SELECT DISTINCT participant_id FROM audit_log WHERE event_id=? AND action='checkin_undone'",
                (session_id,),
            ).fetchall()
        except Exception:
            return set()
        return {str(row[0]) for row in rows if row[0]}

    def _sync_live_attendance(self, window, linked_event_id: str) -> int:
        """Copy live check-in state back into the linked EventHub event records."""
        event = self._event_by_id(linked_event_id)
        if not event or window is None:
            return 0
        try:
            participants = [dict(row) for row in window.connection.execute(
                "SELECT id, voornaam, achternaam, geboortedatum, attendance_status, checkin_time "
                "FROM participant WHERE event_id=?", (window.event_id,)
            ).fetchall()]
        except Exception:
            return 0

        event_records = self._event_visitors(event)
        ongekoppeld: list = []
        changed = apply_live_attendance(
            event_records, participants, event.get("name", ""),
            reverted_ids=self._reverted_checkins(window.connection, window.event_id),
            unmatched=ongekoppeld,
        )
        self._report_unmatched_checkins(ongekoppeld, event)
        if changed:
            self._mark_dirty()
            self._render_live_attendance_scope()
            self.status_label.setText(
                f"Live presentie gesynchroniseerd: {changed} wijziging(en) automatisch verwerkt."
            )
        return changed

    def _forget_live_server_window(self, window, event_id="", offer_completion=False):
        self._live_server_windows = [candidate for candidate in self._live_server_windows if candidate is not window]
        self._update_presence_registration_availability()
        self._refresh_event_control_live_state()
        self._set_live_session_context_status()
        if offer_completion and event_id and not self._allow_application_exit:
            QTimer.singleShot(0, lambda event_id=event_id: self._offer_live_session_completion(event_id))

    def _show_event_control_presence(self, event):
        if not event:
            return
        self._sync_event_combo(self.event_control_event_combo)
        self.event_control_event_combo.set_current_id(event.get("id", ""))
        self.active_event_id = event.get("id", "")
        self.selected_events = {event.get("name", "")}
        self.show_event_control_page()
        self.event_control_tabs.setCurrentWidget(self.presence_tab)

    def _offer_live_session_completion(self, event_id):
        event = self._event_by_id(event_id)
        if not event or self._active_live_server_window(event) is not None:
            return
        records = self._event_visitors(event)
        if not records:
            return
        counts = attendance_counts(records, str(event.get("name", "") or ""))
        unknown_count = counts[ONBEKEND]

        dialog = QMessageBox(self)
        dialog.setWindowTitle("Livesessie afgesloten")
        dialog.setIcon(
            QMessageBox.Icon.Warning if unknown_count else QMessageBox.Icon.Information
        )
        summary = (
            f"{counts[AANWEZIG]} aanwezig, {counts[AFGEMELD]} afgemeld, "
            f"{counts[AFWEZIG]} afwezig en {unknown_count} nog onbeoordeeld."
        )
        if unknown_count:
            dialog.setText(
                f"De livesessie van '{event.get('name', 'dit evenement')}' is afgesloten.\n\n"
                f"{summary}\n\n"
                f"Bij Registratie afronden worden de {unknown_count} onbeoordeelde deelnemer(s) "
                "als afwezig vastgelegd. Controleer ze eerst als u daar niet zeker van bent."
            )
        else:
            dialog.setText(
                f"De livesessie van '{event.get('name', 'dit evenement')}' is afgesloten.\n\n"
                f"{summary}\n\nDe aanwezigheidsregistratie is volledig."
            )
        review_button = dialog.addButton(
            "Aanwezigheid controleren", QMessageBox.ButtonRole.AcceptRole
        )
        finish_button = None
        if unknown_count:
            finish_button = dialog.addButton(
                "Registratie afronden", QMessageBox.ButtonRole.DestructiveRole
            )
        rudder_button = dialog.addButton(
            "Afronden en naar Rudder" if unknown_count else "Aanwezigheid naar Rudder",
            QMessageBox.ButtonRole.ActionRole,
        )
        later_button = dialog.addButton("Later", QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(review_button)
        dialog.setEscapeButton(later_button)
        dialog.exec()
        clicked = dialog.clickedButton()
        if clicked is review_button:
            self._show_event_control_presence(event)
        elif finish_button is not None and clicked is finish_button:
            self._finish_presence_registration(event=event, confirm=False)
        elif clicked is rudder_button:
            if unknown_count and not self._finish_presence_registration(event=event, confirm=False):
                return
            self.export_directly_to_rudder(event=event)

    def _open_internal_webclient(self, url: str):
        """Open de gedeelde webclient binnen EventHub; val terug op de standaardbrowser."""
        target_url = str(url or "").strip().rstrip("/")
        if not target_url:
            return
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            QDesktopServices.openUrl(QUrl(target_url))
            QMessageBox.information(
                self,
                "Webclient extern geopend",
                "De interne browsercomponent is niet beschikbaar in deze build. "
                "De EventHub-webclient is daarom in de standaardbrowser geopend.",
            )
            return

        browser_window = QMainWindow(self)
        browser_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        browser_window.setWindowTitle("EventHub — Live check-in")
        browser_window.resize(1180, 780)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("internalBrowserToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        back_button = _make_button_compact(QPushButton("← Terug naar Event Control"))
        back_button.setObjectName("secondaryButton")
        back_button.clicked.connect(browser_window.close)
        external_button = _make_button_compact(QPushButton("Openen in externe browser"))
        external_button.setObjectName("secondaryButton")
        external_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(target_url)))
        toolbar_layout.addWidget(back_button)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(external_button)

        web_view = QWebEngineView()
        web_view.setUrl(QUrl(target_url))
        layout.addWidget(toolbar)
        layout.addWidget(web_view, 1)
        browser_window.setCentralWidget(container)
        browser_window.show()
        browser_window.raise_()
        browser_window.activateWindow()
        self._live_webclient_window = browser_window

    def open_live_webclient(self):
        """Vind een actieve hub en open diens webclient, zonder de oude desktop-check-inflow."""
        event = self._event_control_selected_event()
        if not event:
            QMessageBox.information(
                self, "Geen evenement", "Kies eerst het evenement waarvoor u wilt inchecken."
            )
            return
        self.live_session_status_label.setText("Actieve livesessies zoeken op het lokale netwerk…")
        QApplication.processEvents()
        try:
            from server.network import discover_hubs
            hubs = discover_hubs()
        except Exception as exc:
            self.live_session_status_label.setText("Livesessie zoeken mislukt.")
            QMessageBox.warning(self, "Verbindpagina niet beschikbaar", str(exc))
            return

        # Een lokaal door EventHub gestart venster blijft bruikbaar als discovery door
        # een firewall of netwerkconfiguratie geen UDP-resultaat teruggeeft.
        active_window = self._active_live_server_window(event)
        local_url = str(getattr(active_window, "local_url", "") or "").strip() if active_window else ""
        if local_url and not any(str(hub.get("url", "")).rstrip("/") == local_url.rstrip("/") for hub in hubs):
            hubs.append({
                "name": str(event.get("name", "") or "Lokale EventHub-sessie"),
                "date": str(event.get("date", "") or ""),
                "source_event_id": str(event.get("id", "") or ""),
                "url": local_url,
            })

        event_id = str(event.get("id", "") or "").strip()
        event_name = str(event.get("name", "") or "").strip().casefold()
        event_date = str(event.get("date", "") or "").strip()

        def belongs_to_selected_event(hub):
            hub_event_id = str(hub.get("source_event_id", "") or "").strip()
            if hub_event_id:
                return bool(event_id) and hub_event_id == event_id
            if str(hub.get("name", "") or "").strip().casefold() != event_name:
                return False
            hub_date = str(hub.get("date", "") or "").strip()
            return not hub_date or not event_date or hub_date == event_date

        hubs = [hub for hub in hubs if belongs_to_selected_event(hub)]

        if not hubs:
            self.live_session_status_label.setText("Geen actieve livesessie gevonden.")
            QMessageBox.information(
                self,
                "Geen livesessie gevonden",
                f"Er is geen actieve livesessie voor '{event.get('name', 'het gekozen evenement')}' "
                "gevonden op dit lokale netwerk. "
                "Controleer of de hostserver actief is en of dit apparaat met hetzelfde netwerk is verbonden.",
            )
            return

        hub = hubs[0]
        if len(hubs) > 1:
            labels = [f"{item.get('name', 'EventHub-sessie')} — {item.get('url', '')}" for item in hubs]
            selected, ok = QInputDialog.getItem(self, "Livesessie kiezen", "Actieve livesessies:", labels, 0, False)
            if not ok:
                self.live_session_status_label.setText("Geen livesessie gekozen.")
                return
            hub = hubs[labels.index(selected)]

        target_url = str(hub.get("url", "") or "").strip()
        if not target_url:
            self.live_session_status_label.setText("Livesessie heeft geen geldig adres.")
            return
        self.live_session_status_label.setText(f"Webclient geopend — {hub.get('name', 'EventHub-sessie')}")
        self._open_internal_webclient(target_url)

    def open_live_connect_page(self):
        # Compatibiliteitsroute voor oudere aanroepen: gebruik voortaan dezelfde webclientflow.
        self.open_live_webclient()

    def open_live_checkin_client(self):
        window = self._active_live_server_window(self._event_control_selected_event())
        default_url = str(getattr(window, "local_url", "") or "") if window is not None else ""
        dialog = LiveCheckinDialog(self, default_url)
        dialog.exec()

    def open_live_dashboard(self):
        event = self._event_control_selected_event()
        window = self._active_live_server_window(event)
        if window is None:
            event_name = str(event.get("name", "") or "het gekozen evenement") if event else "het gekozen evenement"
            QMessageBox.information(
                self, "Geen live sessie",
                f"Open eerst de livesessie van '{event_name}' en start de server."
            )
            return
        window.open_dashboard()

    def _rudder_extension_directory(self):
        candidates = [
            program_directory() / "Browserassistent",
            program_directory() / "browser_extension",
            Path(getattr(sys, "_MEIPASS", program_directory())) / "browser_extension",
        ]
        return next((path for path in candidates if (path / "manifest.json").is_file()), candidates[0])

    def open_rudder_extension_folder(self, *, dialog_parent=None):
        owner = dialog_parent if dialog_parent is not None else self
        directory = self._rudder_extension_directory()
        if not (directory / "manifest.json").is_file():
            QMessageBox.warning(
                owner, "Browserassistent ontbreekt",
                "De map met de Rudder Browserassistent is niet gevonden. Bouw of installeer EventHub opnieuw met de volledige broncode."
            )
            return
        dialog = QDialog(owner)
        dialog.setWindowTitle("Browserassistent instellen")
        _fit_dialog_to_screen(dialog, 660, 510, 480, 380)
        layout = QVBoxLayout(dialog)
        title = QLabel("Verbind EventHub met Rudder")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        intro = QLabel("De browserassistent helpt bij het overnemen van evenementgegevens en aanwezigheid. "
                       "Installeer hem eenmalig in de browser waarin je Rudder gebruikt.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        browser = ScrollSafeComboBox()
        browser.addItem("Microsoft Edge", "edge://extensions")
        browser.addItem("Google Chrome", "chrome://extensions")
        layout.addWidget(browser)
        steps = QLabel()
        steps.setWordWrap(True)
        def update_steps():
            steps.setText(
                f"1. Plak {browser.currentData()} in de adresbalk van {browser.currentText()}.\n"
                "2. Zet Ontwikkelaarsmodus aan.\n"
                "3. Klik op Uitgepakte extensie laden.\n"
                "4. Selecteer de onderstaande map en bevestig.\n"
                "5. Vernieuw eventueel de geopende Rudder-pagina."
            )
        browser.currentIndexChanged.connect(update_steps)
        update_steps()
        layout.addWidget(steps)
        path_field = QLineEdit(str(directory.resolve()))
        path_field.setReadOnly(True)
        layout.addWidget(path_field)
        actions = QHBoxLayout()
        for label, action in (
            ("Adres kopiëren", lambda: QApplication.clipboard().setText(browser.currentData())),
            ("Mappad kopiëren", lambda: QApplication.clipboard().setText(str(directory.resolve()))),
            ("Extensiemap openen", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory.resolve())))),
        ):
            button = QPushButton(label)
            button.setObjectName("secondaryButton")
            button.clicked.connect(action)
            actions.addWidget(button)
        layout.addLayout(actions)
        note = QLabel("Je kunt deze hulp later terugvinden via Algemene instellingen → Browserextensie → "
                      "Browserextensie installeren. Als je organisatie ontwikkelaarsmodus blokkeert, "
                      "vraag je ICT-beheerder om de extensie beschikbaar te maken.")
        note.setObjectName("hintLabel")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        buttons = QDialogButtonBox()
        later = buttons.addButton("Later", QDialogButtonBox.ButtonRole.RejectRole)
        done = buttons.addButton("Gereed", QDialogButtonBox.ButtonRole.AcceptRole)
        done.setObjectName("primaryButton")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def maybe_show_browser_extension_setup(self):
        if self.settings.value("browser_extension_setup_seen", False, type=bool):
            return
        self.open_rudder_extension_folder()
        if (self._rudder_extension_directory() / "manifest.json").is_file():
            self.settings.setValue("browser_extension_setup_seen", True)

    def _selected_rudder_event(self):
        return self._event_control_selected_event()

    def _ensure_rudder_attendance_url(self, event, force_prompt=False):
        if not event:
            QMessageBox.information(self, "Geen evenement", "Kies eerst een evenement in Event Control.")
            return ""
        current = str(event.get("rudder_attendance_url", "") or "").strip()
        if not current and str(event.get("rudder_event_id", "") or "").isdigit():
            current = f"https://werkenbijdefensie.nl/rudder/event/events/{event['rudder_event_id']}/attendance"
        if current and not force_prompt:
            return current
        attendance_url, accepted = QInputDialog.getText(
            self, "Rudder-evenement",
            "Plak de link van Inschrijvingen of Registratie opkomst uit Rudder:", text=current
        )
        if not accepted:
            return ""
        attendance_url = attendance_url.strip()
        parsed = urllib.parse.urlparse(attendance_url)
        path_match = re.fullmatch(
            r"/rudder/event/events/(\d+)/(?:registrations|attendance)/?", parsed.path or "", re.IGNORECASE
        )
        if parsed.scheme.lower() != "https" or parsed.hostname not in {"werkenbijdefensie.nl", "www.werkenbijdefensie.nl"} or not path_match:
            QMessageBox.warning(
                self, "Ongeldige Rudder-link",
                "Plak de volledige Rudder-link van Inschrijvingen of Registratie opkomst.\n\n"
                "Voorbeeld: https://werkenbijdefensie.nl/rudder/event/events/5900/registrations"
            )
            return ""
        event_id = path_match.group(1)
        canonical_path = f"/rudder/event/events/{event_id}/attendance"
        canonical_url = urllib.parse.urlunparse(("https", "werkenbijdefensie.nl", canonical_path, "", "", ""))
        if event.get("rudder_attendance_url") != canonical_url or event.get("rudder_event_id") != event_id:
            event["rudder_attendance_url"] = canonical_url
            event["rudder_event_id"] = event_id
            self._mark_dirty()
        return canonical_url

    def open_rudder_attendance_page(self):
        event = self._selected_rudder_event()
        canonical_url = self._ensure_rudder_attendance_url(event, force_prompt=True)
        if not canonical_url:
            return
        QDesktopServices.openUrl(QUrl(canonical_url))

    def _serve_rudder_attendance(self, request):
        """Beantwoord de Browserassistent, maar alleen na een klik van de gebruiker.

        Er staan namen en registratie-ID's in wat hier de deur uitgaat, dus dit
        gebeurt nooit stilzwijgend.
        """
        try:
            wanted = str(request.rudder_event_id).strip()
            event = next(
                (item for item in self.events
                 if str(item.get("rudder_event_id", "") or "").strip() == wanted),
                None,
            )
            if event is None:
                request.status = 404
                request.error = (
                    f"In het geopende EventHub-dossier staat geen evenement met Rudder-nummer {wanted}."
                )
                return
            visitors = self._event_visitors(event)
            if not visitors:
                request.status = 404
                request.error = f"'{event.get('name', '')}' heeft nog geen deelnemers in EventHub."
                return
            counts = attendance_counts(visitors, event.get("name", ""))
            self.raise_()
            self.activateWindow()
            antwoord = QMessageBox.question(
                self,
                "Presentie doorgeven aan Rudder",
                f"De Browserassistent vraagt de presentie van '{event.get('name', '')}'.\n\n"
                f"{len(visitors)} deelnemer(s): {counts[AANWEZIG]} aanwezig, {counts[AFWEZIG]} niet gekomen, "
                f"{counts[AFGEMELD]} afgemeld, {counts[ONBEKEND]} onbekend.\n\n"
                "Hiermee gaan namen en registratie-ID's naar de browser. Doorgeven?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if antwoord != QMessageBox.StandardButton.Yes:
                request.status = 403
                request.error = "De aanvraag is in EventHub geweigerd."
                return
            payload = self._rudder_payload(event)
            if not payload:
                request.status = 404
                request.error = "EventHub kon voor dit evenement geen presentie samenstellen."
                return
            request.payload = payload
            self.status_label.setText(
                f"Presentie van {event.get('name', '')} doorgegeven aan de Browserassistent."
            )
        finally:
            request.done.set()

    def _rudder_payload(self, event):
        if not event:
            QMessageBox.information(self, "Geen evenement", "Kies eerst een evenement in Event Control.")
            return None
        records = self._event_visitors(event)
        if not records:
            QMessageBox.information(self, "Geen deelnemers", "Dit evenement bevat nog geen deelnemers.")
            return None
        participants = []
        for record in records:
            identifier = str(record.get("Identifier", "") or "").strip()
            identifier_match = re.search(r"(?:registrations?/)?(\d+)(?:\D*)$", identifier, re.IGNORECASE)
            registration_id = identifier_match.group(1) if identifier_match else identifier
            full_name = " ".join(filter(None, [
                str(record.get("Voornaam", "") or "").strip(),
                str(record.get("Tussenvoegsel", "") or "").strip(),
                str(record.get("Achternaam", "") or "").strip(),
            ]))
            participants.append({
                "source_id": str(record.get("_id", "") or ""),
                "identifier": registration_id,
                "full_name": full_name,
                "first_name": str(record.get("Voornaam", "") or "").strip(),
                "middle_name": str(record.get("Tussenvoegsel", "") or "").strip(),
                "last_name": str(record.get("Achternaam", "") or "").strip(),
                "present": is_present(record, event.get("name", "")),
            })
        return {
            "format": "EventHub Rudder Attendance",
            "version": 1,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "default_unknown_to_no": True,
            "event": {
                "id": event.get("id", ""), "rudder_event_id": event.get("rudder_event_id", ""),
                "rudder_attendance_url": event.get("rudder_attendance_url", ""),
                "name": event.get("name", ""), "date": event.get("date", ""),
            },
            "participants": participants,
        }

    def export_directly_to_rudder(self, _checked=False, *, event=None):
        event = event or self._selected_rudder_event()
        attendance_url = self._ensure_rudder_attendance_url(event)
        if not attendance_url:
            return
        payload = self._rudder_payload(event)
        if not payload:
            return
        try:
            if self._rudder_bridge is not None:
                self._rudder_bridge.stop()
            self._rudder_bridge = RudderLocalBridge(payload, lifetime_seconds=300)
            port, token = self._rudder_bridge.start()
            bridge_reference = f"{port}.{token}"
            target_url = f"{attendance_url}#eventhub={bridge_reference}"
            QDesktopServices.openUrl(QUrl(target_url))
            present_count = sum(person["present"] for person in payload["participants"])
            self.rudder_status_label.setText(
                f"Rudder-export klaar: {present_count} Yes en {len(payload['participants']) - present_count} No voorbereid."
            )
            self.status_label.setText(
                "Rudder geopend; de Browserassistent haalt de presentie lokaal op. "
                "Verschijnt niets, herlaad dan de extensie via edge://extensions."
            )
        except Exception as exc:
            self._show_runtime_error("Exporteren naar Rudder", exc)

    def import_rudder_event(self, _checked=False, event=None):
        """Open Rudder and receive an allowlisted event snapshot from the browser assistant."""
        target = event if isinstance(event, dict) else self._active_event()
        linked = is_rudder_event_linked(target)
        expected_event_id = str(target.get("rudder_event_id", "") or "") if linked else ""
        destination_url = canonical_rudder_url(expected_event_id, "edit") if linked else RUDDER_EVENTS_OVERVIEW_URL
        try:
            if self._rudder_bridge is not None:
                self._rudder_bridge.stop()
            self._rudder_bridge = RudderLocalBridge(lifetime_seconds=300, receive_event=True)
            port, token = self._rudder_bridge.start()
            self._rudder_import_target_event_id = str(target.get("id", "") or "") if target else ""
            self._rudder_import_expected_event_id = expected_event_id
            self._rudder_import_started_at = datetime.now()
            if not hasattr(self, "_rudder_import_timer"):
                self._rudder_import_timer = QTimer(self)
                self._rudder_import_timer.setInterval(300)
                self._rudder_import_timer.timeout.connect(self._poll_rudder_event_import)
            self._rudder_import_timer.start()
            QDesktopServices.openUrl(QUrl(f"{destination_url}#eventhub-import={port}.{token}"))
            self.status_label.setText(
                "Gekoppeld Rudder-evenement geopend; klik daar op Importeren naar EventHub."
                if linked else
                "Rudder-evenementen geopend; kies een evenement en klik daar op Importeren naar EventHub."
            )
        except Exception as exc:
            self._show_runtime_error("Importeren uit Rudder", exc)

    def import_rudder_events_bulk(self, _checked=False):
        """Importeer in een keer alle evenementen die in Rudder in beeld staan.

        Rudder filtert zelf op eigenaar, soort en krijgsmacht. Wie daar op de
        eigen naam filtert en dit start, haalt in een keer al die evenementen
        binnen; de assistent loopt de resultaten af en stuurt ze een voor een
        door over dezelfde brug.
        """
        try:
            if self._rudder_bridge is not None:
                self._rudder_bridge.stop()
            self._rudder_bridge = RudderLocalBridge(
                lifetime_seconds=1800, receive_event=True, batch=True
            )
            port, token = self._rudder_bridge.start()
            self._rudder_bulk_import = []
            self._rudder_import_started_at = datetime.now()
            self._rudder_import_target_event_id = ""
            self._rudder_import_expected_event_id = ""
            if not hasattr(self, "_rudder_bulk_timer"):
                self._rudder_bulk_timer = QTimer(self)
                self._rudder_bulk_timer.setInterval(500)
                self._rudder_bulk_timer.timeout.connect(self._poll_rudder_bulk_import)
            self._rudder_bulk_timer.start()
            QDesktopServices.openUrl(
                QUrl(f"{RUDDER_EVENTS_OVERVIEW_URL}#eventhub-import-all={port}.{token}")
            )
            self.status_label.setText(
                "Rudder geopend. Filter daar op uw eigen naam en kies "
                "Alles importeren naar EventHub."
            )
        except Exception as exc:
            self._show_runtime_error("Evenementen importeren uit Rudder", exc)

    def _poll_rudder_bulk_import(self):
        bridge = self._rudder_bridge
        if bridge is None:
            self._rudder_bulk_timer.stop()
            return
        for payload in bridge.take_received_batch():
            if str(payload.get("action", "")) == "done":
                self._finish_rudder_bulk_import()
                return
            try:
                self._rudder_bulk_import.append(sanitize_rudder_event_payload(payload))
            except Exception:
                self._write_error_log("Rudder-bulkimport", traceback.format_exc())
        started = getattr(self, "_rudder_import_started_at", datetime.now())
        if (datetime.now() - started).total_seconds() >= 1800:
            self._finish_rudder_bulk_import(expired=True)
        elif self._rudder_bulk_import:
            self.status_label.setText(
                f"Bezig met importeren uit Rudder: {len(self._rudder_bulk_import)} evenement(en) ontvangen."
            )

    def _finish_rudder_bulk_import(self, expired: bool = False):
        self._rudder_bulk_timer.stop()
        if self._rudder_bridge is not None:
            self._rudder_bridge.stop()
            self._rudder_bridge = None
        imported = list(self._rudder_bulk_import)
        self._rudder_bulk_import = []
        if not imported:
            self.status_label.setText(
                "Rudder-import verlopen zonder evenementen." if expired
                else "Geen evenementen ontvangen uit Rudder."
            )
            return
        self._confirm_rudder_bulk_import(imported)

    def _rudder_bulk_preview(self, imported: list[dict]):
        """Splits de ontvangst in nieuw en bij te werken, op Rudder-event-id."""
        bestaand = {
            str(event.get("rudder_event_id", "") or ""): event
            for event in self.events if event.get("rudder_event_id")
        }
        nieuw, bijwerken = [], []
        for item in imported:
            doel = bestaand.get(str(item.get("event_id", "") or ""))
            (bijwerken if doel else nieuw).append((item, doel))
        return nieuw, bijwerken

    def _confirm_rudder_bulk_import(self, imported: list[dict]):
        nieuw, bijwerken = self._rudder_bulk_preview(imported)
        regels = []
        for item, _ in nieuw:
            updates = rudder_eventhub_updates(item)
            regels.append(f"<li>Nieuw: {escape(str(updates.get('name', '') or 'Onbenoemd'))}</li>")
        for item, doel in bijwerken:
            regels.append(f"<li>Bijwerken: {escape(str(doel.get('name', '') or 'Onbenoemd'))}</li>")

        box = QMessageBox(self)
        box.setWindowTitle("Evenementen importeren")
        box.setIcon(QMessageBox.Icon.Question)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(f"<b>{len(imported)} evenement(en) uit Rudder ontvangen.</b>")
        box.setInformativeText(
            f"<p>{len(nieuw)} nieuw, {len(bijwerken)} bij te werken.</p>"
            f"<ul>{''.join(regels[:20])}</ul>"
            + ("<p>...</p>" if len(regels) > 20 else "")
            + "<p>Bestaande evenementen worden bijgewerkt, niet gedupliceerd. "
            "Afgeronde taken blijven staan.</p>"
        )
        toepassen = box.addButton("Importeren", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annuleren", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(toepassen)
        box.exec()
        if box.clickedButton() is not toepassen:
            self.status_label.setText("Rudder-import geannuleerd.")
            return

        verwerkt, mislukt = 0, []
        for item, doel in nieuw + bijwerken:
            try:
                self._apply_rudder_event_import(item, doel)
                verwerkt += 1
            except Exception as exc:
                mislukt.append(f"{item.get('event_id', '?')}: {exc}")
                self._write_error_log("Rudder-bulkimport toepassen", traceback.format_exc())
        self._mark_dirty()
        self._render_all()
        self._add_recent_activity(f"{verwerkt} evenement(en) uit Rudder geimporteerd")
        melding = f"{verwerkt} evenement(en) verwerkt uit Rudder."
        if mislukt:
            melding += "\n\nOvergeslagen:\n" + "\n".join(mislukt[:6])
        QMessageBox.information(self, "Import gereed", melding)
        self.status_label.setText(f"{verwerkt} evenement(en) uit Rudder verwerkt.")

    def _poll_rudder_event_import(self):
        bridge = self._rudder_bridge
        payload = bridge.take_received_payload() if bridge is not None else None
        if payload is None:
            started = getattr(self, "_rudder_import_started_at", datetime.now())
            if (datetime.now() - started).total_seconds() >= 300:
                self._rudder_import_timer.stop()
                self.status_label.setText("Rudder-import verlopen. Start Importeren uit Rudder opnieuw.")
            return
        self._rudder_import_timer.stop()
        try:
            imported = sanitize_rudder_event_payload(payload)
            expected = str(getattr(self, "_rudder_import_expected_event_id", "") or "")
            if expected and imported["event_id"] != expected:
                raise ValueError(
                    f"De geopende pagina is Rudder-event {imported['event_id']}, terwijl event {expected} werd verwacht."
                )
            target_id = str(getattr(self, "_rudder_import_target_event_id", "") or "")
            target = self._event_by_id(target_id) if target_id else None
            event = self._apply_rudder_event_import(imported, target)
            self.open_event(event, self.rudder_tab)
            self.status_label.setText(f"Bijgewerkt uit Rudder: {event['name']}.")
        except Exception as exc:
            self._show_runtime_error("Rudder-import verwerken", exc)

    def _apply_rudder_event_import(self, imported: dict, target: dict | None = None):
        updates = rudder_eventhub_updates(imported)
        matched_template = matching_eventhub_template(imported, self.project_templates)
        original_name = str((target or {}).get("name", "") or "")
        if target:
            source = deepcopy(target)
        elif matched_template and isinstance(matched_template.get("event"), dict):
            source = event_from_template(matched_template)
            source["id"] = ""
            source["attachments"] = []
            source["evaluation"] = {}
        else:
            source = empty_event(
                updates.get("name", ""), self.task_templates, updates.get("event_type", "Meeloopdag")
            )
        source.update(updates)

        event_type = updates.get("event_type", "Meeloopdag")
        if target and target.get("template_id"):
            # A template is a starting point, not a live subscription to tasks.
            template_tasks = []
        elif matched_template and isinstance(matched_template.get("event"), dict):
            template_tasks = template_event_data(matched_template["event"])["tasks"]
        else:
            template_tasks = tasks_from_templates(self.task_templates, event_type)
        existing_titles = {normalize(task.get("title", "")) for task in source.get("tasks", [])}
        for task in template_tasks if isinstance(template_tasks, list) else []:
            if not isinstance(task, dict) or not task_allowed_for_event_type(task, event_type):
                continue
            title_key = normalize(task.get("title", ""))
            if not title_key or title_key in existing_titles:
                continue
            source.setdefault("tasks", []).append(prepare_task({
                **task, "id": "", "done": False, "completed_on": "",
            }))
            existing_titles.add(title_key)
        source["rudder_event_id"] = imported["event_id"]
        source["rudder_edit_url"] = imported["edit_url"]
        source["rudder_attendance_url"] = canonical_rudder_url(imported["event_id"], "attendance")
        source["rudder_last_synced_at"] = datetime.now().isoformat(timespec="seconds")
        source["rudder_data"] = deepcopy(imported["data"])
        source["name"] = event_name_with_date(source.get("name", ""), source.get("date", ""))
        duplicate = self._event_by_name(source["name"])
        if duplicate and duplicate is not target:
            base_name = source["name"]
            sequence = 2
            while self._event_by_name(source["name"]):
                source["name"] = f"{base_name} ({sequence})"
                sequence += 1
        prepared = prepare_event(source, self.task_templates)
        if target:
            target.clear()
            target.update(prepared)
            event = target
            if normalize(original_name) != normalize(event["name"]):
                for record in self.records:
                    names = [event["name"] if normalize(name) == normalize(original_name) else name for name in record_events(record)]
                    record["Evenement"] = "; ".join(dict.fromkeys(filter(None, names)))
        else:
            event = prepared
            self.events.append(event)
        self.active_event_id = event.get("id", "")
        self.selected_events = {event.get("name", "")}
        self._mark_dirty()
        self._render_all()
        return event

    def export_event_to_rudder(self):
        event = self._active_event()
        if not event:
            QMessageBox.information(self, "Geen evenement", "Open eerst het evenement dat u naar Rudder wilt exporteren.")
            return
        if not is_rudder_event_linked(event):
            QMessageBox.information(
                self, "Niet gekoppeld aan Rudder",
                "Importeer dit evenement eerst uit Rudder voordat u gegevens naar Rudder exporteert.",
            )
            return
        edit_url = canonical_rudder_url(event.get("rudder_event_id", ""), "edit")
        payload = rudder_export_package(event)
        try:
            if self._rudder_bridge is not None:
                self._rudder_bridge.stop()
            self._rudder_bridge = RudderLocalBridge(payload, lifetime_seconds=300)
            port, token = self._rudder_bridge.start()
            QDesktopServices.openUrl(QUrl(f"{edit_url}#eventhub-export={port}.{token}"))
            self.status_label.setText(
                "Rudder geopend; controleer de verschillen, laat de Browserassistent de velden invullen en klik zelf op opslaan."
            )
        except Exception as exc:
            self._show_runtime_error("Exporteren naar Rudder", exc)

    def open_rudder_event_page(self):
        event = self._active_event()
        if not event:
            QMessageBox.information(self, "Geen evenement", "Open eerst een evenement.")
            return
        if not is_rudder_event_linked(event):
            return
        edit_url = canonical_rudder_url(event.get("rudder_event_id", ""), "edit")
        QDesktopServices.openUrl(QUrl(edit_url))

    def _set_navigation_active(self, active_name):
        for name, button in self.sidebar_buttons.items():
            button.setObjectName("sidebarButtonActive" if name == active_name else "sidebarButton")
            button.style().unpolish(button)
            button.style().polish(button)
        titles = {
            "events": ("Evenementen", "Planning, deelnemers en dossiers"),
            "tasks": ("Openstaande taken", "Alle onafgeronde acties"),
            "callbacks": ("After sales", "Bellen, WhatsApp en vervolgafspraken"),
            "trends": ("Trends", "Ontwikkeling over evenementen heen"),
            "event_control": ("Event Control", "Presentie en gedeelde live sessies"),
            "profile": ("Mijn profiel", "Persoonlijke gegevens voor documentexports"),
        }
        if active_name in titles:
            self.app_title.setText(titles[active_name][0])
            self.app_subtitle.setText(titles[active_name][1])

    def _sync_navigation_indicator(self, _index=None):
        current = self.page_stack.currentWidget()
        if current is self.home_page:
            active_name = None
        elif current is self.events_page:
            active_name = "events"
        elif current is self.open_tasks_page:
            active_name = "tasks"
        elif current is self.event_control_page:
            active_name = "event_control"
        elif current is self.profile_page:
            active_name = "profile"
        elif current is self.callback_tab:
            active_name = "callbacks"
        else:
            active_name = None
        self._set_navigation_active(active_name)

    def show_nazorg_page(self):
        event = self._active_event()
        if event:
            self.active_event_id = event.get("id", "")
            self.selected_events = {event.get("name", "")}
            self._sync_latest_live_attendance_for_event(event)
        self._sync_event_combo(self.after_sales_event_combo)
        self.page_stack.setCurrentWidget(self.callback_tab)
        self._set_project_context_ui(False)
        self._set_navigation_active("callbacks")
        self._render_all()

    def _render_standard_tasks_page(self):
        if not hasattr(self, "standard_tasks_table"):
            return
        templates = [prepare_template(template) for template in self.task_templates]
        self.standard_tasks_table.setRowCount(len(templates))
        for row_index, task in enumerate(templates):
            values = [task["title"], template_scope_text(task), task_timing_text(task),
                      f"{task['reminder_days']} dag(en) voor deadline"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, task["id"])
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.standard_tasks_table.setItem(row_index, column, item)

    def _save_standard_tasks(self, templates, apply_existing=False):
        self.task_templates = [prepare_template(template) for template in templates]
        self.settings.setValue("task_templates", json.dumps(self.task_templates, ensure_ascii=False))
        if apply_existing:
            for event in self.events:
                existing = {normalize(task.get("title", "")) for task in event.get("tasks", [])}
                for template in self.task_templates:
                    if not task_allowed_for_event_type(template, event.get("event_type", "Meeloopdag")):
                        continue
                    if normalize(template["title"]) not in existing:
                        source = dict(template)
                        source.update({"id": "", "done": False, "completed_on": ""})
                        event.setdefault("tasks", []).append(prepare_task(source))
        self._mark_dirty()
        self._render_management()
        self._render_standard_tasks_page()

    def add_standard_task(self):
        editor = TaskDialog(None, self, standaard=True)
        if editor.exec() != QDialog.DialogCode.Accepted or not editor.value()["title"]:
            return
        templates = [prepare_template(template) for template in self.task_templates]
        templates.append(editor.value())
        self._save_standard_tasks(templates)

    def edit_standard_task(self):
        row = self.standard_tasks_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen taak gekozen", "Selecteer eerst een standaardtaak.")
            return
        templates = [prepare_template(template) for template in self.task_templates]
        editor = TaskDialog(templates[row], self, standaard=True)
        if editor.exec() != QDialog.DialogCode.Accepted or not editor.value()["title"]:
            return
        templates[row] = editor.value()
        self._save_standard_tasks(templates)

    def remove_standard_task(self):
        row = self.standard_tasks_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen taak gekozen", "Selecteer eerst een standaardtaak.")
            return
        templates = [prepare_template(template) for template in self.task_templates]
        answer = QMessageBox.question(self, "Taak verwijderen", f"Wilt u '{templates[row]['title']}' verwijderen?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        templates.pop(row)
        self._save_standard_tasks(templates)

    def _build_event_support_tabs(self):
        tasks_tab = QWidget()
        self.tasks_tab = tasks_tab
        tasks_layout = QVBoxLayout(tasks_tab)
        tasks_layout.setContentsMargins(14, 14, 14, 14)
        tasks_layout.setSpacing(10)
        tasks_top = QHBoxLayout()
        tasks_heading = QLabel("Planning en taken van dit evenement")
        tasks_heading.setObjectName("hintLabel")
        tasks_top.addWidget(tasks_heading)
        tasks_top.addStretch()
        add_task_button = QPushButton("Taak toevoegen")
        add_task_button.setObjectName("primaryButton")
        add_task_button.clicked.connect(self.add_task)
        tasks_top.addWidget(add_task_button)
        tasks_layout.addLayout(tasks_top)
        task_hint = QLabel("De deadline wordt automatisch berekend vanuit de evenementdatum. Vink een taak af zodra deze is afgerond.")
        task_hint.setObjectName("hintLabel")
        tasks_layout.addWidget(task_hint)
        self.task_table = self._new_table(["Afgerond", "Taak", "Deadline", "Planning", "Melding", "Status", "Notities"])
        self.task_table.itemChanged.connect(self._task_item_changed)
        self.task_table.cellDoubleClicked.connect(lambda *_: self.edit_selected_task())
        self._attach_row_menu(self.task_table, [
            ("Taak aanpassen", self.edit_selected_task),
            (None, None),
            ("Taak verwijderen", self.remove_selected_task),
        ])
        tasks_layout.addWidget(self.task_table, 1)
        self.tabs.addTab(tasks_tab, "Taken")

        documents_tab = QWidget()
        self.documents_tab = documents_tab
        documents_tab_layout = QVBoxLayout(documents_tab)
        documents_tab_layout.setContentsMargins(0, 0, 0, 0)
        documents_tab_layout.setSpacing(0)
        documents_content = QWidget()
        documents_layout = QVBoxLayout(documents_content)
        documents_layout.setContentsMargins(18, 18, 18, 18)
        documents_layout.setSpacing(14)
        document_event_row = QHBoxLayout()
        document_heading = QLabel("Documenten van dit evenement")
        document_heading.setObjectName("sectionTitle")
        document_event_row.addWidget(document_heading)
        document_event_row.addStretch()
        documents_layout.addLayout(document_event_row)

        document_grid = QGridLayout()
        fivewh_box = QGroupBox("5WH")
        fivewh_layout = QVBoxLayout(fivewh_box)
        fivewh_text = QLabel(
            "Plan het evenement volgens het vaste 5WH-format. Evenement- en profielgegevens worden alvast ingevuld."
        )
        fivewh_text.setWordWrap(True)
        fivewh_edit = _make_button_compact(QPushButton("5WH invullen / aanpassen"))
        fivewh_edit.setObjectName("secondaryButton")
        fivewh_edit.clicked.connect(self.edit_fivewh)
        fivewh_export = _make_button_compact(QPushButton("5WH exporteren naar Word"))
        fivewh_export.setObjectName("primaryButton")
        fivewh_export.clicked.connect(self.export_fivewh_document)
        fivewh_layout.addWidget(fivewh_text)
        fivewh_layout.addStretch()
        fivewh_layout.addWidget(fivewh_edit)
        fivewh_layout.addWidget(fivewh_export)
        evaluation_box = QGroupBox("Evaluatieformulier")
        evaluation_layout = QVBoxLayout(evaluation_box)
        evaluation_text = QLabel(
            "Leg na afloop bereik, inzet, middelen en aanbevelingen vast in het officiële evaluatieformulier."
        )
        evaluation_text.setWordWrap(True)
        evaluation_edit = _make_button_compact(QPushButton("Evaluatie invullen / aanpassen"))
        evaluation_edit.setObjectName("secondaryButton")
        evaluation_edit.clicked.connect(self.edit_evaluation)
        evaluation_export = _make_button_compact(QPushButton("Evaluatie exporteren naar Word"))
        evaluation_export.setObjectName("primaryButton")
        evaluation_export.clicked.connect(self.export_evaluation_document)
        evaluation_layout.addWidget(evaluation_text)
        evaluation_layout.addStretch()
        evaluation_layout.addWidget(evaluation_edit)
        evaluation_layout.addWidget(evaluation_export)
        document_grid.addWidget(fivewh_box, 0, 0)
        document_grid.addWidget(evaluation_box, 0, 1)
        document_grid.setColumnStretch(0, 1)
        document_grid.setColumnStretch(1, 1)
        documents_layout.addLayout(document_grid)
        document_note = QLabel(
            "De exports worden als macrovrije .docx-bestanden opgeslagen. De vaste tabellen, velden, marges en pagina-indeling van de aangeleverde voorbeelden blijven behouden."
        )
        document_note.setObjectName("hintLabel")
        document_note.setWordWrap(True)
        documents_layout.addWidget(document_note)

        attachments_box = QGroupBox("Overige documenten en bijlagen")
        attachments_layout = QVBoxLayout(attachments_box)
        attachments_top = QHBoxLayout()
        attachments_hint = QLabel(
            "Voeg Word-, PDF-, Excel- of andere bestanden toe. Bijlagen worden in het .bvp-bestand opgeslagen."
        )
        attachments_hint.setObjectName("hintLabel")
        attachments_top.addWidget(attachments_hint, 1)
        for label, handler, object_name in [
            ("Document toevoegen", self.add_attachment, "primaryButton"),
        ]:
            button = QPushButton(label)
            button.setObjectName(object_name)
            button.clicked.connect(handler)
            attachments_top.addWidget(button)
        attachments_layout.addLayout(attachments_top)
        self.attachments_table = self._new_table(["Bestandsnaam", "Type", "Grootte", "Toegevoegd"])
        self.attachments_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.attachments_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.attachments_table.cellDoubleClicked.connect(lambda *_: self.open_selected_attachment())
        self._attach_row_menu(self.attachments_table, [
            ("Openen", self.open_selected_attachment),
            ("Opslaan als", self.export_selected_attachment),
            (None, None),
            ("Verwijderen", self.remove_selected_attachment),
        ])
        attachments_layout.addWidget(self.attachments_table, 1)
        self.attachments_table.setMinimumHeight(220)
        documents_layout.addWidget(attachments_box, 1)
        documents_scroll = QScrollArea()
        documents_scroll.setWidgetResizable(True)
        documents_scroll.setFrameShape(QFrame.Shape.NoFrame)
        documents_scroll.setWidget(documents_content)
        documents_tab_layout.addWidget(documents_scroll)
        self.tabs.addTab(documents_tab, "Documenten")

        rudder_tab = QWidget()
        self.rudder_tab = rudder_tab
        rudder_tab_layout = QVBoxLayout(rudder_tab)
        rudder_tab_layout.setContentsMargins(0, 0, 0, 0)
        rudder_content = QWidget()
        rudder_layout = QVBoxLayout(rudder_content)
        rudder_layout.setContentsMargins(18, 18, 18, 18)
        rudder_layout.setSpacing(14)
        rudder_heading_row = QHBoxLayout()
        rudder_heading = QLabel("Rudder-koppeling")
        rudder_heading.setObjectName("sectionTitle")
        rudder_heading_row.addWidget(rudder_heading)
        rudder_heading_row.addStretch()
        self.rudder_import_button = _make_button_compact(QPushButton("Importeren uit Rudder"))
        self.rudder_import_button.setObjectName("primaryButton")
        self.rudder_import_button.clicked.connect(self.import_rudder_event)
        self.rudder_export_button = _make_button_compact(QPushButton("Exporteren naar Rudder"))
        self.rudder_export_button.setObjectName("secondaryButton")
        self.rudder_export_button.clicked.connect(self.export_event_to_rudder)
        self.rudder_open_button = _make_button_compact(QPushButton("Openen in Rudder"))
        self.rudder_open_button.setObjectName("secondaryButton")
        self.rudder_open_button.clicked.connect(self.open_rudder_event_page)
        rudder_heading_row.addWidget(self.rudder_import_button)
        rudder_heading_row.addWidget(self.rudder_export_button)
        rudder_heading_row.addWidget(self.rudder_open_button)
        rudder_layout.addLayout(rudder_heading_row)
        self.rudder_link_status = QLabel("Niet gekoppeld aan Rudder")
        self.rudder_link_status.setObjectName("hintLabel")
        self.rudder_link_status.setWordWrap(True)
        rudder_layout.addWidget(self.rudder_link_status)

        self.rudder_detail_labels = {}
        def add_rudder_group(title, rows):
            group = QGroupBox(title)
            form = QFormLayout(group)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for key, label in rows:
                value = QLabel("Niet ingevuld")
                value.setWordWrap(True)
                value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                self.rudder_detail_labels[key] = value
                form.addRow(label + ":", value)
            return group

        rudder_grid = QGridLayout()
        rudder_grid.setSpacing(12)
        rudder_grid.addWidget(add_rudder_group("Configuratie", [
            ("active", "Status"), ("event_template", "Eventtemplate"),
            ("event_type", "Evenementtype"), ("form_type", "Formuliertype"),
            ("owner", "Rudder-beheerder"),
        ]), 0, 0)
        rudder_grid.addWidget(add_rudder_group("Datum en publicatie", [
            ("dates", "Datum(s) en tijd"), ("publication_date", "Publicatie"),
            ("expiration_date", "Vervaldatum"), ("prior_closing_days", "Inschrijving sluit"),
        ]), 0, 1)
        rudder_grid.addWidget(add_rudder_group("Registratie", [
            ("internal_registration", "Registratie"), ("registrant_limit", "Plaatsenlimiet"),
            ("maximum_registrants", "Maximum registraties"), ("allows_invitees", "Introducees"),
            ("invitees_per_registrant", "Max. introducees p.p."),
        ]), 1, 0)
        rudder_grid.addWidget(add_rudder_group("Doelgroep", [
            ("minimal_education", "Minimum opleiding"), ("minimal_age", "Minimum leeftijd"),
            ("maximal_age", "Maximum leeftijd"), ("reference", "Referentie"),
        ]), 1, 1)
        rudder_grid.addWidget(add_rudder_group("Locatie", [
            ("event_location", "Geselecteerde locatie"), ("location_address", "Adres"),
            ("license_plate_registration", "Kentekenregistratie"),
        ]), 2, 0, 1, 2)
        rudder_grid.setColumnStretch(0, 1)
        rudder_grid.setColumnStretch(1, 1)
        rudder_layout.addLayout(rudder_grid)
        instructions_group = QGroupBox("Aanvullende locatie-instructies")
        instructions_layout = QVBoxLayout(instructions_group)
        self.rudder_location_instructions = QTextBrowser()
        self.rudder_location_instructions.setMinimumHeight(150)
        instructions_layout.addWidget(self.rudder_location_instructions)
        rudder_layout.addWidget(instructions_group)
        security_note = QLabel(
            "EventHub bewaart geen Rudder-wachtwoorden, cookies, CSRF-codes of API-tokens. "
            "Export vult alleen ondersteunde velden in; u controleert en slaat daarna zelf op in Rudder."
        )
        security_note.setObjectName("hintLabel")
        security_note.setWordWrap(True)
        rudder_layout.addWidget(security_note)
        rudder_layout.addStretch()
        rudder_scroll = QScrollArea()
        rudder_scroll.setWidgetResizable(True)
        rudder_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rudder_scroll.setWidget(rudder_content)
        rudder_tab_layout.addWidget(rudder_scroll)
        self.tabs.addTab(rudder_tab, "Rudder")

    def _build_menu(self):
        # De klassieke menubalk blijft technisch bestaan voor acties en sneltoetsen,
        # maar is in EventHub 2 visueel vervangen door sidebar- en headerbediening.
        self.menuBar().setVisible(False)
        file_menu = self.menuBar().addMenu("Bestand")
        save_action = QAction("Opslaan", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_project)
        participant_export_action = QAction("Deelnemerslijst exporteren", self)
        participant_export_action.triggered.connect(self.export_participant_list)
        full_export_action = QAction("Volledige Excel-export", self)
        full_export_action.triggered.connect(self.export_excel)
        restore_action = QAction("Vorige versie herstellen", self)
        restore_action.triggered.connect(self.restore_previous_version)
        file_menu.addAction(save_action)
        file_menu.addAction(participant_export_action)
        file_menu.addAction(full_export_action)
        file_menu.addSeparator()
        file_menu.addAction(restore_action)
        view_menu = self.menuBar().addMenu("Weergave")
        self.focus_action = QAction("Werkgebied maximaliseren", self)
        self.focus_action.setShortcut("F11")
        self.focus_action.setEnabled(False)
        self.focus_action.triggered.connect(self.toggle_event_focus_mode)
        view_menu.addAction(self.focus_action)
        settings_menu = self.menuBar().addMenu("Instellingen")
        general_settings_action = QAction("Algemene instellingen", self)
        general_settings_action.triggered.connect(self.show_application_settings)
        task_defaults_action = QAction("Standaardtaken", self)
        task_defaults_action.triggered.connect(self.show_standard_tasks_page)
        project_templates_action = QAction("Evenementtemplates beheren", self)
        project_templates_action.triggered.connect(self.manage_project_templates)
        settings_menu.addAction(general_settings_action)
        settings_menu.addAction(task_defaults_action)
        settings_menu.addAction(project_templates_action)
        whatsapp_templates_action = QAction("WhatsApp-sjablonen", self)
        whatsapp_templates_action.triggered.connect(self.manage_whatsapp_templates)
        settings_menu.addAction(whatsapp_templates_action)
        settings_menu.addSeparator()
        settings_menu.addAction("Opslaglocaties", self.show_storage_locations)
        settings_menu.addAction("Herstelbestanden beheren", self.manage_recovery_files)
        help_menu = self.menuBar().addMenu("Help")
        tutorial_action = QAction("Rondleiding door EventHub", self)
        tutorial_action.triggered.connect(self.start_tutorial)
        update_action = QAction("Nieuw in deze versie", self)
        update_action.triggered.connect(self.show_changelog)
        about_action = QAction("Over EventHub", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(tutorial_action)
        help_menu.addSeparator()
        help_menu.addAction(update_action)
        help_menu.addSeparator()
        help_menu.addAction(about_action)

    def show_changelog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Nieuw in EventHub {APP_VERSION}")
        _fit_dialog_to_screen(dialog, 560, 410, 460, 320)
        layout = QVBoxLayout(dialog)
        browser = QTextBrowser()
        browser.setHtml(UPDATE_LOG_HTML)
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()
        self.settings.setValue("last_seen_changelog_version", APP_VERSION)

    def maybe_show_changelog(self):
        if UPDATE_LOG_HTML.strip() and self.settings.value("last_seen_changelog_version", "") != APP_VERSION:
            self.show_changelog()

    def show_about_dialog(self):
        QMessageBox.information(
            self,
            "Over EventHub",
            f"{APP_NAME}\nVersie {APP_VERSION}\n\nEen product van Cohentra Digital.\n\n"
            "Dossiers worden lokaal opgeslagen. WhatsApp opent alleen na een bewuste actie. "
            "De Rudder Browserassistent gebruikt uitsluitend een tijdelijke koppeling op deze laptop.",
        )

    def _event_workspace_card(self, eyebrow: str, title: str, description: str, button_text: str, handler, primary: bool = False):
        """Create a reusable EventHub 2 workspace card for an event dossier."""
        card = QFrame()
        card.setObjectName("eventWorkspaceCardPrimary" if primary else "eventWorkspaceCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 13, 15, 13)
        layout.setSpacing(5)
        eyebrow_label = QLabel(eyebrow)
        eyebrow_label.setObjectName("choiceEyebrow")
        title_label = QLabel(title)
        title_label.setObjectName("workspaceCardTitle")
        description_label = QLabel(description)
        description_label.setObjectName("choiceText")
        description_label.setWordWrap(True)
        metric_label = QLabel("—")
        metric_label.setObjectName("workspaceCardMetric")
        button = QPushButton(button_text)
        button.setObjectName("primaryButton" if primary else "secondaryButton")
        button.clicked.connect(handler)
        button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout.addWidget(eyebrow_label)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        layout.addStretch()
        bottom = QHBoxLayout()
        bottom.addWidget(metric_label, 1)
        bottom.addWidget(button)
        layout.addLayout(bottom)
        card.setMinimumHeight(145)
        return card, metric_label, description_label, button

    def _summary_card(self, label: str, value: str, detail: str, compact: bool = False):
        card = QFrame()
        card.setObjectName("compactSummaryCard" if compact else "summaryCard")
        layout = QGridLayout(card) if compact else QVBoxLayout(card)
        if compact:
            layout.setContentsMargins(8, 5, 8, 5)
        else:
            layout.setContentsMargins(18, 13, 18, 13)
        layout.setSpacing(7 if compact else 1)
        heading = QLabel(label.upper())
        heading.setObjectName("cardHeading")
        heading.setWordWrap(True)
        number = QLabel(value)
        number.setObjectName("compactCardNumber" if compact else "cardNumber")
        caption = QLabel(detail)
        caption.setObjectName("cardCaption")
        if compact:
            caption.setWordWrap(True)
            layout.addWidget(heading, 0, 0)
            layout.addWidget(number, 0, 1, Qt.AlignmentFlag.AlignRight)
            layout.addWidget(caption, 1, 0, 1, 2)
            layout.setColumnStretch(0, 1)
        else:
            layout.addWidget(heading)
            layout.addWidget(number)
            layout.addWidget(caption)
        return card, number, caption

    def _new_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setWordWrap(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setMinimumHeight(36)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setShowGrid(False)
        table.horizontalHeader().sortIndicatorChanged.connect(
            lambda column, order, table=table: self._remember_table_sort(table, column, order)
        )
        return table

    def _remember_callback_column_width(self, logical_index: int, old_size: int, new_size: int):
        if getattr(self, "_applying_callback_column_widths", False):
            return
        fields = self.visible_fields_by_view.get("callbacks", [])
        if 0 <= logical_index < len(fields):
            self.settings.setValue(f"callback_column_width/{fields[logical_index]}", int(new_size))

    def _apply_callback_column_widths(self, fields=None):
        if not hasattr(self, "callback_table"):
            return
        fields = list(fields or self.visible_fields_by_view.get("callbacks", []))
        if not fields:
            return

        # Compact where possible, wider only for fields that genuinely need it.
        bounds = {
            "Evenement": (170, 320),
            "Voornaam": (105, 180),
            "Tussenvoegsel": (90, 150),
            "Achternaam": (115, 220),
            "Telefoonnummer": (120, 165),
            "Opleiding": (115, 190),
            "Profiel": (160, 320),
            "Geboortedatum": (115, 150),
            "Geboorteplaats": (130, 220),
            "Email": (180, 300),
            "Geslacht": (95, 130),
        }
        header = self.callback_table.horizontalHeader()
        self._applying_callback_column_widths = True
        try:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            for column, field in enumerate(fields):
                minimum, maximum = bounds.get(field, (100, 240))
                stored = self.settings.value(f"callback_column_width/{field}")
                if stored is not None:
                    try:
                        width = int(stored)
                    except (TypeError, ValueError):
                        width = 0
                else:
                    width = 0
                if width <= 0:
                    header_hint = self.callback_table.fontMetrics().horizontalAdvance(FIELD_LABELS.get(field, field)) + 34
                    content_hint = self.callback_table.sizeHintForColumn(column) + 14
                    width = max(header_hint, content_hint, minimum)
                self.callback_table.setColumnWidth(column, max(minimum, min(maximum, width)))
        finally:
            self._applying_callback_column_widths = False

    def _remember_participant_column_width(self, column: int, _old: int, new: int):
        if getattr(self, "_applying_participant_column_widths", False) or self.loading_tables:
            return
        fields = self.visible_fields_by_view.get("participants", [])
        if 0 <= column < len(fields):
            self.settings.setValue(f"participant_column_width/{fields[column]}", int(new))
        self._update_participant_table_width()

    def _remember_participant_column_order(self, _logical_index: int, _old_visual_index: int, _new_visual_index: int):
        if getattr(self, "_applying_participant_column_order", False) or self.loading_tables:
            return
        if not hasattr(self, "participant_table"):
            return
        fields = list(self.visible_fields_by_view.get("participants", []))
        header = self.participant_table.horizontalHeader()
        ordered_fields = [
            fields[logical_index]
            for logical_index in sorted(range(len(fields)), key=header.visualIndex)
            if 0 <= logical_index < len(fields)
        ]
        self.settings.setValue("participant_column_order", ordered_fields)

    def _apply_participant_column_order(self, fields=None):
        if not hasattr(self, "participant_table"):
            return
        fields = list(fields or self.visible_fields_by_view.get("participants", []))
        if not fields:
            return
        stored = self.settings.value("participant_column_order", [])
        if isinstance(stored, str):
            stored = [stored] if stored else []
        else:
            stored = list(stored or [])
        desired = [field for field in stored if field in fields]
        desired.extend(field for field in fields if field not in desired)
        header = self.participant_table.horizontalHeader()
        self._applying_participant_column_order = True
        try:
            for target_visual_index, field in enumerate(desired):
                logical_index = fields.index(field)
                current_visual_index = header.visualIndex(logical_index)
                if current_visual_index != target_visual_index:
                    header.moveSection(current_visual_index, target_visual_index)
        finally:
            self._applying_participant_column_order = False

    def _update_participant_table_width(self):
        """Pas de totale tabelbreedte aan zonder zichtbare kolommen weg te drukken.

        Bij weinig kolommen blijft de tabel compact. Zijn de zichtbare kolommen
        samen breder dan de beschikbare werkruimte, dan gebruikt de tabel de
        volledige beschikbare breedte en zorgt de horizontale scrollbar ervoor
        dat alle geselecteerde kolommen bereikbaar blijven.
        """
        if not hasattr(self, "participant_table"):
            return
        header = self.participant_table.horizontalHeader()
        if self.participant_table.columnCount() <= 0:
            self.participant_table.setMinimumWidth(320)
            self.participant_table.setMaximumWidth(16777215)
            return

        columns_width = sum(
            header.sectionSize(column)
            for column in range(self.participant_table.columnCount())
            if not self.participant_table.isColumnHidden(column)
        )
        # Frame + ruimte voor een eventuele verticale scrollbar.
        chrome_width = self.participant_table.frameWidth() * 2 + 22
        target_width = max(320, columns_width + chrome_width)

        # De tab heeft 14 px layoutmarge aan beide zijden. Zodra het scherm of
        # venster verandert wordt deze berekening via eventFilter opnieuw gedaan.
        available_width = target_width
        if hasattr(self, "participant_tab"):
            tab_width = self.participant_tab.contentsRect().width()
            if tab_width > 0:
                available_width = max(320, tab_width - 28)

        visible_width = min(target_width, available_width)
        self.participant_table.setMinimumWidth(visible_width)
        # Als alle kolommen passen, blijft bewust lege ruimte naast de tabel.
        # Zijn ze breder dan de werkruimte, dan mag Qt de tabel tot de beschikbare
        # breedte vullen; de horizontale scrollbar toont de rest.
        self.participant_table.setMaximumWidth(
            target_width if target_width <= available_width else 16777215
        )

    def _apply_participant_column_widths(self, fields=None):
        if not hasattr(self, "participant_table"):
            return
        fields = list(fields or self.visible_fields_by_view.get("participants", []))
        self._applying_participant_column_widths = True
        try:
            header = self.participant_table.horizontalHeader()
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            for column, field in enumerate(fields):
                stored = self.settings.value(f"participant_column_width/{field}")
                try:
                    width = int(stored) if stored is not None else 0
                except (TypeError, ValueError):
                    width = 0
                if width <= 0:
                    header_hint = self.participant_table.fontMetrics().horizontalAdvance(FIELD_LABELS.get(field, field)) + 34
                    content_hint = self.participant_table.sizeHintForColumn(column) + 14
                    width = max(90, min(260, max(header_hint, content_hint)))
                self.participant_table.setColumnWidth(column, width)
        finally:
            self._applying_participant_column_widths = False
        self._update_participant_table_width()

    def _remember_table_sort(self, table, column, order):
        sort_key = table.objectName()
        if not sort_key or self.loading_tables:
            return
        self.settings.setValue(f"table_sort/{sort_key}/column", column)
        self.settings.setValue(f"table_sort/{sort_key}/order", int(order.value))

    def _restore_table_sort(self, table):
        sort_key = table.objectName()
        if not sort_key:
            return
        try:
            column = int(self.settings.value(f"table_sort/{sort_key}/column", -1) or -1)
            order = Qt.SortOrder(int(self.settings.value(f"table_sort/{sort_key}/order", 0) or 0))
        except (TypeError, ValueError):
            return
        if 0 <= column < table.columnCount():
            table.horizontalHeader().setSortIndicator(column, order)
            table.sortItems(column, order)

    def _columns_button(self, view: str):
        button = QPushButton("☷")
        button.setObjectName("iconButton")
        button.setFixedSize(36, 36)
        button.setToolTip("Kolommen kiezen")
        button.setAccessibleName("Kolommen kiezen")
        button.clicked.connect(lambda _checked=False, target=view: self.choose_columns(target))
        return button

    def _table_tab(self, hint: str, table: QTableWidget):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        hint_label = QLabel(hint)
        hint_label.setObjectName("hintLabel")
        layout.addWidget(hint_label)
        layout.addWidget(table, 1)
        return widget

    def _load_profile(self):
        try:
            stored = json.loads(self.settings.value("profile", "{}"))
            if not isinstance(stored, dict):
                stored = {}
        except (TypeError, ValueError, json.JSONDecodeError):
            stored = {}
        return {key: str(stored.get(key, default) or "").strip() for key, default in DEFAULT_PROFILE.items()}

    def _load_task_templates(self):
        try:
            stored = json.loads(self.settings.value("task_templates", "[]"))
            if not isinstance(stored, list) or not stored:
                stored = DEFAULT_TASK_TEMPLATES
        except (TypeError, ValueError, json.JSONDecodeError):
            stored = DEFAULT_TASK_TEMPLATES
        # Eenmalige migratie: bestaande gebruikers krijgen de nieuwe
        # standaardtaak, maar kunnen hem daarna gewoon verwijderen of aanpassen.
        if not self.settings.value("participant_list_task_added", False, type=bool):
            default_task = next(
                template for template in DEFAULT_TASK_TEMPLATES
                if template.get("title") == "Deelnemerslijst toevoegen"
            )
            if not any(normalize(template.get("title", "")) == normalize(default_task["title"])
                       for template in stored if isinstance(template, dict)):
                stored.append(deepcopy(default_task))
            self.settings.setValue("participant_list_task_added", True)
        return [prepare_template(template) for template in stored if isinstance(template, dict)]

    def _load_project_templates(self):
        try:
            stored = json.loads(self.settings.value("project_templates", "[]"))
            if not isinstance(stored, list):
                stored = []
        except (TypeError, ValueError, json.JSONDecodeError):
            stored = []
        templates = []
        for template in stored:
            if not isinstance(template, dict) or not isinstance(template.get("event"), dict):
                continue
            name = str(template.get("name", "") or "").strip()
            if not name:
                continue
            templates.append({
                "id": str(template.get("id") or uuid.uuid4().hex),
                "name": name,
                "created_at": str(template.get("created_at", "") or "").strip(),
                "event": deepcopy(template["event"]),
            })
        return templates

    def _load_recent_project_paths(self):
        try:
            stored = json.loads(self.settings.value("recent_project_paths", "[]"))
            if not isinstance(stored, list):
                stored = []
        except (TypeError, ValueError, json.JSONDecodeError):
            stored = []
        paths = []
        for value in stored:
            path = Path(str(value or "")).expanduser()
            if path.is_file() and path.suffix.lower() == ".bvp" and str(path) not in paths:
                paths.append(str(path))
        last_path = Path(str(self.settings.value("last_project_path", "") or "")).expanduser()
        if last_path.is_file() and str(last_path) not in paths:
            paths.insert(0, str(last_path))
        return paths[:12]

    def _refresh_recent_projects_ui(self):
        if not hasattr(self, "recent_project_combo"):
            return
        current = str(self.recent_project_combo.currentData() or "")
        self.recent_project_combo.blockSignals(True)
        self.recent_project_combo.clear()
        if not self.recent_project_paths:
            self.recent_project_combo.addItem("Nog geen recente EventHub-bestanden", "")
        else:
            for value in self.recent_project_paths:
                path = Path(value)
                self.recent_project_combo.addItem(f"{path.stem}  —  {path.parent}", str(path))
        index = self.recent_project_combo.findData(current)
        self.recent_project_combo.setCurrentIndex(index if index >= 0 else 0)
        self.recent_project_combo.blockSignals(False)

    def _remember_project_path(self, path: Path):
        resolved = str(path.expanduser().resolve())
        self.recent_project_paths = [
            resolved,
            *[value for value in self.recent_project_paths if str(Path(value)) != resolved],
        ][:12]
        self.settings.setValue("last_project_path", resolved)
        self.settings.setValue("recent_project_paths", json.dumps(self.recent_project_paths, ensure_ascii=False))
        self._refresh_recent_projects_ui()

    def _load_visible_fields(self):
        defaults = {view: list(fields) for view, fields in DEFAULT_VISIBLE_FIELDS_BY_VIEW.items()}
        try:
            stored = json.loads(self.settings.value("visible_fields_by_view", "{}"))
            if not isinstance(stored, dict):
                stored = {}
            legacy = json.loads(self.settings.value("visible_fields", "[]"))
            if isinstance(legacy, list) and "participants" not in stored:
                stored["participants"] = legacy
            result = {}
            for view, default_fields in defaults.items():
                fields = stored.get(view, default_fields)
                fields = [field for field in ALL_VISITOR_FIELDS if field in fields]
                result[view] = fields or list(default_fields)
            schema_version = int(self.settings.value("visible_fields_schema_version", 1) or 1)
            if schema_version < 2 and "Bezoekerstype" not in result["participants"]:
                insert_at = 1 if result["participants"] and result["participants"][0] == "Evenement" else 0
                result["participants"].insert(insert_at, "Bezoekerstype")
            if schema_version < 2:
                self.settings.setValue("visible_fields_by_view", json.dumps(result))
                self.settings.setValue("visible_fields_schema_version", 2)
            return result
        except (TypeError, ValueError, json.JSONDecodeError):
            return defaults

    def _participant_headers(self):
        return [FIELD_LABELS[field] for field in self.visible_fields_by_view["participants"]]

    def _callback_headers(self):
        return [FIELD_LABELS[field] for field in self.visible_fields_by_view["callbacks"]] + ["Aanwezigheid"]

    def _presence_headers(self):
        fields = self.visible_fields_by_view["presence"]
        return [FIELD_LABELS[field] for field in fields] + ["Aanwezigheid"]

    def choose_columns(self, initial_view: str = "participants"):
        dialog = QDialog(self)
        dialog.setWindowTitle("Kolommen per menu kiezen")
        _fit_dialog_to_screen(dialog, 670, 530, 520, 360)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Kies per menu welke bezoekersgegevens zichtbaar zijn. De vaste werkvelden "
            "Contactstatus, contactdatums, WhatsApp-status, Opmerkingen en Aanwezig blijven automatisch beschikbaar."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        menu_tabs = QTabWidget()
        checkboxes_by_view = {}
        for view, view_label in VIEW_LABELS.items():
            page = QWidget()
            page_layout = QVBoxLayout(page)
            fixed_text = {
                "participants": "Vaste kolom: Selectie",
                "callbacks": "Vaste kolommen: Selectie, Contactstatus, Laatste contact, Opnieuw contact, WhatsApp-status en Opmerkingen",
                "presence": "Vaste kolom: Aanwezig",
            }[view]
            fixed_label = QLabel(fixed_text)
            fixed_label.setObjectName("hintLabel")
            page_layout.addWidget(fixed_label)
            grid = QGridLayout()
            checkboxes = {}
            for index, field in enumerate(ALL_VISITOR_FIELDS):
                checkbox = QCheckBox(FIELD_LABELS[field])
                checkbox.setChecked(field in self.visible_fields_by_view[view])
                checkboxes[field] = checkbox
                grid.addWidget(checkbox, index // 2, index % 2)
            checkboxes_by_view[view] = checkboxes
            page_layout.addLayout(grid)
            page_layout.addStretch()
            menu_tabs.addTab(page, view_label)
        initial_index = list(VIEW_LABELS).index(initial_view) if initial_view in VIEW_LABELS else 0
        menu_tabs.setCurrentIndex(initial_index)
        layout.addWidget(menu_tabs, 1)

        presets = QHBoxLayout()
        default_button = QPushButton("Standaard voor dit menu")
        all_button = QPushButton("Alles tonen in dit menu")

        def select_defaults():
            view = list(VIEW_LABELS)[menu_tabs.currentIndex()]
            for field, checkbox in checkboxes_by_view[view].items():
                checkbox.setChecked(field in DEFAULT_VISIBLE_FIELDS_BY_VIEW[view])

        def select_all():
            view = list(VIEW_LABELS)[menu_tabs.currentIndex()]
            for checkbox in checkboxes_by_view[view].values():
                checkbox.setChecked(True)

        default_button.clicked.connect(select_defaults)
        all_button.clicked.connect(select_all)
        presets.addWidget(default_button)
        presets.addWidget(all_button)
        presets.addStretch()
        layout.addLayout(presets)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected_by_view = {}
        for view, checkboxes in checkboxes_by_view.items():
            selected = [field for field in ALL_VISITOR_FIELDS if checkboxes[field].isChecked()]
            if not selected:
                QMessageBox.information(
                    self,
                    "Geen kolommen gekozen",
                    f"Kies voor {VIEW_LABELS[view]} minimaal één bezoekersgegeven.",
                )
                return
            selected_by_view[view] = selected
        self.visible_fields_by_view = selected_by_view
        self.settings.setValue("visible_fields_by_view", json.dumps(selected_by_view))
        self._mark_dirty()
        self._render_all()
        self.status_label.setText("De zichtbare kolommen zijn per menu bijgewerkt.")

    def _apply_style(self):
        # LET OP: alles onder de return hieronder is dode code. De stijl komt
        # uit theme/styles.py; opmaak die je hier toevoegt doet niets.
        self.setStyleSheet(build_stylesheet(self.dark_mode_enabled))
        if hasattr(self, "neon_edge_overlay"):
            self.neon_edge_overlay.set_dark_mode(self.dark_mode_enabled)
        # De grafieken tekenen zelf en volgen het thema niet via de stylesheet.
        for panel_name in ("own_trend_panel", "loose_trend_panel"):
            panel = getattr(self, panel_name, None)
            if panel is not None:
                for chart_name in ("chart", "overview_chart", "demographic_chart"):
                    chart = getattr(panel, chart_name, None)
                    if chart is not None:
                        chart.set_dark_mode(self.dark_mode_enabled)
        return

        light_style = """
            QMainWindow, QWidget { background: #f6f3f8; color: #2c1b35; font-family: 'Segoe UI'; font-size: 10pt; }
            QLabel { background: transparent; }
            QFrame#masthead { background: #5f2477; border: none; }
            QLabel#appLogo { background: #ffffff; border: 2px solid #ffffff; border-radius: 8px; }
            QLabel#appTitle { color: #ffffff; font-size: 20pt; font-weight: 700; }
            QLabel#appSubtitle { color: #eadff0; font-size: 9.5pt; }
            QLabel#privacyLabel { color: #85e3b2; font-weight: 600; }
            QPushButton#notificationButton { background: #ffffff; color: #5f2477; border: 1px solid #d9c4e1; border-radius: 18px; padding: 7px 13px; font-size: 11pt; }
            QPushButton#notificationButton:hover { background: #f2e8f6; }
            QPushButton#notificationButton[hasNotifications="true"] { background: #fff0c7; color: #7b4b00; border-color: #e6bd5c; }
            QFrame#toolbar, QFrame#summaryCard, QFrame#compactSummaryCard, QFrame#statisticsCard, QFrame#eventBar { background: #ffffff; border: 1px solid #dcd1e1; border-radius: 8px; }
            QPushButton { border-radius: 5px; padding: 8px 13px; font-weight: 600; min-height: 18px; }
            QPushButton#headerButton { background: #71368a; color: #ffffff; border: 1px solid #ad87bd; padding: 7px 11px; }
            QPushButton#headerButton:hover { background: #81449a; }
            QPushButton#headerButton[menuOpen="true"] { background: #a85dc1; border: 2px solid #ffffff; }
            QPushButton#primaryButton { background: #6b2c84; color: white; border: 1px solid #6b2c84; }
            QPushButton#primaryButton:hover { background: #55206a; }
            QPushButton#secondaryButton { background: #ffffff; color: #482158; border: 1px solid #c8b7d0; }
            QPushButton#secondaryButton:hover { background: #f0e8f4; }
            QPushButton#iconButton { background: #ffffff; color: #5f2477; border: 1px solid #c8b7d0; font-size: 17pt; padding: 0; }
            QPushButton#iconButton:hover { background: #f0e8f4; border-color: #6b2c84; }
            QPushButton#iconButton[menuOpen="true"] { background: #e8d8ee; border: 2px solid #6b2c84; }
            QPushButton#activeNavigationButton { background: #e8d8ee; color: #5f2477; border: 2px solid #6b2c84; }
            QPushButton#activeNavigationButton:hover { background: #ddc8e5; }
            QPushButton#dangerButton { background: #ffffff; color: #a0272f; border: 1px solid #ddaeb2; }
            QPushButton#dangerButton:hover { background: #fff1f2; }
            QLabel#cardHeading { color: #65758b; font-size: 8pt; font-weight: 700; }
            QLabel#cardNumber { color: #5f2477; font-size: 20pt; font-weight: 700; }
            QLabel#compactCardNumber { color: #5f2477; font-size: 14pt; font-weight: 700; }
            QLabel#cardCaption, QLabel#hintLabel, QLabel#statusLabel { color: #66778d; font-size: 9pt; }
            QLabel#statisticsTitle { color: #5f2477; font-size: 13pt; font-weight: 700; }
            QLabel#statisticsCaption { color: #75687c; font-size: 9pt; }
            QLabel#sectionTitle { color: #5f2477; font-size: 18pt; font-weight: 700; }
            QGroupBox { background: #ffffff; border: 1px solid #dcd1e1; border-radius: 8px; margin-top: 12px; padding-top: 8px; font-weight: 700; color: #5f2477; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QScrollArea { background: #f6f3f8; border: none; }
            QTabWidget::pane { background: #ffffff; border: 1px solid #dce4ee; border-radius: 6px; }
            QTabBar::tab { background: #e6edf5; color: #42536a; padding: 10px 18px; margin-right: 2px; font-weight: 600; }
            QTabBar::tab:selected { background: #ffffff; color: #6b2c84; }
            QTableWidget { background: #ffffff; alternate-background-color: #faf7fb; border: 1px solid #e1d8e6; selection-background-color: #eadcf0; selection-color: #2c1b35; }
            QHeaderView::section { background: #eee6f2; color: #462453; border: none; border-right: 1px solid #ded2e3; padding: 8px; font-weight: 700; }
            QTableWidget::item { padding: 6px; border-bottom: 1px solid #edf1f5; }
            QLineEdit, QComboBox, QPlainTextEdit, QSpinBox { background: #ffffff; border: 1px solid #b9c7d6; border-radius: 5px; padding: 8px 10px; }
            QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus { border: 2px solid #6b2c84; }
            QCheckBox { spacing: 8px; padding: 4px; }
        """
        dark_style = """
            QMainWindow, QWidget { background: #202124; color: #ece7ef; font-family: 'Segoe UI'; font-size: 10pt; }
            QLabel { background: transparent; color: #ece7ef; }
            QFrame#masthead { background: #32133f; border: none; }
            QLabel#appLogo { background: #2b2d31; border: 2px solid #5b3970; border-radius: 8px; }
            QLabel#appTitle { color: #ffffff; font-size: 20pt; font-weight: 700; }
            QLabel#appSubtitle, QLabel#hintLabel, QLabel#statusLabel { color: #bdb2c5; }
            QLabel#privacyLabel { color: #85e3b2; font-weight: 600; }
            QPushButton#notificationButton, QPushButton#secondaryButton, QPushButton#iconButton { background: #2b2d31; color: #eadff0; border: 1px solid #65516d; }
            QPushButton#notificationButton:hover, QPushButton#secondaryButton:hover, QPushButton#iconButton:hover { background: #3b3040; border-color: #a879b7; }
            QPushButton#primaryButton { background: #71368a; color: white; border: 1px solid #a879b7; }
            QPushButton#primaryButton:hover { background: #8a4aa3; }
            QPushButton#activeNavigationButton { background: #5b3970; color: #ffffff; border: 2px solid #c59bd3; }
            QPushButton#dangerButton { background: #30282c; color: #ff9da5; border: 1px solid #a55d66; }
            QFrame#toolbar, QFrame#summaryCard, QFrame#compactSummaryCard, QFrame#statisticsCard, QFrame#eventBar, QGroupBox { background: #292b30; border: 1px solid #48424d; border-radius: 8px; color: #eadff0; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #d8bddf; }
            QLabel#cardHeading { color: #bdb2c5; }
            QLabel#cardNumber, QLabel#compactCardNumber, QLabel#sectionTitle, QLabel#statisticsTitle { color: #d8a9e6; }
            QScrollArea, QTabWidget::pane { background: #202124; border: none; }
            QTabBar::tab { background: #34363b; color: #cfc5d3; padding: 10px 18px; margin-right: 2px; font-weight: 600; }
            QTabBar::tab:selected { background: #292b30; color: #e2b4ee; }
            QTableWidget { background: #292b30; alternate-background-color: #25272b; border: 1px solid #48424d; selection-background-color: #50365c; selection-color: #ffffff; }
            QHeaderView::section { background: #3b3040; color: #eadff0; border: none; border-right: 1px solid #51445a; padding: 8px; font-weight: 700; }
            QLineEdit, QComboBox, QPlainTextEdit, QSpinBox { background: #25272b; color: #f1ecf3; border: 1px solid #655d6b; border-radius: 5px; padding: 8px 10px; }
            QCheckBox { spacing: 8px; padding: 4px; }
        """
        self.setStyleSheet(dark_style if self.dark_mode_enabled else light_style)












































    def _active_event(self):
        event = self._event_by_id(self.active_event_id) if self.active_event_id else None
        if event:
            return event
        if len(self.selected_events) == 1:
            return self._event_by_name(next(iter(self.selected_events)))
        return None

    def switch_event(self):
        """Wissel van evenementdossier zonder eerst terug naar het overzicht.

        Hetzelfde keuzevenster als in de werkruimtes; het huidige evenement
        staat er gemarkeerd in, zodat je ziet waar je vandaan komt.
        """
        if not self.events:
            QMessageBox.information(self, "Geen evenementen", "Maak eerst een evenement aan.")
            return
        huidig = self._active_event() or {}
        gesorteerd = sorted(self.events, key=self._event_sort_key)
        dialog = EventPickerDialog(
            gesorteerd, str(huidig.get("id", "")), self,
            aanmeldingen=self._registration_lines(gesorteerd),
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.chosen_id:
            return
        if dialog.chosen_id == str(huidig.get("id", "")):
            return
        gekozen = self._event_by_id(dialog.chosen_id)
        if gekozen:
            self.open_event(gekozen)

    def _update_event_workspace_header(self):
        if not hasattr(self, "event_title_label"):
            return
        event = self._active_event()
        if not event:
            self.event_title_label.setText("Geen evenement geopend")
            self.event_meta_label.setText("Ga terug naar Evenementen en open een evenement.")
            self.event_details_label.setText("")
            if hasattr(self, "event_status_badge"):
                self.event_status_badge.setText("Geen evenement")
            return
        self.active_event_id = event.get("id", "")
        self.event_title_label.setText(event.get("name", "Onbenoemd evenement"))
        time_text = " – ".join(filter(None, [event.get("start_time", ""), event.get("end_time", "")]))
        meta = "  •  ".join(filter(None, [
            event.get("event_type", ""), event.get("date", ""), time_text, event.get("place", ""),
            event.get("location", ""),
        ]))
        self.event_meta_label.setText(meta or "Nog geen datum of locatie ingevuld")
        status = str(event.get("status", "") or "Niet ingesteld")
        if hasattr(self, "event_status_badge"):
            self.event_status_badge.setText(status)
            self.event_status_badge.setProperty("statusKind", normalize(status))
            self.event_status_badge.style().unpolish(self.event_status_badge)
            self.event_status_badge.style().polish(self.event_status_badge)
        event_records = self._event_visitors(event)
        regular_records = [row for row in event_records if not is_introducee(row)]
        callbacks_done = sum(
            callback_is_done(row) or str(row.get("WhatsAppStatus", "")) == "Verzonden"
            for row in regular_records
        )
        open_callbacks = max(0, len(regular_records) - callbacks_done)
        open_tasks = sum(not bool(task.get("done")) for task in event.get("tasks", []))
        present = sum(is_present(row, event.get("name", "")) for row in event_records)
        attachments = event.get("attachments", []) if isinstance(event.get("attachments", []), list) else []
        contact = " — ".join(filter(None, [
            event.get("external_contact", ""), event.get("external_contact_reachability", ""),
        ])) or "Niet ingevuld"
        self.event_details_label.setText(
            f"<p><b>Soort evenement:</b> {escape(event.get('event_type', '') or 'Niet ingevuld')}<br>"
            f"<b>Template:</b> {escape(next((t['name'] for t in self.project_templates if t['id'] == event.get('template_id')), event.get('template_name') or 'Zonder template'))}<br>"
            f"<b>Datum:</b> {escape(event.get('date', '') or 'Niet ingevuld')}<br>"
            f"<b>Tijd:</b> {escape(time_text or 'Niet ingevuld')}<br>"
            f"<b>Regio:</b> {escape(event.get('region', '') or 'Niet ingevuld')}<br>"
            f"<b>Locatie:</b> {escape(' — '.join(filter(None, [event.get('place', ''), event.get('location', '')])) or 'Niet ingevuld')}<br>"
            f"<b>Adres:</b> {escape(event.get('location_address', '') or 'Niet ingevuld')}<br>"
            f"<b>Max. registraties:</b> {escape(event.get('maximum_registrants', '') or 'Niet ingevuld')}<br>"
            f"<b>Contact:</b> {escape(contact)}<br>"
            f"<b>Doelgroep:</b> {escape(event.get('target_audience', '') or 'Niet ingevuld')}</p>"
            + self._listings_html(event)
            + f"<p><b>Beschrijving</b><br>{escape(event.get('description', '') or 'Niet ingevuld')}</p>"
        )

    def _listings_html(self, event: dict) -> str:
        """Waaruit dit evenement is samengevoegd; leeg als dat niet zo is."""
        samengevoegd = self._event_listings(event)
        if not samengevoegd:
            return ""
        regels = "<br>".join(
            f"{escape(label)} — {aantal} deelnemer(s)" for label, aantal in samengevoegd
        )
        return (
            f"<p><b>Samengevoegd uit {len(samengevoegd)} inschrijvingen</b><br>{regels}</p>"
        )

    def _render_rudder_tab(self):
        if not hasattr(self, "rudder_link_status"):
            return
        event = self._active_event()
        data = event.get("rudder_data", {}) if event and isinstance(event.get("rudder_data"), dict) else {}
        connected = is_rudder_event_linked(event)
        if connected:
            self.rudder_link_status.setText(
                f"Rudder gekoppeld · Laatst gesynchroniseerd: {human_sync_time(event.get('rudder_last_synced_at', ''))}"
            )
        else:
            self.rudder_link_status.setText("Niet gekoppeld aan Rudder")
        self.rudder_import_button.setText("Bijwerken uit Rudder" if connected else "Importeren uit Rudder")
        self.rudder_export_button.setVisible(connected)
        self.rudder_open_button.setVisible(connected)

        def yes_no(value):
            if value is None or value == "":
                return "Niet ingevuld"
            return "Ja" if bool(value) else "Nee"

        dates = []
        for item in data.get("dates", []) if isinstance(data.get("dates"), list) else []:
            parsed = parse_date(item.get("date", ""))
            day = parsed.strftime("%d-%m-%Y") if parsed else str(item.get("date", "") or "")
            times = " – ".join(filter(None, [str(item.get("start_time", "") or ""), str(item.get("end_time", "") or "")]))
            dates.append(" · ".join(filter(None, [day, times])))
        values = {
            "active": "Actief" if data.get("active") is True else "Inactief" if data.get("active") is False else "Niet ingevuld",
            "event_template": data.get("event_template", ""),
            "event_type": data.get("event_type", ""),
            "form_type": data.get("form_type", ""),
            "owner": data.get("owner", ""),
            "dates": "\n".join(dates),
            "publication_date": data.get("publication_date", ""),
            "expiration_date": data.get("expiration_date", ""),
            "prior_closing_days": f"{data.get('prior_closing_days')} dag(en) voor het evenement" if str(data.get("prior_closing_days", "")) else "",
            "internal_registration": "Intern" if data.get("internal_registration") is True else "Extern" if data.get("internal_registration") is False else "",
            "registrant_limit": yes_no(data.get("registrant_limit")),
            "maximum_registrants": data.get("maximum_registrants", ""),
            "allows_invitees": yes_no(data.get("allows_invitees")),
            "invitees_per_registrant": data.get("invitees_per_registrant", ""),
            "minimal_education": data.get("minimal_education", ""),
            "minimal_age": data.get("minimal_age", ""),
            "maximal_age": data.get("maximal_age", ""),
            "reference": data.get("reference", ""),
            "event_location": data.get("event_location", ""),
            "location_address": data.get("location_address", ""),
            "license_plate_registration": yes_no(data.get("license_plate_registration")),
        }
        for key, label in self.rudder_detail_labels.items():
            label.setText(str(values.get(key, "") or "Niet ingevuld"))
        instructions = str(data.get("location_instructions", "") or "").strip()
        self.rudder_location_instructions.setHtml(instructions or "<p><i>Niet ingevuld</i></p>")

    def open_event(self, event: dict, tab: QWidget | None = None, stil: bool = False):
        """Open een evenementdossier.

        Met ``stil`` blijft het bij tonen: geen presentiesynchronisatie en geen
        aantekening dat het dossier is geopend. Dat is wat de rondleiding
        nodig heeft; die mag niets wijzigen en al helemaal geen venster openen
        dat achter de rondleidingslaag verdwijnt.
        """
        if not event:
            return
        self.event_focus_mode = True
        self.settings.setValue("event_focus_mode", True)
        if hasattr(self, "participant_include_introducees"):
            self.participant_include_introducees.setChecked(True)
            self.settings.setValue("participants_include_introducees", True)
        self.active_event_id = event.get("id", "")
        self.selected_events = {event.get("name", "")}
        if not stil:
            self._touch_event(event, opened=True)
            self._sync_latest_live_attendance_for_event(event)
        self._render_all()
        self.page_stack.setCurrentWidget(self.event_page)
        self._set_project_context_ui(True)
        self._set_navigation_active("events")
        self.app_title.setText(event.get("name", "Evenement"))
        self.app_subtitle.setText("Evenementdossier")
        self.tabs.setCurrentWidget(tab or self.event_overview_tab)
        self.status_label.setText(f"Evenement geopend: {event.get('name', 'Onbenoemd evenement')}.")

    def show_home(self):
        self.page_stack.setCurrentWidget(self.home_page)
        self._set_project_context_ui(False)
        self._set_navigation_active(None)
        self._render_management()
        self.status_label.setText("Home — je operationele startpunt.")

    def back_to_home(self):
        # Historische methodenaam: terugknoppen vanuit dossiers horen naar het
        # bestaande evenementenoverzicht te gaan, niet naar het nieuwe Home.
        self.page_stack.setCurrentWidget(self.events_page)
        self._set_project_context_ui(False)
        self._set_navigation_active("events")
        self._render_management()
        self.status_label.setText("Evenementen — selecteer een evenement om het dossier te openen.")

    def _continue_home_context(self):
        event = self._active_event()
        if event:
            self.open_event(event)
        else:
            self.back_to_home()

    def _open_home_today_event(self):
        event = self._event_by_id(getattr(self, "_home_today_event_id", ""))
        if event:
            self.open_event(event)
        else:
            self.back_to_home()

    def _open_home_today_live_session(self):
        event = self._event_by_id(getattr(self, "_home_today_event_id", ""))
        if not event:
            self.back_to_home()
            return
        self.active_event_id = event.get("id", "")
        self.selected_events = {event.get("name", "")}
        self._sync_event_combo(self.event_control_event_combo)
        self.event_control_event_combo.set_current_id(event.get("id", ""))
        self.show_event_control_page()
        self.event_control_tabs.setCurrentWidget(self.live_session_tab)
        self.status_label.setText(f"Event Control — Live sessie · {event.get('name', 'Evenement')}")

    def show_tasks(self):
        event = self._active_event()
        if event and self.page_stack.currentWidget() is self.event_page:
            self.open_event(event, self.tasks_tab)
            return
        if not self.events:
            QMessageBox.information(self, "Geen evenementen", "Maak eerst een evenement aan om taken te bekijken.")
            return
        events = sorted(self.events, key=self._event_sort_key)
        if len(events) == 1:
            self.open_event(events[0], self.tasks_tab)
            return
        labels = [
            f"{event.get('name', 'Onbenoemd evenement')} — {event.get('date', 'Geen datum')}"
            for event in events
        ]
        choice, accepted = QInputDialog.getItem(
            self,
            "Taken openen",
            "Kies een evenement:",
            labels,
            0,
            False,
        )
        if accepted:
            selected_index = labels.index(choice)
            self.open_event(events[selected_index], self.tasks_tab)

    def toggle_event_focus_mode(self):
        # Op Trends maximaliseert dezelfde sneltoets de grafiek; dat is daar het
        # werkgebied waar je ruimte voor wilt.
        if self.page_stack.currentWidget() is self.trends_page:
            panel = self._active_trend_panel()
            panel.open_chart_window()
            self.status_label.setText("Trends — ontwikkeling over evenementen heen.")
            return
        if self.page_stack.currentWidget() is not self.event_page:
            self.status_label.setText("Open eerst een evenement om het werkgebied te maximaliseren.")
            return
        self.event_focus_mode = not self.event_focus_mode
        self.settings.setValue("event_focus_mode", self.event_focus_mode)
        self._apply_event_focus_mode()

    def _apply_event_focus_mode(self):
        focus = bool(self.event_focus_mode)
        self.event_summary_bar.setVisible(True)
        self.event_meta_label.setVisible(not focus)
        if focus:
            self.event_header_layout.setContentsMargins(10, 5, 10, 5)
        else:
            self.event_header_layout.setContentsMargins(14, 9, 14, 9)
        self.event_header_layout.setSpacing(3 if focus else 7)
        button_text = "Overzicht verbergen" if not focus else "Overzicht tonen"
        if hasattr(self, "focus_action"):
            self.focus_action.setText(button_text)

    def _set_project_context_ui(self, active: bool):
        """Gebruik een compacte kop binnen dossiers en de ruime kop bij Evenementen."""
        if self.app_logo is not None:
            self.app_logo.setVisible(not active)
        self.app_subtitle.setVisible(not active)
        if active:
            self.masthead_layout.setContentsMargins(18, 7, 18, 7)
            self.body_layout.setContentsMargins(12, 8, 12, 8)
        else:
            self.masthead_layout.setContentsMargins(24, 12, 24, 12)
            self.body_layout.setContentsMargins(24, 12, 24, 12)
        self.body_layout.setSpacing(7 if active else 14)
        self.event_page_layout.setSpacing(6 if active else 12)
        title_font = self.app_title.font()
        title_font.setPointSize(13 if active else 16)
        title_font.setWeight(QFont.Weight.Bold)
        self.app_title.setFont(title_font)
        if hasattr(self, "focus_action"):
            self.focus_action.setEnabled(active)
        if active:
            self._apply_event_focus_mode()

    def edit_active_event(self):
        event = self._active_event()
        if not event:
            QMessageBox.information(self, "Geen evenement geopend", "Open eerst een evenement bij Evenementen.")
            return
        self._edit_event(event)

    def show_notifications(self):
        notifications = self._all_notifications()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Meldingen ({len(notifications)})")
        _fit_dialog_to_screen(dialog, 900, 480, 620, 340)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Taken van alle evenementen die verlopen zijn, vandaag moeten gebeuren of binnen de ingestelde "
            f"meldingstermijn vallen. Paars gemarkeerd: evenementen waarvan de persoonsgegevens binnen "
            f"{RETENTION_WARNING_DAYS} dagen automatisch worden verwijderd — exporteer vóór die datum wat u nodig heeft."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        table = self._new_table(["Deadline", "Evenement", "Taak", "Melding"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        def render_notifications():
            current = self._all_notifications()
            table.setRowCount(len(current))
            for row_index, notification in enumerate(current):
                values = [
                    notification["due"].strftime("%d-%m-%Y"), notification["event_name"],
                    notification["task_title"], notification["message"],
                ]
                color = {
                    "overdue": QColor("#fde1e1"), "today": QColor("#fff0c7"), "soon": QColor("#edf5ff"),
                    "retention": QColor("#efe3fb"),
                }.get(notification["severity"], QColor("#edf5ff"))
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        (notification["event_id"], notification["task_id"]),
                    )
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setBackground(color)
                    table.setItem(row_index, column, item)
            if not current:
                table.setRowCount(1)
                item = QTableWidgetItem("Geen actieve meldingen. Wonderen bestaan blijkbaar toch.")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setSpan(0, 0, 1, 4)
                table.setItem(0, 0, item)

        def selected_ids():
            row = table.currentRow()
            item = table.item(row, 0) if row >= 0 else None
            data = item.data(Qt.ItemDataRole.UserRole) if item else None
            return tuple(data) if isinstance(data, (tuple, list)) and len(data) == 2 else ("", "")

        def open_selected():
            event_id, task_id = selected_ids()
            event = self._event_by_id(event_id)
            if not event:
                return
            dialog.accept()
            self.open_event(event, self.tasks_tab)
            self._select_task(task_id)

        def complete_selected():
            event_id, task_id = selected_ids()
            event = self._event_by_id(event_id)
            if event_id and not task_id:
                QMessageBox.information(
                    dialog,
                    "Bewaartermijn",
                    "Een aankondiging van de bewaartermijn kan niet worden afgevinkt. "
                    "Exporteer wat u nodig heeft; op de genoemde datum worden de "
                    "persoonsgegevens automatisch verwijderd.",
                )
                return
            task = next((item for item in event.get("tasks", []) if item.get("id") == task_id), None) if event else None
            if not task:
                QMessageBox.information(dialog, "Geen melding gekozen", "Selecteer eerst een melding.")
                return
            task["done"] = True
            task["completed_on"] = date.today().strftime("%d-%m-%Y")
            self._sync_event_status_from_tasks(event)
            self._mark_dirty()
            self._render_all()
            render_notifications()

        layout.addWidget(table, 1)
        buttons = QHBoxLayout()
        open_button = QPushButton("Evenement en taak openen")
        open_button.setObjectName("primaryButton")
        open_button.clicked.connect(open_selected)
        done_button = QPushButton("Markeren als afgerond")
        done_button.setObjectName("secondaryButton")
        done_button.clicked.connect(complete_selected)
        close_button = QPushButton("Sluiten")
        close_button.clicked.connect(dialog.reject)
        buttons.addWidget(open_button)
        buttons.addWidget(done_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        table.cellDoubleClicked.connect(lambda *_: open_selected())
        render_notifications()
        dialog.exec()

    def _upcoming_events(self, days: int | None = None):
        today = date.today()
        horizon = today + timedelta(days=days if days is not None else self._upcoming_window_days())
        upcoming = []
        for event in self.events:
            event_date = parse_date(event.get("date", ""))
            if not event_date or not today <= event_date <= horizon:
                continue
            if event.get("status") in {"Afgerond", "Geannuleerd"}:
                continue
            upcoming.append(event)
        return sorted(upcoming, key=lambda item: (parse_date(item.get("date", "")), normalize(item.get("name", ""))))

    def maybe_show_startup_welcome(self):
        mode = self._startup_welcome_mode()
        if mode == "never":
            return
        notifications = self._all_notifications()
        upcoming = self._upcoming_events()
        first_tutorial_invitation = not self.settings.value("tutorial_invitation_seen", False, type=bool)
        if mode == "always" or notifications or upcoming or first_tutorial_invitation:
            self.show_startup_welcome(notifications, upcoming)

    def show_startup_welcome(self, notifications=None, upcoming=None):
        notifications = list(self._all_notifications() if notifications is None else notifications)
        upcoming = list(self._upcoming_events() if upcoming is None else upcoming)
        self.settings.setValue("tutorial_invitation_seen", True)

        dialog = QDialog(self)
        dialog.setWindowTitle("Welkom bij EventHub")
        _fit_dialog_to_screen(dialog, 1000, 680, 700, 480)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(13)

        header = QHBoxLayout()
        if LOGO_PATH.exists():
            logo = QLabel()
            logo.setPixmap(QPixmap(str(LOGO_PATH)).scaled(
                72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
            logo.setFixedSize(82, 82)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.addWidget(logo)
        heading = QVBoxLayout()
        profile_name = self.profile.get("name") or "collega"
        title = QLabel(f"Welkom terug, {profile_name}")
        title.setObjectName("sectionTitle")
        months = (
            "januari", "februari", "maart", "april", "mei", "juni",
            "juli", "augustus", "september", "oktober", "november", "december",
        )
        weekdays = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")
        today = date.today()
        subtitle = QLabel(
            f"{weekdays[today.weekday()].capitalize()} {today.day} {months[today.month - 1]} {today.year}  •  "
            f"{len(notifications)} melding(en)  •  {len(upcoming)} aankomend(e) evenement(en)"
        )
        subtitle.setObjectName("hintLabel")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        layout.addLayout(header)

        summary = QLabel(
            "Hier staat wat nu aandacht vraagt. Vanuit dit scherm opent u rechtstreeks het juiste evenement of de juiste taak."
            if notifications or upcoming else
            "Er zijn momenteel geen actieve meldingen of naderende evenementen. Een zeldzaam administratief natuurverschijnsel."
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        panels = QHBoxLayout()
        panels.setSpacing(12)
        notification_box = QGroupBox(f"Actie vereist ({len(notifications)})")
        notification_layout = QVBoxLayout(notification_box)
        notification_table = self._new_table(["Deadline", "Evenement", "Taak", "Status"])
        notification_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        notification_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        notification_table.setRowCount(max(1, len(notifications)))
        if notifications:
            for row_index, notification in enumerate(notifications):
                values = [
                    notification["due"].strftime("%d-%m-%Y"), notification["event_name"],
                    notification["task_title"], notification["message"],
                ]
                color = {
                    "overdue": QColor("#fde1e1"), "today": QColor("#fff0c7"), "soon": QColor("#edf5ff"),
                    "retention": QColor("#efe3fb"),
                }.get(notification["severity"], QColor("#edf5ff"))
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setData(Qt.ItemDataRole.UserRole, (notification["event_id"], notification["task_id"]))
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    item.setBackground(color)
                    notification_table.setItem(row_index, column, item)
        else:
            item = QTableWidgetItem("Geen actieve taakmeldingen")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            notification_table.setSpan(0, 0, 1, 4)
            notification_table.setItem(0, 0, item)
        notification_layout.addWidget(notification_table, 1)
        open_task_button = QPushButton("Geselecteerde taak openen")
        open_task_button.setObjectName("primaryButton")
        notification_layout.addWidget(open_task_button)
        panels.addWidget(notification_box, 1)

        upcoming_box = QGroupBox(f"Komende {self._upcoming_window_days()} dagen ({len(upcoming)})")
        upcoming_layout = QVBoxLayout(upcoming_box)
        upcoming_table = self._new_table(["Datum", "Evenement", "Soort", "Locatie"])
        upcoming_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        upcoming_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        upcoming_table.setRowCount(max(1, len(upcoming)))
        if upcoming:
            for row_index, event in enumerate(upcoming):
                values = [
                    event.get("date", ""), event.get("name", "Onbenoemd evenement"),
                    event.get("event_type", ""), " — ".join(filter(None, [event.get("place", ""), event.get("location", "")])),
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value or ""))
                    item.setData(Qt.ItemDataRole.UserRole, event.get("id", ""))
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    upcoming_table.setItem(row_index, column, item)
        else:
            item = QTableWidgetItem("Geen evenementen binnen de ingestelde periode")
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            upcoming_table.setSpan(0, 0, 1, 4)
            upcoming_table.setItem(0, 0, item)
        upcoming_layout.addWidget(upcoming_table, 1)
        open_event_button = QPushButton("Geselecteerd evenement openen")
        open_event_button.setObjectName("primaryButton")
        upcoming_layout.addWidget(open_event_button)
        panels.addWidget(upcoming_box, 1)
        layout.addLayout(panels, 1)

        def open_notification():
            row = notification_table.currentRow()
            item = notification_table.item(row, 0) if row >= 0 else None
            data = item.data(Qt.ItemDataRole.UserRole) if item else None
            if not isinstance(data, (tuple, list)) or len(data) != 2:
                QMessageBox.information(dialog, "Geen taak gekozen", "Selecteer eerst een taakmelding.")
                return
            event = self._event_by_id(data[0])
            if not event:
                return
            dialog.accept()
            self.open_event(event, self.tasks_tab)
            self._select_task(data[1])

        def open_upcoming_event():
            row = upcoming_table.currentRow()
            item = upcoming_table.item(row, 0) if row >= 0 else None
            event_id = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
            event = self._event_by_id(event_id)
            if not event:
                QMessageBox.information(dialog, "Geen evenement gekozen", "Selecteer eerst een evenement.")
                return
            dialog.accept()
            self.open_event(event)

        def start_tour():
            dialog.accept()
            QTimer.singleShot(0, self.start_tutorial)

        def open_preferences():
            dialog.accept()
            QTimer.singleShot(0, self.edit_profile)

        open_task_button.clicked.connect(open_notification)
        open_event_button.clicked.connect(open_upcoming_event)
        notification_table.cellDoubleClicked.connect(lambda *_: open_notification())
        upcoming_table.cellDoubleClicked.connect(lambda *_: open_upcoming_event())

        actions = QHBoxLayout()
        tutorial_button = QPushButton("Rondleiding door EventHub")
        tutorial_button.setObjectName("secondaryButton")
        tutorial_button.clicked.connect(start_tour)
        preferences_button = QPushButton("Opstartinstellingen")
        preferences_button.setObjectName("secondaryButton")
        preferences_button.clicked.connect(open_preferences)
        continue_button = QPushButton("Naar EventHub")
        continue_button.setObjectName("primaryButton")
        continue_button.clicked.connect(dialog.accept)
        actions.addWidget(tutorial_button)
        actions.addWidget(preferences_button)
        actions.addStretch()
        actions.addWidget(continue_button)
        layout.addLayout(actions)
        dialog.exec()

    def open_live_session_manual(self):
        """Toon de handleiding livesessies; bewaren hoeft niet.

        Eerder vroeg dit om een opslaglocatie, maar dan blijft er een bestand
        achter dat vrijwel niemand terugleest. De handleiding wordt nu in de
        tijdelijke map gezet en meteen geopend; wie hem wil doorsturen slaat
        hem vanuit de viewer op.
        """
        try:
            doelmap = Path(tempfile.gettempdir()) / "EventHub"
            doelmap.mkdir(parents=True, exist_ok=True)
            bestand = doelmap / "EventHub - handleiding livesessie.pdf"

            document = QTextDocument(self)
            document.setDefaultFont(QFont("Segoe UI", 10))
            document.setHtml(manual_html(str(self.profile.get("name", "") or "")))
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(str(bestand))
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            printer.setPageMargins(QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter)
            document.print_(printer)

            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(bestand))):
                QMessageBox.warning(
                    self,
                    "Openen mislukt",
                    "De handleiding kon niet worden geopend. Het bestand staat in:\n"
                    f"{bestand}",
                )
                return
            self.status_label.setText("Handleiding livesessies geopend.")
        except Exception as exc:
            self._show_runtime_error("Handleiding openen", exc)

    def _tutorial_is_running(self) -> bool:
        """Staat er al een rondleiding open?

        Na afloop vernietigt Qt de overlay terwijl de Python-verwijzing blijft
        bestaan; isVisible() geeft dan een RuntimeError. Die vangen we op en
        behandelen hem als 'er loopt niets meer'.
        """
        overlay = getattr(self, "_tutorial_overlay", None)
        if overlay is None:
            return False
        try:
            if overlay.isVisible():
                overlay.raise_()
                return True
        except RuntimeError:
            pass
        self._tutorial_overlay = None
        return False

    def start_live_session_tour(self, *_):
        """Losse uitleg over samen inchecken met meerdere apparaten.

        Bewust gescheiden van de algemene rondleiding: die geeft een overzicht
        van de hele applicatie, terwijl dit onderwerp om context op de plek
        zelf vraagt en anders onevenredig veel stappen zou opeisen.
        """
        if self._tutorial_is_running():
            return

        original_tab = self.event_control_tabs.currentWidget()

        def show_live_tab():
            self.show_event_control_page()
            self.event_control_tabs.setCurrentWidget(self.live_session_tab)

        steps = [
            {
                "title": "Samen inchecken op één sessie",
                "body": "Bij een livesessie draait dit apparaat als host. Laptops, tablets en telefoons "
                        "op hetzelfde netwerk checken dan tegelijk bezoekers in, op dezelfde lijst. "
                        "Internet is niet nodig.",
                "prepare": show_live_tab,
                "target": lambda: self.live_start_card,
            },
            {
                "title": "De sessie starten",
                "body": "Naam, datum, locatie en de al ingeladen deelnemers komen uit het gekozen evenement. "
                        "Iedereen start als niet ingecheckt. U krijgt een QR-code, een netwerkadres en een "
                        "sessiecode om de andere apparaten mee aan te melden.",
                "prepare": show_live_tab,
                "target": lambda: self.start_live_button,
            },
            {
                "title": "Een apparaat laten meedoen",
                "body": "Op een telefoon of tablet opent u de verbindpagina en scant u de QR-code of vult u "
                        "de sessiecode in. Op iOS kunt u de pagina via Deel, Zet op beginscherm "
                        "schermvullend openen.",
                "prepare": show_live_tab,
                "target": lambda: self.live_join_card,
            },
            {
                "title": "Onderbrekingen overleven",
                "body": "Valt het netwerk even weg, dan bewaren de apparaten hun handelingen en "
                        "synchroniseren ze daarna vanzelf. Tijdens een actieve sessie maakt EventHub elke "
                        "minuut een herstelkopie.",
                "prepare": show_live_tab,
                "target": lambda: self.live_session_status_label,
            },
            {
                "title": "Meekijken tijdens het evenement",
                "body": "Het live dashboard toont in de browser hoeveel mensen binnen zijn, wat het "
                        "opkomstpercentage is en welke apparaten meedoen. Handig om open te zetten op een "
                        "tweede scherm. Zodra de livesessie actief is, staat de dashboardknop bij de sessiestatus.",
                "prepare": show_live_tab,
                "target": lambda: self.live_session_tab,
            },
            {
                "title": "Terug in het dossier",
                "body": "In- en uitchecken schrijft EventHub terug naar de aanwezigheid van dit evenement, "
                        "zodat presentie, statistieken en de Rudder-export erop aansluiten. Een eerdere "
                        "sessie heropent u met Vorige sessie opnieuw openen.",
                "prepare": show_live_tab,
                "target": lambda: self.reopen_previous_live_button,
            },
        ]

        def finish_live_tour(completed: bool = True):
            del completed
            self._tutorial_overlay = None
            if original_tab is not None:
                index = self.event_control_tabs.indexOf(original_tab)
                if index >= 0:
                    self.event_control_tabs.setCurrentIndex(index)
            self.status_label.setText("Uitleg live sessies afgerond.")

        # TutorialOverlay toont zichzelf al in __init__, net als bij de
        # hoofdrondleiding.
        self._tutorial_overlay = TutorialOverlay(self, steps, finish_live_tour)

    def _show_trends_for_tutorial(self):
        # Alleen tonen: de normale navigatie kan historische cijfers bijwerken.
        self.page_stack.setCurrentWidget(self.trends_page)
        self._set_project_context_ui(False)
        self._set_navigation_active("trends")
        self._render_trends()

    def start_trends_tour(self, *_):
        if self._tutorial_is_running():
            return
        original_page = self.page_stack.currentWidget()
        original_workspace = self.trend_tabs.currentIndex()
        original_navigation = next((name for name, button in self.sidebar_buttons.items()
                                    if button.objectName() == "sidebarButtonActive"), None)
        original_heading = (self.app_title.text(), self.app_subtitle.text())
        original_focus_mode = self.event_focus_mode
        original_focus_action = (self.focus_action.isEnabled(), self.focus_action.text())
        panel = self.own_trend_panel if original_workspace == 0 else self.loose_trend_panel
        original_analysis = panel.analysis_tabs.currentIndex()

        def show_analysis():
            self._show_trends_for_tutorial()
            self.trend_tabs.setCurrentIndex(original_workspace)
            panel.analysis_tabs.setCurrentIndex(1)

        def show_loose():
            self._show_trends_for_tutorial()
            self.trend_tabs.setCurrentIndex(1)

        steps = [
            dict(title="Kies uw gegevens", body="Eigen evenementen en Losse analyse zijn gescheiden werkgebieden. "
                 "Bij eigen evenementen moeten de aanwezigheidscijfers zijn afgerond. Onbekende aanwezigheidsstatussen "
                 "kunnen ervoor zorgen dat een evenement nog niet meetelt.",
                 prepare=self._show_trends_for_tutorial, target=lambda: self.trend_tabs),
            dict(title="Periode en selectie", body="Alle perioden gebruikt alle beschikbare gegevens. Kies een kortere "
                 "periode of filter op template, locatie of evenement voor een gerichte vergelijking. Deze selectie "
                 "gaat ook mee naar de rapportomgeving.", prepare=show_analysis, target=lambda: panel.range_choice),
            dict(title="Wat wilt u onderzoeken?", body="Kies een meetwaarde, zoals aanmeldingen, no-shows of afmeldingen, "
                 "en een uitsplitsing, bijvoorbeeld leeftijd of opleidingsniveau. Zo bepaalt u eerst uw vraag, "
                 "voordat u groepen met elkaar vergelijkt.", prepare=show_analysis, target=lambda: panel.metric_choice),
            dict(title="Statistieken of verloop", body="Statistieken vat de gekozen gegevens samen per groep. Verloop "
                 "toont de ontwikkeling door de tijd. Kies daarvoor een tijdseenheid, bijvoorbeeld per evenement, "
                 "maand of kwartaal. Eén tijdspunt kan alleen een bolletje opleveren, geen ontwikkeling.",
                 prepare=show_analysis, target=lambda: panel.display_choice),
            dict(title="Gericht groepen vergelijken", body="Na een uitsplitsing kunt u via Groepen kiezen bepalen "
                 "welke categorieën u vergelijkt. Beperk de selectie voor een leesbare grafiek. Als percentage van "
                 "totaal toont het aandeel binnen de gekozen meetwaarde; dat is niet automatisch de no-showkans "
                 "binnen een leeftijdsgroep.", prepare=show_analysis, target=lambda: panel.analysis_tabs),
            dict(title="Uw huidige analyse exporteren", body="Exporteren neemt uw selectie mee. Het rapportprofiel "
                 "Huidige analyse sluit aan op de gekozen analyse. Controleer de inhoud en het exportvoorbeeld "
                 "voordat u PDF of Excel opslaat. Een grafiek kunt u ook via het rechtermuisknopmenu als PNG bewaren.",
                 prepare=show_analysis, target=lambda: self.trend_export_button),
            dict(title="Later verder met een losse analyse", body="Via Analyse beheren kiest of bewaart u een analyse "
                 "en voegt u nieuwe bezoekerslijsten toe. Geef de werkelijke evenementdatum op: de datum in een "
                 "Rudder-exportbestandsnaam is niet automatisch de evenementdatum. Zo hoeft u bestaande lijsten "
                 "niet telkens opnieuw in te laden.", prepare=show_loose, target=lambda: self.trend_manage_button),
        ]

        def finish(completed):
            panel.analysis_tabs.setCurrentIndex(original_analysis)
            self.trend_tabs.setCurrentIndex(original_workspace)
            self.page_stack.setCurrentWidget(original_page)
            self.event_focus_mode = original_focus_mode
            self._set_project_context_ui(original_page is self.event_page)
            self._set_navigation_active(original_navigation)
            self.app_title.setText(original_heading[0])
            self.app_subtitle.setText(original_heading[1])
            self.focus_action.setEnabled(original_focus_action[0])
            self.focus_action.setText(original_focus_action[1])
            self._tutorial_overlay = None
            self.status_label.setText("Uitleg Trends afgerond." if completed else "Uitleg Trends gesloten.")

        self._tutorial_overlay = TutorialOverlay(self, steps, finish)

    def start_tutorial(self, *_):
        if self._tutorial_is_running():
            return

        original_page = self.page_stack.currentWidget()
        original_navigation = next((name for name, button in self.sidebar_buttons.items()
                                    if button.objectName() == "sidebarButtonActive"), None)
        original_heading = (self.app_title.text(), self.app_subtitle.text())
        original_focus_action = (self.focus_action.isEnabled(), self.focus_action.text())
        original_event_id = self.active_event_id
        original_selected_events = set(self.selected_events)
        original_tab = self.tabs.currentWidget()
        original_event_control_tab = self.event_control_tabs.currentWidget()
        original_focus_mode = self.event_focus_mode
        tutorial_event = self._active_event()
        demo_event_id = ""
        if tutorial_event is None:
            upcoming = self._upcoming_events(60)
            tutorial_event = upcoming[0] if upcoming else (self.events[0] if self.events else None)
        if tutorial_event is None:
            tutorial_event = empty_event("Voorbeeld: Meeloopdag", self.task_templates, "Meeloopdag")
            tutorial_event["date"] = (date.today() + timedelta(days=30)).strftime("%d-%m-%Y")
            tutorial_event["location"] = "Voorbeeldlocatie"
            tutorial_event["status"] = "In voorbereiding"
            demo_event_id = tutorial_event["id"]
            self.events.append(tutorial_event)
            self._render_all()

        def show_home():
            self.back_to_home()

        def show_start_page():
            # back_to_home opent het evenementenoverzicht; het startscherm zelf
            # kwam in de rondleiding nooit aan bod.
            self.show_home()

        def show_event_tab(tab):
            self.open_event(tutorial_event, tab, stil=True)

        def show_event_control_presence():
            self.active_event_id = tutorial_event.get("id", "")
            self.selected_events = {tutorial_event.get("name", "")}
            self.show_event_control_page()
            self.event_control_tabs.setCurrentWidget(self.presence_tab)

        def event_tab_label(tab):
            bar = self.tabs.tabBar()
            index = self.tabs.indexOf(tab)
            return (bar, bar.tabRect(index)) if index >= 0 else bar

        steps = [
            {
                "title": "Uw startscherm",
                "body": "Hier begint u. <b>Vandaag</b> toont het evenement van vandaag of het eerstvolgende, "
                        "<b>Verder waar je was</b> brengt u terug naar het laatst geopende dossier en "
                        "<b>Aandacht nodig</b> verzamelt wat blijft liggen.",
                "prepare": show_start_page,
                "target": lambda: self.home_today_title,
            },
            {
                "title": "De zijbalk",
                "body": "Alle hoofdonderdelen staan op één vaste plek. Klap de balk onderaan in voor extra werkruimte; de pictogrammen en uitlegballonnen blijven beschikbaar.",
                "prepare": show_home,
                "target": lambda: self.sidebar_buttons["events"],
            },
            {
                "title": "Het evenementenoverzicht",
                "body": "Elk evenement staat op een kaart, gegroepeerd in <b>Vandaag</b>, <b>Komend</b> en "
                        "<b>Geweest</b>. De balk laat zien hoever de voorbereiding is; bij een evenement dat "
                        "is geweest staan de opkomstcijfers. Dubbelklik opent het dossier, en de knop met de "
                        "drie puntjes geeft aanpassen, status wijzigen, samenvoegen en verwijderen. Rechtsboven "
                        "wisselt u tussen kaarten en een compacte lijst.",
                "prepare": show_home,
                "target": lambda: self.event_board,
            },
            {
                "title": "Zoeken en meldingen",
                "body": "Zoek op naam, plaats of datum, of filter op soort evenement en een datum uit de "
                        "kalender. Het <b>alarmbelletje</b> verzamelt taken die aandacht vragen en kondigt aan "
                        "wanneer persoonsgegevens verlopen.",
                "prepare": show_home,
                "target": lambda: self.notification_button,
            },
            {
                "title": "Een evenement aanmaken",
                "body": "Begin met een leeg evenement, hergebruik een evenementtemplate of neem één of meerdere evenementen over uit Rudder. Bij een template vult u de datum in en laadt u de deelnemers voor dit evenement apart in.",
                "prepare": show_home,
                "target": lambda: self.new_event_button,
            },
            {
                "title": "Templatebeheer",
                "body": "Via het tandwiel opent u <b>Templatebeheer</b>: bewaar vaste evenementgegevens en taken voor "
                        "hergebruik. Een bestaand evenement bewaart u via de drie puntjes met <b>Opslaan als template</b>. "
                        "Met <b>Evenementen aan template koppelen</b> groepeert u bestaande evenementen voor Trends, "
                        "zonder hun taken te vervangen. Deelnemers worden niet in het template opgeslagen.",
                "prepare": show_home,
                "target": lambda: self.settings_button,
            },
            {
                "title": "De browserextensie installeren",
                "body": "Ga via het tandwiel naar <b>Algemene instellingen → Browserextensie → Browserextensie installeren</b>. "
                        "De installatiehulp geeft de stappen voor Edge of Chrome en de juiste extensiemap. Dit doet u "
                        "eenmalig in de browser waarmee u Rudder gebruikt. Staat uw organisatie installatie niet toe, "
                        "vraag dan uw ICT-beheerder om hulp.",
                "prepare": show_home,
                "target": lambda: self.settings_button,
            },
            {
                "title": "Evenementoverzicht",
                "body": "In het evenementdossier vindt u de kerngegevens van het evenement. Via <b>Gegevens aanpassen</b> wijzigt u de basisgegevens; deelnemers beheert u in het tabblad Deelnemers.",
                "prepare": lambda: show_event_tab(self.event_overview_tab),
                "target": lambda: self.edit_event_button,
            },
            {
                "title": "Snel naar een ander evenement",
                "body": "Vanuit een geopend dossier brengt <b>Ander evenement</b> u meteen naar een ander "
                        "evenement. U kiest daar uit dezelfde kaarten, met zoekveld, filters en een "
                        "datumkiezer; het evenement waar u nu in zit staat gemarkeerd.",
                "prepare": lambda: show_event_tab(self.event_overview_tab),
                "target": lambda: self.switch_event_button,
            },
            {
                "title": "Deelnemers beheren",
                "body": "Bekijk en bewerk bezoekersgegevens, kies zelf de zichtbare kolommen en bepaal met dit vinkje of introducees worden getoond. Kolommen blijft direct bereikbaar; Excel-export, PDF-export en afdrukvoorbeeld staan overzichtelijk onder <b>••• Meer acties</b>. Kolomkoppen kunt u bovendien verslepen; EventHub onthoudt die volgorde.",
                "prepare": lambda: show_event_tab(self.participant_tab),
                "target": lambda: self.participant_include_introducees,
            },
            {
                "title": "After sales",
                "body": "Selecteer een kandidaat om contactstatus, laatste contact, vervolgafspraak en opmerkingen te beheren. Zonder selectie blijft de kandidatenlijst breed; dubbelklik op een kandidaat om direct de voorbereide WhatsApp-flow te openen. Meerdere kandidaten selecteren blijft mogelijk.",
                "prepare": self.show_nazorg_page,
                "target": lambda: self.callback_search_box,
            },
            {
                "title": "Event Control en presentie",
                "body": "Event Control bundelt presentieregistratie en gedeelde live sessies. Zoek bezoekers, vink aanwezigheid af en beheer een lokale sessie voor meerdere apparaten. Sessiebeheer toont compact de live-status, verbonden apparaten en de lopende sessietijd.",
                "prepare": show_event_control_presence,
                "target": lambda: self.search_box,
            },
            {
                "title": "Statistieken en gegevenscontrole",
                "body": "Bekijk grafieken voor opleiding, profiel, geslacht en leeftijd, en de kruistabel "
                        "opleidingsniveau tegen profiel als kleurvlak of als tabel. In het naastgelegen tabblad "
                        "<b>Gegevenscontrole</b> vindt u ontbrekende waarden, introducees zonder hoofdbezoeker en "
                        "mogelijke dubbelen: meldt iemand zich twee keer aan, dan houdt u er één over en telt de "
                        "andere nergens meer mee.",
                "prepare": lambda: show_event_tab(self.statistics_tab),
                "target": lambda: self.statistics_include_introducees,
            },
            {
                "title": "Taken en deadlines",
                "body": "Taken worden vanuit de evenementdatum gepland. Stel per taak de deadline en "
                        "meldingstermijn in en vink hem af zodra hij gereed is; EventHub verwerkt de rest in het "
                        "welkomsscherm en de meldingenbel. Onder <b>Standaardtaken</b> bepaalt u welke taken "
                        "meekomen, per soort evenement: een online voorlichting hoeft geen vervoer of catering.",
                "prepare": lambda: show_event_tab(self.tasks_tab),
                "target": lambda: self.task_table,
            },
            {
                "title": "Documenten",
                "body": "Vul de 5WH en evaluatie in, exporteer ze naar het vaste Word-format en voeg aanvullende documenten als bijlage aan het evenement toe.",
                "prepare": lambda: show_event_tab(self.documents_tab),
                "target": lambda: event_tab_label(self.documents_tab),
            },
            {
                "title": "Rudder",
                "body": "Gebruik de Rudder-koppeling om evenementgegevens te importeren of ondersteunde velden "
                        "voor Rudder voor te bereiden. Op de aanwezigheidspagina van Rudder staat bovendien de "
                        "knop <b>EventHub aanwezigheid</b>: die haalt de presentie rechtstreeks uit EventHub op, "
                        "zonder dat u een bestand hoeft te zoeken.",
                "prepare": lambda: show_event_tab(self.rudder_tab),
                "target": lambda: self.rudder_import_button,
            },
            {
                "title": "Trends",
                "body": "Zie hoe opkomst, no-shows en afmeldingen zich over evenementen heen ontwikkelen. "
                        "Combineer zelf een meetwaarde met een uitsplitsing, bijvoorbeeld no-shows per "
                        "opleidingsniveau, en kies de tijdseenheid. Onder <b>Losse analyse</b> laadt u "
                        "bezoekerslijsten van elders in zonder uw eigen cijfers te vermengen. Een evenement telt "
                        "pas mee zodra de presentieregistratie definitief is. Het vraagteken naast Exporteren geeft "
                        "een aparte uitleg over selecties, groepen, statistieken en verloop.",
                "prepare": self._show_trends_for_tutorial,
                "target": lambda: self.trend_tabs,
            },
            {
                "title": "Een rapport samenstellen",
                "body": "<b>Exporteren</b> opent de rapportomgeving voor het werkgebied dat openstaat. In vijf "
                        "stappen kiest u de gegevens, vinkt u aan welke onderdelen en grafieken meegaan, stelt u "
                        "titel en pagina-indeling in, bekijkt u het voorbeeld en exporteert u naar PDF of Excel. "
                        "U kiest daarbij tussen <b>statistieken</b> en <b>verloop</b>, en een eigen samenstelling "
                        "bewaart u als sjabloon voor een volgende keer. <b>Huidige analyse</b> neemt de gekozen "
                        "analyse als uitgangspunt; u hoeft niet altijd een volledig rapport te maken.",
                "prepare": self._show_trends_for_tutorial,
                "target": lambda: self.trend_export_button,
            },
            {
                "title": "Persoonsgegevens verdwijnen vanzelf",
                "body": f"Na de bewaartermijn van <b>{self._retention_days()} dagen</b> verwijdert EventHub de "
                        "deelnemersgegevens van een evenement automatisch en onomkeerbaar, ook uit de "
                        "reservekopieën. De opkomstcijfers blijven geanonimiseerd bewaard. Het meldingenoverzicht "
                        "waarschuwt zeven dagen vooraf, zodat u op tijd kunt exporteren. Exporteert u iets, dan "
                        "valt dat bestand buiten EventHub en ruimt u het zelf op.",
                "prepare": show_start_page,
                "target": lambda: self.notification_button,
            },
        ]

        def finish_tutorial(completed: bool):
            if completed:
                self.settings.setValue("tutorial_completed", True)
            self.settings.setValue("tutorial_invitation_seen", True)
            if demo_event_id:
                self.events = [event for event in self.events if event.get("id") != demo_event_id]
            self.active_event_id = original_event_id
            self.selected_events = original_selected_events
            self.event_focus_mode = original_focus_mode
            self._render_all()
            original_event = self._event_by_id(original_event_id) if original_event_id else None
            if original_page is self.event_page and original_event:
                self.open_event(original_event, original_tab, stil=True)
                self.event_focus_mode = original_focus_mode
                self._apply_event_focus_mode()
            elif original_page is self.event_control_page:
                self.show_event_control_page()
                self.event_control_tabs.setCurrentWidget(original_event_control_tab)
            else:
                self.page_stack.setCurrentWidget(original_page)
                self._set_project_context_ui(False)
            self._set_navigation_active(original_navigation)
            self.app_title.setText(original_heading[0])
            self.app_subtitle.setText(original_heading[1])
            self.focus_action.setEnabled(original_focus_action[0])
            self.focus_action.setText(original_focus_action[1])
            self.status_label.setText(
                "Rondleiding afgerond. U kunt deze altijd opnieuw starten via Help."
                if completed else "Rondleiding gesloten. Via Help kunt u later verder kijken."
            )
            self._tutorial_overlay = None

        self._tutorial_overlay = TutorialOverlay(self, steps, finish_tutorial)

    def _select_task(self, task_id: str):
        for task_row in range(self.task_table.rowCount()):
            task_item = self.task_table.item(task_row, 0)
            task_data = task_item.data(Qt.ItemDataRole.UserRole) if task_item else None
            if isinstance(task_data, (tuple, list)) and len(task_data) == 2 and task_data[1] == task_id:
                self.task_table.selectRow(task_row)
                self.task_table.scrollToItem(task_item)
                break

    def edit_profile(self):
        dialog = ProfileDetailsDialog(self.profile, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        profile = dialog.value()
        if profile["email"] and not profile["email"].lower().endswith("@werkenbijdefensie.nl"):
            QMessageBox.warning(
                self,
                "E-mailadres controleren",
                "Gebruik voor het profiel een @werkenbijdefensie.nl-adres.",
            )
            return
        self.profile = profile
        self.settings.setValue("profile", json.dumps(profile, ensure_ascii=False))
        if self._profile_complete(profile):
            self.settings.setValue("initial_profile_complete", True)
        self._mark_dirty()
        self._render_management()
        self._render_profile_page()
        self.status_label.setText("Profiel bijgewerkt. Nieuwe documentexports gebruiken deze gegevens automatisch.")

    def show_profile_page(self):
        self.page_stack.setCurrentWidget(self.profile_page)
        self._set_project_context_ui(False)
        self._set_navigation_active("profile")
        self._render_profile_page()
        self.status_label.setText("Mijn profiel — persoonlijke gegevens voor documentexports.")

    def _render_profile_page(self):
        if not hasattr(self, "profile_name_label"):
            return
        self.profile_name_label.setText(str(self.profile.get("name", "") or "Niet ingevuld"))
        self.profile_function_label.setText(str(self.profile.get("function", "") or "Niet ingevuld"))
        self.profile_email_label.setText(str(self.profile.get("email", "") or "Niet ingevuld"))
        self.profile_phone_label.setText(str(self.profile.get("phone", "") or "Niet ingevuld"))
        signature = _profile_signature(self.profile)
        self.profile_signature_label.setText(signature or "Niet ingevuld")

    def manage_whatsapp_templates(self, _checked=False):
        dialog = WhatsAppTemplatesDialog(load_whatsapp_templates(self.settings), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        saved = save_whatsapp_templates(self.settings, dialog.value())
        self.status_label.setText(f"WhatsApp-sjablonen opgeslagen ({len(saved)}).")

    def show_application_settings(self):
        preferences = {
            "mode": self._startup_welcome_mode(),
            "upcoming_days": self._upcoming_window_days(),
            "autosave_enabled": self._autosave_enabled(),
            "autosave_delay_seconds": self._autosave_delay_seconds(),
            "backups_enabled": self._backups_enabled(),
            "backup_count": self._backup_count(),
            "retention_days": self._retention_days(),
            "dark_mode": self.dark_mode_enabled,
        }
        dialog = ApplicationSettingsDialog(self, preferences)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._save_profile_preferences(dialog.value())
        self.status_label.setText("Instellingen bijgewerkt.")

    def _set_settings_active(self, active: bool):
        self.settings_button.setProperty("menuOpen", bool(active))
        self.settings_button.style().unpolish(self.settings_button)
        self.settings_button.style().polish(self.settings_button)
        
    def show_storage_locations(self):
        QMessageBox.information(
            self,
            "Opslaglocaties",
            f"Nieuwe projecten:\n{projects_directory()}\n\n"
            f"Exports:\n{exports_directory()}\n\n"
            "Bestaande projecten blijven op hun huidige locatie staan.",
        )

    def _startup_welcome_mode(self):
        mode = str(self.settings.value("startup_welcome_mode", "relevant") or "relevant")
        return mode if mode in {"relevant", "always", "never"} else "relevant"

    def _upcoming_window_days(self):
        try:
            days = int(self.settings.value("startup_upcoming_days", 30) or 30)
        except (TypeError, ValueError):
            days = 30
        return days if days in {7, 14, 30, 60} else 30

    def _autosave_enabled(self):
        return self.settings.value("autosave_enabled", True, type=bool)

    def _autosave_delay_seconds(self):
        try:
            seconds = int(self.settings.value("autosave_delay_seconds", 3) or 3)
        except (TypeError, ValueError):
            seconds = 3
        return seconds if seconds in {3, 10, 30, 60} else 3

    def _backups_enabled(self):
        return self.settings.value("backups_enabled", True, type=bool)

    def _backup_count(self):
        try:
            count = int(self.settings.value("backup_count", 5) or 5)
        except (TypeError, ValueError):
            count = 5
        return count if count in {3, 5, 10} else 5

    def _retention_days(self):
        return clamp_retention_days(
            self.settings.value("retention_days", RETENTION_DEFAULT_DAYS)
        )

    def show_trends_page(self):
        upgraded = False
        for event in self.events:
            snapshot = event.get("statistiek", {})
            if isinstance(snapshot, dict) and int(snapshot.get("schema", 0) or 0) < 5:
                upgraded = self._capture_event_statistics(event) or upgraded
        if upgraded:
            self._mark_dirty()
        self.page_stack.setCurrentWidget(self.trends_page)
        self._set_project_context_ui(False)
        self._set_navigation_active("trends")
        if hasattr(self, "focus_action"):
            self.focus_action.setEnabled(True)
            self.focus_action.setText("Grafiek maximaliseren")
        self._sync_trend_sources()
        self._render_trends()
        self.status_label.setText("Trends — ontwikkeling over evenementen heen.")

    def _loose_trend_summaries(self):
        """Uitsluitend de ingeladen sets; het eigen dossier telt hier niet mee."""
        wanted = str(self.trend_source.currentData() or "")
        combined = []
        for source in getattr(self, "trend_sources", []):
            if wanted and source["label"] != wanted:
                continue
            combined.extend(source["summaries"])
        return combined

    def _own_trend_summaries(self):
        names = {item["id"]: item["name"] for item in self.project_templates}
        return [dict(item, template_name=names.get(item.get("template_id"), item.get("template_name", "")))
                for item in collect_trend_summaries(self.events, source="Eigen dossier")]

    def _active_trend_panel(self):
        return (
            self.loose_trend_panel if self.trend_tabs.currentIndex() == 1
            else self.own_trend_panel
        )

    def _open_trend_event(self, event_id: str):
        """Drill-down vanuit Trends naar de bestaande Statistieken van een eigen evenement."""
        event = self._event_by_id(event_id)
        if event is None:
            QMessageBox.information(
                self, "Extern evenement",
                "Dit evenement komt uit een losse, geanonimiseerde analyse en heeft in dit dossier geen Statistieken-pagina.",
            )
            return
        self.open_event(event, self.statistics_tab)

    def _analyses_dir(self) -> Path:
        map_ = self._app_data_root() / "Analyses"
        map_.mkdir(parents=True, exist_ok=True)
        return map_

    def _known_analyses(self) -> list:
        """De bewaarde analyses, op naam."""
        namen = []
        for pad in sorted(self._analyses_dir().glob("*.json")):
            try:
                naam, _ = read_analysis(json.loads(pad.read_text(encoding="utf-8")))
            except Exception:
                continue
            if naam:
                namen.append(naam)
        return sorted(namen, key=normalize)

    def _save_current_analysis(self):
        """Elke wijziging gaat meteen naar schijf; er valt niets te vergeten."""
        naam = str(getattr(self, "current_analysis", "") or "").strip()
        if not naam:
            return
        payload = analysis_payload(naam, getattr(self, "trend_sources", []))
        try:
            self._write_payload_atomic(self._analyses_dir() / analysis_file_name(naam), payload)
        except Exception as exc:
            self._write_error_log(f"Analyse bewaren: {naam}", str(exc))

    def _load_analysis(self, naam: str):
        pad = self._analyses_dir() / analysis_file_name(naam)
        try:
            bewaard, sources = read_analysis(json.loads(pad.read_text(encoding="utf-8")))
        except Exception:
            bewaard, sources = "", []
        self.current_analysis = bewaard or naam
        self.trend_sources = sources
        self.settings.setValue("current_analysis", self.current_analysis)
        self._sync_analysis_picker()
        self._sync_trend_sources()
        self._render_trends()

    def _sync_analysis_picker(self):
        if not hasattr(self, "analysis_picker"):
            return
        namen = self._known_analyses()
        huidig = str(getattr(self, "current_analysis", "") or "")
        if huidig and huidig not in namen:
            namen.append(huidig)
        self.analysis_picker.blockSignals(True)
        self.analysis_picker.clear()
        for naam in namen:
            self.analysis_picker.addItem(naam, naam)
        self.analysis_picker.addItem("Nieuwe analyse...", "")
        index = self.analysis_picker.findData(huidig)
        self.analysis_picker.setCurrentIndex(index if index >= 0 else 0)
        self.analysis_picker.blockSignals(False)

    def _analysis_picked(self, _index=None):
        keuze = str(self.analysis_picker.currentData() or "")
        if keuze:
            if keuze != str(getattr(self, "current_analysis", "") or ""):
                self._load_analysis(keuze)
            return
        naam, ok = QInputDialog.getText(
            self, "Nieuwe analyse", "Hoe heet deze analyse?\n\nBijvoorbeeld: Inloopdagen, Meeloopdagen."
        )
        naam = str(naam or "").strip()
        if not ok or not naam:
            self._sync_analysis_picker()
            return
        if any(normalize(naam) == normalize(bestaand) for bestaand in self._known_analyses()):
            QMessageBox.information(
                self, "Naam al in gebruik", f"Er is al een analyse die '{naam}' heet."
            )
            self._sync_analysis_picker()
            return
        self.current_analysis = naam
        self.trend_sources = []
        self.settings.setValue("current_analysis", naam)
        self._save_current_analysis()
        self._sync_analysis_picker()
        self._sync_trend_sources()
        self._render_trends()
        self.status_label.setText(f"Nieuwe analyse: {naam}. Laad hier bezoekerslijsten in.")

    def _sync_trend_sources(self):
        """Werk de keuzelijst en het overzicht van ingeladen sets bij."""
        if not hasattr(self, "trend_source"):
            return
        current = str(self.trend_source.currentData() or "")
        self.trend_source.blockSignals(True)
        self.trend_source.clear()
        self.trend_source.addItem("Alle ingeladen sets", "")
        for source in getattr(self, "trend_sources", []):
            self.trend_source.addItem(source["label"], source["label"])
        index = self.trend_source.findData(current)
        self.trend_source.setCurrentIndex(index if index >= 0 else 0)
        self.trend_source.blockSignals(False)

        sources = getattr(self, "trend_sources", [])
        if hasattr(self, "trend_manage_button"):
            self.trend_manage_button.setToolTip(
                f"Analyse kiezen, lijsten inladen en sets beheren ({len(sources)} set(s) ingeladen)"
            )
        self.trend_source_list.setRowCount(len(sources))
        for row, source in enumerate(sources):
            participants = sum(
                int(item["statistiek"].get("aangemeld", 0) or 0) for item in source["summaries"]
            )
            values = (source["label"], str(len(source["summaries"])), str(participants))
            for column, text in enumerate(values):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, source["label"])
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.trend_source_list.setItem(row, column, item)

    def _open_trend_source_management(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Losse analyse instellen")
        _fit_dialog_to_screen(dialog, 760, 560, 600, 420)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Kies een bewaarde analyse, laad bezoekerslijsten in en bepaal welke set in de grafieken meetelt. "
            "De sets bevatten uitsluitend geaggregeerde trendgegevens."
        )
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        options = QFormLayout()
        analysis_choice = ScrollSafeComboBox()
        for index in range(self.analysis_picker.count()):
            analysis_choice.addItem(
                self.analysis_picker.itemText(index), self.analysis_picker.itemData(index)
            )
        analysis_choice.setCurrentIndex(self.analysis_picker.currentIndex())
        source_choice = ScrollSafeComboBox()
        for index in range(self.trend_source.count()):
            source_choice.addItem(self.trend_source.itemText(index), self.trend_source.itemData(index))
        source_choice.setCurrentIndex(self.trend_source.currentIndex())
        options.addRow("Analyse:", analysis_choice)
        options.addRow("Meetellen:", source_choice)
        layout.addLayout(options)

        import_button = _make_button_compact(QPushButton("Bezoekerslijsten inladen"))
        import_button.setObjectName("primaryButton")
        import_button.setToolTip(
            "Laad één of meer bezoekerslijsten in (Excel of CSV), of een EventHub-dossier van een collega."
        )
        layout.addWidget(import_button, 0, Qt.AlignmentFlag.AlignLeft)

        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Ingeladen set", "Evenementen", "Deelnemers"])
        table.setObjectName("dashboardTable")
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(table, 1)

        def fill_table():
            sources = getattr(self, "trend_sources", [])
            table.setRowCount(len(sources))
            for row, source in enumerate(sources):
                participants = sum(
                    int(item.get("statistiek", {}).get("aangemeld", 0) or 0)
                    for item in source.get("summaries", [])
                )
                for column, text in enumerate((source["label"], len(source.get("summaries", [])), participants)):
                    item = QTableWidgetItem(str(text))
                    item.setData(Qt.ItemDataRole.UserRole, source["label"])
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    table.setItem(row, column, item)
            if sources:
                table.selectRow(0)

        def remove_selected():
            row = table.currentRow()
            item = table.item(row, 0) if row >= 0 else None
            label = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
            if not label:
                QMessageBox.information(dialog, "Niets geselecteerd", "Selecteer eerst een set.")
                return
            if QMessageBox.question(
                dialog, "Set verwijderen", f"Wilt u '{label}' uit deze losse analyse verwijderen?"
            ) != QMessageBox.StandardButton.Yes:
                return
            self.trend_sources = [source for source in self.trend_sources if source["label"] != label]
            self._save_current_analysis()
            self._sync_trend_sources()
            self._render_trends()
            fill_table()
            if not self.trend_sources:
                dialog.accept()

        def remove_all():
            count = len(getattr(self, "trend_sources", []))
            if QMessageBox.question(
                dialog, "Alle sets verwijderen", f"Alle {count} ingeladen set(s) uit deze analyse verwijderen?"
            ) != QMessageBox.StandardButton.Yes:
                return
            self.trend_sources = []
            self._save_current_analysis()
            self._sync_trend_sources()
            self._render_trends()
            dialog.accept()

        def choose_analysis(index):
            data = analysis_choice.itemData(index)
            target = self.analysis_picker.findData(data)
            if target >= 0:
                self.analysis_picker.setCurrentIndex(target)
                source_choice.clear()
                for source_index in range(self.trend_source.count()):
                    source_choice.addItem(
                        self.trend_source.itemText(source_index),
                        self.trend_source.itemData(source_index),
                    )
                source_choice.setCurrentIndex(self.trend_source.currentIndex())
                fill_table()

        def choose_source(index):
            target = self.trend_source.findData(source_choice.itemData(index))
            if target >= 0:
                self.trend_source.setCurrentIndex(target)

        def import_lists():
            dialog.accept()
            self.import_trend_data()

        fill_table()
        analysis_choice.currentIndexChanged.connect(choose_analysis)
        source_choice.currentIndexChanged.connect(choose_source)
        import_button.clicked.connect(import_lists)
        actions = QHBoxLayout()
        remove_button = _make_button_compact(QPushButton("Selectie verwijderen"))
        remove_button.setObjectName("secondaryButton")
        remove_button.clicked.connect(remove_selected)
        clear_button = _make_button_compact(QPushButton("Alles wissen"))
        clear_button.setObjectName("dangerButton")
        clear_button.clicked.connect(remove_all)
        close_button = _make_button_compact(QPushButton("Sluiten"))
        close_button.setObjectName("primaryButton")
        close_button.clicked.connect(dialog.accept)
        actions.addWidget(remove_button)
        actions.addWidget(clear_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)
        dialog.exec()

    def _render_trends(self, *_):
        if not hasattr(self, "own_trend_panel"):
            return
        incomplete = sum(bool(event.get("statistiek", {}).get("onbekend", 0))
                         for event in self.events if isinstance(event.get("statistiek"), dict)
                         and not event.get("exclude_from_analysis") and not event.get("persoonsgegevens_gewist"))
        historical_unknown = sum(bool(event.get("persoonsgegevens_gewist"))
                                 and bool(event.get("statistiek", {}).get("onbekend", 0))
                                 for event in self.events if isinstance(event.get("statistiek"), dict)
                                 and not event.get("exclude_from_analysis"))
        self.trend_incomplete_notice.setText(
            f"In dit dossier ontbreken {incomplete} evenementen in Trends omdat hun opgeslagen aanwezigheid nog onbekende statussen bevat. Controleer de aanwezigheid bij die evenementen.")
        if historical_unknown:
            self.trend_incomplete_notice.setText(
                (self.trend_incomplete_notice.text() + "\n" if incomplete else "") +
                f"{historical_unknown} geanonimiseerde evenementen bevatten onbekende aanwezigheid. Die telt niet als no-show; de opgeslagen cijfers blijven beschikbaar.")
        self.trend_incomplete_notice.setVisible(bool(incomplete or historical_unknown))
        self._active_trend_panel().refresh()

    def remove_trend_source(self):
        row = self.trend_source_list.currentRow()
        item = self.trend_source_list.item(row, 0) if row >= 0 else None
        if item is None:
            QMessageBox.information(
                self, "Niets geselecteerd", "Selecteer eerst een ingeladen set in de lijst."
            )
            return
        label = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self.trend_sources = [
            source for source in self.trend_sources if source["label"] != label
        ]
        self._save_current_analysis()
        self._sync_trend_sources()
        self._render_trends()
        self.status_label.setText(f"Set verwijderd uit de losse analyse: {label}.")

    def clear_trend_sources(self):
        if not getattr(self, "trend_sources", []):
            return
        confirmed = QMessageBox.question(
            self,
            "Losse analyse wissen",
            f"Alle {len(self.trend_sources)} ingeladen set(s) uit de losse analyse verwijderen?\n\n"
            "Uw eigen evenementen blijven ongemoeid; de bronbestanden worden niet aangeraakt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self.trend_sources = []
        self._save_current_analysis()
        self._sync_trend_sources()
        self._render_trends()
        self.status_label.setText("Losse analyse gewist.")

    def import_trend_data(self):
        """Laad één of meer bezoekerslijsten in en reken ze om naar cijfers.

        De deelnemersrijen worden na het samenvatten weggegooid. Zo levert het
        inladen van een lijst geen tweede verzameling persoonsgegevens op die
        buiten de bewaartermijn zou vallen.
        """
        file_names, _ = QFileDialog.getOpenFileNames(
            self, "Bezoekerslijsten inladen", "",
            "Bezoekerslijsten en dossiers (*.xlsx *.xlsm *.csv *.bvp *.json);;"
            "Excel-bestanden (*.xlsx *.xlsm *.csv);;EventHub-gegevens (*.bvp *.json);;Alle bestanden (*)",
        )
        if not file_names:
            return

        spreadsheets = [name for name in file_names if Path(name).suffix.lower() in {".xlsx", ".xlsm", ".csv"}]
        payloads = [name for name in file_names if name not in spreadsheets]
        added, problems = [], []

        for name in payloads:
            try:
                payload = json.loads(Path(name).read_text(encoding="utf-8"))
            except Exception as exc:
                problems.append(f"{Path(name).name}: {exc}")
                continue
            label = str(payload.get("label", "") or Path(name).stem)
            summaries = read_trend_bundle(payload, label)
            if summaries:
                added.append((label, summaries))
            else:
                problems.append(f"{Path(name).name}: geen evenementen met vastgelegde cijfers")

        if spreadsheets:
            result = import_registration_files(spreadsheets, existing_records=[])
            problems.extend(result.get("errors", []))
            records = result.get("records", [])
            if records:
                label = (
                    Path(spreadsheets[0]).stem if len(spreadsheets) == 1
                    else f"{len(spreadsheets)} bezoekerslijsten"
                )
                # Welk Rudder-evenement hoort bij welke evenementnaam? Daarmee
                # weet EventHub welke datum je hier eerder voor invulde.
                rudder_per_event = {}
                for report in result.get("reports", []):
                    nummer = rudder_id_from_filename(report.get("file_name", ""))
                    for naam in report.get("events", []) if nummer else []:
                        rudder_per_event.setdefault(naam, nummer)
                dates = self._ask_trend_event_dates(records, rudder_per_event)
                if dates is None:
                    return
                self._remember_trend_dates({
                    nummer: dates.get(naam, "") for naam, nummer in rudder_per_event.items()
                })
                summaries = trend_summaries_from_records(records, dates, source=label)
                if summaries:
                    added.append((label, summaries))

        if not added:
            QMessageBox.warning(
                self, "Niets ingeladen",
                "Er zijn geen bruikbare gegevens gevonden.\n\n" + "\n".join(problems[:8]),
            )
            return

        events_added = 0
        for label, summaries in added:
            self.trend_sources = [
                source for source in getattr(self, "trend_sources", []) if source["label"] != label
            ]
            self.trend_sources.append({"label": label, "summaries": summaries})
            events_added += len(summaries)
        self._save_current_analysis()
        self._sync_trend_sources()
        # Ingeladen lijsten horen in het losse werkgebied; spring daarheen zodat
        # het resultaat meteen zichtbaar is.
        self.trend_tabs.setCurrentIndex(1)
        self._render_trends()

        message = (
            f"{events_added} evenement(en) toegevoegd uit {len(file_names)} bestand(en).\n\n"
            "Van bezoekerslijsten zijn alleen de aantallen en verdelingen bewaard; de "
            "deelnemersgegevens zelf zijn niet opgeslagen."
        )
        if problems:
            message += "\n\nOvergeslagen:\n" + "\n".join(problems[:6])
        QMessageBox.information(self, "Bezoekerslijsten ingeladen", message)

    def _remembered_trend_dates(self) -> dict:
        """Datums die eerder bij een Rudder-nummer zijn ingevuld.

        Een aanmeldlijst bevat de evenementdatum nergens, en het evenement
        staat bij een losse analyse meestal niet in het dossier. Wat wel vast
        ligt is het Rudder-nummer in de bestandsnaam: dat is per evenement
        uniek en keert terug bij elke volgende export. Zo hoef je de datum per
        evenement maar een keer in te vullen.
        """
        try:
            bewaard = json.loads(str(self.settings.value("trend_event_dates", "") or "{}"))
        except (TypeError, ValueError):
            return {}
        return {str(key): str(value) for key, value in bewaard.items()} if isinstance(bewaard, dict) else {}

    def _remember_trend_dates(self, per_nummer: dict):
        if not per_nummer:
            return
        bewaard = self._remembered_trend_dates()
        bewaard.update({str(k): str(v) for k, v in per_nummer.items() if str(v).strip()})
        self.settings.setValue("trend_event_dates", json.dumps(bewaard, ensure_ascii=False))

    def _ask_trend_event_dates(self, records, rudder_per_event: dict | None = None):
        """Vraag per gevonden evenement een datum; een bezoekerslijst bevat die niet.

        Zonder datum belandt een evenement op de tijdlijn onder 'Zonder datum'
        en is er geen ontwikkeling uit af te lezen. Wat eerder is ingevuld komt
        terug via het Rudder-nummer van het bestand.
        """
        rudder_per_event = rudder_per_event or {}
        onthouden = self._remembered_trend_dates()
        names = []
        for record in records:
            for name in record_events(record) or ["Onbekend evenement"]:
                if name not in names:
                    names.append(name)
        if not names:
            return {}

        dialog = QDialog(self)
        dialog.setWindowTitle("Datums van de ingeladen evenementen")
        _fit_dialog_to_screen(dialog, 640, 420, 520, 260)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Een bezoekerslijst bevat geen evenementdatum. Vul de datum in om het evenement op "
            "de tijdlijn te kunnen plaatsen. Laat leeg om alleen in totalen mee te tellen."
        )
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        fields = {}
        for name in names:
            field = QLineEdit()
            field.setPlaceholderText("dd-mm-jjjj")
            # Staat het evenement al in het dossier, dan is de datum bekend.
            known = self._event_by_name(name)
            nummer = rudder_per_event.get(name, "")
            if known and known.get("date"):
                field.setText(str(known["date"]))
            elif nummer and onthouden.get(nummer):
                field.setText(onthouden[nummer])
            fields[name] = field
            form.addRow(f"{name}:", with_date_picker(field))
        container = QWidget()
        container.setLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        dates = {}
        for name, field in fields.items():
            value = field.text().strip()
            if value and parse_date(value):
                dates[name] = value
        return dates

    def _confirm_personal_data_export(self, what: str) -> bool:
        """Waarschuw dat persoonsgegevens EventHub verlaten.

        De bewaartermijn geldt alleen binnen EventHub: het dossier, de
        reservekopieën en de livesessiedatabase worden automatisch opgeschoond.
        Een geëxporteerd bestand staat buiten dat bereik en blijft staan tot
        iemand het zelf verwijdert. Daarom hier een expliciete melding vooraf.

        Bewust kort gehouden: deze melding verschijnt bij elke export met
        deelnemersgegevens, en een lange tekst wordt weggeklikt zonder te lezen.
        """
        days = self._retention_days()
        box = QMessageBox(self)
        box.setWindowTitle("Persoonsgegevens exporteren")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(f"<b>{escape(what)} bevat persoonsgegevens.</b>")
        box.setInformativeText(
            "EventHub wist dit bestand niet automatisch. "
            f"Verwijder het zelf binnen {days} dagen na het evenement."
        )
        proceed = box.addButton("Toch exporteren", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annuleren", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(proceed)
        box.exec()
        return box.clickedButton() is proceed

    def _offer_open_export_folder(self, file_name):
        """Bied na elke export aan de map te openen waar het bestand staat."""
        path = Path(file_name)
        folder = path.parent
        answer = QMessageBox.question(
            self,
            "Map openen?",
            f"{escape(path.name)} is opgeslagen in:\n{folder}\n\nWilt u die map openen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve()))):
            QMessageBox.warning(
                self, "Map openen mislukt", f"De map kon niet worden geopend:\n{folder}"
            )

    def export_trend_data(self, panel=None):
        """Open de Report Builder voor dit werkgebied.

        De directe PDF-uitvoer is vervallen: de gebruiker stelt nu zelf samen
        wat er in het rapport komt, ziet een voorbeeld en kiest daarna pas het
        formaat.
        """
        panel = panel or self._active_trend_panel()
        summaries = panel.provider() or []
        selectie = panel.current_filters()
        summaries = trend_participant_scope(
            summaries, bool(selectie.get("include_introducees"))
        )
        los = panel is self.loose_trend_panel
        werkgebied = "Losse analyse" if los else "Eigen evenementen"
        ander_panel = self.own_trend_panel if los else self.loose_trend_panel
        ander_werkgebied = "Eigen evenementen" if los else "Losse analyse"
        elders = len(ander_panel.provider() or [])
        if not summaries:
            uitleg = "Er zijn nog geen cijfers om te rapporteren."
            if elders:
                uitleg += (f"\n\nHet werkgebied {ander_werkgebied} bevat wel "
                           f"{elders} evenement(en) met cijfers.")
            QMessageBox.information(self, "Niets te exporteren", uitleg)
            return
        # Eén exportknop voor twee werkgebieden: wie op het verkeerde tabblad
        # staat, kreeg zonder deze vraag een rapport over één evenement.
        if len(summaries) < 2 <= elders:
            antwoord = QMessageBox.question(
                self, "Welk werkgebied?",
                f"{werkgebied} bevat {len(summaries)} evenement(en) met cijfers, "
                f"{ander_werkgebied} bevat er {elders}.\n\n"
                f"Wilt u het rapport over {werkgebied} maken?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if antwoord != QMessageBox.StandardButton.Yes:
                self.trend_tabs.setCurrentIndex(0 if los else 1)
                return
        if los:
            bron = self.trend_source.currentText() or "Alle ingeladen sets"
        else:
            bron = str(self.project_path.name if self.project_path else "Eigen dossier")
        dialog = ReportBuilderDialog(
            summaries,
            selectie,
            self.settings,
            self,
            bron=bron,
            status_callback=self.status_label.setText,
            folder=exports_directory(),
            werkgebied=werkgebied,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            doel = getattr(dialog, "exported_path", None)
            if doel:
                self._offer_open_export_folder(str(doel))

    def _retention_plan(self):
        return plan_retention_cleanup(self.events, self.records, self._retention_days())

    def _all_notifications(self):
        """Taakmeldingen plus aankondigingen van de bewaartermijn, samen gesorteerd."""
        combined = list(task_notifications(self.events))
        combined.extend(retention_notifications(self.events, self.records, self._retention_days()))
        order = {"retention": 0, "overdue": 1, "today": 2, "soon": 3}
        return sorted(
            combined,
            key=lambda item: (order.get(item["severity"], 9), item["due"], item["event_name"]),
        )

    def _retention_summary_html(self, plan: dict) -> str:
        lines = [
            f"<p>Bewaartermijn: <b>{plan['retention_days']} dagen</b> na de evenementdatum. "
            f"Peildatum {plan['peildatum']}.</p>",
            "<p>Van de volgende evenementen zijn de deelnemersgegevens verlopen:</p><ul>",
        ]
        for summary in plan["events"]:
            lines.append(
                f"<li><b>{escape(str(summary['name']))}</b> ({escape(str(summary['date']))}) — "
                f"verlopen op {escape(str(summary['expires_on']))}, "
                f"{summary['records_removed']} van {summary['records']} deelnemer(s) worden verwijderd</li>"
            )
        lines.append("</ul>")
        lines.append(
            f"<p>In totaal worden <b>{plan['records_removed']} deelnemer(s)</b> onomkeerbaar verwijderd "
            "uit het dossier, de reservekopieën, de herstelkopie en de livesessiegegevens.</p>"
        )
        if plan["records_kept_upcoming"]:
            lines.append(
                f"<p>{plan['records_kept_upcoming']} deelnemer(s) blijven staan omdat zij ook op een "
                "nog komend evenement zijn ingeschreven.</p>"
            )
        if plan["records_kept_unknown"]:
            lines.append(
                f"<p>{plan['records_kept_unknown']} deelnemer(s) blijven staan omdat zij gekoppeld zijn "
                "aan een evenement dat niet in dit dossier voorkomt; de termijn is daar niet vast te stellen.</p>"
            )
        lines.append(
            "<p>De opkomstcijfers en verdelingen blijven als geanonimiseerd overzicht bij het "
            "evenement bewaard. Namen, geboortedatums en contactgegevens niet.</p>"
        )
        return "".join(lines)

    def review_retention_cleanup(self):
        """Dry-run: toon wat er zou verdwijnen zonder iets te wijzigen."""
        plan = self._retention_plan()
        if not has_work(plan):
            QMessageBox.information(
                self,
                "Niets te verwijderen",
                f"Er zijn geen evenementen ouder dan {plan['retention_days']} dagen waarvan de "
                "deelnemersgegevens nog aanwezig zijn.",
            )
            return
        box = QMessageBox(self)
        box.setWindowTitle("Controle bewaartermijn")
        box.setIcon(QMessageBox.Icon.Information)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText("<b>Dit is een controle. Er wordt nu niets verwijderd.</b>")
        box.setInformativeText(self._retention_summary_html(plan))
        box.setStandardButtons(QMessageBox.StandardButton.Close)
        box.exec()

    def maybe_apply_retention(self):
        """Handhaaf de bewaartermijn automatisch; verlopen is verlopen.

        Er wordt niet om bevestiging gevraagd: een bewaartermijn die op een
        klik wacht wordt in de praktijk niet nageleefd. De aankondiging in het
        meldingenoverzicht is het moment om nog te exporteren; die verschijnt
        RETENTION_WARNING_DAYS dagen voordat de gegevens verdwijnen.
        """
        if not self.events or not self.project_path:
            return
        plan = self._retention_plan()
        if not has_work(plan) or not plan["records_removed"]:
            return
        self.apply_retention_cleanup_now(plan)

    def apply_retention_cleanup_now(self, plan: dict | None = None, announce: bool = True):
        """Verwijder verlopen persoonsgegevens uit alle opslaglocaties."""
        retention_days = self._retention_days()
        # De cijfers moeten vastliggen vóór de bron verdwijnt; daarna is de
        # momentopname de enige overgebleven bron.
        self._refresh_past_event_statistics()

        plan = apply_retention_cleanup(self.events, self.records, retention_days, plan=plan)
        self._mark_dirty()
        # Direct wegschrijven: een verwijdering die alleen in het geheugen
        # staat is bij het afsluiten zonder opslaan gewoon weer terug.
        self.save_project()

        copies = self._scrub_stored_copies(retention_days)
        sessions = self._scrub_live_session_data(retention_days)

        self._render_all()
        names = ", ".join(summary["name"] for summary in plan["events"]) or "—"
        self._add_recent_activity(
            f"Bewaartermijn toegepast: {plan['records_removed']} deelnemer(s) gewist ({names})"
        )
        self._write_retention_log(plan, copies, sessions)
        if announce:
            self.status_label.setText(
                f"Bewaartermijn toegepast: {plan['records_removed']} deelnemer(s) definitief verwijderd "
                f"uit {names}."
            )
        return plan

    def _write_retention_log(self, plan: dict, copies: int, sessions: int):
        """Leg vast dát er gewist is, zonder vast te leggen wie.

        Voor verantwoording achteraf: automatisch verwijderen zonder spoor is
        niet uit te leggen, maar het logboek mag zelf geen persoonsgegevens
        bevatten.
        """
        try:
            log_path = self._app_data_root() / "bewaartermijn.log"
            stamp = datetime.now().strftime("%d-%m-%Y %H:%M")
            lines = [
                f"[{stamp}] termijn {plan['retention_days']} dagen · "
                f"{plan['records_removed']} deelnemer(s) verwijderd · "
                f"{copies} kopie(ën) · {sessions} livesessie(s)"
            ]
            for summary in plan["events"]:
                lines.append(
                    f"    {summary['name']} ({summary['date']}) — verlopen {summary['expires_on']} — "
                    f"{summary['records_removed']} van {summary['records']} deelnemer(s)"
                )
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
        except Exception:
            self._write_error_log("Bewaartermijn loggen", traceback.format_exc())

    def _scrub_stored_copies(self, retention_days: int) -> int:
        """Pas de bewaartermijn ook toe op reservekopieën en de herstelkopie.

        Zonder deze stap blijven de persoonsgegevens gewoon op schijf staan en
        heeft het opschonen van het hoofddossier geen effect.
        """
        targets = list(self._backup_files())
        recovery = self._recovery_path()
        if recovery.is_file():
            targets.append(recovery)
        cleaned = 0
        for path in targets:
            try:
                payload = json.loads(Path(path).read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            result = scrub_payload(payload, retention_days)
            if not result["records_removed"]:
                continue
            try:
                self._write_payload_atomic(Path(path), payload)
                cleaned += 1
            except Exception:
                self._write_error_log("Bewaartermijn op kopie toepassen", traceback.format_exc())
        return cleaned

    def _scrub_live_session_data(self, retention_days: int) -> int:
        """Verwijder deelnemers uit verlopen livesessies, inclusief sessieback-ups.

        De sessiedatabase bevat naast de deelnemerstabel ook een audit- en een
        calamiteitenregistratie met namen erin; die gaan mee.
        """
        try:
            from server.paths import backups_directory, events_directory
            from server.services import session_service as live_session_service
        except Exception:
            return 0

        scrubbed = [event for event in self.events if event.get("persoonsgegevens_gewist")]
        if not scrubbed:
            return 0
        wanted_ids = {str(event.get("id", "") or "").strip() for event in scrubbed} - {""}
        wanted_legacy = {
            (str(event.get("name", "") or "").strip().casefold(), str(event.get("date", "") or "").strip())
            for event in scrubbed
        }

        try:
            sessions = live_session_service.list_recent_sessions()
        except Exception:
            return 0

        # Eén evenement kan meerdere livesessies hebben gehad; ze gaan allemaal mee.
        session_ids = set()
        for session in sessions:
            linked = str(session.get("source_event_id", "") or "").strip()
            legacy = (
                str(session.get("name", "") or "").strip().casefold(),
                str(session.get("date", "") or "").strip(),
            )
            if (linked and linked in wanted_ids) or (not linked and legacy in wanted_legacy):
                session_id = str(session.get("id", "") or "").strip()
                if session_id:
                    session_ids.add(session_id)

        cleaned = 0
        for session_id in session_ids:
            if self._scrub_session_database(events_directory() / session_id / "event.db"):
                cleaned += 1
            for backup in backups_directory().glob(f"{session_id}-*.db"):
                self._scrub_session_database(backup)
        return cleaned

    def _scrub_session_database(self, database: Path) -> bool:
        if not Path(database).is_file():
            return False
        connection = None
        try:
            connection = sqlite3.connect(str(database))
            existing = {
                row[0] for row in
                connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            for table in ("participant", "audit_log", "emergency_status", "emergency_incident"):
                if table in existing:
                    connection.execute(f"DELETE FROM {table}")
            connection.commit()
            # VACUUM haalt de verwijderde rijen ook fysiek uit het bestand;
            # zonder deze stap blijven ze met een editor leesbaar.
            connection.execute("VACUUM")
            connection.commit()
            return True
        except Exception:
            self._write_error_log("Livesessiegegevens opschonen", traceback.format_exc())
            return False
        finally:
            if connection is not None:
                connection.close()

    def _save_profile_preferences(self, preferences: dict):
        if "retention_days" in preferences:
            self.settings.setValue("retention_days", clamp_retention_days(preferences["retention_days"]))
        self.settings.setValue("startup_welcome_mode", preferences.get("mode", "relevant"))
        self.settings.setValue("startup_upcoming_days", int(preferences.get("upcoming_days", 30) or 30))
        self.settings.setValue("autosave_enabled", bool(preferences.get("autosave_enabled", True)))
        self.settings.setValue("autosave_delay_seconds", int(preferences.get("autosave_delay_seconds", 3) or 3))
        self.settings.setValue("backups_enabled", bool(preferences.get("backups_enabled", True)))
        self.settings.setValue("backup_count", int(preferences.get("backup_count", 5) or 5))
        self.dark_mode_enabled = bool(preferences.get("dark_mode", False))
        self.settings.setValue("dark_mode", self.dark_mode_enabled)
        self._apply_style()
        if self._autosave_enabled() and self.dirty:
            self._schedule_autosave()
        else:
            self.autosave_timer.stop()

    def _profile_complete(self, profile=None):
        profile = profile or self.profile
        return all(str(profile.get(key, "") or "").strip() for key in ("name", "function", "email", "phone")) and (
            str(profile.get("email", "")).lower().endswith("@werkenbijdefensie.nl")
        )

    def _write_error_log(self, context: str, details: str):
        try:
            base = application_data_root()
            log_path = base / "eventhub-error.log"
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"\n[{datetime.now().isoformat(timespec='seconds')}] {context}\n{details}\n"
                )
            return log_path
        except Exception:
            return None

    @staticmethod
    def _sanitized_error_report(context: str, details: str) -> str:
        """Maak een deelbaar foutrapport zonder herkenbare contactgegevens."""
        cleaned = str(details or "")
        home_path = str(Path.home())
        if home_path:
            cleaned = re.sub(re.escape(home_path), "<gebruikersmap>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            "<e-mailadres>",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"(?<!\d)(?:\+31|0)6[\s.-]*\d(?:[\s.-]*\d){7}(?!\d)", "<telefoonnummer>", cleaned)
        return (
            "EventHub beta-foutrapport\n"
            f"Tijdstip: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Onderdeel: {context}\n"
            f"Python: {sys.version.split()[0]}\n"
            f"Platform: {sys.platform}\n\n"
            f"{cleaned.strip()}\n"
        )

    def _prepare_error_email(self, context: str, details: str):
        try:
            report_dir = application_data_root() / "Foutrapporten"
            report_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            report_path = report_dir / f"EventHub-foutrapport-{stamp}.txt"
            report_path.write_text(
                self._sanitized_error_report(context, details), encoding="utf-8"
            )
            subject = f"EventHub closed beta – fout in {context}"
            body = (
                "Hallo,\n\nTijdens het testen van EventHub trad een fout op. "
                "Het bijbehorende foutrapport staat klaar om aan deze e-mail toe te voegen:\n\n"
                f"{report_path}\n\nWat deed u vlak voor de fout?\n"
            )
            mail_url = QUrl("mailto:")
            query = QUrlQuery()
            query.addQueryItem("subject", subject)
            query.addQueryItem("body", body)
            mail_url.setQuery(query)
            QDesktopServices.openUrl(mail_url)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(report_dir)))
            QApplication.clipboard().setText(str(report_path))
            self.status_label.setText(
                "E-mailconcept geopend. Het pad naar het foutrapport staat op het klembord."
            )
        except Exception as report_exc:
            QMessageBox.warning(
                self,
                "Foutrapport kon niet worden voorbereid",
                f"Het e-mailconcept of foutrapport kon niet worden gemaakt.\n\n{report_exc}",
            )

    def _show_error_with_report(self, title: str, message: str, context: str, details: str):
        dialog = QMessageBox(self)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        send_button = dialog.addButton(
            "Log per e-mail versturen", QMessageBox.ButtonRole.ActionRole
        )
        dialog.addButton("Sluiten", QMessageBox.ButtonRole.RejectRole)
        dialog.exec()
        if dialog.clickedButton() is send_button:
            self._prepare_error_email(context, details)

    def _show_runtime_error(self, context: str, exc: BaseException):
        details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        log_path = self._write_error_log(context, details)
        location = f"\n\nTechnische details zijn opgeslagen in:\n{log_path}" if log_path else ""
        self._show_error_with_report(
            f"{context} mislukt",
            "Er ging iets mis. De fout is niet genegeerd; dat leek ons na de vorige versie een aardige vooruitgang."
            + location,
            context,
            details,
        )

    def _handle_unexpected_exception(self, exc_type, exc_value, exc_traceback):
        try:
            details = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            log_path = self._write_error_log("Onverwachte programmafout", details)
            location = f"\n\nFoutlog:\n{log_path}" if log_path else ""
            self._show_error_with_report(
                "Onverwachte programmafout",
                "EventHub heeft een onverwachte fout onderschept." + location,
                "Onverwachte programmafout",
                details,
            )
        except Exception:
            if self._previous_excepthook:
                self._previous_excepthook(exc_type, exc_value, exc_traceback)

    def maybe_require_initial_profile(self):
        if self.settings.value("initial_profile_complete", False, type=bool):
            return True
        if self._profile_complete():
            self.settings.setValue("initial_profile_complete", True)
            return True
        dialog = ProfileDetailsDialog(self.profile, self, required=True)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self.profile = dialog.value()
        self.settings.setValue("profile", json.dumps(self.profile, ensure_ascii=False))
        self.settings.setValue("initial_profile_complete", True)
        self._mark_dirty()
        self._render_management()
        self.status_label.setText("Profiel ingesteld. U kunt nu uw eerste evenement aanmaken.")
        return True

    def run_post_startup(self):
        # Onderdrukt de controle op de bewaartermijn tijdens het herstellen van
        # het laatste dossier; die volgt hieronder, na de opstartschermen.
        self._starting_up = True
        try:
            self._restore_last_or_discovered_project()
            self.maybe_restore_autosave()
            if self.maybe_require_initial_profile():
                self.maybe_show_changelog()
                self.maybe_show_browser_extension_setup()
                self.maybe_show_startup_welcome()
        finally:
            self._starting_up = False
        # Pas na de opstartschermen: de vraag om onomkeerbaar te verwijderen
        # hoort niet achter een welkomstvenster te verdwijnen.
        self.maybe_apply_retention()
        self._schedule_daily_refresh()

    def _schedule_daily_refresh(self):
        """Ververs dag-afhankelijke schermen zodra de kalenderdatum verspringt.

        Zonder deze timer blijft een app die 's nachts blijft openstaan het
        Vandaag-blok, de datumkop en de taakstatussen (Vandaag / Te laat) op de
        vorige dag hangen tot de gebruiker ergens op klikt. Pollen is bewust
        eenvoudig gehouden: het overleeft ook slaapstand en klokwijzigingen,
        wat een singleShot naar middernacht niet doet.
        """
        self._daily_refresh_date = date.today()
        if not hasattr(self, "_daily_refresh_timer"):
            self._daily_refresh_timer = QTimer(self)
            self._daily_refresh_timer.setInterval(60_000)
            self._daily_refresh_timer.timeout.connect(self._daily_refresh_tick)
        self._daily_refresh_timer.start()

    def _daily_refresh_tick(self):
        current_date = date.today()
        if current_date == getattr(self, "_daily_refresh_date", current_date):
            return
        self._daily_refresh_date = current_date
        try:
            self._render_management()
            if hasattr(self, "_update_event_workspace_header"):
                self._update_event_workspace_header()
            # Een dossier dat dagenlang open blijft staan moet de termijn ook
            # halen; zonder deze stap wacht het wissen tot de volgende start.
            self.maybe_apply_retention()
        except Exception:
            # Een mislukte verversing mag de timer nooit stoppen.
            pass

    def _standard_project_search_roots(self):
        roots = []
        for location in (
            QStandardPaths.StandardLocation.DocumentsLocation,
            QStandardPaths.StandardLocation.DownloadLocation,
            QStandardPaths.StandardLocation.DesktopLocation,
        ):
            roots.extend(Path(value) for value in QStandardPaths.standardLocations(location) if value)
        roots.extend(Path.home() / name for name in ("Documents", "Downloads", "Desktop"))
        one_drive = str(os.environ.get("OneDrive", "") or "").strip()
        if one_drive:
            roots.extend([Path(one_drive) / "Documents", Path(one_drive) / "Desktop"])
        local_app_data = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
        if local_app_data:
            roots.extend([
                Path(local_app_data) / "DCPL EMT",
                Path(local_app_data) / "Programs" / "DCPL EMT",
                Path(local_app_data) / "Programs" / "DCPL Event Management Tool (EMT)",
            ])
        unique = []
        seen = set()
        for root in roots:
            key = os.path.normcase(os.path.abspath(str(root)))
            if key not in seen and root.is_dir():
                seen.add(key)
                unique.append(root)
        return unique

    def _discover_existing_projects(self, roots=None, max_depth: int = 4):
        roots = list(roots or self._standard_project_search_roots())
        found = {}
        for root in roots:
            root = Path(root).expanduser()
            if not root.is_dir():
                continue
            try:
                for current, directories, files in os.walk(root):
                    current_path = Path(current)
                    try:
                        depth = len(current_path.relative_to(root).parts)
                    except ValueError:
                        depth = 0
                    directories[:] = [name for name in directories if not name.startswith(".")]
                    if depth >= max_depth:
                        directories[:] = []
                    for file_name in files:
                        if not file_name.lower().endswith(".bvp"):
                            continue
                        path = current_path / file_name
                        try:
                            found[str(path.resolve())] = path.stat().st_mtime
                        except OSError:
                            continue
                        if len(found) >= 100:
                            break
                    if len(found) >= 100:
                        break
            except (OSError, PermissionError):
                continue
        return [path for path, _ in sorted(found.items(), key=lambda item: item[1], reverse=True)]

    def _merge_recent_project_paths(self, paths):
        merged = []
        for value in [*paths, *self.recent_project_paths]:
            path = Path(str(value or "")).expanduser()
            if not path.is_file() or path.suffix.lower() != ".bvp":
                continue
            resolved = str(path.resolve())
            if not any(os.path.normcase(existing) == os.path.normcase(resolved) for existing in merged):
                merged.append(resolved)
        self.recent_project_paths = merged[:12]
        self.settings.setValue("recent_project_paths", json.dumps(self.recent_project_paths, ensure_ascii=False))
        self._refresh_recent_projects_ui()

    def _restore_last_or_discovered_project(self):
        try:
            discovery_version = int(self.settings.value("project_discovery_schema_version", 0) or 0)
        except (TypeError, ValueError):
            discovery_version = 0
        if discovery_version < 2 or not self.recent_project_paths:
            discovered = self._discover_existing_projects()
            self._merge_recent_project_paths(discovered)
            self.settings.setValue("project_discovery_schema_version", 2)
        last_path = str(self.settings.value("last_project_path", "") or "")
        candidates = [last_path, *self.recent_project_paths] if last_path else list(self.recent_project_paths)
        tried = set()
        for value in candidates:
            path = Path(value)
            key = os.path.normcase(os.path.abspath(str(path)))
            if key in tried:
                continue
            tried.add(key)
            if path.is_file() and self._open_project_path(path, confirm_discard=False, quiet=True):
                self.status_label.setText(
                    f"Laatst gebruikte EventHub-bestand automatisch geopend: {path.name}."
                )
                return True
        self._merge_recent_project_paths(candidates)
        return False

    def open_recent_project(self):
        path = Path(str(self.recent_project_combo.currentData() or ""))
        if not str(path) or not path.is_file():
            QMessageBox.information(
                self,
                "Geen recent EventHub-bestand",
                "Er is nog geen bereikbaar recent EventHub-bestand. Gebruik Bestand openen om een .bvp-bestand te kiezen.",
            )
            return
        self._open_project_path(path)

    def add_event(self):
        self.new_project()

    def edit_selected_home_event(self):
        event = self._selected_management_event(self.home_event_table)
        if event:
            self._edit_event(event)

    def edit_selected_event(self):
        event = self._selected_management_event(self.event_table)
        if not event:
            QMessageBox.information(self, "Geen evenement gekozen", "Selecteer eerst een evenement.")
            return
        self._edit_event(event)

    def _edit_event(self, event: dict):
        try:
            self._edit_event_impl(event)
        except Exception as exc:
            self._show_runtime_error("Evenement aanpassen", exc)

    def _edit_event_impl(self, event: dict):
        original_name = event.get("name", "")
        original_type = event.get("event_type", "Meeloopdag")
        dialog = NewProjectDialog(self, event, project_templates=self.project_templates)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        source = deepcopy(event)
        source.update(dialog.value())
        updated = prepare_event(source, self.task_templates)
        updated["name"] = event_name_with_date(updated.get("name", ""), updated.get("date", ""))
        new_type = updated.get("event_type", "Meeloopdag")
        if new_type != original_type and not updated.get("template_id"):
            updated["tasks"] = [
                task for task in updated.get("tasks", [])
                if task_allowed_for_event_type(task, new_type)
            ]
            if new_type != "Online voorlichting":
                existing_tasks = {normalize(task.get("title", "")) for task in updated.get("tasks", [])}
                for task in tasks_from_templates(self.task_templates, new_type):
                    if normalize(task.get("title", "")) not in existing_tasks:
                        updated["tasks"].append(task)
        if not updated["name"]:
            QMessageBox.information(self, "Naam ontbreekt", "Geef het evenement een naam.")
            return
        if updated["date"] and parse_date(updated["date"]) is None:
            QMessageBox.information(self, "Datum ongeldig", "Gebruik voor de evenementdatum bijvoorbeeld 29-09-2026.")
            return
        duplicate = self._event_by_name(updated["name"])
        if duplicate and duplicate is not event:
            QMessageBox.information(self, "Evenement bestaat al", "Er bestaat al een evenement met deze naam.")
            return
        event.clear()
        event.update(updated)
        if normalize(original_name) != normalize(event["name"]):
            for record in self.records:
                names = record_events(record)
                changed = False
                for index, name in enumerate(names):
                    if normalize(name) == normalize(original_name):
                        names[index] = event["name"]
                        changed = True
                if changed:
                    record["Evenement"] = "; ".join(names)
                # Aanwezigheid hangt aan de evenementnaam en moet meeverhuizen.
                rename_attendance_event(record, original_name, event["name"])
            if original_name in self.selected_events:
                self.selected_events.discard(original_name)
                self.selected_events.add(event["name"])
        self._mark_dirty()
        self._render_all()
        self._touch_event(event)
        self.status_label.setText(f"Evenement bijgewerkt: {event['name']}.")

    def activate_selected_event(self):
        event = self._selected_management_event(self.event_table)
        if not event:
            QMessageBox.information(self, "Geen evenement gekozen", "Selecteer eerst een evenement.")
            return
        self.open_event(event)

    def clear_event_visitor_lists(self):
        """Alle bezoekers van dit evenement loskoppelen, het evenement zelf blijft staan.

        Bedoeld om de aanmeldlijsten opnieuw te kunnen inlezen zonder het
        evenement met zijn taken en documenten te verliezen.
        """
        event = self._active_event()
        if not event:
            QMessageBox.information(
                self,
                "Geen evenement geopend",
                "Open eerst het evenement waarvan u de bezoekerslijst(en) wilt wissen.",
            )
            return
        event_name = event.get("name", "")
        visitors = self._event_visitors(event)
        if not visitors:
            QMessageBox.information(
                self,
                "Geen bezoekers gekoppeld",
                f"Aan '{event_name}' zijn geen bezoekers gekoppeld; er valt niets te wissen.",
            )
            return
        attended = sum(1 for record in visitors if is_present(record, event_name))
        elsewhere = sum(1 for record in visitors if len(record_events(record)) > 1)
        question = (
            f"Wilt u de bezoekerslijst(en) van '{event_name}' wissen?\n\n"
            f"{len(visitors)} bezoeker(s) worden losgekoppeld, inclusief de vastgelegde aanwezigheid "
            f"van {attended} bezoeker(s). Het evenement zelf blijft staan met zijn taken en documenten, "
            "zodat u de lijsten opnieuw kunt inlezen."
        )
        if elsewhere:
            question += (
                f"\n\n{elsewhere} bezoeker(s) zijn ook aan een ander evenement gekoppeld; "
                "daar blijven zij behouden."
            )
        question += "\n\nDit kan niet ongedaan worden gemaakt."
        answer = QMessageBox.warning(
            self,
            "Bezoekerslijst(en) wissen",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.records = detach_event_from_records(self.records, event_name)
        self._touch_event(event)
        self._mark_dirty()
        self._render_all()
        self.status_label.setText(
            f"Bezoekerslijst(en) gewist: {event_name} ({len(visitors)} bezoeker(s) losgekoppeld)."
        )

    def _merge_candidates(self, event):
        """Evenementen die logischerwijs bij dit evenement horen.

        Zelfde datum en plaats is in de praktijk hetzelfde evenement dat onder
        meerdere namen online staat om verschillende doelgroepen te trekken.
        """
        datum = normalize(event.get("date", ""))
        plaats = normalize(event.get("place", "") or event.get("location", ""))
        vanzelfsprekend = []
        overig = []
        for other in self.events:
            if other.get("id") == event.get("id"):
                continue
            zelfde_dag = datum and normalize(other.get("date", "")) == datum
            zelfde_plek = normalize(other.get("place", "") or other.get("location", "")) == plaats
            (vanzelfsprekend if zelfde_dag and zelfde_plek else overig).append(other)
        return vanzelfsprekend, overig

    def merge_selected_events(self):
        """Voeg meerdere evenementen samen tot één.

        De namen van de samengevoegde evenementen blijven per deelnemer bewaard
        als inschrijving: dat is precies waarvoor die aparte aanmeldpagina's
        bestaan, en zonder die vastlegging is die informatie na het bundelen weg.
        """
        event = self._selected_management_event(self.event_table)
        if not event:
            QMessageBox.information(self, "Geen evenement gekozen", "Selecteer eerst een evenement.")
            return
        vanzelfsprekend, overig = self._merge_candidates(event)
        if not vanzelfsprekend and not overig:
            QMessageBox.information(
                self, "Niets om samen te voegen", "Er is maar een evenement in dit dossier."
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Evenementen samenvoegen")
        _fit_dialog_to_screen(dialog, 640, 520, 520, 380)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Kies de evenementen die in werkelijkheid hetzelfde evenement zijn. Ze worden een "
            "deelnemerslijst, een aanwezigheidsregistratie en een statistiek. De namen blijven "
            "per deelnemer bewaard als inschrijving."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        vast = QLabel(f"<b>{event.get('name', '')}</b> ({len(self._event_visitors(event))} deelnemers)")
        vast.setWordWrap(True)
        layout.addWidget(vast)

        keuzes = {}
        keuze_widget = QWidget()
        keuze_layout = QVBoxLayout(keuze_widget)
        keuze_layout.setContentsMargins(0, 0, 0, 0)
        for groep, voorgeselecteerd in ((vanzelfsprekend, True), (overig, False)):
            for other in groep:
                vinkje = QCheckBox(
                    f"{other.get('name', '')}  —  {len(self._event_visitors(other))} deelnemers"
                )
                vinkje.setChecked(voorgeselecteerd)
                keuzes[other.get("id", "")] = vinkje
                keuze_layout.addWidget(vinkje)
        keuze_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(keuze_widget)
        layout.addWidget(scroll, 1)

        naam_veld = QLineEdit()
        layout.addWidget(QLabel("Naam van het samengevoegde evenement:"))
        layout.addWidget(naam_veld)
        samenvatting = QLabel("")
        samenvatting.setObjectName("hintLabel")
        samenvatting.setWordWrap(True)
        layout.addWidget(samenvatting)

        def gekozen():
            return [
                other for other in self.events
                if other.get("id") in keuzes and keuzes[other.get("id", "")].isChecked()
            ]

        naam_handmatig = {"aangepast": False}
        naam_veld.textEdited.connect(lambda *_: naam_handmatig.update(aangepast=True))

        def ververs(*_):
            bronnen = gekozen()
            namen = [event.get("name", "")] + [other.get("name", "") for other in bronnen]
            if not naam_handmatig["aangepast"]:
                naam_veld.setText(event_name_with_date(common_event_name(namen), event.get("date", "")))
            labels = distinctive_labels(namen)
            deelnemers = sum(
                len(self._event_visitors(item)) for item in [event, *bronnen]
            )
            if bronnen:
                samenvatting.setText(
                    f"{len(bronnen) + 1} evenementen worden er een, met {deelnemers} deelnemer(s). "
                    f"Bewaard als inschrijving: {' | '.join(labels[naam] for naam in namen)}."
                )
            else:
                samenvatting.setText("Kies minimaal een evenement om mee samen te voegen.")

        for vinkje in keuzes.values():
            vinkje.toggled.connect(ververs)
        ververs()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Samenvoegen")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        bronnen = gekozen()
        if not bronnen:
            QMessageBox.information(self, "Niets gekozen", "Kies minimaal een evenement om mee samen te voegen.")
            return
        nieuwe_naam = naam_veld.text().strip()
        if not nieuwe_naam:
            QMessageBox.information(self, "Geen naam", "Geef het samengevoegde evenement een naam.")
            return
        botsing = next(
            (other for other in self.events
             if normalize(other.get("name", "")) == normalize(nieuwe_naam)
             and other.get("id") not in {event.get("id"), *[b.get("id") for b in bronnen]}),
            None,
        )
        if botsing is not None:
            QMessageBox.information(
                self, "Naam al in gebruik",
                f"Er bestaat al een ander evenement met de naam '{nieuwe_naam}'. Kies een andere naam.",
            )
            return

        namen = [event.get("name", "")] + [other.get("name", "") for other in bronnen]
        deelnemers = sum(len(self._event_visitors(item)) for item in [event, *bronnen])
        antwoord = QMessageBox.warning(
            self,
            "Evenementen samenvoegen",
            f"Wilt u {len(namen)} evenementen samenvoegen tot '{nieuwe_naam}'?\n\n"
            f"{deelnemers} deelnemer(s), hun aanwezigheid, de taken en de documenten komen samen onder "
            "een evenement. De oude evenementen verdwijnen uit het overzicht; hun namen blijven per "
            "deelnemer bewaard als inschrijving.\n\nDit kan niet ongedaan worden gemaakt.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if antwoord != QMessageBox.StandardButton.Yes:
            return

        labels = distinctive_labels(namen)
        listings = list(event.get("listings", []) or [])
        titels = {normalize(task.get("title", "")) for task in event.get("tasks", []) or []}
        for item in [event, *bronnen]:
            merge_event_into(self.records, item.get("name", ""), nieuwe_naam, labels[item.get("name", "")])
            listings.append({
                "label": labels[item.get("name", "")],
                "rudder_event_id": str(item.get("rudder_event_id", "") or "").strip(),
            })
        for other in bronnen:
            for task in other.get("tasks", []) or []:
                if normalize(task.get("title", "")) not in titels:
                    event.setdefault("tasks", []).append(task)
                    titels.add(normalize(task.get("title", "")))
            event.setdefault("attachments", []).extend(other.get("attachments", []) or [])

        event["name"] = nieuwe_naam
        event["listings"] = listings
        self._touch_event(event)
        verdwenen = {other.get("id") for other in bronnen}
        self.events = [item for item in self.events if item.get("id") not in verdwenen]
        self.records, dubbel = merge_duplicate_registrations(self.records, nieuwe_naam)
        self.selected_events = {nieuwe_naam}
        self.active_event_id = event.get("id", "")
        self._mark_dirty()
        self._render_all()
        bericht = f"{len(namen)} evenementen samengevoegd tot {nieuwe_naam}."
        if dubbel:
            bericht += f" {dubbel} deelnemer(s) stonden op meerdere lijsten en zijn samengevoegd."
        self.status_label.setText(bericht)

    def remove_selected_event(self):
        event = self._selected_management_event(self.event_table)
        if not event:
            QMessageBox.information(self, "Geen evenement gekozen", "Selecteer eerst een evenement.")
            return
        visitors = self._event_visitors(event)
        document_count = len(event.get("attachments", []) or [])
        task_count = len(event.get("tasks", []) or [])
        answer = QMessageBox.warning(
            self,
            "Evenement definitief verwijderen",
            f"Wilt u '{event['name']}' definitief verwijderen?\n\n"
            f"Hiermee verwijdert u ook de koppeling met {len(visitors)} deelnemer(s), "
            f"{task_count} taak/taken en {document_count} documentverwijzing(en). "
            "Deelnemers die óók aan een ander evenement zijn gekoppeld, blijven daar behouden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        event_name = event.get("name", "")
        self.records = detach_event_from_records(self.records, event_name)
        self.events = [item for item in self.events if item.get("id") != event.get("id")]
        self.selected_events.discard(event.get("name", ""))
        if self.active_event_id == event.get("id"):
            self.active_event_id = ""
            self.page_stack.setCurrentWidget(self.home_page)
            self._set_project_context_ui(False)
        self._mark_dirty()
        self._render_all()
        self.status_label.setText(f"Evenement verwijderd: {event_name}.")

    def _current_task_event(self):
        return self._active_event()

    def _task_from_row(self):
        row = self.task_table.currentRow()
        event = self._current_task_event()
        if row < 0 or not event:
            return event, None
        item = self.task_table.item(row, 0)
        task_id = ""
        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            task_id = data[1] if isinstance(data, (tuple, list)) and len(data) > 1 else str(data or "")
        task = next((task for task in event.get("tasks", []) if task.get("id") == task_id), None)
        return event, task

    def _render_task_table(self, *_):
        if not hasattr(self, "task_table"):
            return
        event = self._current_task_event()
        previous_loading = self.loading_tables
        self.loading_tables = True
        try:
            tasks = event.get("tasks", []) if event else []
            self.task_table.setRowCount(len(tasks))
            for row_index, task in enumerate(tasks):
                event_id = event.get("id", "")
                task_id = task.get("id", "")
                done_item = self._check_item(bool(task.get("done")), task_id)
                done_item.setData(Qt.ItemDataRole.UserRole, (event_id, task_id))
                self.task_table.setItem(row_index, 0, done_item)
                due = task_due_date(event, task)
                values = [
                    task.get("title", ""), due.strftime("%d-%m-%Y") if due else "—",
                    task_timing_text(task),
                    f"{task.get('reminder_days', 0)} dag(en) voor deadline",
                    task_state(event, task), task.get("notes", ""),
                ]
                for column, value in enumerate(values, 1):
                    item = QTableWidgetItem(str(value or ""))
                    item.setData(Qt.ItemDataRole.UserRole, (event_id, task_id))
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    if values[4] == "Te laat":
                        item.setBackground(QColor("#fde1e1"))
                    elif values[4] == "Vandaag":
                        item.setBackground(QColor("#fff0c7"))
                    self.task_table.setItem(row_index, column, item)
        finally:
            self.loading_tables = previous_loading

    def _sync_event_status_from_tasks(self, event: dict | None) -> bool:
        """Werk de evenementstatus automatisch bij op basis van datum en taken.

        Een verstreken evenementdatum krijgt vanaf de volgende kalenderdag de
        status Afgerond. Voor toekomstige en lopende evenementen bepaalt de
        takenvoorraad of de voorbereiding Gereed is. Geannuleerd blijft altijd
        een expliciete eindstatus en wordt nooit automatisch overschreven.
        """
        if not event or event.get("status") == "Geannuleerd":
            return False
        if event.get("status_manual"):
            # De gebruiker heeft bewust een status gekozen; die is leidend.
            return False
        current = str(event.get("status", "") or "Concept")
        event_date = parse_date(event.get("date", ""))
        if event_date and event_date < date.today():
            if current == "Afgerond":
                return False
            event["status"] = "Afgerond"
            return True
        if current == "Afgerond":
            return False
        open_tasks = sum(
            not bool(task.get("done")) and self._task_blocks_readiness(event, task)
            for task in event.get("tasks", [])
        )
        target = current
        if open_tasks == 0:
            target = "Gereed"
        elif current == "Gereed":
            target = "In voorbereiding"
        if target == current:
            return False
        event["status"] = target
        return True

    @staticmethod
    def _task_blocks_readiness(event: dict, task: dict) -> bool:
        """Telt deze taak mee voor de vraag of de voorbereiding Gereed is?

        De voor/na-aanduiding op de taak is leidend. Wie een taak op na zet,
        bedoelt werk dat pas na afloop hoort te gebeuren — ook wanneer die op
        de evenementdag zelf valt. Zulke taken hielden een Gereed-status eerder
        tegen, waardoor een evenement met het standaardtemplate (dat twee taken
        na afloop bevat) tot de laatste dag In voorbereiding bleef.

        Een taak met aanduiding voor valt per definitie op of vóór de
        evenementdag, dus een datumvergelijking voegt hier niets toe.
        """
        del event
        return str(task.get("relative", "before")) != "after"

    def _task_item_changed(self, item: QTableWidgetItem):
        if self.loading_tables or item.column() != 0:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(data, (tuple, list)) or len(data) != 2:
            return
        event = self._event_by_id(data[0])
        task = next((task for task in event.get("tasks", []) if task.get("id") == data[1]), None) if event else None
        if not task:
            return
        done = item.checkState() == Qt.CheckState.Checked
        task["done"] = done
        task["completed_on"] = date.today().strftime("%d-%m-%Y") if done else ""
        self._sync_event_status_from_tasks(event)
        self._mark_dirty()
        self._render_management()

    def add_task(self):
        event = self._current_task_event()
        if not event:
            QMessageBox.information(self, "Geen evenement", "Maak of selecteer eerst een evenement.")
            return
        dialog = TaskDialog(None, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        task = dialog.value()
        if not task["title"]:
            QMessageBox.information(self, "Taaknaam ontbreekt", "Geef de taak een naam.")
            return
        event.setdefault("tasks", []).append(task)
        self._sync_event_status_from_tasks(event)
        self._mark_dirty()
        self._render_management()

    def edit_selected_task(self):
        event, task = self._task_from_row()
        if not event or not task:
            QMessageBox.information(self, "Geen taak gekozen", "Selecteer eerst een taak.")
            return
        dialog = TaskDialog(task, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        updated = dialog.value()
        task.clear()
        task.update(updated)
        self._sync_event_status_from_tasks(event)
        self._mark_dirty()
        self._render_management()

    def remove_selected_task(self):
        event, task = self._task_from_row()
        if not event or not task:
            QMessageBox.information(self, "Geen taak gekozen", "Selecteer eerst een taak.")
            return
        answer = QMessageBox.question(self, "Taak verwijderen", f"Wilt u '{task['title']}' verwijderen?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        event["tasks"] = [item for item in event.get("tasks", []) if item.get("id") != task.get("id")]
        self._sync_event_status_from_tasks(event)
        self._mark_dirty()
        self._render_management()

    def edit_task_templates(self):
        templates = [prepare_template(template) for template in self.task_templates]
        dialog = QDialog(self)
        dialog.setWindowTitle("Standaardtaken voor nieuwe evenementen")
        _fit_dialog_to_screen(dialog, 820, 560, 600, 380)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Deze taken worden automatisch toegevoegd aan nieuwe evenementen, per soort "
            "evenement. De termijnen zijn daarna per evenement aanpasbaar."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        table = self._new_table(["Taak", "Geldt voor", "Planning", "Melding"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(table, 1)

        def render():
            table.setRowCount(len(templates))
            for row_index, task in enumerate(templates):
                values = [task["title"], template_scope_text(task), task_timing_text(task),
                          f"{task['reminder_days']} dag(en) voor deadline"]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, task["id"])
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    table.setItem(row_index, column, item)

        def add_template():
            editor = TaskDialog(None, dialog, standaard=True)
            if editor.exec() == QDialog.DialogCode.Accepted and editor.value()["title"]:
                templates.append(editor.value())
                render()

        def edit_template():
            row = table.currentRow()
            if row < 0:
                return
            editor = TaskDialog(templates[row], dialog, standaard=True)
            if editor.exec() == QDialog.DialogCode.Accepted and editor.value()["title"]:
                templates[row] = editor.value()
                render()

        def remove_template():
            row = table.currentRow()
            if row >= 0:
                templates.pop(row)
                render()

        actions = QHBoxLayout()
        for label, handler, style in [
            ("Toevoegen", add_template, "primaryButton"),
            ("Aanpassen", edit_template, "secondaryButton"),
            ("Verwijderen", remove_template, "dangerButton"),
        ]:
            button = QPushButton(label)
            button.setObjectName(style)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        apply_existing = QCheckBox("Ontbrekende standaarden ook toevoegen aan bestaande evenementen")
        apply_existing.setToolTip("Evenementen met een gekoppeld template behouden hun eigen taken.")
        layout.addWidget(apply_existing)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        table.cellDoubleClicked.connect(lambda *_: edit_template())
        render()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.task_templates = [prepare_task(template) for template in templates]
        self.settings.setValue("task_templates", json.dumps(self.task_templates, ensure_ascii=False))
        if apply_existing.isChecked():
            for event in self.events:
                if event.get("template_id"):
                    continue
                existing = {normalize(task.get("title", "")) for task in event.get("tasks", [])}
                for template in self.task_templates:
                    if not task_allowed_for_event_type(template, event.get("event_type", "Meeloopdag")):
                        continue
                    if normalize(template["title"]) not in existing:
                        source = dict(template)
                        source.update({"id": "", "done": False, "completed_on": ""})
                        event.setdefault("tasks", []).append(prepare_task(source))
        self._mark_dirty()
        self._render_management()

    def _template_event_data(self, event: dict):
        return template_event_data(event)

    def _save_project_templates(self):
        self.project_templates.sort(key=lambda item: normalize(item.get("name", "")))
        self.settings.setValue("project_templates", json.dumps(self.project_templates, ensure_ascii=False))

    def save_active_event_as_template(self, _checked=False, *, event=None):
        event = event if event is not None else self._active_event()
        if not event:
            QMessageBox.information(self, "Geen evenement geopend", "Open eerst een evenement.")
            return
        editor = TemplateEditor(self, TaskDialog, self.task_templates, event=event)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        template = editor.value()
        existing = next((item for item in self.project_templates
                         if normalize(item["name"]) == normalize(template["name"])), None)
        if existing:
            if QMessageBox.question(self, "Template vervangen",
                    f"'{template['name']}' bestaat al. Wilt u dit template vervangen? Bestaande evenementen blijven behouden."
                    ) != QMessageBox.StandardButton.Yes:
                return
            template["id"] = existing["id"]
            self.project_templates.remove(existing)
        self.project_templates.append(template)
        self._save_project_templates()
        if editor.link.isChecked():
            event.update(template_id=template["id"], template_name=template["name"])
            self._touch_event(event)
            self._mark_dirty()
            self._render_all()
        self.status_label.setText(f"Template opgeslagen: {template['name']}.")

    def manage_project_templates(self):
        TemplateManager(self, self.project_templates, TaskDialog,
                        self.task_templates, self._save_project_templates).exec()
        self._update_event_workspace_header()

    def link_events_to_template(self, event=None):
        if not self.project_templates:
            QMessageBox.information(self, "Geen templates", "Maak eerst een template aan via Templatebeheer, of sla een evenement op als template.")
            return
        dialog = LinkEventsDialog(self, sorted(self.events, key=self._event_sort_key),
                                  self.project_templates, (event or {}).get("id", ""))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        template_id = str(dialog.template.currentData())
        template_name = dialog.template.currentText()
        targets = [item for item in self.events if item["id"] in set(dialog.selected_ids())]
        changed = sum(bool(item.get("template_id")) and item["template_id"] != template_id for item in targets)
        if changed and QMessageBox.question(self, "Templatekoppeling vervangen",
                f"Bij {changed} evenementen vervangt u de huidige templatekoppeling. Doorgaan?") != QMessageBox.StandardButton.Yes:
            return
        for item in targets:
            item.update(template_id=template_id, template_name=template_name)
            self._touch_event(item)
        self._mark_dirty()
        self._render_all()
        self.status_label.setText(f"{len(targets)} evenementen gekoppeld aan {template_name}.")

    def _document_event(self):
        return self._active_event()

    def edit_fivewh(self):
        event = self._document_event()
        if not event:
            QMessageBox.information(self, "Geen evenement", "Maak of selecteer eerst een evenement.")
            return False
        dialog = FiveWhDialog(event, self.profile, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        event["fivewh"] = dialog.value()
        self._mark_dirty()
        self.status_label.setText(f"5WH-gegevens opgeslagen voor {event['name']}.")
        return True

    def edit_evaluation(self):
        event = self._document_event()
        if not event:
            QMessageBox.information(self, "Geen evenement", "Maak of selecteer eerst een evenement.")
            return False
        dialog = EvaluationDialog(event, self.profile, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        event["evaluation"] = dialog.value()
        self._mark_dirty()
        self.status_label.setText(f"Evaluatiegegevens opgeslagen voor {event['name']}.")
        return True

    def _safe_document_name(self, value: str):
        return re.sub(r"[<>:\"/\\|?*]+", "-", str(value or "Evenement")).strip(" .") or "Evenement"

    def _event_date_suffix(self, event: dict | None):
        if not event:
            return ""
        event_date = parse_date(str(event.get("date", "") or ""))
        return f" - {event_date.strftime('%d-%m-%Y')}" if event_date else ""

    def export_fivewh_document(self):
        event = self._document_event()
        if not event:
            QMessageBox.information(self, "Geen evenement", "Maak of selecteer eerst een evenement.")
            return
        if not FIVEWH_TEMPLATE.exists():
            self._show_error_with_report(
                "Sjabloon ontbreekt", "Het 5WH-sjabloon ontbreekt in de installatie.",
                "5WH-sjabloon controleren", f"Ontbrekend bestand: {FIVEWH_TEMPLATE}",
            )
            return
        suggested = exports_directory() / f"5WH - {self._safe_document_name(event['name'])}{self._event_date_suffix(event)}.docx"
        if not self._confirm_personal_data_export("Het 5WH-document"):
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "5WH exporteren", str(suggested), "Word-document (*.docx)")
        if not file_name:
            return
        if not file_name.lower().endswith(".docx"):
            file_name += ".docx"
        try:
            export_fivewh(FIVEWH_TEMPLATE, file_name, event, self.profile, event.get("fivewh", {}))
            self.status_label.setText(f"5WH geëxporteerd: {file_name}")
            QMessageBox.information(self, "5WH gereed", "Het 5WH-document is volgens het vaste format opgeslagen.")
            self._offer_open_export_folder(file_name)
        except Exception as exc:
            self._show_runtime_error("5WH exporteren", exc)

    def export_evaluation_document(self):
        event = self._document_event()
        if not event:
            QMessageBox.information(self, "Geen evenement", "Maak of selecteer eerst een evenement.")
            return
        if not EVALUATION_TEMPLATE.exists():
            self._show_error_with_report(
                "Sjabloon ontbreekt", "Het evaluatiesjabloon ontbreekt in de installatie.",
                "Evaluatiesjabloon controleren", f"Ontbrekend bestand: {EVALUATION_TEMPLATE}",
            )
            return
        suggested = exports_directory() / f"Evaluatie - {self._safe_document_name(event['name'])}{self._event_date_suffix(event)}.docx"
        file_name, _ = QFileDialog.getSaveFileName(self, "Evaluatie exporteren", str(suggested), "Word-document (*.docx)")
        if not file_name:
            return
        if not file_name.lower().endswith(".docx"):
            file_name += ".docx"
        try:
            export_evaluation(
                EVALUATION_TEMPLATE, file_name, event, self.profile, event.get("evaluation", {})
            )
            self.status_label.setText(f"Evaluatie geëxporteerd: {file_name}")
            self._offer_open_export_folder(file_name)
            QMessageBox.information(
                self,
                "Evaluatie gereed",
                "Het evaluatieformulier is macrovrij en volgens het aangeleverde format opgeslagen.",
            )
        except Exception as exc:
            self._show_runtime_error("Evaluatie exporteren", exc)

    def _selected_attachment(self):
        event = self._document_event()
        row = self.attachments_table.currentRow() if hasattr(self, "attachments_table") else -1
        if not event or row < 0:
            return event, None
        item = self.attachments_table.item(row, 0)
        attachment_id = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        attachment = next(
            (item for item in event.get("attachments", []) if str(item.get("id", "")) == attachment_id),
            None,
        )
        return event, attachment

    def _attachment_bytes(self, attachment: dict):
        try:
            return base64.b64decode(str(attachment.get("data", "") or ""), validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("De opgeslagen bijlage is beschadigd of onvolledig.") from exc

    def _format_file_size(self, size):
        size = max(0, int(size or 0))
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.1f} kB"
        return f"{size} bytes"

    def add_attachment(self):
        event = self._document_event()
        if not event:
            QMessageBox.information(self, "Geen evenement geopend", "Open eerst een evenement.")
            return
        file_names, _ = QFileDialog.getOpenFileNames(self, "Documenten toevoegen", "", "Alle bestanden (*.*)")
        if not file_names:
            return
        added = 0
        skipped = []
        attachments = event.setdefault("attachments", [])
        for file_name in file_names:
            path = Path(file_name)
            try:
                size = path.stat().st_size
                if size > MAX_ATTACHMENT_SIZE:
                    skipped.append(f"{path.name} (groter dan 25 MB)")
                    continue
                data = path.read_bytes()
            except OSError as exc:
                skipped.append(f"{path.name} ({exc})")
                continue
            existing = next(
                (item for item in attachments if normalize(item.get("name", "")) == normalize(path.name)),
                None,
            )
            if existing:
                answer = QMessageBox.question(
                    self,
                    "Bijlage vervangen",
                    f"'{path.name}' is al toegevoegd. Wilt u de opgeslagen versie vervangen?",
                )
                if answer != QMessageBox.StandardButton.Yes:
                    continue
                attachments.remove(existing)
            attachments.append({
                "id": uuid.uuid4().hex,
                "name": path.name,
                "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "size": len(data),
                "added_at": datetime.now().strftime("%d-%m-%Y %H:%M"),
                "data": base64.b64encode(data).decode("ascii"),
            })
            added += 1
        if added:
            self._mark_dirty()
            self._render_attachments()
            self.status_label.setText(f"{added} document(en) aan {event.get('name', 'het evenement')} toegevoegd.")
        if skipped:
            QMessageBox.warning(
                self,
                "Niet alle documenten toegevoegd",
                "De volgende bestanden zijn overgeslagen:\n\n" + "\n".join(skipped),
            )

    def open_selected_attachment(self):
        _, attachment = self._selected_attachment()
        if not attachment:
            QMessageBox.information(self, "Geen document gekozen", "Selecteer eerst een toegevoegd document.")
            return
        try:
            cache_root = application_data_root() / "Documentcache"
            cache_root.mkdir(parents=True, exist_ok=True)
            original = Path(str(attachment.get("name", "document") or "document")).name
            safe_name = self._safe_document_name(Path(original).stem) + Path(original).suffix
            target = cache_root / f"{attachment.get('id', uuid.uuid4().hex)}-{safe_name}"
            target.write_bytes(self._attachment_bytes(attachment))
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
                raise OSError("Er is geen geschikt programma gevonden om dit bestand te openen.")
        except Exception as exc:
            self._show_runtime_error("Document openen", exc)

    def export_selected_attachment(self):
        event, attachment = self._selected_attachment()
        if not attachment:
            QMessageBox.information(self, "Geen document gekozen", "Selecteer eerst een toegevoegd document.")
            return
        attachment_name = Path(str(attachment.get("name", "document") or "document")).name
        attachment_path = Path(attachment_name)
        dated_name = f"{attachment_path.stem}{self._event_date_suffix(event)}{attachment_path.suffix}"
        suggested = exports_directory() / dated_name
        if not self._confirm_personal_data_export("Dit document"):
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "Bijlage opslaan als", str(suggested), "Alle bestanden (*.*)")
        if not file_name:
            return
        try:
            Path(file_name).write_bytes(self._attachment_bytes(attachment))
            self.status_label.setText(f"Bijlage opgeslagen: {file_name}")
            self._offer_open_export_folder(file_name)
        except Exception as exc:
            self._show_runtime_error("Bijlage opslaan", exc)

    def remove_selected_attachment(self):
        event, attachment = self._selected_attachment()
        if not event or not attachment:
            QMessageBox.information(self, "Geen document gekozen", "Selecteer eerst een toegevoegd document.")
            return
        answer = QMessageBox.question(
            self,
            "Document verwijderen",
            f"Wilt u '{attachment.get('name', 'dit document')}' uit het evenement verwijderen?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        event["attachments"] = [
            item for item in event.get("attachments", []) if item.get("id") != attachment.get("id")
        ]
        self._mark_dirty()
        self._render_attachments()

    def _render_attachments(self):
        if not hasattr(self, "attachments_table"):
            return
        event = self._document_event()
        attachments = event.get("attachments", []) if event else []
        self.attachments_table.setRowCount(len(attachments))
        for row_index, attachment in enumerate(attachments):
            values = [
                attachment.get("name", ""),
                attachment.get("mime_type", "application/octet-stream"),
                self._format_file_size(attachment.get("size", 0)),
                attachment.get("added_at", ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.ItemDataRole.UserRole, attachment.get("id", ""))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.attachments_table.setItem(row_index, column, item)
        tab_index = self.tabs.indexOf(self.documents_tab)
        if tab_index >= 0:
            self.tabs.setTabText(tab_index, f"Documenten ({len(attachments)})" if attachments else "Documenten")

    def _filtered_records(self, include_skipped: bool = False):
        """De deelnemers in beeld.

        Een overgeslagen dubbele inschrijving hoort nergens meer op te duiken:
        niet in de lijsten, niet in de tellingen en niet in de exports. Alleen
        Gegevenscontrole vraagt hem op, want daar draai je het terug.
        """
        if self.selected_events and all((self._event_by_name(name) or {}).get("persoonsgegevens_gewist")
                                        for name in self.selected_events):
            return []
        rows = [record for record in self.records if matches_event_filter(record, self.selected_events)]
        return rows if include_skipped else [record for record in rows if not is_skipped(record)]

    def choose_event_filter(self):
        events = self._available_events()
        if not events:
            QMessageBox.information(self, "Geen evenementen", "Maak eerst een evenement of voeg een aanmeldlijst toe.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Evenementen filteren")
        _fit_dialog_to_screen(dialog, 520, min(700, 230 + 34 * len(events)), 440, 340)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Kies welke evenementen in Deelnemers, After sales, Event Control, Statistieken, "
            "Gegevenscontrole, afdrukken en export worden gebruikt."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        all_checkbox = QCheckBox("Alle evenementen")
        all_checkbox.setChecked(not self.selected_events)
        layout.addWidget(all_checkbox)
        event_checkboxes = {}
        event_container = QWidget()
        event_layout = QVBoxLayout(event_container)
        event_layout.setContentsMargins(18, 0, 0, 0)
        for event in events:
            checkbox = QCheckBox(event)
            checkbox.setChecked(not self.selected_events or event in self.selected_events)
            checkbox.setEnabled(bool(self.selected_events))
            event_checkboxes[event] = checkbox
            event_layout.addWidget(checkbox)
        event_scroll = QScrollArea()
        event_scroll.setWidgetResizable(True)
        event_scroll.setFrameShape(QFrame.Shape.NoFrame)
        event_scroll.setWidget(event_container)
        layout.addWidget(event_scroll, 1)

        def toggle_all(checked):
            for checkbox in event_checkboxes.values():
                checkbox.setEnabled(not checked)
                if checked:
                    checkbox.setChecked(True)

        all_checkbox.toggled.connect(toggle_all)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if all_checkbox.isChecked():
            selected = set()
        else:
            selected = {event for event, checkbox in event_checkboxes.items() if checkbox.isChecked()}
            if not selected:
                QMessageBox.information(self, "Geen evenement gekozen", "Kies minimaal één evenement of selecteer Alle evenementen.")
                return
        if selected != self.selected_events:
            self.selected_events = selected
            self._mark_dirty()
            self._render_all()

    def _update_event_filter_ui(self):
        events = self._available_events()
        if self.selected_events:
            valid = self.selected_events & set(events)
            self.selected_events = valid
        active = self._active_event()
        if active:
            self.selected_events = {active.get("name", "")}
        self._update_event_workspace_header()

    def _display_value(self, record: dict, field: str):
        if field == "Bezoekerstype":
            return visitor_type(record)
        if field == "IntroduceeVan":
            return primary_visitor_name(record, self._identifier_lookup)
        return record.get(field, "")

    def _participant_scope_changed(self, *_):
        include = self.participant_include_introducees.isChecked()
        self.settings.setValue("participants_include_introducees", include)
        self._filter_participants()

    def _restore_picker(self, picker, setting: str, fallback: str):
        """Zet een keuzelijst terug op de laatst gekozen waarde."""
        stored = str(self.settings.value(setting, fallback) or fallback)
        index = picker.findData(stored)
        picker.setCurrentIndex(index if index >= 0 else 0)

    def _crosstab_options_changed(self, *_):
        self.settings.setValue("crosstab_view", self._crosstab_view())
        self.settings.setValue("crosstab_value", self._crosstab_value_mode())
        self._update_statistics()

    def _crosstab_view(self) -> str:
        return str(self.crosstab_view_picker.currentData() or "grafiek")

    def _crosstab_value_mode(self) -> str:
        return str(self.crosstab_value_picker.currentData() or "aantallen")

    def _crosstab_data(self, records):
        """De kruistabel zoals hij nu getoond moet worden, inclusief bundeling."""
        data = education_crosstab(records)
        if self._show_all_values():
            return data
        return education_collapse(data, CROSSTAB_COLUMN_LIMIT)

    def _statistics_scope_changed(self, *_):
        include = self.statistics_include_introducees.isChecked()
        self.settings.setValue("statistics_include_introducees_v2", include)
        presence_filter = str(self.statistics_presence_filter.currentData() or "all")
        self.settings.setValue("statistics_presence_filter", presence_filter)
        self.settings.setValue("statistics_show_all", self._show_all_values())
        self._update_statistics()

    def _sorted_records(self, records=None):
        source = self.records if records is None else records
        return sorted(source, key=lambda row: (
            normalize(row.get("Achternaam")), normalize(row.get("Tussenvoegsel")), normalize(row.get("Voornaam")),
        ))

    def _text_item(self, value, record_id: str, editable: bool = False):
        item = QTableWidgetItem(str(value or ""))
        item.setData(Qt.ItemDataRole.UserRole, record_id)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        return item

    PRESENCE_COLOURS = {
        AANWEZIG: "#2f7d4f",
        AFWEZIG: "#b8434a",
        AFGEMELD: "#a5751f",
        ONBEKEND: "#7b6d82",
    }

    def _status_item(self, status: str, record_id: str):
        """De aanwezigheidsstand met een snel aanklikbaar aanwezig-vinkje."""
        item = QTableWidgetItem(ATTENDANCE_LABELS.get(status, ATTENDANCE_LABELS[ONBEKEND]))
        item.setData(Qt.ItemDataRole.UserRole, record_id)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setCheckState(
            Qt.CheckState.Checked if status == AANWEZIG else Qt.CheckState.Unchecked
        )
        item.setForeground(QColor(self.PRESENCE_COLOURS.get(status, "#7b6d82")))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setToolTip(
            "Vink aan zodra deze deelnemer langs is geweest. "
            "Rechtsklik voor Afgemeld, Afwezig of Onbekend."
        )
        return item

    def _check_item(self, checked: bool, record_id: str, selectable: bool = True):
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, record_id)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
        if selectable:
            flags |= Qt.ItemFlag.ItemIsSelectable
        item.setFlags(flags)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _render_presence_table(self):
        """Ververs alleen de snelle presentielijst, zonder alle grafieken."""
        if not hasattr(self, "access_table"):
            return
        event = self._event_control_selected_event()
        rows = self._sorted_records(self._event_visitors(event)) if event else []
        presence_fields = self.visible_fields_by_view["presence"]
        signature = self._presence_table_signature(rows, presence_fields)
        if signature == self._presence_render_signature:
            self._filter_presence(self.search_box.text() if hasattr(self, "search_box") else "")
            return
        self.loading_tables = True
        try:
            self.access_table.setSortingEnabled(False)
            self.access_table.setColumnCount(len(presence_fields) + 1)
            self.access_table.setHorizontalHeaderLabels(self._presence_headers())
            self.access_table.setRowCount(len(rows))
            for row_index, record in enumerate(rows):
                record_id = record["_id"]
                for column, field in enumerate(presence_fields):
                    self.access_table.setItem(
                        row_index,
                        column,
                        self._text_item(self._display_value(record, field), record_id),
                    )
                self.access_table.setItem(
                    row_index,
                    len(presence_fields),
                    self._status_item(self._scoped_status(record), record_id),
                )
        finally:
            self.loading_tables = False
            self.access_table.setSortingEnabled(True)
            self._restore_table_sort(self.access_table)
        self._presence_render_signature = signature
        self._filter_presence(self.search_box.text() if hasattr(self, "search_box") else "")

    def _presence_table_signature(self, rows, presence_fields):
        """Goedkope momentopname om een ongewijzigde tabel te kunnen hergebruiken."""
        return (
            tuple(presence_fields),
            tuple(sorted(self.selected_events, key=normalize)),
            tuple(
                (
                    str(record.get("_id", "")),
                    tuple(self._display_value(record, field) for field in presence_fields),
                    self._scoped_status(record),
                )
                for record in rows
            ),
        )

    def _render_event_control_scope(self):
        """Ververs alleen gegevens die door de Event Control-keuze veranderen."""
        self._update_event_filter_ui()
        self._render_presence_table()
        self._update_summary()
        self._update_statistics()
        self._update_quality_table()
        self._update_previous_live_session_action()
        self._update_presence_registration_availability()

    def _render_live_attendance_scope(self):
        """Houd live check-ins licht: geen grafieken opnieuw tekenen per scan."""
        self._render_presence_table()
        self._update_summary()
        self._update_presence_registration_availability()

    def _render_all(self):
        status_changed = self._archive_passed_events()
        for event in self.events:
            status_changed = self._sync_event_status_from_tasks(event) or status_changed
        # Cijfers van geweeste evenementen vastleggen zolang de bron er nog is;
        # na het wissen van persoonsgegevens is dit de enige overgebleven bron.
        status_changed = self._refresh_past_event_statistics() or status_changed
        if status_changed:
            self._mark_dirty()
        self.loading_tables = True
        try:
            for table in (self.participant_table, self.callback_table, self.access_table):
                table.setSortingEnabled(False)
            self._update_event_filter_ui()
            rows = self._sorted_records(self._filtered_records())
            after_sales_event = self._combo_event(self.after_sales_event_combo)
            callback_source = self._event_visitors(after_sales_event) if after_sales_event else []
            callback_rows = [record for record in callback_source if not is_introducee(record)]
            presence_event = self._event_control_selected_event()
            presence_rows = self._sorted_records(self._event_visitors(presence_event)) if presence_event else []
            self._identifier_lookup = registration_lookup(self.records)
            participant_fields = self.visible_fields_by_view["participants"]
            callback_fields = self.visible_fields_by_view["callbacks"]
            presence_fields = self.visible_fields_by_view["presence"]
            self.participant_table.setColumnCount(len(participant_fields))
            self.participant_table.setHorizontalHeaderLabels(self._participant_headers())
            self._apply_participant_column_order(participant_fields)
            self.callback_table.setColumnCount(len(callback_fields) + 1)
            self.callback_table.setHorizontalHeaderLabels(self._callback_headers())
            self.access_table.setColumnCount(len(presence_fields) + 1)
            self.access_table.setHorizontalHeaderLabels(self._presence_headers())
            self.participant_table.setRowCount(len(rows))
            self.callback_table.setRowCount(len(callback_rows))
            self.access_table.setRowCount(len(presence_rows))
            for row_index, record in enumerate(rows):
                record_id = record["_id"]
                for column, field in enumerate(participant_fields):
                    editable = field in EDITABLE_VISITOR_FIELDS
                    participant_item = self._text_item(self._display_value(record, field), record_id, editable)
                    self.participant_table.setItem(row_index, column, participant_item)
                if is_introducee(record):
                    for column in range(self.participant_table.columnCount()):
                        item = self.participant_table.item(row_index, column)
                        if item:
                            item.setBackground(QColor("#f2e5f7"))
                            item.setToolTip("Introducé")
            self._apply_participant_column_widths(participant_fields)

            for row_index, record in enumerate(callback_rows):
                record_id = record["_id"]
                for column, field in enumerate(callback_fields):
                    self.callback_table.setItem(
                        row_index,
                        column,
                        self._text_item(self._display_value(record, field), record_id),
                    )
                present = is_present_in_scope(record, self.selected_events)
                presence_item = self._text_item("Aanwezig" if present else "Afwezig", record_id)
                presence_item.setToolTip("Deze kandidaat is tijdens de livesessie aanwezig geweest." if present else "Voor deze kandidaat is geen aanwezigheid geregistreerd.")
                self.callback_table.setItem(row_index, len(callback_fields), presence_item)
                self._apply_callback_status_marker(row_index, record)
            self._apply_callback_column_widths(callback_fields)
            if self.callback_table.columnCount() > len(callback_fields):
                self.callback_table.setColumnWidth(len(callback_fields), 110)

            for row_index, record in enumerate(presence_rows):
                record_id = record["_id"]
                for column, field in enumerate(presence_fields):
                    self.access_table.setItem(
                        row_index,
                        column,
                        self._text_item(self._display_value(record, field), record_id),
                    )
                self.access_table.setItem(
                    row_index,
                    len(presence_fields),
                    self._status_item(self._scoped_status(record), record_id),
                )
        finally:
            self.loading_tables = False
            for table in (self.participant_table, self.callback_table, self.access_table):
                table.setSortingEnabled(True)
                self._restore_table_sort(table)
        self._presence_render_signature = self._presence_table_signature(presence_rows, presence_fields)
        self._filter_participants()
        self._filter_callbacks()
        self._filter_presence(self.search_box.text() if hasattr(self, "search_box") else "")
        self._update_callback_selection_label()
        self._update_summary()
        self._update_statistics()
        self._update_quality_table()
        self._render_attachments()
        self._render_management()
        self._render_profile_page()
        self._update_after_sales_availability()

    def _update_summary(self):
        scoped_records = self._filtered_records()
        total = len(scoped_records)
        introducees = sum(is_introducee(row) for row in scoped_records)
        regular_records = [row for row in scoped_records if not is_introducee(row)]
        callbacks = sum(
            callback_is_done(row) or str(row.get("WhatsAppStatus", "")) == "Verzonden"
            for row in regular_records
        )
        present = sum(is_present_in_scope(row, self.selected_events) for row in scoped_records)
        event = self._active_event()
        historical = self._event_is_anonymized(event) if event else False
        snapshot = historical_scope(event) if historical else None
        self.count_total[1].setText(
            str(snapshot.get("aangemeld", "—")) if snapshot else ("—" if historical else str(total))
        )
        self.count_total[2].setText(
            ("Geanonimiseerd" if snapshot else "Historische aantallen niet bewaard")
            if historical else f"{len(regular_records)} regulier • {introducees} introducé"
        )
        open_callbacks = max(0, len(regular_records) - callbacks)
        self.count_callbacks[1].setText("—" if historical else str(open_callbacks))
        self.count_callbacks[2].setText("Geanonimiseerd" if historical else ("Nog te behandelen" if open_callbacks else "After sales bijgewerkt"))
        open_tasks = sum(not bool(task.get("done")) for task in event.get("tasks", [])) if event else 0
        self.count_tasks[1].setText(str(open_tasks))
        self.count_tasks[2].setText("Openstaande acties" if open_tasks else "Geen openstaande acties")
        if hasattr(self, "after_sales_total"):
            after_sales_event = self._combo_event(self.after_sales_event_combo)
            after_sales_records = self._event_visitors(after_sales_event) if after_sales_event else []
            after_sales_regular = [row for row in after_sales_records if not is_introducee(row)]
            after_sales_callbacks = sum(
                callback_is_done(row) or str(row.get("WhatsAppStatus", "")) == "Verzonden"
                for row in after_sales_regular
            )
            open_callbacks = max(0, len(after_sales_regular) - after_sales_callbacks)
            followups = sum(
                bool(str(row.get("TerugbellenOp", "") or "").strip())
                and callback_status(row) not in {"Afgerond", "Niet meer benaderen"}
                for row in after_sales_regular
            )
            fully_done = sum(
                callback_status(row) in CALLBACK_DONE_STATUSES
                and not str(row.get("TerugbellenOp", "") or "").strip()
                for row in after_sales_regular
            )
            actionable = max(0, len(after_sales_regular) - fully_done)
            self.after_sales_total[1].setText(str(len(after_sales_regular)))
            self.after_sales_total[2].setText("Reguliere kandidaten")
            self.after_sales_open[1].setText(str(actionable))
            self.after_sales_open[2].setText("Actie nodig" if actionable else "Alles bijgewerkt")
            self.after_sales_followup[1].setText(str(followups))
            self.after_sales_followup[2].setText("Terugbellen gepland" if followups else "Geen vervolgafspraken")
            self.after_sales_done[1].setText(str(fully_done))
            self.after_sales_done[2].setText("Geen actie meer nodig")
        self.count_present[1].setText(
            str(snapshot.get("aanwezig", "—")) if snapshot else ("—" if historical else str(present))
        )
        self.count_present[2].setText(
            ("Historische aanwezigheid" if snapshot else "Historische cijfers niet bewaard")
            if historical else f"Nog {total - present} niet afgevinkt"
        )
        if hasattr(self, "participant_include_introducees"):
            self.participant_include_introducees.setText(f"Introducees tonen ({introducees})")
        if hasattr(self, "statistics_include_introducees"):
            self.statistics_include_introducees.setText(
                f"Introducees meetellen in grafieken ({snapshot.get('introducees', 0) if snapshot else introducees})"
            )
        if hasattr(self, "participant_history_notice"):
            self.participant_history_notice.setVisible(historical)
            self.participant_table.setVisible(not historical)
            self.participant_search_box.setEnabled(not historical)
            self.participant_include_introducees.setEnabled(not historical)
            self.participant_import_button.setEnabled(not historical)
            self.participant_columns_button.setEnabled(not historical)
            self.participant_more_button.setEnabled(not historical)
            if historical:
                self.participant_history_notice.setText(
                    "Geanonimiseerd — persoonsgegevens zijn verwijderd. "
                    + ("Historische cijfers en export vindt u bij Statistieken." if snapshot else
                       "Er is geen historische cijfermomentopname bewaard; daarom zijn de aantallen niet beschikbaar.")
                )

    def _person_name(self, record: dict):
        return " ".join(filter(None, [
            str(record.get("Voornaam", "") or "").strip(),
            str(record.get("Tussenvoegsel", "") or "").strip(),
            str(record.get("Achternaam", "") or "").strip(),
        ])) or "Naam onbekend"

    def _quality_issues(self, records):
        issues = []
        duplicate_keys = {}
        for record in records:
            name_date = normalize("|".join([
                str(record.get("Voornaam", "")), str(record.get("Tussenvoegsel", "")),
                str(record.get("Achternaam", "")), str(record.get("Geboortedatum", "")),
            ]))
            email = normalize(record.get("Email", ""))
            phone = re.sub(r"\D", "", str(record.get("Telefoonnummer", "") or ""))
            for key in (
                f"naam:{name_date}" if name_date else "",
                f"mail:{email}" if email else "",
                f"tel:{phone}" if len(phone) >= 9 else "",
            ):
                if key:
                    duplicate_keys.setdefault(key, []).append(record["_id"])
        duplicate_ids = {
            record_id for record_ids in duplicate_keys.values() if len(set(record_ids)) > 1 for record_id in record_ids
        }

        for record in records:
            phone_text = str(record.get("Telefoonnummer", "") or "").strip()
            phone_digits = re.sub(r"\D", "", phone_text)
            birth_date = str(record.get("Geboortedatum", "") or "").strip()
            education = normalize(record.get("Opleiding", ""))
            profile = normalize(record.get("Profiel", ""))
            if not str(record.get("Geboorteplaats", "") or "").strip():
                issues.append(("Geboorteplaats ontbreekt", record, "Vul de geboorteplaats aan."))
            if not birth_date:
                issues.append(("Geboortedatum ontbreekt", record, "Vul de geboortedatum aan."))
            elif self._age_from_text(birth_date) is None:
                issues.append(("Geboortedatum ongeldig", record, f"Controleer de waarde: {birth_date}"))
            if not is_introducee(record):
                if not phone_text:
                    issues.append(("Telefoonnummer ontbreekt", record, "Nodig voor bellen of WhatsApp-after-sales."))
                elif not 9 <= len(phone_digits) <= 15:
                    issues.append(("Telefoonnummer lijkt ongeldig", record, f"Controleer de waarde: {phone_text}"))
            if record["_id"] in duplicate_ids:
                issues.append(("Mogelijk dubbele deelnemer", record, "Controleer naam, geboortedatum, e-mail en telefoonnummer."))
            if is_introducee(record) and primary_visitor_name(record, self._identifier_lookup) == "Onbekende hoofdbezoeker":
                issues.append(("Introducé zonder hoofdbezoeker", record, "Het registratie-ID in Gast van is niet gevonden."))
            if not is_introducee(record):
                if education in ("", "onbekend", "nietingevuld"):
                    issues.append(("Opleidingsniveau ontbreekt", record, "Vul het opleidingsniveau aan indien bekend."))
                if profile in ("", "onbekend", "nietingevuld"):
                    issues.append(("Profiel ontbreekt", record, "Vul profiel of opleidingsrichting aan indien bekend."))
        return sorted(issues, key=lambda row: (normalize(row[0]), normalize(row[1].get("Achternaam")), normalize(row[1].get("Voornaam"))))

    def _update_quality_table(self):
        if not hasattr(self, "quality_table"):
            return
        issues = self._quality_issues(self._filtered_records(include_skipped=True))
        self.quality_table.setRowCount(len(issues))
        for row_index, (problem, record, advice) in enumerate(issues):
            if is_skipped(record):
                problem = f"{problem} — overgeslagen"
                advice = f"Telt niet mee ({skip_reason(record)}). Rechtsklik om dat terug te draaien."
            values = [problem, self._person_name(record), record.get("Evenement", ""), advice]
            for column, value in enumerate(values):
                item = self._text_item(value, record["_id"])
                if "ongeldig" in normalize(problem) or "zonderhoofdbezoeker" in normalize(problem):
                    item.setBackground(QColor("#fde8e8"))
                elif "dubbele" in normalize(problem):
                    item.setBackground(QColor("#fff3d6"))
                self.quality_table.setItem(row_index, column, item)
        if issues:
            self.quality_scope_label.setText(f"{len(issues)} aandachtspunt(en) gevonden binnen het geopende evenement.")
        else:
            self.quality_scope_label.setText("Geen aandachtspunten gevonden binnen het geopende evenement.")
        tab_index = self.tabs.indexOf(self.quality_tab)
        if tab_index >= 0:
            self.tabs.setTabText(tab_index, f"Gegevenscontrole ({len(issues)})")

    def _duplicate_partners(self, record):
        """Regels die over dezelfde persoon lijken te gaan.

        Zelfde sleutels als de controle in Gegevenscontrole gebruikt: naam met
        geboortedatum, e-mailadres of telefoonnummer.
        """
        def sleutels(other):
            naam = normalize("|".join([
                str(other.get("Voornaam", "")), str(other.get("Tussenvoegsel", "")),
                str(other.get("Achternaam", "")), str(other.get("Geboortedatum", "")),
            ]))
            email = normalize(other.get("Email", ""))
            telefoon = re.sub(r"\D", "", str(other.get("Telefoonnummer", "") or ""))
            gevonden = set()
            if naam.strip("|"):
                gevonden.add(f"naam:{naam}")
            if email:
                gevonden.add(f"mail:{email}")
            if len(telefoon) >= 9:
                gevonden.add(f"tel:{telefoon}")
            return gevonden

        eigen = sleutels(record)
        if not eigen:
            return []
        return [
            other for other in self._filtered_records(include_skipped=True)
            if other is not record and eigen & sleutels(other)
        ]

    def skip_duplicate_registration(self):
        """Laat van een dubbel ingeschreven persoon nog een regel meetellen."""
        record = self._record_from_item(self.quality_table.currentItem())
        if not record:
            QMessageBox.information(self, "Geen regel gekozen", "Selecteer eerst een aandachtspunt.")
            return
        partners = [other for other in self._duplicate_partners(record) if not is_skipped(other)]
        if not partners:
            QMessageBox.information(
                self,
                "Geen dubbele inschrijving",
                f"Er staat geen tweede regel van {self._person_name(record)} in beeld.",
            )
            return
        groep = [record, *partners] if not is_skipped(record) else partners
        blijft = richest_record(groep)
        rest = [other for other in groep if other is not blijft]
        if not rest:
            return
        antwoord = QMessageBox.question(
            self,
            "Dubbele inschrijving overslaan",
            f"{self._person_name(blijft)} staat {len(groep)} keer in de lijst.\n\n"
            f"Een regel blijft meetellen en neemt de aanwezigheid en de ingevulde gegevens van de "
            f"andere over. De {len(rest)} andere regel(s) verdwijnen uit de lijsten, de tellingen en "
            "de exports, maar blijven hier zichtbaar zodat u het kunt terugdraaien.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if antwoord != QMessageBox.StandardButton.Yes:
            return
        for other in rest:
            absorb_duplicate(blijft, other)
        self._mark_dirty()
        self._render_all()
        self.status_label.setText(
            f"{len(rest)} dubbele inschrijving(en) van {self._person_name(blijft)} tellen niet meer mee."
        )

    def include_record_again(self):
        record = self._record_from_item(self.quality_table.currentItem())
        if not record:
            QMessageBox.information(self, "Geen regel gekozen", "Selecteer eerst een aandachtspunt.")
            return
        if not include_again(record):
            QMessageBox.information(
                self, "Telt al mee", f"{self._person_name(record)} telt gewoon mee in de lijsten en tellingen."
            )
            return
        self._mark_dirty()
        self._render_all()
        self.status_label.setText(f"{self._person_name(record)} telt weer mee.")

    def edit_selected_quality_record(self):
        row = self.quality_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen regel gekozen", "Selecteer eerst een aandachtspunt.")
            return
        item = self.quality_table.item(row, 0)
        record = self._record_map().get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        if not record:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Gegevens aanpassen — {self._person_name(record)}")
        _fit_dialog_to_screen(dialog, 660, 720, 520, 380)
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        form = QFormLayout()
        fields = [
            ("Evenement", "Evenement"), ("Voornaam", "Voornaam"),
            ("Tussenvoegsel", "Tussenvoegsel"), ("Achternaam", "Achternaam"),
            ("Telefoonnummer", "Telefoonnummer"), ("Email", "E-mail"),
            ("Geboortedatum", "Geboortedatum"), ("Geboorteplaats", "Geboorteplaats"),
            ("Opleiding", "Opleidingsniveau"), ("Profiel", "Profiel / richting"),
            ("Geslacht", "Geslacht"), ("Identifier", "Registratie-ID"),
            ("GastVan", "Gast van (registratie-ID)"),
        ]
        editors = {}
        for field, label in fields:
            editor = QLineEdit(str(record.get(field, "") or ""))
            editors[field] = editor
            form.addRow(label + ":", editor)
        content_layout.addLayout(form)
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        for field, editor in editors.items():
            record[field] = editor.text().strip()
        self._mark_dirty()
        self._render_all()
        self.status_label.setText(f"Gegevens bijgewerkt voor {self._person_name(record)}.")

    def _event_statistics_snapshot(self, event: dict) -> dict:
        return snapshot_for_event(event, self.records) or {}

    def _grouped_counts(self, records, event_name: str, labeller) -> dict:
        """De vier standen per groep, zodat je ze achteraf kunt uitsplitsen."""
        grouped: dict[str, dict] = {}
        for record in records:
            bucket = grouped.setdefault(
                labeller(record),
                {"aangemeld": 0, "aanwezig": 0, "noshow": 0, "afgemeld": 0},
            )
            bucket["aangemeld"] += 1
            bucket["aanwezig"] += is_present(record, event_name)
            bucket["noshow"] += is_no_show(record, event_name)
            bucket["afgemeld"] += is_cancelled(record, event_name)
        return dict(sorted(grouped.items(), key=lambda item: (-item[1]["aangemeld"], normalize(item[0]))))

    def _capture_event_statistics(self, event: dict) -> bool:
        """Werk de cijfers bij zolang de persoonsgegevens er nog zijn.

        Zolang een evenement niet is opgeschoond blijft de momentopname
        meelopen met latere correcties op de presentie. Zodra de gegevens zijn
        gewist wordt hij bevroren: opnieuw berekenen zou dan op een leeg
        dossier gebeuren en de cijfers definitief vernietigen.
        """
        if not event or event.get("persoonsgegevens_gewist") or event.get("exclude_from_analysis"):
            return False
        visitors = self._event_visitors(event)
        if not visitors:
            return False
        if attendance_counts(visitors, str(event.get("name", "") or ""))[ONBEKEND]:
            return False
        snapshot = self._event_statistics_snapshot(event)
        if event.get("statistiek") == snapshot:
            return False
        event["statistiek"] = snapshot
        return True

    def _refresh_past_event_statistics(self) -> bool:
        """Houd de momentopname bij voor evenementen die geweest zijn."""
        today = date.today()
        changed = False
        for event in self.events:
            event_date = parse_date(event.get("date", ""))
            if event_date and event_date <= today:
                changed = self._capture_event_statistics(event) or changed
        return changed

    def _show_all_values(self) -> bool:
        """Toont het tabblad elke waarde apart, of gaat de staart onder Overig?"""
        return bool(getattr(self, "statistics_show_all", None) and self.statistics_show_all.isChecked())

    def _grouped_value(self, field: str, record: dict, spellings: dict) -> str:
        """De waarde zoals hij geteld wordt, op dezelfde noemer als de kruistabel.

        Opleiding en Profiel komen als vrije tekst uit de aanmeldlijsten. MBO 4,
        mbo-4 en MBO niveau 4 zijn hetzelfde niveau, en Techniek en techniek
        hetzelfde profiel. Telde de grafiek die apart, dan stonden ze als losse
        balken naast elkaar en verdrongen ze samen een echte categorie uit de
        top acht.
        """
        raw = record.get(field, "")
        if field == "Opleiding":
            return education_level(raw)
        if field == "Profiel":
            return profile_label(raw, spellings)
        return str(raw or "").strip() or "Onbekend"

    def _field_counts(self, field: str, limit: int = 8, records=None):
        source = self.records if records is None else records
        spellings: dict = {}
        counts = Counter(self._grouped_value(field, record, spellings) for record in source)
        ordered = sorted(counts.items(), key=lambda item: (-item[1], normalize(item[0])))
        if self._show_all_values() or limit <= 0 or len(ordered) <= limit:
            return ordered
        # Het aantal erbij: zonder dat weet je niet of er twee waarden onder
        # Overig zitten of de helft van je bezoekers.
        rest = ordered[limit:]
        return ordered[:limit] + [(f"Overig ({len(rest)})", sum(value for _, value in rest))]

    def _age_from_text(self, value: str, reference: date | None = None):
        """Leeftijd in jaren, standaard vandaag maar desgewenst op een peildatum.

        Voor een momentopname telt de leeftijd op de evenementdatum: dat is de
        waarde die bewaard blijft wanneer de geboortedatum wordt gewist.
        """
        value = str(value or "").strip()
        reference = reference or date.today()
        for date_format in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                born = datetime.strptime(value, date_format).date()
                age = reference.year - born.year - ((reference.month, reference.day) < (born.month, born.day))
                return age if 0 <= age <= 120 else None
            except ValueError:
                continue
        return None

    def _date_from_text(self, value: str):
        value = str(value or "").strip()
        if not value:
            return None
        for date_format in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(value, date_format).date()
            except ValueError:
                continue
        return None

    def _age_label(self, record: dict, reference: date | None = None) -> str:
        """Leeftijdsgroep van één deelnemer op de peildatum.

        Gebruikt bewust dezelfde indeling als ingeladen bezoekerslijsten; twee
        definities zouden groepen opleveren die in een trend niet vergelijkbaar
        zijn.
        """
        return trend_age_group(self._age_from_text(record.get("Geboortedatum", ""), reference))

    def _dimension_rows(self, labeller, records, limit: int = 8, order=None):
        """Per categorie de aantallen per stand, klaar om horizontaal te lezen.

        Levert (categorie, aangemeld, aanwezig, niet gekomen, afgemeld). Eerder
        gingen dezelfde categorieen drie keer los gesorteerd de export in,
        waardoor je niet kon zien hoeveel van een groep was komen opdagen.
        """
        spellings: dict = {}
        buckets: dict = {}
        for record in records or []:
            label = labeller(record, spellings)
            bucket = buckets.setdefault(label, Counter())
            bucket["aangemeld"] += 1
            bucket[self._scoped_status(record)] += 1
        if order:
            geordend = [(label, buckets[label]) for label in order if label in buckets]
        else:
            geordend = sorted(buckets.items(), key=lambda item: (-item[1]["aangemeld"], normalize(item[0])))
        if not order and not self._show_all_values() and limit > 0 and len(geordend) > limit:
            staart = geordend[limit:]
            samen = Counter()
            for _, bucket in staart:
                samen.update(bucket)
            geordend = geordend[:limit] + [(f"Overig ({len(staart)})", samen)]
        return [
            (label, bucket["aangemeld"], bucket[AANWEZIG], bucket[AFWEZIG], bucket[AFGEMELD])
            for label, bucket in geordend
        ]

    def _registration_counts(self, records=None):
        """Hoeveel deelnemers er via elke aanmeldpagina binnenkwamen."""
        source = self.records if records is None else records
        counts = Counter()
        for record in source:
            for label in registrations(record):
                counts[label] += 1
        return sorted(counts.items(), key=lambda item: (-item[1], normalize(item[0])))

    def _age_counts(self, records=None, reference: date | None = None):
        source = self.records if records is None else records
        labels = list(AGE_GROUPS)
        counts = Counter()
        for record in source:
            age = self._age_from_text(record.get("Geboortedatum", ""), reference)
            if age is None:
                label = "Onbekend"
            elif age < 18:
                label = "Jonger dan 18"
            elif age <= 20:
                label = "18–20"
            elif age <= 24:
                label = "21–24"
            elif age <= 29:
                label = "25–29"
            elif age <= 39:
                label = "30–39"
            else:
                label = "40 en ouder"
            counts[label] += 1
        return [(label, counts[label]) for label in labels if counts[label]]

    def _statistics_scope(self):
        event = self._active_event()
        if event and event.get("exclude_from_analysis"):
            return [], (
                "Dit evenement telt volgens de evenementgegevens niet mee in Statistieken en Trends. "
                "De deelnemers- en presentiegegevens blijven verder beschikbaar."
            )
        incomplete_presence = False
        if event:
            visitors = self._event_visitors(event)
            if not visitors:
                return [], "Statistieken worden beschikbaar zodra een deelnemerslijst is toegevoegd."
            incomplete_presence = bool(
                attendance_counts(visitors, str(event.get("name", "") or ""))[ONBEKEND]
            )
        include_introducees = self.statistics_include_introducees.isChecked()
        presence_filter = str(self.statistics_presence_filter.currentData() or "all")
        scoped_records = self._filtered_records()
        records = scoped_records if include_introducees else [
            record for record in scoped_records if not is_introducee(record)
        ]
        introducees = sum(is_introducee(record) for record in scoped_records)
        presence_notes = {
            AANWEZIG: "alleen bezoekers die aanwezig waren",
            AFWEZIG: "alleen no-shows (aangemeld maar niet gekomen)",
            AFGEMELD: "alleen bezoekers die zich hebben afgemeld",
            ONBEKEND: "alleen bezoekers zonder vastgelegde aanwezigheid",
        }
        if presence_filter in presence_notes:
            records = [
                record for record in records
                if has_status_in_scope(record, self.selected_events, presence_filter)
            ]
            presence_note = presence_notes[presence_filter]
        else:
            presence_note = None
        if include_introducees:
            base_text = f"Grafieken op basis van {len(records)} personen, inclusief {introducees} introducees."
        else:
            base_text = f"Grafieken op basis van {len(records)} reguliere bezoekers; introducees zijn uitgesloten."
        if presence_note:
            base_text += f" Filter: {presence_note}."
        if incomplete_presence:
            base_text += (
                " Aanwezigheid is nog niet voor iedereen geregistreerd; "
                "opkomst- en no-showuitsplitsingen zijn daarom nog onvolledig."
            )
        overgeslagen = sum(1 for record in self._filtered_records(include_skipped=True) if is_skipped(record))
        if overgeslagen:
            base_text += f" {overgeslagen} dubbele inschrijving(en) tellen niet mee."
        return records, base_text

    def _historical_statistics_selection(self):
        event = self._active_event() or {}
        base = historical_scope(event)
        has_regular = isinstance((event.get("statistiek") or {}).get("regulier"), dict)
        self.statistics_include_introducees.setEnabled(not base or not base.get("introducees") or has_regular)
        if base and base.get("introducees") and not has_regular:
            self.statistics_include_introducees.blockSignals(True)
            self.statistics_include_introducees.setChecked(True)
            self.statistics_include_introducees.blockSignals(False)
        return historical_scope(event, self.statistics_include_introducees.isChecked()), str(
            self.statistics_presence_filter.currentData() or "all"
        )

    def _update_historical_statistics(self):
        snapshot, status = self._historical_statistics_selection()
        note = "Geanonimiseerd — persoonsgegevens verwijderd; historische statistieken behouden."
        if snapshot is None:
            self.statistics_scope_label.setText(
                note + " Voor dit oude evenement zijn geen statistieken vastgelegd; ze zijn niet uit gewiste gegevens te herstellen."
            )
            for card in self.statistics_cards.values():
                card.chart.set_data([])
            self.statistics_cards["listing"].hide()
            self._update_historical_crosstab(None)
            return
        quantity = bucket_value(snapshot, status)
        if quantity is not None:
            note += f" {ATTENDANCE_LABELS.get(status, 'Alle statussen')}: {quantity}."
        if status != "all" and any(
            historical_distribution(snapshot, dimension, status) is None
            for dimension in ("Opleidingsniveau", "Profiel", "Geslacht", "Leeftijdsgroep")
        ):
            note += " Deze oude momentopname bevat geen uitsplitsing per aanwezigheidsstatus; de totale verdelingen blijven wel beschikbaar."
        if snapshot.get("onbekend"):
            note += f" {snapshot['onbekend']} aanwezigheid(sstatussen) zijn onbekend en niet als no-show geteld."
        self.statistics_scope_label.setText(note)
        mapping = (("education", "Opleidingsniveau", 8), ("profile", "Profiel", 8),
                   ("gender", "Geslacht", 10), ("age", "Leeftijdsgroep", 0))
        for card_key, dimension, limit in mapping:
            values = historical_distribution(snapshot, dimension, status) or []
            if not self._show_all_values() and limit and len(values) > limit:
                tail = values[limit:]
                values = values[:limit] + [(f"Overig ({len(tail)})", sum(value for _, value in tail))]
            if card_key == "age":
                values.sort(key=lambda item: AGE_GROUPS.index(item[0]) if item[0] in AGE_GROUPS else len(AGE_GROUPS))
            self.statistics_cards[card_key].chart.set_data(values)
        self.statistics_cards["listing"].chart.set_data([])
        self.statistics_cards["listing"].hide()
        data = historical_crosstab(snapshot, status)
        if data is not None and not self._show_all_values():
            data = education_collapse(data, CROSSTAB_COLUMN_LIMIT)
        self._update_historical_crosstab(data)

    def _update_statistics(self):
        if not hasattr(self, "statistics_cards"):
            return
        if self._event_is_anonymized(self._active_event() or {}):
            self._update_historical_statistics()
            return
        self.statistics_include_introducees.setEnabled(True)
        records, scope_text = self._statistics_scope()
        self.statistics_scope_label.setText(scope_text)
        self.statistics_cards["education"].chart.set_data(self._field_counts("Opleiding", records=records))
        self.statistics_cards["profile"].chart.set_data(self._field_counts("Profiel", records=records))
        self.statistics_cards["gender"].chart.set_data(self._field_counts("Geslacht", limit=10, records=records))
        self.statistics_cards["age"].chart.set_data(self._age_counts(records))
        # Zonder samengevoegd evenement zegt deze grafiek niets; dan is hij weg
        # in plaats van leeg.
        inschrijvingen = self._registration_counts(records)
        self.statistics_cards["listing"].setVisible(bool(inschrijvingen))
        self.statistics_cards["listing"].chart.set_data(inschrijvingen)
        self._update_crosstab(records)

    def _update_historical_crosstab(self, data):
        self._historical_crosstab_data = data
        try:
            self._update_crosstab([])
        finally:
            self._historical_crosstab_data = _NO_HISTORICAL_CROSSTAB

    def _update_crosstab(self, records):
        """Vul de kruistabel opleidingsniveau x profiel: als heatmap en als tabel."""
        if not hasattr(self, "crosstab_table"):
            return
        table = self.crosstab_table
        historical = getattr(self, "_historical_crosstab_data", _NO_HISTORICAL_CROSSTAB)
        data = historical if historical is not _NO_HISTORICAL_CROSSTAB else self._crosstab_data(records)
        if data is None:
            self.crosstab_heatmap.set_data({}, self._crosstab_value_mode())
            table.setRowCount(0)
            table.setColumnCount(0)
            self.crosstab_note.setText("Geanonimiseerd — deze kruistabel is niet vastgelegd in de historische gegevens.")
            return
        rows, columns = data["rows"], data["columns"]
        grafiek = self._crosstab_view() == "grafiek"
        self.crosstab_stack.setCurrentIndex(0 if grafiek else 1)
        # De keuze tussen aantallen en percentage kleurt de heatmap; de tabel
        # is er juist voor de exacte getallen en blijft daarop staan.
        self.crosstab_value_picker.setEnabled(grafiek)
        if not rows:
            self.crosstab_heatmap.set_data({}, self._crosstab_value_mode())
            table.setRowCount(0)
            table.setColumnCount(0)
            self.crosstab_note.setText("Nog geen deelnemers met een opleidingsniveau.")
            return

        self.crosstab_heatmap.set_data(data, self._crosstab_value_mode())

        table.setColumnCount(len(columns) + 2)
        table.setHorizontalHeaderLabels(["Opleidingsniveau", *columns, "Totaal"])
        table.setRowCount(len(rows) + 1)

        def cell(text, bold=False, dim=False):
            item = QTableWidgetItem(str(text))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if bold:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            if dim and str(text) == "0":
                item.setForeground(QColor("#8899ad"))
            return item

        for row_index, level in enumerate(rows):
            table.setItem(row_index, 0, cell(level, bold=True))
            for column_index, profile in enumerate(columns, start=1):
                value = data["counts"].get((level, profile), 0)
                table.setItem(row_index, column_index, cell(value, dim=True))
            table.setItem(row_index, len(columns) + 1, cell(data["row_totals"][level], bold=True))

        total_row = len(rows)
        table.setItem(total_row, 0, cell("Totaal", bold=True))
        for column_index, profile in enumerate(columns, start=1):
            table.setItem(total_row, column_index, cell(data["column_totals"][profile], bold=True))
        table.setItem(total_row, len(columns) + 1, cell(data["total"], bold=True))
        table.resizeColumnsToContents()

        # Laat zien wat de weergave met de aangeleverde waarden doet: welke
        # profielen zijn gebundeld en welke schrijfwijzen zijn samengevoegd.
        notes = []
        bundled = data.get("gebundeld") or []
        if bundled:
            notes.append(f"Overig ({len(bundled)}) bundelt: {', '.join(bundled)}")
        merged = data["merged"]
        if merged:
            samenvatting = "; ".join(
                f"{level}: {', '.join(values)}" for level, values in sorted(merged.items())
            )
            notes.append(f"Samengevoegde schrijfwijzen — {samenvatting}")
        self.crosstab_note.setText("\n".join(notes))

    def _app_data_root(self):
        return application_data_root()

    def _recovery_path(self):
        recovery_dir = self._app_data_root() / "Herstel"
        recovery_dir.mkdir(parents=True, exist_ok=True)
        return recovery_dir / "autosave.bvp"

    def _project_payload(self, autosave: bool = False):
        payload = {
            "format": "DCPL Event Management Tool",
            # 11: aanwezigheid wordt per evenement bewaard in plaats van als
            # één boolean per persoon.
            # 12: per evenement staat er een stand in plaats van een ja/nee:
            # aanwezig, afwezig, afgemeld of onbekend. Daarmee is 'niet gekomen'
            # eindelijk te onderscheiden van 'we weten het niet'. Oudere
            # bestanden migreren bij openen.
            "version": 12,
            "visible_fields_by_view": self.visible_fields_by_view,
            "selected_events": sorted(self.selected_events, key=normalize),
            "profile": self.profile,
            "task_templates": self.task_templates,
            "events": self.events,
            "records": self.records,
        }
        if autosave:
            payload["_autosave"] = {
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "source_path": str(self.project_path or ""),
            }
        return payload

    def _write_bytes_atomic(self, target: Path, data: bytes):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _write_payload_atomic(self, target: Path, payload: dict):
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self._write_bytes_atomic(target, data)

    def _backup_directory(self, source_path: Path | None = None):
        raw_source = source_path or self.project_path
        if not raw_source:
            return self._app_data_root() / "Back-ups" / "onbekend"
        source = Path(raw_source)
        identity = os.path.normcase(str(source.expanduser().resolve(strict=False)))
        digest = hashlib.sha256(identity.encode("utf-8", errors="replace")).hexdigest()[:16]
        return self._app_data_root() / "Back-ups" / digest

    def _backup_files(self, source_path: Path | None = None):
        directory = self._backup_directory(source_path)
        if not directory.is_dir():
            return []
        return sorted(
            (path for path in directory.glob("*.bvp") if path.is_file()),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )

    def _create_backup(self, source_path: Path | None = None):
        raw_source = source_path or self.project_path
        if not self._backups_enabled() or not raw_source:
            return None
        source = Path(raw_source)
        if not source.is_file():
            return None
        try:
            if source.stat().st_size <= 0:
                return None
            json.loads(source.read_text(encoding="utf-8"))
            directory = self._backup_directory(source)
            directory.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            target = directory / f"{source.stem} - {stamp}.bvp"
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
            try:
                shutil.copy2(source, temporary)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            for old_backup in self._backup_files(source)[self._backup_count():]:
                old_backup.unlink(missing_ok=True)
            return target
        except Exception:
            self._write_error_log("Reservekopie maken", traceback.format_exc())
            return None

    def _remove_recovery_file(self, force: bool = False):
        try:
            recovery_path = self._recovery_path()
            if recovery_path.is_file() and not force:
                ignored_mtime = int(self.settings.value("ignored_autosave_mtime_ns", 0) or 0)
                if ignored_mtime == recovery_path.stat().st_mtime_ns:
                    return
            recovery_path.unlink(missing_ok=True)
            self.settings.remove("ignored_autosave_mtime_ns")
        except OSError:
            self._write_error_log("Herstelbestand verwijderen", traceback.format_exc())

    def _set_clean(self):
        self.dirty = False
        self.autosave_timer.stop()
        if self.windowTitle().endswith(" *"):
            self.setWindowTitle(self.windowTitle()[:-2])

    def _schedule_autosave(self):
        if self._autosave_enabled() and self.dirty and not self._autosave_in_progress:
            self.autosave_timer.start(self._autosave_delay_seconds() * 1000)

    def _perform_autosave(self):
        if not self.dirty or not self._autosave_enabled() or self._autosave_in_progress:
            return
        self._autosave_in_progress = True
        try:
            recovery_path = self._recovery_path()
            self._write_payload_atomic(recovery_path, self._project_payload(autosave=True))
            if self.project_path:
                self._create_backup(self.project_path)
                self._write_payload_atomic(self.project_path, self._project_payload())
                self._remove_recovery_file(force=True)
                self._set_clean()
                self._remember_project_path(self.project_path)
                self.setWindowTitle(APP_NAME)
                message = f"Automatisch opgeslagen om {datetime.now().strftime('%H:%M:%S')}"
            else:
                message = f"Lokale herstelkopie bijgewerkt om {datetime.now().strftime('%H:%M:%S')}"
            self.status_label.setStyleSheet("")
            self.status_label.setText(message)
            self._autosave_error_reported = False
        except Exception as exc:
            self.status_label.setStyleSheet("color: #b42318; font-weight: 600;")
            self.status_label.setText("Automatisch opslaan mislukt — uw wijzigingen staan nog open.")
            self._write_error_log("Automatisch opslaan", traceback.format_exc())
            if not self._autosave_error_reported:
                self._autosave_error_reported = True
                QMessageBox.warning(
                    self,
                    "Automatisch opslaan mislukt",
                    f"EventHub kon de wijzigingen niet automatisch opslaan. Gebruik voorlopig de knop Opslaan.\n\n{exc}",
                )
        finally:
            self._autosave_in_progress = False

    def _mark_dirty(self):
        self.dirty = True
        suffix = " *"
        if not self.windowTitle().endswith(suffix):
            self.setWindowTitle(self.windowTitle() + suffix)
        self._schedule_autosave()

    def _record_from_item(self, item: QTableWidgetItem):
        return self._record_map().get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _participant_changed(self, item: QTableWidgetItem):
        if self.loading_tables:
            return
        record = self._record_from_item(item)
        if not record:
            return
        participant_fields = self.visible_fields_by_view["participants"]
        if item.column() < 0 or item.column() >= len(participant_fields):
            return
        field = participant_fields[item.column()]
        if field not in EDITABLE_VISITOR_FIELDS:
            return
        record[field] = item.text().strip()
        self._mark_dirty()
        self._render_all()

    def _callback_changed(self, item: QTableWidgetItem):
        # After sales is edited from the contact panel; the person table is read-only.
        return

    def _presence_changed(self, item: QTableWidgetItem):
        """Een klik op het vinkje registreert direct of iemand langs is geweest."""
        if self.loading_tables or self._presence_registration_locked():
            return
        presence_fields = self.visible_fields_by_view["presence"]
        if item.column() != len(presence_fields):
            return
        record = self._record_from_item(item)
        if not record:
            return
        status = (
            AANWEZIG
            if item.checkState() == Qt.CheckState.Checked
            else ONBEKEND
        )
        if self._scoped_status(record) == status:
            return
        for target in self._presence_targets(record):
            set_attendance(record, target, status)
        self._set_presence_save_pending(True)
        self._mark_dirty()
        self._refresh_presence_status_item(item, status)
        self.status_label.setText(
            f"{self._person_name(record)}: {ATTENDANCE_LABELS[status].lower()}."
        )

    def _refresh_presence_status_item(self, item: QTableWidgetItem, status: str):
        """Werk één statuscel bij zonder alle schermen opnieuw op te bouwen."""
        previous_loading = self.loading_tables
        self.loading_tables = True
        try:
            item.setText(ATTENDANCE_LABELS.get(status, ATTENDANCE_LABELS[ONBEKEND]))
            item.setCheckState(
                Qt.CheckState.Checked if status == AANWEZIG else Qt.CheckState.Unchecked
            )
            item.setForeground(QColor(self.PRESENCE_COLOURS.get(status, "#7b6d82")))
        finally:
            self.loading_tables = previous_loading
        self._presence_render_signature = None

    def _set_presence_save_pending(self, pending: bool):
        self.presence_changes_pending = pending
        if hasattr(self, "presence_save_button"):
            self.presence_save_button.setVisible(
                pending and not self._presence_registration_locked()
            )

    def _presence_registration_event(self):
        if hasattr(self, "event_control_event_combo"):
            return self._combo_event(self.event_control_event_combo)
        return self._active_event()

    def _presence_registration_locked(self, event=None) -> bool:
        event = event or self._presence_registration_event()
        event_id = str(event.get("id", "") or "") if event else ""
        if not event_id:
            return False
        return any(
            window is not None
            and str(getattr(window, "linked_event_id", "") or "") == event_id
            and getattr(window, "server_thread", None) is not None
            for window in self._live_server_windows
        )

    def _update_presence_registration_availability(self):
        if not hasattr(self, "access_table"):
            return
        has_event = self._event_control_selected_event() is not None
        locked = self._presence_registration_locked()
        self.access_table.setEnabled(has_event and not locked)
        if hasattr(self, "event_control_tabs"):
            self.event_control_tabs.setEnabled(has_event)
        if hasattr(self, "event_control_context_hint"):
            self.event_control_context_hint.setVisible(not has_event)
        if hasattr(self, "presence_live_lock_label"):
            self.presence_live_lock_label.setVisible(locked)
        if hasattr(self, "presence_save_button"):
            self.presence_save_button.setVisible(
                has_event and self.presence_changes_pending and not locked
            )

    def _update_after_sales_availability(self):
        """Maak duidelijk dat After sales pas met een gekozen evenement werkt."""
        if not hasattr(self, "after_sales_event_combo"):
            return
        has_event = self._combo_event(self.after_sales_event_combo) is not None
        if hasattr(self, "after_sales_context_hint"):
            self.after_sales_context_hint.setVisible(not has_event)
        for naam in (
            "callback_table",
            "callback_search_box",
            "callback_status_filter",
            "select_all_callbacks_button",
            "select_visible_callbacks_button",
            "whatsapp_queue_button",
        ):
            widget = getattr(self, naam, None)
            if widget is not None:
                widget.setEnabled(has_event)
        for naam in ("after_sales_total", "after_sales_open", "after_sales_followup", "after_sales_done"):
            summary = getattr(self, naam, None)
            if summary:
                summary[0].setEnabled(has_event)

    def _finish_presence_registration(self, _checked=False, *, event=None, confirm=True):
        event = event or self._presence_registration_event()
        if self._presence_registration_locked(event):
            return False
        event_name = str(event.get("name", "") or "") if event else ""
        records = self._event_visitors(event) if event else []
        counts = attendance_counts(records, event_name) if event_name else {
            AANWEZIG: 0, AFWEZIG: 0, AFGEMELD: 0, ONBEKEND: 0,
        }
        unknown_count = counts[ONBEKEND]
        if confirm and unknown_count:
            answer = QMessageBox.warning(
                self,
                "Registratie afronden?",
                f"Voor '{event_name}' zijn {counts[AANWEZIG]} deelnemer(s) aanwezig, "
                f"{counts[AFGEMELD]} afgemeld en {counts[AFWEZIG]} afwezig.\n\n"
                f"De {unknown_count} nog onbeoordeelde deelnemer(s) worden bij het afronden "
                "als afwezig vastgelegd. Wilt u doorgaan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        absent_count = 0
        if event_name:
            for record in records:
                # Alleen de nog niet beoordeelde regels afronden. Expliciete
                # statussen (Aanwezig, Afgemeld of Afwezig) blijven staan.
                if attendance_status(record, event_name) == ONBEKEND:
                    absent_count += int(set_attendance(record, event_name, AFWEZIG))
        if absent_count:
            self._mark_dirty()
            current = self._presence_registration_event()
            if current and str(current.get("id", "")) == str(event.get("id", "")):
                self._render_event_control_scope()
        if self.save_project():
            self._set_presence_save_pending(False)
            suffix = (
                f" {absent_count} niet-beoordeelde deelnemer(s) zijn als afwezig vastgelegd."
                if absent_count else ""
            )
            self.status_label.setText(f"Aanwezigheidsregistratie afgerond.{suffix}")
            return True
        return False

    def _apply_callback_status_marker(self, row_index: int, record: dict):
        """Toon de contactstatus als gekleurde stip vooraan de rij."""
        item = self.callback_table.item(row_index, 0)
        if item is None:
            return
        status = callback_status(record)
        item.setIcon(callback_status_icon(status))
        item.setData(Qt.ItemDataRole.ToolTipRole, f"Contactstatus: {status}")

    def _refresh_callback_status_marker(self, record_id: str):
        record = self._record_map().get(record_id)
        if not record:
            return
        for row in range(self.callback_table.rowCount()):
            item = self.callback_table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == record_id:
                self._apply_callback_status_marker(row, record)

    def _callback_status_changed(self, record_id: str, status: str):
        if self.loading_tables:
            return
        record = self._record_map().get(record_id)
        if not record or status not in CALLBACK_STATUSES or callback_status(record) == status:
            return
        record["Terugbelstatus"] = status
        record["Teruggebeld"] = status in CALLBACK_DONE_STATUSES
        if status != "Nog bellen" and not str(record.get("LaatsteContact", "")).strip():
            record["LaatsteContact"] = date.today().strftime("%d-%m-%Y")
        self._mark_dirty()
        self._update_summary()
        self._refresh_callback_status_marker(record_id)
        self._filter_callbacks()
        self._update_callback_detail_panel()

    def _presence_targets(self, record):
        """Aanwezigheid hoort bij één evenement.

        Staan er meerdere in beeld, dan is er geen eenduidig doel en gelden
        alle evenementen van deze bezoeker die nu in de selectie zitten.
        """
        return [
            name for name in record_events(record)
            if not self.selected_events or name in self.selected_events
        ]

    def _scoped_status(self, record) -> str:
        """De stand zoals hij voor de huidige selectie geldt.

        Bij meerdere evenementen in beeld wint de sterkste uitspraak: wie
        ergens aanwezig was, was aanwezig.
        """
        statuses = {attendance_status(record, name) for name in self._presence_targets(record)}
        for status in (AANWEZIG, AFWEZIG, AFGEMELD):
            if status in statuses:
                return status
        return ONBEKEND

    def _set_presence_status(self, status: str):
        if self._presence_registration_locked():
            return
        current_item = self.access_table.currentItem()
        record = self._record_from_item(current_item)
        if not record:
            QMessageBox.information(self, "Geen deelnemer gekozen", "Selecteer eerst een deelnemer.")
            return
        for target in self._presence_targets(record):
            set_attendance(record, target, status)
        self._set_presence_save_pending(True)
        self._mark_dirty()
        status_item = self.access_table.item(
            current_item.row(), len(self.visible_fields_by_view["presence"])
        )
        if status_item:
            self._refresh_presence_status_item(status_item, status)
        self.status_label.setText(
            f"{self._person_name(record)}: {ATTENDANCE_LABELS[status].lower()}."
        )

    def _filter_participants(self, *_):
        if not hasattr(self, "participant_include_introducees"):
            return
        include_introducees = self.participant_include_introducees.isChecked()
        needle = normalize(self.participant_search_box.text()) if hasattr(self, "participant_search_box") else ""
        records_by_id = self._record_map()

        for row in range(self.participant_table.rowCount()):
            item = self.participant_table.item(row, 0)
            record = records_by_id.get(item.data(Qt.ItemDataRole.UserRole)) if item else None
            hidden_for_type = bool(record) and is_introducee(record) and not include_introducees
            values = []
            for column in range(self.participant_table.columnCount()):
                cell = self.participant_table.item(row, column)
                if cell:
                    values.append(cell.text())
            hidden_for_search = bool(needle) and needle not in normalize(" ".join(values))
            self.participant_table.setRowHidden(
                row, hidden_for_type or hidden_for_search
            )
        self._update_participant_selection_label()

    def _participant_selection_changed(self):
        self._update_participant_selection_label()

    def _update_participant_selection_label(self):
        if not hasattr(self, "participant_selection_label"):
            return
        rows = {index.row() for index in self.participant_table.selectionModel().selectedRows()}
        self.participant_selection_label.setText(f"{len(rows)} geselecteerd")

    def _filter_callbacks(self, *_):
        if not hasattr(self, "callback_status_filter"):
            return
        needle = normalize(self.callback_search_box.text())
        wanted_status = self.callback_status_filter.currentText()
        records_by_id = self._record_map()
        for row in range(self.callback_table.rowCount()):
            values = []
            record_item = self.callback_table.item(row, 0)
            record = records_by_id.get(record_item.data(Qt.ItemDataRole.UserRole)) if record_item else None
            for column in range(self.callback_table.columnCount()):
                item = self.callback_table.item(row, column)
                if item:
                    values.append(item.text())
            status = callback_status(record) if record else ""
            if record:
                values.extend([
                    str(record.get("Telefoonnummer", "") or ""),
                    str(record.get("Opmerkingen", "") or ""),
                    str(record.get("LaatsteContact", "") or ""),
                    str(record.get("TerugbellenOp", "") or ""),
                ])
            matches_query = not needle or needle in normalize(" ".join(values))
            followup_planned = bool(record and str(record.get("TerugbellenOp", "") or "").strip())
            if wanted_status == "Alle statussen":
                matches_status = True
            elif wanted_status == "Actie nodig":
                matches_status = status not in CALLBACK_DONE_STATUSES or followup_planned
            elif wanted_status == "Opvolging gepland":
                matches_status = followup_planned
            elif wanted_status == "Afgehandeld":
                matches_status = status in CALLBACK_DONE_STATUSES and not followup_planned
            else:
                matches_status = status == wanted_status
            self.callback_table.setRowHidden(row, not (matches_query and matches_status))
        self._update_callback_selection_label()
        self._update_callback_detail_panel()

    def eventFilter(self, watched, event):
        if (
            hasattr(self, "access_table")
            and watched in (self.access_table, self.access_table.viewport())
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Space
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
            and not self._presence_registration_locked()
        ):
            row = self.access_table.currentRow()
            status_column = len(self.visible_fields_by_view["presence"])
            item = self.access_table.item(row, status_column) if row >= 0 else None
            if item:
                item.setCheckState(
                    Qt.CheckState.Unchecked
                    if item.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                return True
        if (
            hasattr(self, "sidebar_logo")
            and watched is self.sidebar_logo
            and event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self.show_home()
            return True
        if (
            hasattr(self, "participant_tab")
            and watched is self.participant_tab
            and event.type() == QEvent.Type.Resize
        ):
            self._update_participant_table_width()
        if (
            hasattr(self, "participant_table")
            and watched is self.participant_table.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            modifiers = event.modifiers()
            multi_modifier = modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
            if not multi_modifier:
                index = self.participant_table.indexAt(event.position().toPoint())
                if index.isValid():
                    selected_rows = {selected.row() for selected in self.participant_table.selectionModel().selectedRows()}
                    if index.row() in selected_rows:
                        self.participant_table.clearSelection()
                        return True
        if (
            hasattr(self, "callback_table")
            and watched is self.callback_table.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            modifiers = event.modifiers()
            multi_modifier = modifiers & (
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
            )
            if not multi_modifier:
                index = self.callback_table.indexAt(event.position().toPoint())
                if index.isValid():
                    selected_rows = {
                        selected.row()
                        for selected in self.callback_table.selectionModel().selectedRows()
                    }
                    if index.row() in selected_rows:
                        self.callback_table.clearSelection()
                        return True
        return super().eventFilter(watched, event)

    def _selected_callback_records(self):
        records_by_id = self._record_map()
        selected = []
        seen = set()
        rows = sorted({index.row() for index in self.callback_table.selectionModel().selectedRows()})
        for row in rows:
            item = self.callback_table.item(row, 0)
            if not item:
                continue
            record_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            record = records_by_id.get(record_id)
            if record and record_id not in seen and not is_introducee(record):
                selected.append(record)
                seen.add(record_id)
        return selected

    def _callback_selection_changed(self):
        if self.loading_tables:
            return
        self._update_callback_selection_label()
        self._update_callback_detail_panel()

    def _update_callback_selection_label(self):
        if not hasattr(self, "callback_selection_label"):
            return
        count = len(self._selected_callback_records())
        self.callback_selection_label.setText(
            f"{count} kandidaat geselecteerd" if count == 1 else f"{count} kandidaten geselecteerd"
        )
        if hasattr(self, "whatsapp_queue_button"):
            self.whatsapp_queue_button.setEnabled(count > 0)
        if hasattr(self, "select_all_callbacks_button"):
            selectable_rows = [row for row in range(self.callback_table.rowCount())]
            selected_rows = {index.row() for index in self.callback_table.selectionModel().selectedRows()}
            all_selected = bool(selectable_rows) and all(row in selected_rows for row in selectable_rows)
            self.select_all_callbacks_button.setText("Alles deselecteren" if all_selected else "Alles selecteren")

    def _select_callback_rows(self, rows, clear=True):
        selection_model = self.callback_table.selectionModel()
        if clear:
            selection_model.clearSelection()
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        for row in rows:
            if self.callback_table.columnCount():
                selection_model.select(self.callback_table.model().index(row, 0), flags)
        self._update_callback_selection_label()
        self._update_callback_detail_panel()

    def _select_visible_callbacks(self):
        rows = [row for row in range(self.callback_table.rowCount()) if not self.callback_table.isRowHidden(row)]
        self._select_callback_rows(rows)

    def _toggle_all_callbacks(self):
        selected_rows = {index.row() for index in self.callback_table.selectionModel().selectedRows()}
        rows = list(range(self.callback_table.rowCount()))
        if rows and all(row in selected_rows for row in rows):
            self.callback_table.clearSelection()
            self._update_callback_selection_label()
            self._update_callback_detail_panel()
        else:
            self._select_callback_rows(rows)

    def _update_callback_detail_panel(self):
        if not hasattr(self, "callback_detail_name"):
            return
        records = self._selected_callback_records()
        # Geen selectie: verberg het volledige rechterpaneel. QSplitter geeft de
        # vrijgekomen ruimte dan automatisch terug aan de kandidatentabel.
        has_selection = bool(records)
        if self.callback_detail_card.isVisible() != has_selection:
            self.callback_detail_card.setVisible(has_selection)
            if has_selection:
                saved_state = self.settings.value("after_sales_workspace_splitter")
                if saved_state:
                    try:
                        self.callback_workspace_splitter.restoreState(saved_state)
                    except (TypeError, ValueError):
                        self.callback_workspace_splitter.setSizes([760, 380])
                else:
                    self.callback_workspace_splitter.setSizes([760, 380])

        self._callback_detail_loading = True
        try:
            if len(records) != 1:
                self._callback_detail_record_id = None
                if records:
                    self.callback_detail_name.setText(f"{len(records)} kandidaten geselecteerd")
                    self.callback_detail_person.setText("Gebruik WhatsApp-berichten voor de huidige selectie. Selecteer één kandidaat om contact en opvolging te bewerken.")
                else:
                    self.callback_detail_name.setText("Selecteer een kandidaat")
                    self.callback_detail_person.setText("Klik op een rij om de contactgegevens en opvolging te bekijken.")
                for widget in (self.callback_detail_status, self.callback_detail_followup, self.callback_detail_notes):
                    widget.setEnabled(False)
                self.callback_detail_status.setCurrentIndex(0)
                self.callback_detail_last_contact.setText("—")
                self.callback_detail_followup.clear()
                self.callback_detail_notes.clear()
                self.callback_detail_whatsapp.setText("—")
                return
            record = records[0]
            self._callback_detail_record_id = record.get("_id")
            self.callback_detail_name.setText(self._person_name(record))
            person_bits = [str(record.get("Telefoonnummer", "") or "").strip()]
            education = str(record.get("Opleidingsniveau", "") or "").strip()
            profile = str(record.get("Profiel", "") or record.get("Opleidingsrichting", "") or "").strip()
            person_bits.extend(bit for bit in (education, profile) if bit)
            self.callback_detail_person.setText("  •  ".join(bit for bit in person_bits if bit) or "Geen aanvullende persoonsgegevens")
            for widget in (self.callback_detail_status, self.callback_detail_followup, self.callback_detail_notes):
                widget.setEnabled(True)
            self.callback_detail_status.setCurrentText(callback_status(record))
            self.callback_detail_last_contact.setText(str(record.get("LaatsteContact", "") or "Nog geen contact"))
            self.callback_detail_followup.setText(str(record.get("TerugbellenOp", "") or ""))
            self.callback_detail_notes.setPlainText(str(record.get("Opmerkingen", "") or ""))
            whatsapp = str(record.get("WhatsAppStatus", "Nog te sturen") or "Nog te sturen")
            sent = str(record.get("WhatsAppVerzondenOp", "") or "").strip()
            self.callback_detail_whatsapp.setText(f"{whatsapp}{' · ' + sent if sent else ''}")
        finally:
            self._callback_detail_loading = False

    def _callback_detail_status_changed(self, status):
        if self._callback_detail_loading or not self._callback_detail_record_id:
            return
        self._callback_status_changed(str(self._callback_detail_record_id), status)

    def _save_callback_detail(self):
        if self._callback_detail_loading or not self._callback_detail_record_id:
            return
        record = self._record_map().get(str(self._callback_detail_record_id))
        if not record:
            return
        record["TerugbellenOp"] = self.callback_detail_followup.text().strip()
        record["Opmerkingen"] = self.callback_detail_notes.toPlainText()
        self._mark_dirty()
        self._update_summary()
        self._filter_callbacks()

    def _callback_detail_notes_changed(self):
        if self._callback_detail_loading or not self._callback_detail_record_id:
            return
        record = self._record_map().get(str(self._callback_detail_record_id))
        if record is not None:
            record["Opmerkingen"] = self.callback_detail_notes.toPlainText()
            self._mark_dirty()

    def _send_whatsapp_for_callback_row(self, row, _column=0):
        """Open de WhatsApp-flow direct voor de kandidaat waarop dubbel is geklikt."""
        if row < 0 or row >= self.callback_table.rowCount():
            return
        self._select_callback_rows([row], clear=True)
        self._start_whatsapp_queue()

    def _start_whatsapp_queue(self):
        event = self._active_event()
        if not event:
            QMessageBox.information(self, "Geen evenement geopend", "Open eerst het evenement waarvoor u after sales wilt uitvoeren.")
            return
        selected = self._selected_callback_records()
        if not selected:
            QMessageBox.information(self, "Geen kandidaten gekozen", "Selecteer in After sales eerst één of meer kandidaten.")
            return
        valid = [record for record in selected if _whatsapp_phone(record.get("Telefoonnummer", ""))]
        invalid = [record for record in selected if record not in valid]
        if invalid:
            names = "\n".join(f"• {self._person_name(record)}" for record in invalid[:12])
            extra = f"\n• … en nog {len(invalid) - 12}" if len(invalid) > 12 else ""
            QMessageBox.information(
                self,
                "Telefoonnummers overgeslagen",
                f"{len(invalid)} kandidaat/kandidaten hebben geen bruikbaar telefoonnummer en worden overgeslagen:\n\n"
                f"{names}{extra}",
            )
        if not valid:
            return
        dialog = WhatsAppQueueDialog(valid, event, self.profile, self,
                                     templates=load_whatsapp_templates(self.settings))
        dialog.exec()
        if dialog.changed:
            self._mark_dirty()
            self._render_all()
            self.status_label.setText("De WhatsApp-wachtrij en het after-sales-sjabloon zijn bijgewerkt.")

    def _statistics_chart_type_changed(self, chart_key: str, chart_type: str):
        allowed = {value for _, value in STATISTICS_CHART_TYPES}
        if chart_key in STATISTICS_CHART_DEFAULTS and chart_type in allowed:
            self.settings.setValue(f"statistics_chart_type/{chart_key}", chart_type)

    def _filter_presence(self, query: str):
        needle = normalize(query)
        field_count = len(self.visible_fields_by_view["presence"])
        for row in range(self.access_table.rowCount()):
            haystack = " ".join(self.access_table.item(row, col).text() for col in range(field_count))
            self.access_table.setRowHidden(row, bool(needle) and needle not in normalize(haystack))

    def _confirm_discard(self):
        if not self.dirty:
            return True
        result = QMessageBox.question(
            self,
            "Wijzigingen opslaan?",
            "Er zijn nog niet-opgeslagen wijzigingen. Wilt u deze eerst opslaan?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Cancel:
            return False
        if result == QMessageBox.StandardButton.Save:
            return self.save_project()
        self.autosave_timer.stop()
        self._remove_recovery_file(force=True)
        return True

    def new_project(self):
        """Choose an event source, then open the relevant creation flow."""
        try:
            source_dialog = NewEventSourceDialog(self, templates_available=bool(self.project_templates))
            if source_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            if source_dialog.choice == "rudder":
                self.import_rudder_event(event={})
                return
            if source_dialog.choice == "rudder_bulk":
                self.import_rudder_events_bulk()
                return
            template_only = source_dialog.choice == "template"
            dialog = NewProjectDialog(
                self,
                project_templates=self.project_templates if template_only else [],
                template_only=template_only,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            values = dialog.value()
            template = dialog.selected_template()
            if template and isinstance(template.get("event"), dict):
                source = event_from_template(template)
                template_type = source.get("event_type", "Meeloopdag")
                source["id"] = ""
                source["attachments"] = []
                source["evaluation"] = {}
            else:
                source = empty_event(values["name"], self.task_templates, values["event_type"])
                template_type = values["event_type"]
            source.update(values)
            source["status"] = "In voorbereiding"
            source["tasks"] = [
                prepare_task({**task, "id": "", "done": False, "completed_on": ""})
                for task in source.get("tasks", [])
                if template or task_allowed_for_event_type(task, values["event_type"])
            ]
            if not template and template_type != values["event_type"] and values["event_type"] != "Online voorlichting":
                existing_tasks = {normalize(task.get("title", "")) for task in source["tasks"]}
                for task in tasks_from_templates(self.task_templates, values["event_type"]):
                    if normalize(task.get("title", "")) not in existing_tasks:
                        source["tasks"].append(task)
            project_name = event_name_with_date(values["name"], values["date"])
            source["name"] = project_name
            if self._event_by_name(project_name):
                base_name = project_name
                sequence = 2
                while self._event_by_name(project_name):
                    project_name = f"{base_name} ({sequence})"
                    sequence += 1
                source["name"] = project_name
            event = prepare_event(source, self.task_templates)
            self.events.append(event)
            self._mark_dirty()
            self._add_recent_activity(f"Evenement aangemaakt · {event['name']}")
            self.open_event(event)
            self.status_label.setText(f"Evenement aangemaakt en geopend: {event['name']}.")
        except Exception as exc:
            self._show_runtime_error("Nieuw evenement", exc)

    def open_project(self):
        if not self._confirm_discard():
            return
        file_name, _ = QFileDialog.getOpenFileName(self, "EventHub-bestand openen", "", FILE_FILTER)
        if not file_name:
            return
        return self._open_project_path(Path(file_name), confirm_discard=False)

    def _apply_project_payload(self, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("Het EventHub-bestand heeft geen geldige structuur.")
        source_records = payload.get("records", payload.get("Participants", []))
        if not isinstance(source_records, list):
            raise ValueError("Het EventHub-bestand bevat geen geldige deelnemerslijst.")
        self.records = [prepare_record(record) for record in source_records]
        project_templates = payload.get("task_templates")
        if isinstance(project_templates, list) and project_templates:
            self.task_templates = [prepare_task(task) for task in project_templates if isinstance(task, dict)]
            self.settings.setValue("task_templates", json.dumps(self.task_templates, ensure_ascii=False))
        source_events = payload.get("events", [])
        self.events = [
            prepare_event(event, self.task_templates)
            for event in source_events
            if isinstance(event, dict)
        ] if isinstance(source_events, list) else []
        self._ensure_events_from_records()
        renamed_events = self._ensure_event_date_names()
        # Dossiers van voor deze versie hebben aanwezigheid staan onder de naam
        # van de aanmeldlijst. Die telt nergens mee tot hij is thuisgebracht.
        self._repaired_attendance = repair_orphan_attendance(
            self.records, [event.get("name", "") for event in self.events]
        )
        self._cleared_absence = self._migrate_future_absence(payload)
        project_profile = payload.get("profile")
        if isinstance(project_profile, dict):
            self.profile = {
                key: str(project_profile.get(key, self.profile.get(key, "")) or "").strip()
                for key in DEFAULT_PROFILE
            }
            self.settings.setValue("profile", json.dumps(self.profile, ensure_ascii=False))
        selected_events = payload.get("selected_events", [])
        self.selected_events = {
            renamed_events.get(str(event).strip(), str(event).strip())
            for event in selected_events if str(event).strip()
        } if isinstance(selected_events, list) else set()
        self.active_event_id = ""
        project_views = payload.get("visible_fields_by_view")
        if isinstance(project_views, dict):
            validated = {}
            for view, defaults in DEFAULT_VISIBLE_FIELDS_BY_VIEW.items():
                fields = project_views.get(view, defaults)
                fields = [field for field in ALL_VISITOR_FIELDS if field in fields]
                validated[view] = fields or list(defaults)
            self.visible_fields_by_view = validated
            self.settings.setValue("visible_fields_by_view", json.dumps(validated))
        else:
            legacy_fields = payload.get("visible_fields")
            if isinstance(legacy_fields, list):
                legacy_fields = [field for field in ALL_VISITOR_FIELDS if field in legacy_fields]
                if legacy_fields:
                    self.visible_fields_by_view["participants"] = legacy_fields

    def _open_project_path(self, path: Path, confirm_discard: bool = True, quiet: bool = False):
        if confirm_discard and not self._confirm_discard():
            return False
        path = Path(path).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._apply_project_payload(payload)
            self.project_path = path
            self._set_clean()
            self.setWindowTitle(APP_NAME)
            self._remember_project_path(self.project_path)
            self._render_all()
            self.page_stack.setCurrentWidget(self.home_page)
            self._set_project_context_ui(False)
            self.status_label.setStyleSheet("")
            opened = f"EventHub-bestand geopend: {self.project_path.name} ({len(self.records)} deelnemers)."
            if getattr(self, "_repaired_attendance", 0):
                opened += (
                    f" Bij {self._repaired_attendance} deelnemers is de aanwezigheid uit een eerdere import"
                    " alsnog aan het juiste evenement gekoppeld; sla het bestand op om dat te bewaren."
                )
            if getattr(self, "_cleared_absence", 0):
                opened += (
                    f" Bij {self._cleared_absence} deelnemers van evenementen die nog moeten plaatsvinden"
                    " staat de aanwezigheid nu op onbekend in plaats van no-show."
                )
            self.status_label.setText(opened)
            # Elk geopend dossier wordt op de bewaartermijn gecontroleerd. Tijdens
            # het opstarten gebeurt dat bewust later, na de profiel- en
            # welkomstschermen, zodat de vraag niet tussen andere vensters valt.
            if not getattr(self, "_starting_up", False):
                self.maybe_apply_retention()
            return True
        except Exception as exc:
            if quiet:
                self._write_error_log(f"EventHub-bestand automatisch openen: {path}", traceback.format_exc())
            else:
                self._show_runtime_error("EventHub-bestand openen", exc)
            return False

    def save_project(self):
        had_changes = self.dirty
        if not self.project_path:
            event_name = self._safe_document_name(self.events[0].get("name", "EventHub")) if self.events else "EventHub"
            event_date = parse_date(self.events[0].get("date", "")) if self.events else None
            date_suffix = f" - {event_date.strftime('%d-%m-%Y')}" if event_date else ""
            suggested = projects_directory() / f"{event_name}{date_suffix}.bvp"
            file_name, _ = QFileDialog.getSaveFileName(self, "EventHub-bestand opslaan", str(suggested), FILE_FILTER)
            if not file_name:
                return False
            self.project_path = Path(file_name if file_name.lower().endswith(".bvp") else file_name + ".bvp")
        try:
            self.autosave_timer.stop()
            if had_changes:
                self._create_backup(self.project_path)
            self._write_payload_atomic(self.project_path, self._project_payload())
            self._set_clean()
            self._set_presence_save_pending(False)
            self._remove_recovery_file()
            self._remember_project_path(self.project_path)
            self.setWindowTitle(APP_NAME)
            self._autosave_error_reported = False
            self.status_label.setStyleSheet("")
            self.status_label.setText(f"Opgeslagen: {self.project_path}")
            return True
        except Exception as exc:
            self._show_runtime_error("EventHub-bestand opslaan", exc)
            return False

    def _restore_autosave_payload(self, payload: dict):
        metadata = payload.get("_autosave", {}) if isinstance(payload.get("_autosave"), dict) else {}
        source_text = str(metadata.get("source_path", "") or "").strip()
        self._apply_project_payload(payload)
        self.project_path = Path(source_text).expanduser() if source_text else None
        self.dirty = True
        if self.project_path:
            self.setWindowTitle(f"{APP_NAME} *")
        else:
            self.setWindowTitle(f"{APP_NAME} — hersteld, nog niet opgeslagen *")
        self._render_all()
        self.page_stack.setCurrentWidget(self.home_page)
        self._set_project_context_ui(False)
        self.settings.remove("ignored_autosave_mtime_ns")
        self.status_label.setStyleSheet("")
        self.status_label.setText("Automatisch opgeslagen werk hersteld. Controleer het dossier en sla het zo nodig handmatig op.")
        self._schedule_autosave()

    def maybe_restore_autosave(self):
        recovery_path = self._recovery_path()
        if not recovery_path.is_file():
            return False
        try:
            recovery_mtime = recovery_path.stat().st_mtime_ns
            ignored_mtime = int(self.settings.value("ignored_autosave_mtime_ns", 0) or 0)
            if recovery_mtime == ignored_mtime:
                return False
            payload = json.loads(recovery_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("records", []), list):
                raise ValueError("De herstelkopie heeft geen geldige EventHub-structuur.")
            metadata = payload.get("_autosave", {}) if isinstance(payload.get("_autosave"), dict) else {}
            source_text = str(metadata.get("source_path", "") or "").strip()
            source_path = Path(source_text).expanduser() if source_text else None
            if source_path and source_path.is_file() and source_path.stat().st_mtime_ns >= recovery_mtime:
                recovery_path.unlink(missing_ok=True)
                return False
        except Exception:
            self._write_error_log("Herstelkopie controleren", traceback.format_exc())
            return False

        while True:
            message = QMessageBox(self)
            message.setWindowTitle("Automatisch opgeslagen werk gevonden")
            message.setIcon(QMessageBox.Icon.Question)
            message.setText("EventHub heeft een recentere herstelkopie gevonden.")
            message.setInformativeText(
                "Dit kan gebeuren wanneer EventHub of Windows onverwacht is afgesloten. Wilt u het automatisch opgeslagen werk herstellen?"
            )
            restore_button = message.addButton("Herstellen", QMessageBox.ButtonRole.AcceptRole)
            compare_button = message.addButton("Vergelijken", QMessageBox.ButtonRole.ActionRole)
            ignore_button = message.addButton("Negeren", QMessageBox.ButtonRole.RejectRole)
            message.setDefaultButton(restore_button)
            message.exec()
            clicked = message.clickedButton()
            if clicked is restore_button:
                self._restore_autosave_payload(payload)
                return True
            if clicked is compare_button:
                recovered_events = payload.get("events", []) if isinstance(payload.get("events"), list) else []
                recovered_records = payload.get("records", []) if isinstance(payload.get("records"), list) else []
                saved_at = str(metadata.get("saved_at", "Onbekend") or "Onbekend").replace("T", " ")
                QMessageBox.information(
                    self,
                    "Herstelkopie vergelijken",
                    f"Herstelkopie\n• Opgeslagen: {saved_at}\n• Evenementen: {len(recovered_events)}\n"
                    f"• Deelnemers: {len(recovered_records)}\n\nHuidig geopend bestand\n"
                    f"• Evenementen: {len(self.events)}\n• Deelnemers: {len(self.records)}",
                )
                continue
            if clicked is ignore_button or clicked is None:
                self.settings.setValue("ignored_autosave_mtime_ns", recovery_mtime)
                return False

    def _restore_backup_file(self, backup_path: Path):
        if not self.project_path:
            QMessageBox.information(self, "Geen EventHub-bestand geopend", "Open eerst het EventHub-bestand waarvan u een versie wilt herstellen.")
            return False
        try:
            data = Path(backup_path).read_bytes()
            payload = json.loads(data.decode("utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("records", []), list):
                raise ValueError("De gekozen reservekopie is geen geldig EventHub-bestand.")
            if not self._confirm_discard():
                return False
            answer = QMessageBox.question(
                self,
                "Vorige versie herstellen",
                "De huidige versie wordt eerst als reservekopie bewaard. Wilt u daarna de gekozen versie herstellen?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
            self._create_backup(self.project_path)
            self._write_bytes_atomic(self.project_path, data)
            if not self._open_project_path(self.project_path, confirm_discard=False):
                raise ValueError("De herstelde versie kon niet opnieuw worden geopend.")
            self.status_label.setText(f"Vorige versie hersteld: {Path(backup_path).name}")
            return True
        except Exception as exc:
            self._show_runtime_error("Reservekopie herstellen", exc)
            return False

    def restore_previous_version(self):
        if not self.project_path:
            QMessageBox.information(self, "Geen EventHub-bestand geopend", "Open eerst een opgeslagen EventHub-bestand.")
            return
        backups = self._backup_files(self.project_path)
        if not backups:
            QMessageBox.information(self, "Geen reservekopieën", "Voor dit EventHub-bestand zijn nog geen reservekopieën beschikbaar.")
            return
        labels = [
            f"{datetime.fromtimestamp(path.stat().st_mtime).strftime('%d-%m-%Y %H:%M:%S')}  —  {path.stat().st_size / 1024:.0f} kB"
            for path in backups
        ]
        selected, accepted = QInputDialog.getItem(
            self,
            "Vorige versie herstellen",
            "Kies een reservekopie:",
            labels,
            0,
            False,
        )
        if accepted and selected in labels:
            self._restore_backup_file(backups[labels.index(selected)])

    def manage_recovery_files(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Herstelbestanden beheren")
        _fit_dialog_to_screen(dialog, 820, 500, 600, 360)
        layout = QVBoxLayout(dialog)
        intro = QLabel(
            "Hier vindt u de automatische herstelkopie en reservekopieën van het geopende EventHub-bestand."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        table = self._new_table(["Type", "Datum", "Bestand", "Grootte"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        layout.addWidget(table, 1)

        def available_files():
            items = []
            recovery = self._recovery_path()
            if recovery.is_file():
                items.append(("Herstelkopie", recovery))
            items.extend(("Reservekopie", path) for path in self._backup_files(self.project_path))
            return items

        def render():
            items = available_files()
            table.setRowCount(max(1, len(items)))
            table.clearSpans()
            if not items:
                item = QTableWidgetItem("Geen herstel- of reservekopieën beschikbaar")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                table.setSpan(0, 0, 1, 4)
                table.setItem(0, 0, item)
                return
            for row_index, (kind, path) in enumerate(items):
                values = [
                    kind,
                    datetime.fromtimestamp(path.stat().st_mtime).strftime("%d-%m-%Y %H:%M:%S"),
                    path.name,
                    f"{path.stat().st_size / 1024:.0f} kB",
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setData(Qt.ItemDataRole.UserRole, (kind, str(path)))
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                    table.setItem(row_index, column, item)

        def selected_file():
            row = table.currentRow()
            item = table.item(row, 0) if row >= 0 else None
            data = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(data, (tuple, list)) and len(data) == 2:
                return str(data[0]), Path(str(data[1]))
            return "", None

        def restore_selected():
            kind, path = selected_file()
            if path is None:
                QMessageBox.information(dialog, "Geen bestand gekozen", "Selecteer eerst een herstelbestand.")
                return
            if kind == "Herstelkopie":
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if not self._confirm_discard():
                        return
                    self._restore_autosave_payload(payload)
                    dialog.accept()
                except Exception as exc:
                    self._show_runtime_error("Herstelbestand openen", exc)
            elif self._restore_backup_file(path):
                dialog.accept()

        def delete_selected():
            _, path = selected_file()
            if path is None:
                QMessageBox.information(dialog, "Geen bestand gekozen", "Selecteer eerst een herstelbestand.")
                return
            answer = QMessageBox.question(dialog, "Herstelbestand verwijderen", f"Wilt u '{path.name}' verwijderen?")
            if answer == QMessageBox.StandardButton.Yes:
                try:
                    path.unlink(missing_ok=True)
                    if path == self._recovery_path():
                        self.settings.remove("ignored_autosave_mtime_ns")
                    render()
                except OSError as exc:
                    self._show_runtime_error("Herstelbestand verwijderen", exc)

        def open_folder():
            _, path = selected_file()
            folder = path.parent if path is not None else self._app_data_root()
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

        actions = QHBoxLayout()
        restore_button = QPushButton("Geselecteerde versie herstellen")
        restore_button.setObjectName("primaryButton")
        restore_button.clicked.connect(restore_selected)
        delete_button = QPushButton("Verwijderen")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(delete_selected)
        folder_button = QPushButton("Map openen")
        folder_button.setObjectName("secondaryButton")
        folder_button.clicked.connect(open_folder)
        close_button = QPushButton("Sluiten")
        close_button.clicked.connect(dialog.reject)
        actions.addWidget(restore_button)
        actions.addWidget(delete_button)
        actions.addWidget(folder_button)
        actions.addStretch()
        actions.addWidget(close_button)
        layout.addLayout(actions)
        table.cellDoubleClicked.connect(lambda *_: restore_selected())
        render()
        dialog.exec()

    def import_excel(self):
        active_event = self._active_event()
        if not active_event or self.page_stack.currentWidget() is not self.event_page:
            QMessageBox.information(
                self,
                "Open eerst een evenement",
                "Deelnemerslijsten worden binnen een evenement geüpload. Open of maak eerst een evenement.",
            )
            return
        file_names, _ = QFileDialog.getOpenFileNames(self, "Een of meer aanmeldlijsten toevoegen", "", EXCEL_FILTER)
        if not file_names:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # De import verhuist elke ingelezen regel naar dit evenement, ook
            # de regels die een bestaande bezoeker aanvullen.
            result = import_registration_files(file_names, self.records, target_event=active_event["name"])
        finally:
            QApplication.restoreOverrideCursor()
        overwritten = self._ask_about_attendance_conflicts(result.get("attendance_conflicts") or [])
        added = [prepare_record(record) for record in result["records"]]
        self._touch_event(active_event)
        linked_to_active = active_event["name"]
        self.records.extend(added)
        self._ensure_events_from_records()
        enriched = int(result.get("enriched", 0))
        if added or enriched:
            self._mark_dirty()
            self._render_all()
        fallback_events = sum(report["fallback_events"] for report in result["reports"])
        missing_places = sum(report["missing_birth_places"] for report in result["reports"])
        repaired_headers = sum(bool(report.get("repaired_birthplace_header")) for report in result["reports"])
        introducees = sum(int(report.get("introducees", 0)) for report in result["reports"])
        presence_detected = sum(int(report.get("presence_detected", 0)) for report in result["reports"])
        parts = [f"{len(added)} deelnemers toegevoegd"]
        if overwritten:
            parts.append(f"bij {overwritten} deelnemers is de aanwezigheid uit het bestand overgenomen")
        if linked_to_active:
            parts.append(f"gekoppeld aan {linked_to_active}")
        if introducees:
            parts.append(f"{introducees} introducees automatisch herkend")
        if presence_detected:
            parts.append(f"aanwezigheid van {presence_detected} deelnemers automatisch overgenomen uit de bron")
        if enriched:
            parts.append(f"{enriched} bestaande deelnemers met ontbrekende gegevens aangevuld")
        skipped_duplicates = result["duplicates"] - enriched
        if skipped_duplicates:
            parts.append(f"{skipped_duplicates} ongewijzigde duplicaten overgeslagen")
        if fallback_events:
            parts.append(f"bij {fallback_events} regels is de bestandsnaam als evenement gebruikt")
        if missing_places:
            parts.append(f"{missing_places} geboorteplaatsen ontbreken in de bron")
        if repaired_headers:
            parts.append(f"in {repaired_headers} bestand(en) is de dubbele kolom Geboortedatum automatisch hersteld")
        if result["errors"]:
            parts.append(f"{len(result['errors'])} bestand(en) niet ingelezen")
        message = "; ".join(parts) + "."
        self.status_label.setText(message)
        if added or enriched:
            self._add_recent_activity(f"{len(added)} deelnemers geïmporteerd · {active_event.get('name', 'Evenement')}")
        if result["errors"]:
            QMessageBox.warning(self, "Import deels voltooid", message + "\n\n" + "\n".join(result["errors"]))
        elif missing_places or fallback_events or repaired_headers or presence_detected:
            QMessageBox.information(self, "Import voltooid", message)

    def _participant_export_records(self):
        records = self._filtered_records()
        if hasattr(self, "participant_include_introducees") and not self.participant_include_introducees.isChecked():
            records = [record for record in records if not is_introducee(record)]
        return self._sorted_records(records)

    def _participant_export_ready(self, action: str):
        event = self._active_event()
        if not event or self.page_stack.currentWidget() is not self.event_page:
            QMessageBox.information(self, "Open eerst een evenement", f"Open het evenement waarvan u de deelnemerslijst wilt {action}.")
            return None, []
        records = self._participant_export_records()
        if not records:
            QMessageBox.information(self, "Geen deelnemers", "Voeg eerst één of meer deelnemers toe die binnen de huidige weergave vallen.")
            return None, []
        return event, records

    def export_participant_list(self):
        event, records = self._participant_export_ready("exporteren")
        if not event:
            return
        if not PARTICIPANT_TEMPLATE.is_file():
            self._show_error_with_report(
                "Template ontbreekt",
                "De vaste DCPL-deelnemerslijst kon niet worden gevonden. Installeer EventHub opnieuw of neem contact op met de beheerder.",
                "Deelnemerslijst-template controleren",
                f"Ontbrekend bestand: {PARTICIPANT_TEMPLATE}",
            )
            return
        safe_name = re.sub(r"[^A-Za-z0-9À-ÿ _.-]+", "", str(event.get("name", "") or "Evenement")).strip()
        if not self._confirm_personal_data_export("De deelnemerslijst"):
            return
        default_name = exports_directory() / f"Bezoekerslijst - {safe_name or 'Evenement'}{self._event_date_suffix(event)}.xlsx"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Deelnemerslijst exporteren",
            str(default_name),
            "Excel-werkmap (*.xlsx)",
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".xlsx"):
            file_name += ".xlsx"
        try:
            result = export_participant_template(
                records,
                event,
                self.profile,
                PARTICIPANT_TEMPLATE,
                file_name,
            )
            self.status_label.setText(f"Deelnemerslijst gemaakt: {file_name}")
            self._offer_open_export_folder(file_name)
            QMessageBox.information(
                self,
                "Deelnemerslijst gereed",
                f"{result['participants']} deelnemer(s) zijn in de vaste DCPL-template geplaatst. "
                f"Het afdrukbereik stopt automatisch na de laatste gebruikte rij.",
            )
        except Exception as exc:
            self._show_runtime_error("Deelnemerslijst exporteren", exc)

    def _participant_print_document(self, event: dict, records: list[dict]):
        del event
        if LOGO_PATH.is_file():
            logo_html = "<img src='dcpl-emt-logo' width='86' height='86'>"
        else:
            logo_html = "DCPL"

        labels = [
            ("Naam evenement:", ""),
            ("Datum:", ""),
            ("Aanvangstijd & vertrek:", ""),
            ("Locatie van evenement:", ""),
            ("Contactpersoon:", ""),
            ("Telefoonnummer:", ""),
        ]
        top_rows = []
        for index, (label, value) in enumerate(labels):
            cells = []
            if index == 0:
                cells.append(f"<td class='logo' rowspan='6'>{logo_html}</td>")
            cells.append(f"<td class='info-label' colspan='2'>{escape(label)}</td>")
            cells.append(f"<td class='info-value' colspan='2'>{escape(str(value or ''))}</td>")
            top_rows.append("<tr>" + "".join(cells) + "</tr>")

        visitor_headers = ["Achternaam", "Tussenvoegsel", "Voornaam", "Geboortedatum", "Geboorteplaats"]
        heading_row = "<tr>" + "".join(f"<th>{escape(value)}</th>" for value in visitor_headers)
        heading_row += "</tr>"

        data_rows = []
        for index, record in enumerate(records):
            values = [
                record.get("Achternaam", ""),
                record.get("Tussenvoegsel", ""),
                record.get("Voornaam", ""),
                record.get("Geboortedatum", ""),
                record.get("Geboorteplaats", ""),
            ]
            visitor_cells = "".join(f"<td class='visitor-cell'>{escape(str(value or ''))}</td>" for value in values)
            data_rows.append(f"<tr class='data-row row-{index % 2}'>{visitor_cells}</tr>")

        document = QTextDocument(self)
        document.setDefaultFont(QFont("Verdana", 7))
        if LOGO_PATH.is_file():
            document.addResource(
                QTextDocument.ResourceType.ImageResource,
                QUrl("dcpl-emt-logo"),
                QPixmap(str(LOGO_PATH)),
            )
        document.setHtml("""
            <html><head><style>
            body { color: #000000; margin: 0; font-family: Verdana; font-size: 7pt; }
            table.sheet { width: 100%; border-collapse: collapse; table-layout: fixed; }
            td, th { padding: 2px 3px; }
            td.logo { text-align: center; vertical-align: middle; border: 1.5px solid #000; }
            td.info-label { font-family: Calibri; font-size: 10pt; font-weight: bold; text-align: center; border: 1px solid #000; }
            td.info-value { font-family: Calibri; font-size: 9pt; border: 1px solid #000; }
            th { background: #000; color: #fff; font-size: 5.7pt; font-weight: bold; text-align: left; border: 1px solid #000; }
            td.visitor-cell { height: 13px; border: 1px solid #555; font-size: 6.5pt; }
            tr.row-0 td.visitor-cell { background: #dedede; }
            </style></head><body>
            <table class='sheet' cellspacing='0' cellpadding='0'>
            <colgroup>
              <col width='24.39%'><col width='16.93%'><col width='15.81%'><col width='21.60%'><col width='21.27%'>
            </colgroup>
            """ + "".join(top_rows) + heading_row + "".join(data_rows) + "</table></body></html>")
        return document

    def preview_participant_list(self):
        event, records = self._participant_export_ready("bekijken")
        if not event:
            return
        try:
            document = self._participant_print_document(event, records)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            printer.setPageMargins(QMarginsF(18, 19, 18, 19), QPageLayout.Unit.Millimeter)
            preview = QPrintPreviewDialog(printer, self)
            preview.setWindowTitle("Afdrukvoorbeeld deelnemerslijst")
            preview.resize(1180, 820)
            preview.paintRequested.connect(lambda device: document.print_(device))
            preview.exec()
            self.status_label.setText(
                f"Afdrukvoorbeeld bekeken voor {len(records)} deelnemer(s); lege vervolgpagina's zijn uitgesloten."
            )
        except Exception as exc:
            self._show_runtime_error("Afdrukvoorbeeld deelnemerslijst", exc)

    def export_participant_pdf(self):
        event, records = self._participant_export_ready("exporteren")
        if not event:
            return
        if not self._confirm_personal_data_export("De deelnemerslijst-PDF"):
            return
        default_name = exports_directory() / f"Deelnemerslijst{self._event_date_suffix(event)}.pdf"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Deelnemerslijst exporteren",
            str(default_name),
            "PDF-bestand (*.pdf)",
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".pdf"):
            file_name += ".pdf"
        try:
            document = self._participant_print_document(event, records)
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(file_name)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            printer.setPageMargins(QMarginsF(18, 19, 18, 19), QPageLayout.Unit.Millimeter)
            document.print_(printer)
            self.status_label.setText(f"Deelnemerslijst geëxporteerd als PDF: {file_name}")
            QMessageBox.information(self, "Export gereed", f"De deelnemerslijst is geëxporteerd naar:\n{file_name}")
            self._offer_open_export_folder(file_name)
        except Exception as exc:
            self._show_runtime_error("Deelnemerslijst exporteren", exc)

    def export_excel(self):
        if not self._active_event() or self.page_stack.currentWidget() is not self.event_page:
            QMessageBox.information(self, "Open eerst een evenement", "Open het evenement dat u wilt exporteren.")
            return
        scoped_records = self._filtered_records()
        if not scoped_records:
            QMessageBox.information(self, "Niets te exporteren", "Voeg eerst één of meer aanmeldlijsten toe.")
            return
        event = self._active_event()
        default_name = exports_directory() / f"EventHub-bezoekerslijsten{self._event_date_suffix(event)}.xlsx"
        if not self._confirm_personal_data_export("Deze Excel-werkmap"):
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "Exporteren naar Excel", str(default_name), "Excel-werkmap (*.xlsx)")
        if not file_name:
            return
        if not file_name.lower().endswith(".xlsx"):
            file_name += ".xlsx"
        try:
            export_workbook(scoped_records, file_name, reference_records=self.records)
            self.status_label.setText(f"Excel-werkmap gemaakt: {file_name}")
            scope = self._active_event().get("name", "het geopende evenement")
            QMessageBox.information(
                self,
                "Export gereed",
                f"De Excel-werkmap bevat Deelnemerslijst, Ruwe aanmeldingen, After sales en Presentie voor {scope}.",
            )
            self._offer_open_export_folder(file_name)
        except Exception as exc:
            self._show_runtime_error("Deelnemerslijst exporteren", exc)

    def _crosstab_export_scope_dialog(self, records):
        """Kies de groep voor de hele export en, apart, voor de kruistabel."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Deelnemers voor de export")
        dialog.setMinimumWidth(430)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("<b>Hele export</b>"))
        layout.addWidget(QLabel(
            "Standaard worden alle groepen meegenomen. Kies desgewenst één aanwezigheidsstatus."
        ))
        export_scope = ScrollSafeComboBox()
        for label, value in (
            ("Alle groepen", "all"),
            ("Alleen aanwezig", AANWEZIG),
            ("Alleen afwezig", AFWEZIG),
            ("Alleen afgemeld", AFGEMELD),
        ):
            export_scope.addItem(label, value)
        layout.addWidget(export_scope)

        layout.addWidget(QLabel("<b>Alleen de kruistabel</b>"))
        layout.addWidget(QLabel(
            "Deze aanvullende afvinklijst geldt uitsluitend voor Opleidingsniveau × Profiel."
        ))

        current_filter = str(self.statistics_presence_filter.currentData() or "all")
        counts = Counter(self._scoped_status(record) for record in records)
        checkboxes = {}
        for status in (AANWEZIG, AFGEMELD, AFWEZIG, ONBEKEND):
            checkbox = QCheckBox(f"{ATTENDANCE_LABELS[status]} ({counts[status]})")
            checkbox.setChecked(current_filter == "all" or current_filter == status)
            checkboxes[status] = checkbox
            layout.addWidget(checkbox)

        def sync_crosstab_with_export_scope(*_):
            gekozen = str(export_scope.currentData() or "all")
            if gekozen != "all":
                for status, checkbox in checkboxes.items():
                    checkbox.setChecked(status == gekozen)

        export_scope.currentIndexChanged.connect(sync_crosstab_with_export_scope)

        include_introducees = QCheckBox(
            f"Introducees meenemen ({sum(is_introducee(record) for record in records)})"
        )
        include_introducees.setChecked(self.statistics_include_introducees.isChecked())
        layout.addWidget(include_introducees)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Exporteren")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        statuses = {status for status, checkbox in checkboxes.items() if checkbox.isChecked()}
        if not statuses:
            QMessageBox.information(
                self, "Geen deelnemers gekozen", "Vink ten minste één aanwezigheidsstatus aan."
            )
            return None
        return statuses, include_introducees.isChecked(), str(export_scope.currentData() or "all")

    def _export_historical_statistics(self, event: dict):
        snapshot, status = self._historical_statistics_selection()
        if snapshot is None:
            QMessageBox.information(
                self, "Geen historische statistieken",
                "De persoonsgegevens zijn verwijderd voordat een statistische momentopname beschikbaar was."
            )
            return
        dimensions = historical_export_dimensions(snapshot, status)
        if not dimensions:
            QMessageBox.information(self, "Geen historische verdelingen", "Voor deze selectie zijn geen verdelingen vastgelegd.")
            return
        count = bucket_value(snapshot, status)
        statuses = {AANWEZIG: "aanwezig", AFWEZIG: "noshows", AFGEMELD: "afgemeld", ONBEKEND: "onbekend"}
        summary = {
            "evenement": event.get("name", "Evenement"), "datum": event.get("date", ""),
            "locatie": " — ".join(filter(None, [event.get("place", ""), event.get("location", "")])),
            "aangemeld": count if count is not None else 0,
            "aanwezig": snapshot.get("aanwezig", 0) if status == "all" else (count if status == AANWEZIG else 0),
            "afwezig": snapshot.get("noshows", 0) if status == "all" else (count if status == AFWEZIG else 0),
            "afgemeld": snapshot.get("afgemeld", 0) if status == "all" else (count if status == AFGEMELD else 0),
            "onbekend": snapshot.get("onbekend", 0) if status == "all" else (count if status == ONBEKEND else 0),
            "opmerkingen": ["Geanonimiseerd: persoonsgegevens zijn verwijderd; deze export bevat uitsluitend historische aggregaten."],
        }
        event_label = self._safe_document_name(event_base_name(event.get("name", "")))
        default_name = exports_directory() / f"EventHub-statistieken - {event_label}{self._event_date_suffix(event)}.xlsx"
        file_name, _ = QFileDialog.getSaveFileName(self, "Historische statistieken exporteren", str(default_name), "Excel-werkmap (*.xlsx)")
        if not file_name:
            return
        if not file_name.lower().endswith(".xlsx"):
            file_name += ".xlsx"
        try:
            export_statistics_workbook(dimensions, file_name, summary=summary,
                                       crosstab=historical_crosstab(snapshot, status))
            self.status_label.setText(f"Historische statistieken geëxporteerd: {file_name}")
            self._offer_open_export_folder(file_name)
        except Exception as exc:
            self._show_runtime_error("Historische statistieken exporteren", exc)

    def export_statistics(self):
        if not self._active_event() or self.page_stack.currentWidget() is not self.event_page:
            QMessageBox.information(self, "Open eerst een evenement", "Open het evenement dat u wilt exporteren.")
            return
        if self._active_event().get("exclude_from_analysis"):
            QMessageBox.information(
                self, "Uitgesloten van analyse",
                "Dit evenement staat ingesteld op niet meetellen in Statistieken en Trends. Pas dit aan in de evenementgegevens om statistieken te exporteren.",
            )
            return
        active_event = self._active_event()
        if active_event.get("persoonsgegevens_gewist"):
            self._export_historical_statistics(active_event)
            return
        event_visitors = self._event_visitors(active_event)
        if (not event_visitors or attendance_counts(
                event_visitors, str(active_event.get("name", "") or ""))[ONBEKEND]):
            QMessageBox.information(
                self, "Aanwezigheid nog niet afgerond",
                "Statistieken kunnen worden geëxporteerd zodra een deelnemerslijst aanwezig is en iedere deelnemer als aanwezig, afwezig of afgemeld is geregistreerd.",
            )
            return
        event_records = self._filtered_records()
        crosstab_scope = self._crosstab_export_scope_dialog(event_records)
        if crosstab_scope is None:
            return
        crosstab_statuses, crosstab_include_introducees, export_status = crosstab_scope
        if export_status != "all":
            event_records = [
                record for record in event_records if self._scoped_status(record) == export_status
            ]
        crosstab_records = [
            record for record in event_records if self._scoped_status(record) in crosstab_statuses
        ]
        if not crosstab_include_introducees:
            crosstab_records = [record for record in crosstab_records if not is_introducee(record)]
        if not crosstab_records:
            QMessageBox.information(
                self, "Lege kruistabel", "De gekozen groepen bevatten geen deelnemers voor de kruistabel."
            )
            return
        if hasattr(self, "statistics_include_introducees") and not self.statistics_include_introducees.isChecked():
            event_records = [record for record in event_records if not is_introducee(record)]
        if not event_records:
            QMessageBox.information(self, "Niets te exporteren", "Voeg eerst één of meer aanmeldlijsten toe aan dit evenement.")
            return
        event = self._active_event()
        peildatum = parse_date(str(event.get("date", "") or "")) or date.today()
        dimensions = [
            ("Opleidingsniveau", self._dimension_rows(
                lambda record, spellings: self._grouped_value("Opleiding", record, spellings), event_records)),
            ("Profiel", self._dimension_rows(
                lambda record, spellings: self._grouped_value("Profiel", record, spellings), event_records)),
            ("Geslacht", self._dimension_rows(
                lambda record, spellings: self._grouped_value("Geslacht", record, spellings),
                event_records, limit=10)),
            ("Leeftijdsgroep", self._dimension_rows(
                lambda record, spellings: self._age_label(record, peildatum),
                event_records, order=AGE_GROUPS)),
        ]
        if self._registration_counts(event_records):
            dimensions.append(("Inschrijving", self._dimension_rows(
                lambda record, spellings: "; ".join(registrations(record)) or "Onbekend",
                event_records, limit=0)))

        standen = Counter(self._scoped_status(record) for record in event_records)
        overgeslagen = sum(1 for record in self._filtered_records(include_skipped=True) if is_skipped(record))
        opmerkingen = []
        if overgeslagen:
            opmerkingen.append(f"{overgeslagen} dubbele inschrijving(en) tellen niet mee.")
        if not self.statistics_include_introducees.isChecked():
            opmerkingen.append("Introducees zijn buiten de telling gelaten.")
        if self._show_all_values():
            opmerkingen.append("Alle waarden staan apart; er is niets samengevat onder Overig.")
        if export_status != "all":
            opmerkingen.append(f"Deze export bevat alleen: {ATTENDANCE_LABELS[export_status]}.")
        summary = {
            "evenement": event.get("name", "Evenement"),
            "datum": event.get("date", ""),
            "locatie": " — ".join(filter(None, [event.get("place", ""), event.get("location", "")])),
            "aangemeld": len(event_records),
            "aanwezig": standen[AANWEZIG],
            "afwezig": standen[AFWEZIG],
            "afgemeld": standen[AFGEMELD],
            "onbekend": standen[ONBEKEND],
            "opmerkingen": opmerkingen,
        }
        # De naam van het evenement hoort in de bestandsnaam; anders zijn twee
        # exports van dezelfde dag niet uit elkaar te houden.
        event_label = self._safe_document_name(event_base_name(event.get("name", "")))
        default_name = exports_directory() / (
            f"EventHub-statistieken - {event_label}{self._event_date_suffix(event)}.xlsx"
        )
        file_name, _ = QFileDialog.getSaveFileName(self, "Statistieken exporteren naar Excel", str(default_name), "Excel-werkmap (*.xlsx)")
        if not file_name:
            return
        if not file_name.lower().endswith(".xlsx"):
            file_name += ".xlsx"
        try:
            export_statistics_workbook(
                dimensions, file_name, summary=summary,
                # Dezelfde kruistabel als op het scherm, inclusief de keuze om
                # de kleinste profielen wel of niet te bundelen.
                crosstab=self._crosstab_data(crosstab_records),
            )
            self.status_label.setText(f"Statistieken geëxporteerd: {file_name}")
            self._offer_open_export_folder(file_name)
            QMessageBox.information(
                self,
                "Export gereed",
                "De werkmap begint met een overzicht van de aantallen en de opkomst. Daarna staat per "
                "statistiek een tabel met per categorie hoeveel er waren aangemeld, aanwezig, niet gekomen "
                "en afgemeld, met de opkomst per categorie en een grafiek eronder.",
            )
        except Exception as exc:
            self._show_runtime_error("Volledige Excel-export", exc)

    def remove_selected(self):
        ids = set()
        for index in self.participant_table.selectionModel().selectedRows():
            row = index.row()
            if self.participant_table.isRowHidden(row):
                continue
            item = self.participant_table.item(row, 0)
            if item:
                ids.add(item.data(Qt.ItemDataRole.UserRole))
        if not ids:
            QMessageBox.information(self, "Geen selectie", "Selecteer in het tabblad Deelnemers eerst één of meer regels.")
            return
        answer = QMessageBox.question(self, "Deelnemers verwijderen", f"Weet u zeker dat u {len(ids)} deelnemer(s) wilt verwijderen?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.records = [record for record in self.records if record["_id"] not in ids]
        self._mark_dirty()
        self._render_all()
        self.status_label.setText(f"{len(ids)} deelnemer(s) verwijderd.")

    def print_presence_list(self):
        if not self._active_event() or self.page_stack.currentWidget() is not self.event_page:
            QMessageBox.information(self, "Open eerst een evenement", "Open het evenement waarvan u de presentielijst wilt printen.")
            return
        scoped_records = self._filtered_records()
        if not scoped_records:
            QMessageBox.information(self, "Niets te printen", "Voeg eerst één of meer aanmeldlijsten toe.")
            return
        fields = self.visible_fields_by_view["presence"]
        rows = []
        for record in self._sorted_records(scoped_records):
            values = [self._display_value(record, field) for field in fields]
            cells = "".join(f"<td>{escape(str(value or ''))}</td>" for value in values)
            cells += f"<td class='check'>{'☒' if is_present_in_scope(record, self.selected_events) else '☐'}</td>"
            rows.append(f"<tr>{cells}</tr>")
        headers = "".join(f"<th>{escape(FIELD_LABELS[field])}</th>" for field in fields)
        headers += "<th>Aanwezig</th>"
        document = QTextDocument(self)
        document.setDefaultFont(QFont("Segoe UI", 9))
        scope_text = ", ".join(sorted(self.selected_events, key=normalize)) if self.selected_events else "Alle evenementen"
        document.setHtml("""
            <html><head><style>
            body { color: #17233a; }
            h1 { font-size: 18pt; margin-bottom: 4px; }
            p { color: #5d6b7c; margin-top: 0; }
            table { width: 100%; border-collapse: collapse; }
            th { background: #0d1117; color: white; padding: 6px; text-align: left; }
            td { border-bottom: 1px solid #cbd5df; padding: 6px; }
            .check { font-size: 14pt; text-align: center; }
            </style></head><body>
            <h1>EventHub — Presentie</h1>
            <p>Bezoekerslijst — afvinken bij binnenkomst — """ + escape(scope_text) + """</p>
            <table><thead><tr>""" + headers + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></body></html>")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Presentielijst printen")
        if dialog.exec():
            document.print_(printer)
            self.status_label.setText("Presentielijst naar de printer gestuurd.")

    def _setup_system_tray(self):
        """Keep EventHub available in the Windows notification area."""
        if self._tray_icon is not None:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            # Explorer/the notification area can still be starting while EventHub
            # is launched with Windows. Retry instead of silently disabling tray mode.
            QTimer.singleShot(1500, self._setup_system_tray)
            return
        icon_path = APP_ICON_PATH if APP_ICON_PATH.exists() else LOGO_PATH
        tray_icon = QSystemTrayIcon(QIcon(str(icon_path)) if icon_path.exists() else self.windowIcon(), self)
        tray_icon.setToolTip(f"{APP_NAME} — actief op de achtergrond")
        tray_menu = QMenu(self)
        open_action = tray_menu.addAction("EventHub openen")
        open_action.triggered.connect(self._restore_from_tray)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("EventHub afsluiten")
        quit_action.triggered.connect(self._quit_from_tray)
        tray_icon.setContextMenu(tray_menu)
        tray_icon.activated.connect(self._tray_activated)
        tray_icon.show()
        self._tray_icon = tray_icon

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self._restore_from_tray()

    def _restore_from_tray(self):
        self.show()
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def _has_active_live_session(self):
        return any(getattr(window, "server_thread", None) is not None for window in self._live_server_windows if window is not None)

    def _quit_from_tray(self):
        if self._has_active_live_session():
            answer = QMessageBox.warning(
                self,
                "Actieve livesessie",
                "Er is nog een livesessie actief. EventHub afsluiten stopt ook deze sessie.\n\nWilt u EventHub echt afsluiten?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._allow_application_exit = True
        self._restore_from_tray()
        self.close()
        if not self.isVisible():
            QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent):
        # The window close button always means 'keep running'. Never let a
        # temporarily unavailable Windows notification area turn X into Exit.
        if not self._allow_application_exit:
            event.ignore()
            if self._tray_icon is not None and self._tray_icon.isVisible():
                self.hide()
                if not self.settings.value("tray_close_notice_shown", False, type=bool):
                    self._tray_icon.showMessage(
                        APP_NAME,
                        "EventHub blijft actief op de achtergrond. Gebruik het systeemvak om EventHub weer te openen of volledig af te sluiten.",
                        QSystemTrayIcon.MessageIcon.Information,
                        5000,
                    )
                    self.settings.setValue("tray_close_notice_shown", True)
            else:
                # Safe fallback: keep the process/window recoverable in the taskbar
                # until Windows exposes the notification area.
                self.showMinimized()
                self._setup_system_tray()
            return

        if self._rudder_bridge is not None:
            self._rudder_bridge.stop()
            self._rudder_bridge = None
        self.rudder_attendance_service.stop()
        for window in list(self._live_server_windows):
            try:
                linked_event_id = str(getattr(window, "linked_event_id", "") or "")
                if linked_event_id:
                    self._sync_live_attendance(window, linked_event_id)
            except RuntimeError:
                pass
        if self._confirm_discard():
            for window in list(self._live_server_windows):
                try:
                    window.close()
                except RuntimeError:
                    pass
            self.settings.setValue("window_geometry", self.saveGeometry())
            event.accept()
        else:
            self._allow_application_exit = False
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Avenir Next", 10))
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("DCPL")
    if LOGO_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH if APP_ICON_PATH.exists() else LOGO_PATH)))
    app.setStyle("Fusion")
    splash = StartupSplash()
    splash.show()
    splash.set_progress(8, "Programmacomponenten laden…")
    window = BezoekerslijstWindow(progress_callback=splash.set_progress)
    splash.set_progress(100, "Gereed")
    window.show()
    # Draait er al een EventHub, dan houdt die de poort; deze werkt dan gewoon
    # zonder de assistent.
    window.rudder_attendance_service.start()
    splash.finish(window)
    QTimer.singleShot(250, window.run_post_startup)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
