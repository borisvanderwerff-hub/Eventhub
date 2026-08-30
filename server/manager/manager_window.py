from __future__ import annotations

import re
import sqlite3
import sys
import threading
import webbrowser
import json
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QMessageBox, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QGridLayout, QLineEdit, QApplication, QScrollArea,
    QInputDialog, QCheckBox, QDialogButtonBox, QComboBox, QSizePolicy, QMenu,
)

# server/ is self-contained: this only needs the *parent of server/* on
# sys.path so that `import server...` resolves regardless of the current
# working directory — it does not reach into any EventHub Desktop files.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from server import importer, network
from server.database import connect, close_database, backup_database
from server.exporter import export_participants_workbook, COLUMNS
from server.logging_setup import get_logger
from server.manager.theme import build_stylesheet
from server.paths import exports_directory, logs_directory, backups_directory
from server.qrgen import generate_matrix
from server.services import client_service, emergency_service, participant_service, session_service
from server.web.app import create_app

logger = get_logger("manager")


def _record_event_names(record: dict) -> list[str]:
    """Evenementnamen van één EventHub-record (veld ``Evenement``, ; of , gescheiden)."""
    raw = str(record.get("Evenement", "") or "").replace(";", ",")
    return [value.strip() for value in raw.split(",") if value.strip()]


def _set_record_presence(record: dict, event_name: str, present: bool) -> bool:
    """Zet aanwezigheid voor één evenement in een EventHub-record.

    Spiegelt ``bezoekerslijst_core.set_present``; bewust hier gedupliceerd
    omdat server/ zelfstandig blijft en niet in Desktop-bestanden grijpt.
    Bestandsversie 10 en ouder had één boolean per persoon; die wordt hier
    naar het dict-formaat per evenement gemigreerd.
    """
    value = record.get("Aanwezig", False)
    if isinstance(value, dict):
        presence = {str(name): bool(flag) for name, flag in value.items()}
    else:
        presence = {name: bool(value) for name in _record_event_names(record)}
    wanted = event_name.strip().casefold()
    key = next((name for name in presence if name.strip().casefold() == wanted), event_name)
    changed = bool(presence.get(key, False)) != bool(present)
    presence[key] = bool(present)
    record["Aanwezig"] = presence
    return changed


def _compact(button: QPushButton) -> QPushButton:
    button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return button

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DEFAULT_PORT = 8080


class ServerThread(threading.Thread):
    """Runs the Flask app in a background thread so the Qt GUI stays responsive.

    Uses Flask's built-in threaded dev server. This is adequate for a LAN
    event with a handful of clients; swapping in a production WSGI server
    (waitress) is a drop-in change noted in the project README as a
    follow-up once that package can be installed on the build machine.
    """

    def __init__(self, app, host: str, port: int):
        super().__init__(daemon=True)
        self.app = app
        self.host = host
        self.port = port
        self._server = None

    def run(self):
        from werkzeug.serving import make_server
        self._server = make_server(self.host, self.port, self.app, threaded=True)
        logger.info("EventHub Server luistert op %s:%s", self.host, self.port)
        self._server.serve_forever()

    def stop(self):
        if self._server is not None:
            self._server.shutdown()


