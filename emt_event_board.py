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


def event_name_with_date(name: str, event_date: str) -> str:
    """Return one stable event title whose date is always visible."""
    raw_name = str(name or "").strip()
    sequence_match = re.search(r"\s+\((\d+)\)\s*$", raw_name)
    sequence = f" ({sequence_match.group(1)})" if sequence_match else ""
    if sequence_match:
        raw_name = raw_name[:sequence_match.start()].rstrip()
    base = EVENT_NAME_DATE_SUFFIX.sub("", raw_name).strip() or "Onbenoemd evenement"
    parsed = parse_date(event_date)
    dated = f"{base} ({parsed.strftime("%d-%m-'%y")})" if parsed else base
    return dated + sequence

class EventBoardMixin:
    """Event list, board, and event-selection behavior for the main window."""

    def _record_map(self):
        return {record["_id"]: record for record in self.records}

    def _available_events(self):
        events = {str(event.get("name", "") or "").strip() for event in self.events if event.get("name")}
        events.update(event for record in self.records for event in record_events(record))
        return sorted(events, key=normalize)

    def _ensure_events_from_records(self):
        known = {normalize(event.get("name", "")) for event in self.events if event.get("name")}
        for name in sorted({value for record in self.records for value in record_events(record)}, key=normalize):
            if normalize(name) not in known:
                self.events.append(empty_event(name, self.task_templates))
                known.add(normalize(name))

    def _migrate_future_absence(self, payload: dict) -> int:
        """Haal de no-shows weg bij evenementen die nog moeten plaatsvinden.

        Tot bestandsversie 11 kende EventHub alleen aanwezig of niet, en werd
        alles wat geen aanwezigheid was een no-show. Bij een evenement dat nog
        komt kan dat niet kloppen: er is nog niemand weggebleven. Vanaf versie
        12 heet die stand onbekend, en deze migratie brengt oudere dossiers
        eenmalig op orde.
        """
        try:
            version = int(payload.get("version", 0) or 0)
        except (TypeError, ValueError):
            version = 0
        if version >= 12:
            return 0
        today = date.today()
        toekomstig = []
        for event in self.events:
            event_date = parse_date(str(event.get("date", "") or ""))
            if event_date and event_date > today:
                toekomstig.append(event.get("name", ""))
        return clear_absence_for_events(self.records, toekomstig)

    def _ensure_event_date_names(self):
        """Migrate dated events and every participant link to the standard title."""
        renamed = {}
        used = set()
        for event in self.events:
            old_name = str(event.get("name", "") or "").strip()
            new_name = event_name_with_date(old_name, event.get("date", ""))
            candidate = new_name
            sequence = 2
            while normalize(candidate) in used:
                candidate = f"{new_name} ({sequence})"
                sequence += 1
            used.add(normalize(candidate))
            event["name"] = candidate
            if old_name and old_name != candidate:
                renamed[old_name] = candidate
        if renamed:
            for record in self.records:
                names = [renamed.get(name, name) for name in record_events(record)]
                record["Evenement"] = "; ".join(dict.fromkeys(filter(None, names)))
        return renamed

    def _event_by_id(self, event_id: str):
        return next((event for event in self.events if event.get("id") == event_id), None)

    def _touch_event(self, event, opened: bool = False):
        """Noteer dat er aan dit evenement is gewerkt.

        De kaarten in de kiezer laten zien waar je het laatst was; zonder deze
        twee tijdstippen is die volgorde niet te maken.
        """
        if not event:
            return
        nu = datetime.now().isoformat(timespec="minutes")
        if opened:
            event["last_opened_at"] = nu
        else:
            event["updated_at"] = nu

    def _event_by_name(self, name: str):
        wanted = normalize(name)
        return next((event for event in self.events if normalize(event.get("name", "")) == wanted), None)

    def _event_sort_key(self, event: dict):
        """Wat eraan komt eerst, daarna het verleden van recent naar oud.

        Puur chronologisch oplopend sorteren zette het oudste — en dus altijd
        het afgeronde — bovenaan, terwijl je vrijwel altijd met de eerstvolgende
        evenementen werkt. Afgerond en Geannuleerd horen bij het verleden, ook
        als de datum toevallig nog in de toekomst ligt.
        """
        event_date = parse_date(event.get("date", ""))
        name = normalize(event.get("name", ""))
        if event_date is None:
            # Zonder datum onderaan: er valt niets over de actualiteit te zeggen.
            return (2, 0, name)
        closed = event.get("status") in {"Afgerond", "Geannuleerd"}
        if event_date >= date.today() and not closed:
            return (0, event_date.toordinal(), name)
        # Negatief sorteert het verleden aflopend: het meest recente eerst.
        return (1, -event_date.toordinal(), name)

    def _attach_row_menu(self, table, actions):
        """Geef een tabel een rechtermuismenu met acties op de gekozen rij.

        Rij-acties stonden als knoppenrij boven elke tabel. Die rijen groeiden
        mee met de applicatie en namen ruimte in terwijl ze alleen bruikbaar
        zijn zodra er iets geselecteerd is. Aanmaken blijft wel een knop: bij
        een lege tabel valt er niets aan te wijzen.
        """
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda position, target=table, items=actions: self._show_row_menu(target, items, position)
        )

    def _show_row_menu(self, table, actions, position):
        row = table.rowAt(position.y())
        if row < 0 or table.isRowHidden(row):
            return
        table.selectRow(row)
        menu = QMenu(table)
        for label, handler in actions:
            if label is None:
                menu.addSeparator()
                continue
            menu.addAction(label, handler)
        menu.exec(table.viewport().mapToGlobal(position))

    def _set_event_view(self, modus: str):
        """Kaarten of de compacte tabel; de keuze blijft bewaard."""
        kaarten = str(modus or "kaarten") != "lijst"
        self.event_view_stack.setCurrentIndex(0 if kaarten else 1)
        # Op de knop staat waar je heen gaat, niet waar je bent.
        self.view_toggle_button.setText("Lijst" if kaarten else "Kaarten")
        self.view_toggle_button.setToolTip(
            "Toon de evenementen als compacte lijst" if kaarten
            else "Toon de evenementen als kaarten"
        )
        self.settings.setValue("event_view_mode", "kaarten" if kaarten else "lijst")

    def _toggle_event_view(self):
        self._set_event_view("lijst" if self.event_view_stack.currentIndex() == 0 else "kaarten")

    def _visitors_by_event(self, events):
        """De deelnemers per evenement, in een doorloop van de aanmeldingen.

        Per evenement apart zoeken betekent bij elke toetsaanslag in het
        zoekvak de hele deelnemerslijst maal het aantal evenementen; zo blijft
        het een enkele ronde.
        """
        op_naam = {}
        for event in events:
            op_naam.setdefault(normalize(event.get("name", "")), []).append(str(event.get("id", "")))
        gevonden = {str(event.get("id", "")): [] for event in events}
        for record in self.records:
            if is_skipped(record):
                continue
            for naam in record_events(record):
                for sleutel in op_naam.get(normalize(naam), []):
                    gevonden[sleutel].append(record)
        return gevonden

    def _registration_lines(self, events) -> dict:
        """Aanmeldingen per evenement voor het keuzevenster, in één doorloop."""
        bezoekers = self._visitors_by_event(events)
        regels = {}
        for event in events:
            event_id = str(event.get("id", "") or "")
            if self._event_is_anonymized(event):
                snapshot = historical_scope(event)
                if snapshot is not None and "aangemeld" in snapshot:
                    regels[event_id] = f"<b>{snapshot['aangemeld']}</b> aanmeldingen · geanonimiseerd"
                else:
                    regels[event_id] = "Geanonimiseerd · historische cijfers niet beschikbaar"
                continue
            deelnemers = bezoekers.get(event_id, [])
            introducees = sum(1 for record in deelnemers if is_introducee(record))
            regel = f"<b>{len(deelnemers)}</b> {'aanmelding' if len(deelnemers) == 1 else 'aanmeldingen'}"
            if introducees:
                regel += f" · waarvan {introducees} introducé"
            regels[event_id] = regel
        return regels

    def _card_figures(self, event: dict, visitors, geweest: bool) -> str:
        """De cijfers op een kaart: wat er nog moet, of hoe het is gelopen."""
        if self._event_is_anonymized(event):
            snapshot = historical_scope(event)
            if snapshot is None:
                return "Geanonimiseerd · historische cijfers niet beschikbaar"
            parts = ["Geanonimiseerd", f"<b>{snapshot['aangemeld']}</b> aangemeld"]
            for key, label in (("aanwezig", "aanwezig"), ("noshows", "no-shows"),
                               ("afgemeld", "afgemeld"), ("onbekend", "onbekend")):
                if key in snapshot:
                    parts.append(f"<b>{snapshot[key]}</b> {label}")
            return " · ".join(parts)
        if geweest:
            tellingen = attendance_counts(visitors, str(event.get("name", "") or ""))
            delen = [
                f"<b>{len(visitors)}</b> aangemeld",
                f"<b>{tellingen.get(AANWEZIG, 0)}</b> aanwezig",
                f"<b>{tellingen.get(AFWEZIG, 0)}</b> niet gekomen",
            ]
            if tellingen.get(AFGEMELD, 0):
                delen.append(f"<b>{tellingen[AFGEMELD]}</b> afgemeld")
            if visitors:
                delen.append(f"<b>{turnout_percentage(tellingen):.0f}%</b> opkomst")
            return "  \u00b7  ".join(delen)
        delen = [f"<b>{len(visitors)}</b> aanmeldingen"]
        open_taken = sum(1 for taak in event_tasks(event) if not taak.get("done"))
        if open_taken:
            delen.append(f"<b>{open_taken}</b> taken open")
        documenten = len(event.get("attachments", []) or [])
        if documenten:
            delen.append(f"<b>{documenten}</b> documenten")
        return "  \u00b7  ".join(delen)

    def _event_is_anonymized(self, event: dict) -> bool:
        """Recognize retained aggregate statistics when the erase marker is missing."""
        if not event:
            return False
        if event.get("persoonsgegevens_gewist"):
            return True
        snapshot = historical_scope(event)
        if snapshot is None or int(snapshot.get("aangemeld", 0) or 0) <= 0:
            return False
        return not self._event_visitors(event, include_skipped=True)

    def _card_footnote(self, event: dict) -> str:
        delen = []
        if is_rudder_event_linked(event):
            delen.append("\U0001f517 Rudder \u00b7 " + human_sync_time(event.get("rudder_last_synced_at", "")))
        samengevoegd = self._event_listings(event)
        if samengevoegd:
            delen.append(f"{len(samengevoegd)} inschrijvingen")
        laatste = event_activity_line(event)
        if laatste:
            delen.append(laatste)
        return "  \u00b7  ".join(delen)

    def _refresh_event_board(self, events):
        """Bouw één rustig kaartenbord; archiefzichtbaarheid komt uit het filter."""
        bord = getattr(self, "event_board_layout", None)
        if bord is None:
            return
        # De kaart met de focus verdwijnt bij het opnieuw opbouwen. Qt legt de
        # focus dan op de eerstvolgende knop en het scrollvenster springt daar
        # naartoe - meestal helemaal naar beneden. Onthoud dus waar je stond,
        # en of de focus hier lag: zoek je in het zoekvak, dan blijft die daar.
        balk = self.event_board.verticalScrollBar()
        stand = balk.value()
        actief = QApplication.focusWidget()
        focus_op_bord = bool(actief is not None and self.event_board.isAncestorOf(actief))
        while bord.count():
            item = bord.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Eerst verbergen, dan pas losknippen: een zichtbare widget
                # zonder ouder is een los venster en dat flitst over het
                # scherm. Losknippen moet wel, anders blijven de oude kaarten
                # tot de volgende ronde in de boom staan en tellen ze dubbel.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._event_cards = []

        bezoekers = self._visitors_by_event(events)
        rooster_houder = QWidget(self.event_board.widget())
        rooster_houder.setObjectName("eventBoardBody")
        rooster = QGridLayout(rooster_houder)
        rooster.setContentsMargins(0, 0, 0, 6)
        rooster.setSpacing(10)
        for index, event in enumerate(events):
            deelnemers = bezoekers.get(str(event.get("id", "")), [])
            kaart = EventOverviewCard(
                event,
                cijfers=self._card_figures(event, deelnemers, event_has_passed(event)),
                voet=self._card_footnote(event),
                geweest=event_has_passed(event),
            )
            kaart.aangeklikt.connect(self._select_event_row)
            kaart.geopend.connect(self._open_event_from_card)
            kaart.menu_gevraagd.connect(self._show_card_menu)
            kaart.markeer(kaart.event_id == self._board_selected_id)
            rooster.addWidget(kaart, index // 2, index % 2)
            self._event_cards.append(kaart)
        rooster.setColumnStretch(0, 1)
        rooster.setColumnStretch(1, 1)
        bord.addWidget(rooster_houder)
        if not events:
            leeg = QLabel("Geen evenementen gevonden.")
            leeg.setObjectName("hintLabel")
            bord.addWidget(leeg)
        bord.addStretch(1)

        if focus_op_bord:
            self.event_board.setFocus(Qt.FocusReason.OtherFocusReason)
        # Eerst de layout laten rekenen: zolang de hoogte nog niet klaar is,
        # loopt de schuifbalk maar tot nul en wordt de stand afgekapt.
        bord.activate()
        inhoud = self.event_board.widget()
        if inhoud is not None:
            inhoud.adjustSize()
        balk.setValue(stand)
        # En nog een keer zodra Qt zelf klaar is met opnieuw indelen. Met het
        # scrollvenster als context vervalt dit vanzelf als het venster sluit.
        QTimer.singleShot(0, self.event_board, lambda waarde=stand: balk.setValue(waarde))

    def _board_section(self, sleutel: str, titel: str, events, bezoekers: dict) -> QWidget:
        """Een groep kaarten onder een kop die je kunt in- en uitklappen."""
        houder = QWidget()
        houder.setObjectName("eventBoardBody")
        buiten = QVBoxLayout(houder)
        buiten.setContentsMargins(0, 0, 0, 0)
        buiten.setSpacing(4)

        ingeklapt = bool(self._board_collapsed.get(sleutel, False)) and not self._board_searching
        kop = QPushButton(f"{'\u25b8' if ingeklapt else '\u25be'}  {titel}  ({len(events)})")
        kop.setObjectName("boardSectionToggle")
        kop.setCursor(Qt.CursorShape.PointingHandCursor)
        kop.clicked.connect(lambda _checked=False, naam=sleutel: self._toggle_board_section(naam))
        buiten.addWidget(kop)

        # Met houder als ouder: een widget zonder ouder die zichtbaar wordt
        # gemaakt is een los venster, en dat flitst over het scherm tot de
        # layout hem opneemt.
        rooster_houder = QWidget(houder)
        rooster_houder.setObjectName("eventBoardBody")
        rooster = QGridLayout(rooster_houder)
        rooster.setContentsMargins(0, 0, 0, 6)
        rooster.setSpacing(10)
        geweest = sleutel == "geweest"
        # Een ingeklapte groep krijgt geen kaarten: onzichtbaar bouwen kost bij
        # elke toetsaanslag in het zoekvak tijd voor niets.
        for index, event in enumerate([] if ingeklapt else events):
            deelnemers = bezoekers.get(str(event.get("id", "")), [])
            kaart = EventOverviewCard(
                event,
                cijfers=self._card_figures(event, deelnemers, geweest),
                voet=self._card_footnote(event),
                geweest=geweest,
            )
            kaart.aangeklikt.connect(self._select_event_row)
            kaart.geopend.connect(self._open_event_from_card)
            kaart.menu_gevraagd.connect(self._show_card_menu)
            kaart.markeer(kaart.event_id == self._board_selected_id)
            rooster.addWidget(kaart, index // 2, index % 2)
            self._event_cards.append(kaart)
        rooster.setColumnStretch(0, 1)
        rooster.setColumnStretch(1, 1)
        buiten.addWidget(rooster_houder)
        rooster_houder.setVisible(not ingeklapt)
        return houder

    def _toggle_board_section(self, sleutel: str):
        self._board_collapsed[sleutel] = not self._board_collapsed.get(sleutel, False)
        self._refresh_event_board(self._board_pending)

    def _select_event_row(self, event_id: str):
        """De tabel blijft de bron van de selectie, ook als je op een kaart klikt.

        Zo werken Openen, Aanpassen, Status en Verwijderen in beide weergaven
        op precies hetzelfde evenement.
        """
        gezocht = str(event_id or "")
        table = self.home_event_table
        for row in range(table.rowCount()):
            if self._event_id_for_row(row) == gezocht:
                table.selectRow(row)
                break
        self._board_selected_id = gezocht
        for kaart in self._event_cards:
            kaart.markeer(kaart.event_id == gezocht)

    def _open_event_from_card(self, event_id: str):
        self._select_event_row(event_id)
        self.activate_selected_event()

    def _show_card_menu(self, event_id: str, punt):
        self._select_event_row(event_id)
        event = self._event_by_id(str(event_id or ""))
        if event:
            self._event_actions_menu(event, self).exec(punt)

    def _show_event_context_menu(self, position):
        table = self.home_event_table
        row = table.rowAt(position.y())
        if row < 0 or table.isRowHidden(row):
            return
        table.selectRow(row)
        event = self._event_by_id(self._event_id_for_row(row))
        if not event:
            return
        self._event_actions_menu(event, table).exec(table.viewport().mapToGlobal(position))

    def _event_actions_menu(self, event: dict, parent) -> QMenu:
        """De acties bij een evenement, gelijk vanuit de tabel en vanaf een kaart."""
        menu = QMenu(parent)
        menu.addAction("Openen", self.activate_selected_event)
        menu.addAction("Aanpassen", self.edit_selected_event)
        status_menu = menu.addMenu("Status")
        current = str(event.get("status", "") or "")
        automatic = not event.get("status_manual")
        for label in [AUTOMATIC_STATUS, *EVENT_STATUSES]:
            action = status_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(automatic if label == AUTOMATIC_STATUS else (not automatic and label == current))
            action.triggered.connect(
                lambda _checked=False, value=label, target=event: self._set_event_status(target, value)
            )
        menu.addAction("Samenvoegen met...", self.merge_selected_events)
        menu.addAction("Opslaan als template", lambda: self.save_active_event_as_template(event=event))
        menu.addAction("Evenementen aan template koppelen…", lambda: self.link_events_to_template(event))
        menu.addSeparator()
        menu.addAction(
            "Terugzetten uit archief" if event.get("archived") else "Archiveren",
            lambda _checked=False, target=event: self._set_event_archived(
                target, not bool(target.get("archived"))
            ),
        )
        menu.addAction("Verwijderen", self.remove_selected_event)
        return menu

    def _set_event_archived(self, event: dict, archived: bool):
        """Verberg een evenement uit het werkoverzicht zonder gegevens te wissen."""
        if archived:
            event["archived"] = True
            event.pop("archive_exempt", None)
        else:
            event.pop("archived", None)
            # Een bewust teruggezet oud evenement blijft zichtbaar en wordt
            # niet bij de eerstvolgende schermverversing opnieuw gearchiveerd.
            event["archive_exempt"] = True
        self._touch_event(event)
        self._mark_dirty()
        self._render_management()
        self.status_label.setText(
            f"{event.get('name', 'Evenement')} is "
            + ("gearchiveerd." if archived else "teruggezet uit het archief.")
        )

    def _archive_passed_events(self) -> bool:
        """Archiveer een evenement zodra de bekende eindtijd voorbij is."""
        changed = False
        for event in self.events:
            if (
                event_has_passed(event)
                and not event.get("archived")
                and not event.get("archive_exempt")
            ):
                event["archived"] = True
                changed = True
        return changed

    def _set_event_status(self, event: dict, status: str):
        """Zet de status vanuit het overzicht, of geef hem terug aan de automatiek."""
        if status == AUTOMATIC_STATUS:
            event.pop("status_manual", None)
            self._sync_event_status_from_tasks(event)
            message = f"Status van {event.get('name', 'evenement')} wordt weer automatisch bepaald."
        else:
            event["status"] = status
            event["status_manual"] = True
            self._touch_event(event)
            message = f"Status van {event.get('name', 'evenement')} staat op {status}."
        self._mark_dirty()
        self._render_all()
        self.status_label.setText(message)

    def _events_in_display_order(self):
        """De evenementen zoals ze in het overzicht moeten staan.

        Klikken op de kolomkop kan hier niet: de kolom Evenement gebruikt een
        cel-widget, en die verhuist niet mee wanneer Qt de rijen omwisselt.
        Daarom sorteren we de gegevens en bouwen we de tabel opnieuw op.
        """
        mode = "smart"
        if hasattr(self, "event_sort_mode"):
            mode = str(self.event_sort_mode.currentData() or "smart")
        if mode == "name":
            return sorted(self.events, key=lambda event: normalize(event.get("name", "")))
        if mode in {"date_asc", "date_desc"}:
            def key(event):
                event_date = parse_date(event.get("date", ""))
                # Evenementen zonder datum blijven onderaan, in beide richtingen.
                return (event_date is None, event_date or date.min, normalize(event.get("name", "")))
            dated = [event for event in self.events if parse_date(event.get("date", ""))]
            undated = [event for event in self.events if not parse_date(event.get("date", ""))]
            dated.sort(key=key, reverse=(mode == "date_desc"))
            undated.sort(key=lambda event: normalize(event.get("name", "")))
            return dated + undated
        return sorted(self.events, key=self._event_sort_key)

    def _event_sort_changed(self, *_):
        self.settings.setValue("event_sort_mode", str(self.event_sort_mode.currentData() or "smart"))
        self._render_management()

    def _show_archived_events_changed(self, checked: bool):
        self.settings.setValue("show_archived_events", bool(checked))
        self._filter_events()

    def _filter_events(self, *_):
        """Filter het evenementenoverzicht op zoektekst en status."""
        table = getattr(self, "home_event_table", None)
        if table is None or not hasattr(self, "event_search_box"):
            return
        needle = normalize(self.event_search_box.text())
        wanted_status = str(self.event_status_filter.currentData() or "")
        soort_filter = getattr(self, "event_type_filter", None)
        wanted_type = str(soort_filter.currentData() or "") if soort_filter is not None else ""
        datum_veld = getattr(self, "event_date_filter", None)
        wanted_date = parse_date(datum_veld.text()) if datum_veld is not None else None
        show_archived = bool(
            getattr(self, "show_archived_events", None)
            and self.show_archived_events.isChecked()
        )
        visible = 0
        for row in range(table.rowCount()):
            event = self._event_by_id(self._event_id_for_row(row))
            if event is None:
                table.setRowHidden(row, bool(needle) or bool(wanted_status))
                continue
            status = str(event.get("status", "") or "")
            if wanted_status == "_open":
                matches_status = status not in {"Afgerond", "Geannuleerd"}
            else:
                matches_status = not wanted_status or status == wanted_status
            haystack = normalize(" ".join(str(event.get(field, "") or "") for field in (
                "name", "date", "event_type", "place", "location", "status", "target_audience",
            )))
            matches_search = not needle or needle in haystack
            matches_type = not wanted_type or str(event.get("event_type", "") or "") == wanted_type
            matches_date = not wanted_date or parse_date(event.get("date", "")) == wanted_date
            matches_archive = show_archived or not bool(event.get("archived", False))
            hidden = not (
                matches_status and matches_search and matches_type and matches_date and matches_archive
            )
            table.setRowHidden(row, hidden)
            visible += not hidden
        total = table.rowCount()
        self.event_filter_summary.setText(
            "" if visible == total else f"{visible} van {total} getoond"
        )
        if getattr(self, "event_board_layout", None) is not None:
            zichtbaar = [self._event_by_id(self._event_id_for_row(row))
                         for row in range(total) if not table.isRowHidden(row)]
            self._board_pending = [event for event in zichtbaar if event]
            # Zoek je iets, dan hoort het resultaat in beeld te staan en niet
            # verstopt onder een ingeklapte kop.
            self._board_searching = bool(needle or wanted_status or wanted_type or wanted_date)
            self._board_timer.start()

    def _event_id_for_row(self, row: int) -> str:
        item = self.home_event_table.item(row, 0)
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _event_listings(self, event: dict):
        """De aanmeldpagina's waaruit dit evenement is opgebouwd, met aantallen.

        Leeg zolang een evenement niet is samengevoegd; dan is er ook niets te
        tonen en blijft het scherm zoals het was.
        """
        listings = event.get("listings", []) or []
        if len(listings) < 2:
            return []
        visitors = self._event_visitors(event)
        gevonden = []
        for listing in listings:
            label = str(listing.get("label", "") or "").strip()
            if not label:
                continue
            aantal = sum(
                1 for record in visitors
                if any(normalize(name) == normalize(label) for name in registrations(record))
            )
            gevonden.append((label, aantal))
        return gevonden

    def _event_visitors(self, event: dict, include_skipped: bool = False):
        if event.get("persoonsgegevens_gewist"):
            return []
        wanted = normalize(event.get("name", ""))
        gevonden = [record for record in self.records
                    if any(normalize(name) == wanted for name in record_events(record))]
        return gevonden if include_skipped else [r for r in gevonden if not is_skipped(r)]

    def _selected_management_event(self, table=None):
        table = table or self.event_table
        row = table.currentRow()
        if row < 0:
            return None
        # Een weggefilterde rij blijft in Qt de huidige rij. Zonder deze controle
        # werken Openen, Aanpassen en vooral Verwijderen op een evenement dat
        # niet in beeld staat.
        if table.isRowHidden(row):
            return None
        item = table.item(row, 0)
        return self._event_by_id(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _combo_event(self, combo):
        return self._event_by_id(combo.current_id())

    def _sync_event_combo(self, combo):
        """Laat elke schermkiezer dezelfde, gedeelde evenementcontext tonen."""
        gekozen = self._active_event()
        huidig = str(gekozen.get("id", "")) if gekozen else ""
        combo.set_events(sorted(self.events, key=self._event_sort_key), huidig)

    def _sync_event_context_pickers(self):
        """Werk alle evenementgebonden menu's direct en zonder extra signalen bij."""
        for naam in ("event_control_event_combo", "after_sales_event_combo"):
            combo = getattr(self, naam, None)
            if combo is not None:
                self._sync_event_combo(combo)

    def _recent_activity(self):
        try:
            value = json.loads(self.settings.value("home_recent_activity", "[]"))
        except Exception:
            value = []
        return value if isinstance(value, list) else []

    def _add_recent_activity(self, text: str):
        text = str(text or "").strip()
        if not text:
            return
        items = self._recent_activity()
        items.insert(0, {"at": datetime.now().isoformat(timespec="minutes"), "text": text})
        self.settings.setValue("home_recent_activity", json.dumps(items[:8], ensure_ascii=False))
        self._render_recent_activity()

    def _render_recent_activity(self):
        if not hasattr(self, "home_activity_label"):
            return
        items = self._recent_activity()[:5]
        if not items:
            self.home_activity_label.setText("Nog geen recente activiteit.")
            return
        today = date.today()
        lines = []
        for item in items:
            try:
                stamp = datetime.fromisoformat(str(item.get("at", "")))
                prefix = stamp.strftime("%H:%M") if stamp.date() == today else stamp.strftime("%d-%m · %H:%M")
            except Exception:
                prefix = "•"
            lines.append(f"{prefix}   {item.get('text', '')}")
        self.home_activity_label.setText("\n".join(lines))

    def _render_management(self):
        if not hasattr(self, "event_table"):
            return
        if hasattr(self, "event_control_event_combo"):
            self._sync_event_combo(self.event_control_event_combo)
        if hasattr(self, "after_sales_event_combo"):
            self._sync_event_combo(self.after_sales_event_combo)
        events = self._events_in_display_order()
        profile_name = self.profile.get("name") or "collega"
        self.home_welcome.setText(f"Evenementen · {profile_name}")
        if hasattr(self, "start_welcome"):
            hour = datetime.now().hour
            greeting = "Goedemorgen" if hour < 12 else ("Goedemiddag" if hour < 18 else "Goedenavond")
            self.start_welcome.setText(f"{greeting}, {profile_name}")
            weekdays = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
            months = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
            now = date.today()
            self.start_date_label.setText(f"{weekdays[now.weekday()].capitalize()} {now.day} {months[now.month - 1]} · dit vraagt nu je aandacht")
            self._render_recent_activity()

            active = self._active_event()
            if active:
                self.home_continue_title.setText(str(active.get("name", "Evenement")))
                self.home_continue_meta.setText("Laatst gebruikte evenementcontext · open het dossier om verder te werken.")
                self.home_continue_button.setEnabled(True)
                self.home_continue_button.setVisible(True)
            else:
                self.home_continue_title.setText("Nog geen recente werkcontext")
                self.home_continue_meta.setText("Open een evenement om hier later direct verder te gaan.")
                self.home_continue_button.setEnabled(False)
                # Zonder werkcontext heeft de knop geen doel: verbergen i.p.v. grijs tonen.
                self.home_continue_button.setVisible(False)

            open_rows = self._open_task_rows()
            overdue = sum(1 for due, *_ in open_rows if self._task_bucket(due) == "Te laat")
            due_today = sum(1 for due, *_ in open_rows if self._task_bucket(due) == "Vandaag")
            attention = []
            if overdue:
                attention.append(f"⚠ {overdue} taak/taken te laat")
            if due_today:
                attention.append(f"• {due_today} taak/taken vandaag")
            self.home_attention_label.setText("\n".join(attention) if attention else "✓ Alles op orde\nEventHub ziet op dit moment geen bijzonderheden.")

            todays = [event for event in events if parse_date(event.get("date", "")) == now and event.get("status") != "Geannuleerd"]
            if todays:
                today_event = todays[0]
                self._home_today_event_id = str(today_event.get("id", ""))
                visitors = len(self._event_visitors(today_event))
                self.home_today_title.setText(str(today_event.get("name", "Evenement")))
                meta = " · ".join(filter(None, [str(today_event.get("start_time", "") or ""), str(today_event.get("place", "") or today_event.get("location", "") or "")]))
                self.home_today_meta.setText(f"{visitors} deelnemers" + (f" · {meta}" if meta else ""))
                self.home_today_button.setText("Evenement openen →")
                self.home_today_button.setEnabled(True)
                self.home_today_live_button.setEnabled(True)
                self.home_today_button.setVisible(True)
                self.home_today_live_button.setVisible(True)
            else:
                # Een live sessie hoort bij een evenement van vandaag; buiten die dag
                # heeft de knop geen doel.
                self.home_today_live_button.setEnabled(False)
                self.home_today_live_button.setVisible(False)
                self.home_today_title.setText("Geen evenementen vandaag")
                next_events = self._upcoming_events()
                if next_events:
                    # Maak het lege blok bruikbaar: wijs naar het eerstvolgende evenement.
                    next_event = next_events[0]
                    self._home_today_event_id = str(next_event.get("id", ""))
                    next_date = parse_date(next_event.get("date", ""))
                    days_until = (next_date - now).days if next_date else None
                    if days_until == 1:
                        when = "morgen"
                    elif days_until and days_until > 1:
                        when = f"over {days_until} dagen"
                    else:
                        when = "binnenkort"
                    meta = " · ".join(filter(None, [
                        str(next_event.get("start_time", "") or ""),
                        str(next_event.get("place", "") or next_event.get("location", "") or ""),
                    ]))
                    self.home_today_meta.setText(
                        f"Volgende: {next_event.get('name', 'Evenement')} · {when}"
                        + (f" · {meta}" if meta else "")
                    )
                    self.home_today_button.setText("Volgende evenement openen →")
                    self.home_today_button.setEnabled(True)
                    self.home_today_button.setVisible(True)
                else:
                    self._home_today_event_id = ""
                    self.home_today_meta.setText("Je planning is vandaag leeg.")
                    self.home_today_button.setEnabled(False)
                    self.home_today_button.setVisible(False)
        self.home_event_table.setRowCount(len(events))
        for row_index, event in enumerate(events):
            visitors = self._event_visitors(event)
            home_values = [
                event.get("date", ""), event.get("name", ""),
                event.get("event_type", "Meeloopdag"),
                " — ".join(filter(None, [event.get("place", ""), event.get("location", "")])),
                event.get("status", ""), str(len(visitors)),
            ]
            for column, value in enumerate(home_values):
                item = QTableWidgetItem(str(value or ""))
                item.setData(Qt.ItemDataRole.UserRole, event.get("id", ""))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.home_event_table.setItem(row_index, column, item)
            rudder_connected = is_rudder_event_linked(event)
            if rudder_connected:
                sync_text = human_sync_time(event.get("rudder_last_synced_at", ""))
                rudder_text = f"🔗 Rudder gekoppeld · Laatst gesynchroniseerd: {sync_text}"
            else:
                rudder_text = "Niet gekoppeld aan Rudder"
            samengevoegd = self._event_listings(event)
            if samengevoegd:
                rudder_text = f"{rudder_text} · {len(samengevoegd)} inschrijvingen"
            event_item = self.home_event_table.item(row_index, 1)
            event_item.setText(f"{event.get('name', '')}\n{rudder_text}")
            cell = QWidget()
            cell.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(8, 4, 6, 4)
            cell_layout.setSpacing(1)
            name_label = QLabel(str(event.get("name", "") or "Onbenoemd evenement"))
            tooltip = str(event.get("name", "") or "Onbenoemd evenement")
            if samengevoegd:
                tooltip += "\nSamengevoegd uit: " + " · ".join(
                    f"{label} ({aantal})" for label, aantal in samengevoegd
                )
            name_label.setToolTip(tooltip)
            status_label = QLabel(rudder_text)
            status_label.setStyleSheet("color: #7f8ba0; font-size: 11px;")
            cell_layout.addWidget(name_label)
            cell_layout.addWidget(status_label)
            self.home_event_table.setCellWidget(row_index, 1, cell)
            self.home_event_table.setRowHeight(row_index, 44)
        # De tabel is opnieuw opgebouwd, dus de zoek- en statusfilters moeten
        # opnieuw worden toegepast; anders komt alles weer zichtbaar terug.
        self._filter_events()

        notifications = self._all_notifications()
        self.notification_button.setText(f"🔔  {len(notifications)}")
        self.notification_button.setProperty("hasNotifications", bool(notifications))
        self.notification_button.style().unpolish(self.notification_button)
        self.notification_button.style().polish(self.notification_button)
        self.notification_button.setToolTip(
            f"{len(notifications)} actieve melding(en)" if notifications else "Geen actieve meldingen"
        )
        task_tab_index = self.tabs.indexOf(self.tasks_tab)
        if task_tab_index >= 0:
            active_notifications = sum(
                notification["event_id"] == self.active_event_id for notification in notifications
            )
            self.tabs.setTabText(
                task_tab_index,
                f"Taken ({active_notifications})" if active_notifications else "Taken",
            )
        self._update_event_workspace_header()
        self._render_rudder_tab()
        self._render_task_table()
        self._render_open_tasks_page()
