"""New-session / resume-session dialog for EventHub Server Manager.

Reuses the same PySide6 visual system as EventHub Desktop
(a vendored copy in ``server.manager.theme``) so this feels like part
of the same product family rather than a bolted-on tool, while keeping
EventHub Server fully independent of the EventHub Desktop codebase.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QDateEdit, QTabWidget, QWidget, QCheckBox, QSizePolicy,
)
from PySide6.QtCore import QDate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from server.services import session_service


class NewSessionDialog(QDialog):
    """Collects Naam/Datum/Locatie for a new session, or lets the user resume one."""

    def __init__(self, parent=None, default_name: str = "", default_date: str = "", default_location: str = "",
                 source_event_id: str = ""):
        super().__init__(parent)
        self.setWindowTitle("EventHub Server — Sessie")
        self.setMinimumWidth(460)
        self.result_session = None  # SessionCreateResult, or a dict with 'id' for resume
        self.created_new = False
        self.source_event_id = (source_event_id or "").strip()

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- New session tab -------------------------------------------------
        new_tab = QWidget()
        new_layout = QVBoxLayout(new_tab)
        new_layout.addWidget(QLabel("Nieuw gedeeld evenement"))

        new_layout.addWidget(QLabel("Naam evenement"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Meeloopdag Drone Operaties")
        self.name_input.setText(default_name)
        new_layout.addWidget(self.name_input)

        new_layout.addWidget(QLabel("Datum"))
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd-MM-yyyy")
        self.date_input.setDate(QDate.currentDate())
        parsed_default_date = QDate.fromString(default_date, "dd-MM-yyyy")
        if parsed_default_date.isValid():
            self.date_input.setDate(parsed_default_date)
        new_layout.addWidget(self.date_input)

        new_layout.addWidget(QLabel("Locatie"))
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Gebouw IJsduiker – Nieuwe Haven")
        self.location_input.setText(default_location)
        new_layout.addWidget(self.location_input)

        self.checkout_required = QCheckBox("Uitchecken registreren (toon wie nog in het pand is)")
        self.checkout_required.setToolTip("Gebruik dit bij evenementen waarbij vertrekregistratie verplicht is.")
        new_layout.addWidget(self.checkout_required)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c9385a;")
        self.error_label.setWordWrap(True)
        new_layout.addWidget(self.error_label)

        create_button = QPushButton("Sessie aanmaken")
        create_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(self._create_session)
        new_layout.addWidget(create_button)
        new_layout.addStretch(1)
        tabs.addTab(new_tab, "Nieuwe sessie")

        # --- Resume tab --------------------------------------------------------
        resume_tab = QWidget()
        resume_layout = QVBoxLayout(resume_tab)
        resume_layout.addWidget(QLabel("Recente sessies"))
        self.sessions_list = QListWidget()
        self._populate_recent_sessions()
        resume_layout.addWidget(self.sessions_list, 1)
        resume_actions = QHBoxLayout()
        delete_button = QPushButton("Sessie verwijderen")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self._delete_session)
        resume_actions.addWidget(delete_button)
        resume_actions.addStretch(1)
        resume_button = QPushButton("Hervatten")
        resume_button.setObjectName("primaryButton")
        resume_button.clicked.connect(self._resume_session)
        resume_actions.addWidget(resume_button)
        resume_layout.addLayout(resume_actions)
        tabs.addTab(resume_tab, "Hervatten")

        if self.sessions_list.count() and not self.source_event_id:
            tabs.setCurrentIndex(1)

    def _populate_recent_sessions(self):
        self.sessions_list.clear()
        for session in session_service.list_recent_sessions():
            label = f"{session['name']}\n{session['date']} — {session['location']} · {session.get('participant_count', 0)} deelnemers"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, session["id"])
            self.sessions_list.addItem(item)

    def _create_session(self):
        try:
            result = session_service.create_session(
                self.name_input.text(),
                self.date_input.date().toString("dd-MM-yyyy"),
                self.location_input.text(),
                self.checkout_required.isChecked(),
                self.source_event_id,
            )
        except session_service.SessionValidationError as exc:
            self.error_label.setText(str(exc))
            return
        self.result_session = result
        self.created_new = True
        self.accept()

    def _resume_session(self):
        item = self.sessions_list.currentItem()
        if not item:
            QMessageBox.information(self, "Geen sessie gekozen", "Selecteer eerst een sessie om te hervatten.")
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            db_path = session_service.resume_session(session_id)
        except session_service.SessionValidationError as exc:
            QMessageBox.warning(self, "Kan sessie niet hervatten", str(exc))
            return
        self.result_session = type("ResumedSession", (), {"id": session_id, "db_path": db_path})()
        self.created_new = False
        self.accept()

    def _delete_session(self):
        item = self.sessions_list.currentItem()
        if not item:
            QMessageBox.information(self, "Geen sessie gekozen", "Selecteer eerst een sessie om te verwijderen.")
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        session = next((entry for entry in session_service.list_recent_sessions() if entry.get("id") == session_id), {})
        answer = QMessageBox.warning(
            self,
            "Livesessie definitief verwijderen",
            f"Wilt u '{session.get('name', 'deze sessie')}' met {session.get('participant_count', 0)} deelnemer(s) definitief verwijderen?\n\n"
            "De sessiedatabase verdwijnt. Eerder gemaakte automatische back-ups blijven beschikbaar.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            session_service.delete_session(session_id)
        except (OSError, session_service.SessionValidationError) as exc:
            QMessageBox.critical(self, "Sessie verwijderen mislukt", str(exc))
            return
        self._populate_recent_sessions()
        QMessageBox.information(self, "Sessie verwijderd", "De livesessie is verwijderd.")