class ManagerWindow(QMainWindow):
    attendance_changed = Signal()

    def __init__(self, session_result, parent=None):
        super().__init__(parent)
        self.session_result = session_result
        self.event_id = session_result.id
        self.db_path = session_result.db_path
        self.connection = connect(self.db_path)
        self.app = create_app(self.db_path, self.event_id)
        self.server_thread: ServerThread | None = None
        self.server_started_at: datetime | None = None
        self.discovery_responder = None
        self._closing = False
        self._attendance_signature = None
        self.event_code = session_service.ensure_event_code(self.connection)

        self.setWindowTitle("EventHub 2 • Event Control")
        self.setMinimumSize(940, 680)
        self.resize(1120, 900)
        self.setStyleSheet(build_stylesheet(dark_mode=True))
        icon_path = ASSETS_DIR / "eventhub_server.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll_area)

        central = QWidget()
        scroll_area.setWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("masthead")
        header_layout = QHBoxLayout(header)
        logo_path = ASSETS_DIR / "eventhub_logo.png"
        if logo_path.is_file():
            logo = QLabel()
            logo.setPixmap(QPixmap(str(logo_path)).scaled(
                58, 58, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            logo.setFixedSize(64, 64)
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(logo)
        heading_layout = QVBoxLayout()
        title = QLabel("Event Control")
        title.setObjectName("appTitle")
        subtitle = QLabel("Live sessie beheren en bezoekers inchecken  •  Powered by Cohentra Digital")
        subtitle.setObjectName("appSubtitle")
        heading_layout.addWidget(title)
        heading_layout.addWidget(subtitle)
        header_layout.addLayout(heading_layout)
        header_layout.addStretch(1)
        layout.addWidget(header)

        event_box = QFrame()
        event_box.setObjectName("toolbar")
        event_layout = QHBoxLayout(event_box)
        session = session_service.get_session(self.connection) or {}

        event_text = QVBoxLayout()
        event_text.setSpacing(2)
        event_text.addWidget(self._bold_label(session.get("name", "")))
        event_text.addWidget(QLabel(f"{session.get('date', '')} — {session.get('location', '')}"))
        event_layout.addLayout(event_text, 1)

        # Compact live status: the most important operational information stays
        # visible without a separate wall of summary cards.
        live_status = QVBoxLayout()
        live_status.setSpacing(2)
        self.session_live_label = QLabel("● Server gestopt")
        self.session_live_label.setObjectName("actionStatus")
        self.session_live_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.session_meta_label = QLabel("00:00:00  •  0 apparaten")
        self.session_meta_label.setObjectName("actionMeta")
        self.session_meta_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        live_status.addWidget(self.session_live_label)
        live_status.addWidget(self.session_meta_label)
        event_layout.addLayout(live_status)
        layout.addWidget(event_box)

        cards_layout = QGridLayout()
        self.participants_card, self.participants_value = self._summary_card("Bezoekerslijst", "0 geladen")
        self.inside_card, self.inside_value = self._summary_card("Nog binnen", "0")
        cards_layout.addWidget(self.participants_card, 0, 0)
        cards_layout.addWidget(self.inside_card, 0, 1)
        layout.addLayout(cards_layout)

        connect_box = QFrame()
        connect_box.setObjectName("toolbar")
        connect_layout = QHBoxLayout(connect_box)

        connect_text_layout = QVBoxLayout()
        connect_heading = QLabel("Verbinden vanaf een ander apparaat")
        connect_heading.setObjectName("cardHeading")
        connect_text_layout.addWidget(connect_heading)

        url_row = QHBoxLayout()
        self.connect_url_field = QLineEdit("Start eerst de server om een adres te tonen.")
        self.connect_url_field.setReadOnly(True)
        url_row.addWidget(self.connect_url_field, 1)
        copy_button = QPushButton("Kopiëren")
        copy_button.setObjectName("secondaryButton")
        copy_button.clicked.connect(self.copy_connect_url)
        url_row.addWidget(copy_button)
        connect_text_layout.addLayout(url_row)

        connect_hint = QLabel("Scan de QR-code met een telefoon of tablet op hetzelfde netwerk, of vul "
                               "het adres hierboven in de browser in. Bij het inloggen als incheck moet "
                               "de sessiecode hiernaast worden ingevuld.")
        connect_hint.setObjectName("hintLabel")
        connect_hint.setWordWrap(True)
        connect_text_layout.addWidget(connect_hint)

        open_connect_button = _compact(QPushButton("Verbindpagina openen"))
        open_connect_button.setObjectName("secondaryButton")
        open_connect_button.clicked.connect(self.open_connect_page)
        connect_text_layout.addWidget(open_connect_button)
        connect_text_layout.addStretch(1)

        self.qr_label = QLabel()
        self.qr_label.setFixedSize(160, 160)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setStyleSheet("background: #ffffff; border: 1px solid #d8e0eb; border-radius: 8px;")
        self._set_qr_placeholder()

        qr_column = QVBoxLayout()
        qr_column.addWidget(self.qr_label)
        code_heading = QLabel("Sessiecode")
        code_heading.setObjectName("hintLabel")
        code_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_column.addWidget(code_heading)
        self.event_code_label = QLabel(self._format_event_code(self.event_code))
        self.event_code_label.setObjectName("statisticsTitle")
        self.event_code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_column.addWidget(self.event_code_label)

        connect_layout.addLayout(connect_text_layout, 1)
        connect_layout.addLayout(qr_column)
        layout.addWidget(connect_box)

        # EventHub 2 action deck: one server command strip + three focused cards.
        actions = QVBoxLayout()
        actions.setSpacing(14)

        # SERVER — the single primary action for the live session.
        server_box, server_layout = self._action_section("SERVER")
        server_box.setProperty("tone", "server")
        server_buttons = QHBoxLayout()
        server_buttons.setSpacing(10)
        self.start_stop_button = QPushButton("Server starten")
        self.start_stop_button.setObjectName("primaryButton")
        self.start_stop_button.clicked.connect(self.toggle_server)
        self.dashboard_button = QPushButton("Dashboard")
        self.dashboard_button.setObjectName("secondaryButton")
        self.dashboard_button.clicked.connect(self.open_dashboard)
        self.connections_button = QPushButton("Apparaten")
        self.connections_button.setObjectName("secondaryButton")
        self.connections_button.clicked.connect(self.show_connections)
        server_buttons.addWidget(self.start_stop_button, 2)
        server_buttons.addWidget(self.dashboard_button, 1)
        server_buttons.addWidget(self.connections_button, 1)
        server_layout.addLayout(server_buttons)
        actions.addWidget(server_box)

        # Lower command deck: separate concerns instead of a mixed wall of buttons.
        command_grid = QGridLayout()
        command_grid.setHorizontalSpacing(14)
        command_grid.setVerticalSpacing(14)
        command_grid.setColumnStretch(0, 1)
        command_grid.setColumnStretch(1, 1)
        command_grid.setColumnStretch(2, 1)

        # BEZOEKERSLIJST
        participant_box, participant_layout = self._action_section("BEZOEKERSLIJST")
        participant_box.setProperty("tone", "participants")
        self.participant_action_status = QLabel("0 bezoekers geladen")
        self.participant_action_status.setObjectName("actionMeta")
        participant_layout.addWidget(self.participant_action_status)

        participant_top = QHBoxLayout()
        participant_top.setSpacing(8)
        import_button = QPushButton("Importeren")
        import_button.setObjectName("secondaryButton")
        import_button.clicked.connect(self.import_participants)
        manage_button = QPushButton("Beheren")
        manage_button.setObjectName("secondaryButton")
        manage_button.clicked.connect(self.manage_participants)
        participant_top.addWidget(import_button)
        participant_top.addWidget(manage_button)
        participant_layout.addLayout(participant_top)

        participant_bottom = QHBoxLayout()
        participant_bottom.setSpacing(8)
        export_button = QPushButton("Exporteren")
        export_button.setObjectName("secondaryButton")
        export_button.clicked.connect(self.export_participants)
        participant_bottom.addWidget(export_button, 1)

        participant_more = QPushButton("Meer  ▾")
        participant_more.setObjectName("tertiaryButton")
        participant_menu = QMenu(participant_more)
        sync_action = participant_menu.addAction("Dossier synchroniseren")
        sync_action.triggered.connect(self.sync_to_bvp)
        logs_action = participant_menu.addAction("Logmap openen")
        logs_action.triggered.connect(self.open_logs_folder)
        participant_more.setMenu(participant_menu)
        participant_bottom.addWidget(participant_more)
        participant_layout.addLayout(participant_bottom)
        participant_layout.addStretch(1)
        command_grid.addWidget(participant_box, 0, 0)

        # INCHECKEN
        checkin_box, checkin_layout = self._action_section("INCHECKEN")
        checkin_box.setProperty("tone", "checkin")
        self.checkin_action_status = QLabel("● Actief")
        self.checkin_action_status.setObjectName("actionStatus")
        checkin_layout.addWidget(self.checkin_action_status)

        checkin_hint = QLabel("Beheer het incheckproces voor alle verbonden apparaten.")
        checkin_hint.setObjectName("actionMeta")
        checkin_hint.setWordWrap(True)
        checkin_layout.addWidget(checkin_hint)
        checkin_layout.addStretch(1)

        checkin_buttons = QHBoxLayout()
        checkin_buttons.setSpacing(8)
        self.freeze_button = QPushButton("Pauzeren")
        self.freeze_button.setObjectName("secondaryButton")
        self.freeze_button.clicked.connect(self.toggle_freeze)
        self.stop_checkin_button = QPushButton("Stoppen")
        self.stop_checkin_button.setObjectName("dangerButton")
        self.stop_checkin_button.clicked.connect(self.stop_checkin)
        checkin_buttons.addWidget(self.freeze_button, 1)
        checkin_buttons.addWidget(self.stop_checkin_button, 1)
        checkin_layout.addLayout(checkin_buttons)
        command_grid.addWidget(checkin_box, 0, 1)

        # CALAMITEITEN
        emergency_box, emergency_layout = self._action_section("CALAMITEITEN")
        emergency_box.setProperty("tone", "emergency")
        self.emergency_action_status = QLabel("Alleen gebruiken bij een daadwerkelijke calamiteit.")
        self.emergency_action_status.setObjectName("actionMeta")
        self.emergency_action_status.setWordWrap(True)
        emergency_layout.addWidget(self.emergency_action_status)
        emergency_layout.addStretch(1)

        self.emergency_button = QPushButton("Calamiteitenmodus starten")
        self.emergency_button.setObjectName("dangerButton")
        self.emergency_button.clicked.connect(self.toggle_emergency)
        emergency_layout.addWidget(self.emergency_button)

        emergency_export_button = QPushButton("Registratie exporteren")
        emergency_export_button.setObjectName("secondaryButton")
        emergency_export_button.clicked.connect(self.export_emergency)
        emergency_layout.addWidget(emergency_export_button)
        command_grid.addWidget(emergency_box, 0, 2)

        actions.addLayout(command_grid)
        layout.addLayout(actions)

        footer = QHBoxLayout()
        footer_version = QLabel("EventHub 2 • v2.24.2")
        footer_version.setObjectName("footerLabel")
        footer.addWidget(footer_version)
        footer.addStretch(1)
        footer_brand = QLabel("Operations, connected.")
        footer_brand.setObjectName("footerLabel")
        footer.addWidget(footer_brand)
        layout.addLayout(footer)
        layout.addSpacing(24)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_status)
        self.refresh_timer.start(1000)
        self.backup_timer = QTimer(self)
        self.backup_timer.setInterval(60000)
        self.backup_timer.timeout.connect(self.create_automatic_backup)
        self.backup_timer.start()
        self.refresh_status()

    # ---- helpers ------------------------------------------------------------
    def _bold_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def _format_event_code(self, code: str) -> str:
        return f"{code[:2]} {code[2:]}" if len(code) == 4 else code

    def _summary_card(self, heading: str, initial_value: str):
        card = QFrame()
        card.setObjectName("summaryCard")
        card_layout = QVBoxLayout(card)
        heading_label = QLabel(heading)
        heading_label.setObjectName("cardHeading")
        value_label = QLabel(initial_value)
        value_label.setObjectName("cardNumber")
        card_layout.addWidget(heading_label)
        card_layout.addWidget(value_label)
        return card, value_label

    def _action_section(self, title: str):
        frame = QFrame()
        frame.setObjectName("actionSection")
        section_layout = QVBoxLayout(frame)
        section_layout.setContentsMargins(16, 14, 16, 16)
        section_layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("actionSectionTitle")
        section_layout.addWidget(heading)
        return frame, section_layout

    def refresh_status(self):
        # A Qt timer event can already be queued while the manager is closing.
        # Never let such a late refresh touch a connection that has just been
        # closed; this used to produce "Cannot operate on a closed database".
        if self._closing or self.connection is None:
            return
        try:
            return self._refresh_status_impl()
        except sqlite3.ProgrammingError as exc:
            if self._closing or "closed database" in str(exc).lower():
                logger.debug("Statusverversing overgeslagen tijdens afsluiten van sessiedatabase.")
                return
            raise

    def _refresh_status_impl(self):
        count_row = self.connection.execute(
            "SELECT COUNT(*) AS n FROM participant WHERE event_id = ?", (self.event_id,)
        ).fetchone()
        self.participants_value.setText(f"{count_row['n']} geladen")
        self.participant_action_status.setText(f"{count_row['n']} bezoekers geladen")
        online = client_service.online_client_count(self.connection, self.event_id)
        device_text = f"{online} apparaat" if online == 1 else f"{online} apparaten"
        if self.server_thread is not None:
            self.session_live_label.setText("● Live")
            if self.server_started_at is not None:
                elapsed = max(0, int((datetime.now() - self.server_started_at).total_seconds()))
                hours, remainder = divmod(elapsed, 3600)
                minutes, seconds = divmod(remainder, 60)
                timer_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                timer_text = "00:00:00"
            self.session_meta_label.setText(f"{timer_text}  •  {device_text}")
        else:
            self.session_live_label.setText("● Server gestopt")
            self.session_meta_label.setText(f"00:00:00  •  {device_text}")
        self.dashboard_button.setEnabled(self.server_thread is not None)
        self.connections_button.setEnabled(self.server_thread is not None)
        frozen = session_service.freeze_state(self.connection)["frozen"]
        state = session_service.freeze_state(self.connection)
        emergency = emergency_service.state(self.connection)
        self.emergency_button.setText(
            "Calamiteitenmodus beëindigen" if emergency["active"] else "Calamiteitenmodus starten"
        )
        emergency_style = "secondaryButton" if emergency["active"] else "dangerButton"
        if self.emergency_button.objectName() != emergency_style:
            self.emergency_button.setObjectName(emergency_style)
            self.emergency_button.style().unpolish(self.emergency_button)
            self.emergency_button.style().polish(self.emergency_button)
        self.emergency_action_status.setText(
            "● Calamiteitenmodus actief" if emergency["active"]
            else "Alleen gebruiken bij een daadwerkelijke calamiteit."
        )
        self.freeze_button.setText("Hervatten" if frozen else "Pauzeren")
        inside = self.connection.execute("SELECT COUNT(*) AS n FROM participant WHERE event_id=? AND attendance_status='present'", (self.event_id,)).fetchone()["n"]
        self.inside_value.setText(str(inside))
        self.stop_checkin_button.setEnabled(True)
        self.stop_checkin_button.setText("Hervatten" if state["checkin_stopped"] else "Stoppen")
        if state["checkin_stopped"]:
            self.checkin_action_status.setText("● Gestopt")
        elif frozen:
            self.checkin_action_status.setText("● Gepauzeerd")
        else:
            self.checkin_action_status.setText("● Actief")
        wanted_style = "secondaryButton" if state["checkin_stopped"] else "dangerButton"
        if self.stop_checkin_button.objectName() != wanted_style:
            self.stop_checkin_button.setObjectName(wanted_style)
            self.stop_checkin_button.style().unpolish(self.stop_checkin_button)
            self.stop_checkin_button.style().polish(self.stop_checkin_button)
        signature = tuple(
            (row["id"], row["attendance_status"])
            for row in self.connection.execute(
                "SELECT id, attendance_status FROM participant WHERE event_id=? ORDER BY id", (self.event_id,)
            ).fetchall()
        )
        if self._attendance_signature is not None and signature != self._attendance_signature:
            self.attendance_changed.emit()
        self._attendance_signature = signature

    def toggle_freeze(self):
        state = session_service.freeze_state(self.connection)
        if state["frozen"]:
            session_service.set_frozen(self.connection, False, by="Serverbeheerder")
        else:
            reason, accepted = QInputDialog.getText(self, "Inchecken pauzeren", "Reden (optioneel):")
            if not accepted:
                return
            session_service.set_frozen(self.connection, True, reason, "Serverbeheerder")
        self.refresh_status()

    def stop_checkin(self):
        state = session_service.freeze_state(self.connection)
        if state["checkin_stopped"]:
            answer = QMessageBox.question(
                self, "Inchecken hervatten",
                "Nieuwe check-ins weer toestaan? Bezoekers die door de stopactie automatisch als afwezig zijn gemarkeerd, worden teruggezet naar 'nog niet ingecheckt'.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            result = session_service.resume_checkin(self.connection, "Serverbeheerder")
            self.refresh_status()
            QMessageBox.information(self, "Inchecken hervat", f"Inchecken is weer mogelijk. {result['restored']} bezoeker(s) zijn teruggezet.")
            return
        answer = QMessageBox.question(self, "Inchecken stoppen",
            "Iedereen die nog niet is ingecheckt wordt als afwezig gemarkeerd. Nieuwe check-ins worden geblokkeerd. Doorgaan?")
        if answer != QMessageBox.StandardButton.Yes: return
        reason, ok = QInputDialog.getText(self, "Inchecken stoppen", "Reden (optioneel):")
        if not ok: return
        session_service.stop_checkin(self.connection, reason, "Serverbeheerder")
        # refresh_status detects the changed signature and emits exactly once;
        # emitting a second time made large linked dossiers appear to freeze.
        self.refresh_status()

    def toggle_emergency(self):
        emergency = emergency_service.state(self.connection)
        if emergency["active"]:
            overview = emergency_service.overview(self.connection)
            answer = QMessageBox.question(
                self, "Calamiteitenmodus beëindigen",
                f"Calamiteitenmodus beëindigen?\n\nNog te controleren: {overview['unaccounted']} persoon/personen.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            emergency_service.end(self.connection, "Serverbeheerder")
            QMessageBox.information(
                self, "Calamiteitenmodus beëindigd", "De normale functies zijn hervat."
            )
        else:
            answer = QMessageBox.warning(
                self, "Calamiteitenmodus starten",
                "Hiermee ontvangen alle verbonden apparaten een duidelijke calamiteitenmelding en worden "
                "normale check-inhandelingen tijdelijk geblokkeerd. Doorgaan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            instruction, accepted = QInputDialog.getText(
                self, "Instructie voor medewerkers", "Actuele instructie:",
                QLineEdit.EchoMode.Normal, emergency_service.DEFAULT_INSTRUCTION,
            )
            if not accepted:
                return
            emergency_service.start(self.connection, instruction, "Serverbeheerder")
        self.refresh_status()

    def export_emergency(self):
        current = emergency_service.active_incident(self.connection)
        if not current:
            current = self.connection.execute(
                "SELECT * FROM emergency_incident ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        if not current:
            QMessageBox.information(self, "Geen registratie", "Er is nog geen calamiteitenregistratie beschikbaar.")
            return
        default_path = exports_directory() / "EventHub-calamiteitenregistratie.xlsx"
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Calamiteitenregistratie exporteren", str(default_path), "Excel-werkmap (*.xlsx)"
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".xlsx"):
            file_name += ".xlsx"
        output = emergency_service.export_workbook(self.connection, current["id"])
        Path(file_name).write_bytes(output.getvalue())
        QMessageBox.information(self, "Export gereed", f"Calamiteitenregistratie opgeslagen:\n{file_name}")

    def create_automatic_backup(self):
        try:
            backup_database(self.db_path)
            backups = sorted(backups_directory().glob(f"{self.db_path.parent.name}-*.db"),
                             key=lambda p: p.stat().st_mtime, reverse=True)
            for old in backups[20:]:
                old.unlink(missing_ok=True)
        except Exception:
            logger.exception("Automatische sessieback-up mislukt")

    def _set_qr_placeholder(self):
        pixmap = QPixmap(self.qr_label.size())
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)
        painter.setPen(Qt.GlobalColor.gray)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                          "QR-code verschijnt\nzodra de server draait")
        painter.end()
        self.qr_label.setPixmap(pixmap)

    def _render_qr(self, url: str):
        try:
            matrix = generate_matrix(url, ec_level="M")
        except ValueError as exc:
            logger.warning("Kon geen QR-code genereren voor %s: %s", url, exc)
            self._set_qr_placeholder()
            return
        size = len(matrix)
        border = 2
        module_size = max(2, self.qr_label.width() // (size + border * 2))
        canvas = (size + border * 2) * module_size
        pixmap = QPixmap(canvas, canvas)
        pixmap.fill(Qt.GlobalColor.white)
        painter = QPainter(pixmap)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(Qt.GlobalColor.black)
        for row_index, row in enumerate(matrix):
            for col_index, dark in enumerate(row):
                if dark:
                    x = (col_index + border) * module_size
                    y = (row_index + border) * module_size
                    painter.drawRect(x, y, module_size, module_size)
        painter.end()
        self.qr_label.setFixedSize(canvas, canvas)
        self.qr_label.setPixmap(pixmap)

    def copy_connect_url(self):
        url = self.connect_url_field.text()
        if not url or self.server_thread is None:
            return
        QApplication.clipboard().setText(url)
        self.status_bar_message("Adres gekopieerd naar het klembord.")

    def status_bar_message(self, message: str):
        if self.statusBar():
            self.statusBar().showMessage(message, 3000)

    # ---- server lifecycle -----------------------------------------------------
    def toggle_server(self):
        if self.server_thread is None:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        host = "0.0.0.0"
        port = network.find_free_port(DEFAULT_PORT)
        try:
            self.server_thread = ServerThread(self.app, host, port)
            self.server_thread.start()
            self.server_started_at = datetime.now()
            # Eén startmoment voor manager én webdashboard. Bij iedere nieuwe
            # serverstart wordt dit overschreven, zodat de looptijd altijd vanaf 00:00:00 begint.
            self.app.config["SERVER_STARTED_AT"] = self.server_started_at.isoformat()
        except OSError as exc:
            QMessageBox.critical(
                self, "Server kon niet starten",
                f"Kon niet starten op poort {port}. Controleer of de Windows Firewall of "
                f"een andere toepassing deze poort niet blokkeert.\n\nDetails: {exc}",
            )
            self.server_thread = None
            return
        ip_address = network.local_ip_address()
        self.local_url = f"http://{ip_address}:{port}"
        session = session_service.get_session(self.connection) or {}
        self.discovery_responder = network.HubDiscoveryResponder(port, session.get("name", "EventHub-sessie"))
        self.discovery_responder.start()
        self.create_automatic_backup()
        self.connect_url_field.setText(self.local_url)
        addresses = network.local_ip_addresses()
        if len(addresses) > 1:
            self.connect_url_field.setToolTip("Andere gevonden netwerkadressen:\n" + "\n".join(
                f"http://{address}:{port}" for address in addresses[1:]
            ))
        else:
            self.connect_url_field.setToolTip("Automatisch gekozen netwerkadres")
        self._render_qr(self.local_url)
        self.start_stop_button.setText("Server stoppen")
        logger.info("Server gestart op %s", self.local_url)
        self.refresh_status()

    def stop_server(self, refresh: bool = True):
        disconnected = 0
        if self.server_thread is not None:
            disconnected = client_service.disconnect_all_for_server_stop(self.connection, self.event_id)
            # Geef de SSE-responsdraden kort de tijd om het expliciete
            # afsluitsignaal te verzenden voordat de listener wordt gesloten.
            threading.Event().wait(0.35)
        if self.discovery_responder is not None:
            self.discovery_responder.stop()
            self.discovery_responder.join(timeout=2)
            self.discovery_responder = None
        if self.server_thread is not None:
            self.server_thread.stop()
            self.server_thread.join(timeout=5)
            self.server_thread = None
        self.start_stop_button.setText("Server starten")
        self.server_started_at = None
        # Expliciet wissen bij stoppen: een volgende start krijgt altijd een nieuwe timer.
        self.app.config["SERVER_STARTED_AT"] = None
        self.connect_url_field.setText("Start eerst de server om een adres te tonen.")
        self._set_qr_placeholder()
        logger.info("Server gestopt; %s clientregistratie(s) afgemeld.", disconnected)
        if refresh and not self._closing:
            self.refresh_status()

    def closeEvent(self, event):
        self._closing = True
        self.refresh_timer.stop()
        self.backup_timer.stop()
        self.attendance_changed.emit()
        self.stop_server(refresh=False)
        close_database(self.db_path)
        self.connection = None
        super().closeEvent(event)

    # ---- actions ------------------------------------------------------------
    def open_dashboard(self):
        if self.server_thread is None:
            QMessageBox.information(self, "Server niet actief", "Start eerst de server om het dashboard te openen.")
            return
        webbrowser.open(f"{self.local_url}/dashboard")

    def open_connect_page(self):
        if self.server_thread is None:
            QMessageBox.information(self, "Server niet actief", "Start eerst de server om te kunnen verbinden.")
            return
        webbrowser.open(self.local_url)

    def open_logs_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_directory())))

    def import_participants(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Bezoekerslijst importeren", "", "Excel-bestanden (*.xlsx *.xlsm *.xls)"
        )
        if not file_name:
            return
        existing = participant_service.list_participants(self.connection, self.event_id, limit=5000)
        try:
            preview = importer.preview_import(file_name, existing_participants=existing)
        except Exception as exc:
            QMessageBox.critical(self, "Import mislukt", str(exc))
            return
        warning = f"\n⚠ {preview['duplicate_count']} mogelijk dubbele deelnemer(s)." if preview["duplicate_count"] else ""
        answer = QMessageBox.question(
            self, "Importcontrole",
            f"Bestand: {preview['file_name']}\n"
            f"Aantal gevonden rijen: {preview['row_count']}\n"
            f"Herkende kolommen: {', '.join(preview['detected_columns'])}{warning}\n\n"
            "Doorgaan met importeren?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        rows = importer.records_to_participants(preview["records"], self.event_id)
        count = participant_service.add_participants(self.connection, self.event_id, rows)
        QMessageBox.information(self, "Import voltooid", f"{count} deelnemer(s) toegevoegd.")
        self.refresh_status()

    def manage_participants(self):
        dialog = ParticipantsDialog(self.connection, self.event_id, self)
        dialog.exec()
        self.refresh_status()

    def export_participants(self):
        participants = participant_service.list_participants(self.connection, self.event_id, limit=5000)
        if not participants:
            QMessageBox.information(self, "Geen deelnemers", "Er zijn nog geen deelnemers om te exporteren.")
            return
        session = session_service.get_session(self.connection) or {}
        safe_name = re.sub(r"[^A-Za-z0-9À-ÿ _.-]+", "", str(session.get("name", "") or "Evenement")).strip()
        default_path = exports_directory() / f"Bezoekerslijst - {safe_name or 'Evenement'}.xlsx"
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Bezoekerslijst exporteren", str(default_path), "Excel-werkmap (*.xlsx)"
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".xlsx"):
            file_name += ".xlsx"
        selected_fields = self._choose_export_columns()
        if selected_fields is None:
            return
        try:
            count = export_participants_workbook(participants, session, file_name, selected_fields)
        except Exception as exc:
            QMessageBox.critical(self, "Exporteren mislukt", str(exc))
            return
        self.status_bar_message(f"Bezoekerslijst geëxporteerd: {file_name}")
        QMessageBox.information(self, "Export gereed", f"{count} deelnemer(s) geëxporteerd naar:\n{file_name}")

    def show_connections(self):
        dialog = ConnectionsDialog(self.connection, self.event_id, self)
        dialog.exec()

    def _choose_export_columns(self):
        dialog = QDialog(self); dialog.setWindowTitle("Kolommen kiezen"); layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Kies welke gegevens in de live-export komen:"))
        checks = []
        defaults = {"voornaam","tussenvoegsel","achternaam","geboortedatum","geboorteplaats","aanwezig"}
        for label, field, _width in COLUMNS:
            check = QCheckBox(label); check.setChecked(field in defaults); layout.addWidget(check); checks.append((field,check))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted: return None
        fields=[field for field,check in checks if check.isChecked()]
        if not fields: QMessageBox.information(self,"Geen kolommen","Selecteer minimaal één kolom."); return None
        return fields

    def sync_to_bvp(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "EventHub-dossier kiezen", "", "EventHub-bestand (*.bvp)")
        if not file_name: return
        try: payload=json.loads(Path(file_name).read_text(encoding="utf-8"))
        except Exception as exc: QMessageBox.critical(self,"Dossier openen mislukt",str(exc)); return
        events=payload.get("events",[])
        if not events: QMessageBox.information(self,"Geen evenementen","Dit dossier bevat geen evenementen."); return
        labels=[f"{e.get('name','Onbenoemd')} — {e.get('date','')}" for e in events]
        choice,ok=QInputDialog.getItem(self,"Evenement kiezen","Koppel aan:",labels,0,False)
        if not ok: return
        event=events[labels.index(choice)]; event_name=str(event.get("name","")).strip(); wanted=event_name.casefold()
        # Het veld heet Evenement, niet Event; met de oude sleutel matchte deze
        # synchronisatie nooit een record en bleef het aantal altijd nul.
        records=[r for r in payload.get("records",[]) if wanted in {name.casefold() for name in _record_event_names(r)}]
        participants=participant_service.list_participants(self.connection,self.event_id,limit=10000)
        by_id={str(r.get("_id","")):r for r in records}; changed=0
        for p in participants:
            r=by_id.get(str(p.get("id","")))
            if r is None:
                matches=[x for x in records if str(x.get("Voornaam","")).casefold()==str(p.get("voornaam","")).casefold() and str(x.get("Achternaam","")).casefold()==str(p.get("achternaam","")).casefold() and str(x.get("Geboortedatum","")).strip()==str(p.get("geboortedatum","")).strip()]
                r=matches[0] if len(matches)==1 else None
            if r is not None:
                present=bool(p.get("checkin_time"))
                if _set_record_presence(r,event_name,present): changed+=1
        backup=Path(file_name).with_name(f"{Path(file_name).stem}.voor-live-sync-{datetime.now():%Y%m%d-%H%M%S}.bvp")
        shutil.copy2(file_name,backup)
        temporary=Path(file_name).with_suffix(".bvp.tmp"); temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8"); temporary.replace(file_name)
        QMessageBox.information(self,"Synchronisatie voltooid",f"{changed} aanwezigheidsstatus(sen) bijgewerkt.\nBack-up: {backup.name}")


class ParticipantsDialog(QDialog):
    """Simple read-oriented participant browser for Server Manager."""

    def __init__(self, connection, event_id: str, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.event_id = event_id
        self.setWindowTitle("Bezoekerslijst")
        self.resize(760, 480)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        headers = ["Naam", "Geboortedatum", "Opleiding", "Profiel", "Status"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        export_button = _compact(QPushButton("Exporteren naar Excel"))
        export_button.setObjectName("secondaryButton")
        export_button.clicked.connect(self._export)
        layout.addWidget(export_button)

        self._populate()

    def _export(self):
        manager = self.parent()
        if manager is not None and hasattr(manager, "export_participants"):
            manager.export_participants()

    def _populate(self):
        rows = participant_service.list_participants(self.connection, self.event_id, limit=2000)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                participant_service.defence_display_name(row), row["geboortedatum"] or "",
                row["opleidingsniveau"] or "", row["profiel"] or "",
                {"present":"Binnen", "checked_out":"Uitgecheckt", "absent":"Afwezig"}.get(
                    row["attendance_status"], "Nog niet ingecheckt"),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(str(value)))


class ConnectionsDialog(QDialog):
    def __init__(self, connection, event_id: str, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.event_id = event_id
        self.setWindowTitle("Verbonden apparaten")
        self.resize(600, 400)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        headers = ["Naam", "Type", "IP", "Rol", "Status", "Laatste activiteit"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        role_button = QPushButton("Rol aanpassen"); role_button.clicked.connect(self._change_role)
        kick_button = QPushButton("Client verwijderen"); kick_button.setObjectName("dangerButton"); kick_button.clicked.connect(self._kick)
        all_button = QPushButton("Alle clients loskoppelen"); all_button.setObjectName("dangerButton"); all_button.clicked.connect(self._kick_all)
        actions.addWidget(role_button); actions.addWidget(kick_button); actions.addWidget(all_button); actions.addStretch(); layout.addLayout(actions)
        self._populate()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2000)
        self.refresh_timer.timeout.connect(self._populate)
        self.refresh_timer.start()

    def _selected_id(self):
        row=self.table.currentRow(); item=self.table.item(row,0) if row>=0 else None
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""

    def _change_role(self):
        client_id=self._selected_id()
        if not client_id: QMessageBox.information(self,"Geen client","Selecteer eerst een client."); return
        labels={"Check-in":"checkin","Eventmanager":"event_manager","Beheerder":"admin","Alleen bekijken":"viewer"}
        choice,ok=QInputDialog.getItem(self,"Rol aanpassen","Nieuwe rol:",list(labels),0,False)
        if ok:
            try: client_service.set_role(self.connection,self.event_id,client_id,labels[choice],"Serverbeheerder")
            except ValueError as exc: QMessageBox.warning(self,"Rol aanpassen mislukt",str(exc))
            self._populate()

    def _kick(self):
        client_id=self._selected_id()
        if not client_id: QMessageBox.information(self,"Geen client","Selecteer eerst een client."); return
        if QMessageBox.question(self,"Client verwijderen","Deze client onmiddellijk afmelden?") == QMessageBox.StandardButton.Yes:
            client_service.kick_client(self.connection,self.event_id,client_id,"Serverbeheerder"); self._populate()

    def _kick_all(self):
        if QMessageBox.question(self,"Alle clients loskoppelen","Alle verbonden clients onmiddellijk afmelden?") != QMessageBox.StandardButton.Yes: return
        for client in client_service.list_clients(self.connection,self.event_id):
            client_service.kick_client(self.connection,self.event_id,client["id"],"Serverbeheerder")
        self._populate()

    def _populate(self):
        selected_id = self._selected_id()
        clients = client_service.list_clients(self.connection, self.event_id)
        self.table.setRowCount(len(clients))
        for row_index, client in enumerate(clients):
            values = [
                client["client_name"], client["client_type"] or "", client["ip_address"] or "",
                client["role"], "● online" if client["online"] else "○ offline", client["last_seen"],
            ]
            for column, value in enumerate(values):
                item=QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole,client["id"])
                if column == 4 and client["online"]:
                    item.setBackground(QColor("#dcfce7")); item.setForeground(QColor("#166534"))
                elif column == 4:
                    item.setBackground(QColor("#fee2e2")); item.setForeground(QColor("#991b1b"))
                self.table.setItem(row_index,column,item)
            if client["id"] == selected_id:
                self.table.selectRow(row_index)
