"""De invulvensters van EventHub: nieuw evenement, evenement aanpassen, taken,
het 5WH- en evaluatieformulier, het profiel en de algemene instellingen.

Ieder venster krijgt gegevens mee en geeft met value() terug wat de gebruiker
invulde; opslaan doet het hoofdvenster.
"""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from emt_event_templates import template_event_data
from emt_models import (
    EVENT_STATUSES, EVENT_TYPES, parse_date, prepare_task, prepare_template,
    template_event_types,
)
from emt_retention import (
    RETENTION_CHOICES, RETENTION_DEFAULT_DAYS, RETENTION_MAX_DAYS,
    RETENTION_WARNING_DAYS, clamp_retention_days,
)
from emt_widgets import (
    ScrollSafeComboBox, _fit_dialog_to_screen, _make_button_compact, valid_time_text,
    with_date_picker, with_time_picker,
)


# Kiest de gebruiker deze, dan bepaalt EventHub de status zelf op basis van
# datum en openstaande taken; elke andere keuze blijft staan.
AUTOMATIC_STATUS = "Automatisch bepalen"


FIVEWH_FIELDS = [
    ("event_address", "Locatie en adres evenement"),
    ("briefing_address", "Locatie en adres briefing"),
    ("build_time", "Tijdstip opbouw"),
    ("briefing_time", "Tijdstip briefing"),
    ("event_time", "Tijdstip(pen) evenement"),
    ("debrief_time", "Tijdstip debriefing"),
    ("teardown_time", "Tijdstip afbouw"),
    ("roster", "Rooster: één regel per persoon als Naam | Taak"),
    ("poc_questions", "POC bij vragen"),
    ("poc_location", "POC locatie"),
    ("objective", "Doelstelling / boodschap"),
    ("target_audience", "Doelgroep"),
    ("current_status", "Hoe staan we ervoor"),
    ("defence_activities_map", "Plattegrond activiteiten Defensie"),
    ("event_map", "Plattegrond event"),
    ("support", "Steun"),
    ("vacancies", "Meest actuele vacatureoverzicht"),
    ("access", "Toegangsregeling"),
    ("attire", "Tenue"),
    ("catering", "Voeding"),
    ("route", "Route"),
    ("parking", "Parkeren"),
    ("materials", "Materiaal (folders en goodies)"),
    ("accommodation", "Overnachting"),
    ("first_aid", "BHV / EHBO"),
    ("evaluation", "Evaluatie"),
    ("risks", "Risico's op het gebied van Arbo en milieu"),
    ("measures", "Genomen maatregelen"),
    ("program", "Programma"),
]


EVALUATION_TARGET_GROUPS = [
    (15, "Ouders"), (16, "Decanen/studiebegeleiders"), (17, "Jongeren"),
    (18, "Vrouwen (16-35 jaar)"), (19, "Multiculturele doelgroep"),
    (20, "Technisch"), (21, "Maritiem"), (22, "Verpleegkundigen"),
    (23, "Logistiek"), (24, "VMBO"), (25, "MBO"), (26, "HAVO/VWO"),
    (27, "HBO"), (28, "WO"),
]


def _scroll_form_page():
    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(14, 14, 14, 14)
    content_layout.setSpacing(12)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(content)
    return scroll, content_layout


class ProfileDialog(QDialog):
    def __init__(
        self,
        profile: dict,
        parent=None,
        required: bool = False,
        startup_mode: str = "relevant",
        upcoming_days: int = 30,
        autosave_enabled: bool = True,
        autosave_delay_seconds: int = 3,
        backups_enabled: bool = True,
        backup_count: int = 5,
        dark_mode: bool = False,
    ):
        super().__init__(parent)
        self.required = required
        self.setWindowTitle("Eerste configuratie" if required else "Mijn profiel")
        _fit_dialog_to_screen(self, 680, 650, 520, 420)
        if required:
            self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        layout = QVBoxLayout(self)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(12)
        intro = QLabel(
            "Vul uw profiel één keer in. Deze gegevens worden uitsluitend lokaal bewaard en automatisch gebruikt "
            "in 5WH's en evaluatieformulieren. Updates vragen hierna niet opnieuw om deze gegevens."
            if required else
            "Deze gegevens worden lokaal bewaard en automatisch gebruikt in 5WH's en evaluatieformulieren."
        )
        intro.setWordWrap(True)
        content_layout.addWidget(intro)
        form = QFormLayout()
        self.name = QLineEdit(str(profile.get("name", "") or ""))
        self.function = QLineEdit(str(profile.get("function", "") or ""))
        self.email = QLineEdit(str(profile.get("email", "") or ""))
        self.email.setPlaceholderText("naam@werkenbijdefensie.nl")
        self.phone = QLineEdit(str(profile.get("phone", "") or ""))
        self.phone.setPlaceholderText("06-12345678")
        form.addRow("Naam:", self.name)
        form.addRow("Functie:", self.function)
        form.addRow("E-mailadres:", self.email)
        form.addRow("06-nummer:", self.phone)
        content_layout.addLayout(form)

        startup_group = QGroupBox("Opstartscherm")
        startup_layout = QFormLayout(startup_group)
        self.startup_mode = ScrollSafeComboBox()
        self.startup_mode.addItem("Alleen bij relevante meldingen of evenementen", "relevant")
        self.startup_mode.addItem("Altijd tonen", "always")
        self.startup_mode.addItem("Niet tonen", "never")
        mode_index = self.startup_mode.findData(startup_mode)
        self.startup_mode.setCurrentIndex(mode_index if mode_index >= 0 else 0)
        self.upcoming_days = ScrollSafeComboBox()
        for days in (7, 14, 30, 60):
            self.upcoming_days.addItem(f"{days} dagen vooruit", days)
        days_index = self.upcoming_days.findData(int(upcoming_days or 30))
        self.upcoming_days.setCurrentIndex(days_index if days_index >= 0 else 2)
        startup_layout.addRow("Welkomstscherm:", self.startup_mode)
        startup_layout.addRow("Aankomende evenementen:", self.upcoming_days)
        content_layout.addWidget(startup_group)

        save_group = QGroupBox("Opslaan en herstel")
        save_layout = QFormLayout(save_group)
        self.autosave_enabled = QCheckBox("Wijzigingen automatisch opslaan")
        self.autosave_enabled.setChecked(bool(autosave_enabled))
        self.autosave_delay = ScrollSafeComboBox()
        for seconds in (3, 10, 30, 60):
            self.autosave_delay.addItem(f"Na {seconds} seconden rust", seconds)
        delay_index = self.autosave_delay.findData(int(autosave_delay_seconds or 3))
        self.autosave_delay.setCurrentIndex(delay_index if delay_index >= 0 else 0)
        self.backups_enabled = QCheckBox("Automatische reservekopieën bewaren")
        self.backups_enabled.setChecked(bool(backups_enabled))
        self.backup_count = ScrollSafeComboBox()
        for count in (3, 5, 10):
            self.backup_count.addItem(f"Laatste {count} versies", count)
        backup_index = self.backup_count.findData(int(backup_count or 5))
        self.backup_count.setCurrentIndex(backup_index if backup_index >= 0 else 1)
        self.autosave_delay.setEnabled(self.autosave_enabled.isChecked())
        self.backup_count.setEnabled(self.backups_enabled.isChecked())
        self.autosave_enabled.toggled.connect(self.autosave_delay.setEnabled)
        self.backups_enabled.toggled.connect(self.backup_count.setEnabled)
        save_layout.addRow("Autosave:", self.autosave_enabled)
        save_layout.addRow("Opslaan:", self.autosave_delay)
        save_layout.addRow("Reservekopieën:", self.backups_enabled)
        save_layout.addRow("Bewaren:", self.backup_count)
        content_layout.addWidget(save_group)

        appearance_group = QGroupBox("Weergave")
        appearance_layout = QFormLayout(appearance_group)
        self.dark_mode = QCheckBox("☾ Dark mode")
        self.dark_mode.setChecked(bool(dark_mode))
        appearance_layout.addRow("Thema:", self.dark_mode)
        content_layout.addWidget(appearance_group)
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        button_flags = QDialogButtonBox.StandardButton.Save
        if not required:
            button_flags |= QDialogButtonBox.StandardButton.Cancel
        buttons = QDialogButtonBox(button_flags)
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _try_accept(self):
        profile = self.value()
        if self.required:
            missing = [
                label for key, label in (
                    ("name", "naam"), ("function", "functie"),
                    ("email", "e-mailadres"), ("phone", "06-nummer"),
                ) if not profile[key]
            ]
            if missing:
                QMessageBox.information(
                    self,
                    "Profiel nog niet compleet",
                    "Vul ook het volgende in: " + ", ".join(missing) + ".",
                )
                return
        if profile["email"] and not profile["email"].lower().endswith("@werkenbijdefensie.nl"):
            QMessageBox.warning(
                self,
                "E-mailadres controleren",
                "Gebruik een @werkenbijdefensie.nl-adres.",
            )
            return
        self.accept()

    def value(self):
        return {
            "name": self.name.text().strip(),
            "function": self.function.text().strip(),
            "email": self.email.text().strip(),
            "phone": self.phone.text().strip(),
        }

    def startup_preferences(self):
        return {
            "mode": str(self.startup_mode.currentData() or "relevant"),
            "upcoming_days": int(self.upcoming_days.currentData() or 30),
            "autosave_enabled": self.autosave_enabled.isChecked(),
            "autosave_delay_seconds": int(self.autosave_delay.currentData() or 3),
            "backups_enabled": self.backups_enabled.isChecked(),
            "backup_count": int(self.backup_count.currentData() or 5),
            "dark_mode": self.dark_mode.isChecked(),
        }


class ProfileDetailsDialog(QDialog):
    """Profielgegevens zonder applicatie-instellingen."""

    def __init__(self, profile: dict, parent=None, required: bool = False):
        super().__init__(parent)
        self.required = required
        self.setWindowTitle("Eerste configuratie" if required else "Mijn profiel aanpassen")
        _fit_dialog_to_screen(self, 590, 590, 500, 430)
        if required:
            self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Vul uw profiel één keer in. Deze gegevens blijven lokaal en worden gebruikt in documentexports en WhatsApp-berichten."
            if required else
            "Deze gegevens blijven lokaal en worden automatisch gebruikt in 5WH's, evaluatieformulieren en desgewenst WhatsApp-berichten."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.name = QLineEdit(str(profile.get("name", "") or ""))
        self.function = QLineEdit(str(profile.get("function", "") or ""))
        self.email = QLineEdit(str(profile.get("email", "") or ""))
        self.email.setPlaceholderText("naam@werkenbijdefensie.nl")
        self.phone = QLineEdit(str(profile.get("phone", "") or ""))
        self.phone.setPlaceholderText("06-12345678")
        form.addRow("Naam:", self.name)
        form.addRow("Functie:", self.function)
        form.addRow("E-mailadres:", self.email)
        form.addRow("06-nummer:", self.phone)
        layout.addLayout(form)

        signature_group = QGroupBox("Handtekening")
        signature_layout = QFormLayout(signature_group)
        self.signature_rank = QLineEdit(str(profile.get("signature_rank", "") or ""))
        self.signature_rank.setPlaceholderText("evt. afgekort")
        self.signature_first_name = QLineEdit(str(profile.get("signature_first_name", "") or ""))
        if not self.signature_first_name.text().strip():
            self.signature_first_name.setText(str(profile.get("name", "") or "").strip().split(" ", 1)[0])
        self.signature_department = QLineEdit(str(profile.get("signature_department", "") or ""))
        self.signature_organization = QLineEdit(
            str(profile.get("signature_organization", "Ministerie van Defensie") or "Ministerie van Defensie")
        )
        self.signature_organization.setReadOnly(True)
        signature_layout.addRow("Rang:", self.signature_rank)
        signature_layout.addRow("Voornaam:", self.signature_first_name)
        signature_layout.addRow("Afdeling:", self.signature_department)
        signature_layout.addRow("Organisatie:", self.signature_organization)
        layout.addWidget(signature_group)
        layout.addStretch()
        flags = QDialogButtonBox.StandardButton.Save
        if not required:
            flags |= QDialogButtonBox.StandardButton.Cancel
        buttons = QDialogButtonBox(flags)
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self):
        return {
            "name": self.name.text().strip(),
            "function": self.function.text().strip(),
            "email": self.email.text().strip(),
            "phone": self.phone.text().strip(),
            "signature_rank": self.signature_rank.text().strip(),
            "signature_first_name": self.signature_first_name.text().strip(),
            "signature_department": self.signature_department.text().strip(),
            "signature_organization": "Ministerie van Defensie",
        }

    def _try_accept(self):
        profile = self.value()
        if self.required:
            missing = [label for key, label in (
                ("name", "naam"), ("function", "functie"),
                ("email", "e-mailadres"), ("phone", "06-nummer"),
            ) if not profile[key]]
            if missing:
                QMessageBox.information(self, "Profiel nog niet compleet", "Vul ook in: " + ", ".join(missing) + ".")
                return
        if profile["email"] and not profile["email"].lower().endswith("@werkenbijdefensie.nl"):
            QMessageBox.warning(self, "E-mailadres controleren", "Gebruik een @werkenbijdefensie.nl-adres.")
            return
        self.accept()


class ApplicationSettingsDialog(QDialog):
    """Centrale instellingen voor opstarten, opslag, herstel en weergave."""

    def __init__(self, parent, preferences: dict):
        super().__init__(parent)
        self.setWindowTitle("EventHub-instellingen")
        _fit_dialog_to_screen(self, 650, 610, 520, 430)
        layout = QVBoxLayout(self)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        extension_group = QGroupBox("Browserextensie")
        extension_layout = QVBoxLayout(extension_group)
        extension_note = QLabel("Installeer de browserassistent eenmalig in Edge of Chrome om EventHub met Rudder te verbinden.")
        extension_note.setObjectName("hintLabel")
        extension_note.setWordWrap(True)
        extension_layout.addWidget(extension_note)
        self.extension_install_button = _make_button_compact(QPushButton("Browserextensie installeren"))
        self.extension_install_button.setObjectName("secondaryButton")
        self.extension_install_button.clicked.connect(
            lambda: parent.open_rudder_extension_folder(dialog_parent=self)
        )
        extension_layout.addWidget(self.extension_install_button)
        content_layout.addWidget(extension_group)

        startup_group = QGroupBox("Opstartinstellingen")
        startup_layout = QFormLayout(startup_group)
        self.startup_mode = ScrollSafeComboBox()
        self.startup_mode.addItem("Alleen bij relevante meldingen of evenementen", "relevant")
        self.startup_mode.addItem("Altijd tonen", "always")
        self.startup_mode.addItem("Niet tonen", "never")
        self.startup_mode.setCurrentIndex(max(0, self.startup_mode.findData(preferences["mode"])))
        self.upcoming_days = ScrollSafeComboBox()
        for days in (7, 14, 30, 60):
            self.upcoming_days.addItem(f"{days} dagen vooruit", days)
        self.upcoming_days.setCurrentIndex(max(0, self.upcoming_days.findData(preferences["upcoming_days"])))
        startup_layout.addRow("Welkomstscherm:", self.startup_mode)
        startup_layout.addRow("Aankomende evenementen:", self.upcoming_days)
        content_layout.addWidget(startup_group)

        save_group = QGroupBox("Opslaan en herstel")
        save_layout = QFormLayout(save_group)
        self.autosave_enabled = QCheckBox("Wijzigingen automatisch opslaan")
        self.autosave_enabled.setChecked(preferences["autosave_enabled"])
        self.autosave_delay = ScrollSafeComboBox()
        for seconds in (3, 10, 30, 60):
            self.autosave_delay.addItem(f"Na {seconds} seconden rust", seconds)
        self.autosave_delay.setCurrentIndex(max(0, self.autosave_delay.findData(preferences["autosave_delay_seconds"])))
        self.backups_enabled = QCheckBox("Automatische reservekopieën bewaren")
        self.backups_enabled.setChecked(preferences["backups_enabled"])
        self.backup_count = ScrollSafeComboBox()
        for count in (3, 5, 10):
            self.backup_count.addItem(f"Laatste {count} versies", count)
        self.backup_count.setCurrentIndex(max(0, self.backup_count.findData(preferences["backup_count"])))
        self.autosave_delay.setEnabled(self.autosave_enabled.isChecked())
        self.backup_count.setEnabled(self.backups_enabled.isChecked())
        self.autosave_enabled.toggled.connect(self.autosave_delay.setEnabled)
        self.backups_enabled.toggled.connect(self.backup_count.setEnabled)
        save_layout.addRow("Autosave:", self.autosave_enabled)
        save_layout.addRow("Opslaan:", self.autosave_delay)
        save_layout.addRow("Reservekopieën:", self.backups_enabled)
        save_layout.addRow("Bewaren:", self.backup_count)
        storage_button = _make_button_compact(QPushButton("Opslaglocaties bekijken"))
        storage_button.setObjectName("secondaryButton")
        storage_button.clicked.connect(parent.show_storage_locations)
        recovery_button = _make_button_compact(QPushButton("Herstelbestanden beheren"))
        recovery_button.setObjectName("secondaryButton")
        recovery_button.clicked.connect(parent.manage_recovery_files)
        save_layout.addRow(storage_button, recovery_button)
        content_layout.addWidget(save_group)

        privacy_group = QGroupBox("Bewaartermijn persoonsgegevens")
        privacy_layout = QFormLayout(privacy_group)
        self.retention_days = ScrollSafeComboBox()
        for days in RETENTION_CHOICES:
            label = f"{days} dagen na het evenement"
            if days == RETENTION_DEFAULT_DAYS:
                label += "  (standaard)"
            self.retention_days.addItem(label, days)
        self.retention_days.setCurrentIndex(
            max(0, self.retention_days.findData(clamp_retention_days(preferences["retention_days"])))
        )
        privacy_note = QLabel(
            "Na deze termijn worden de deelnemersgegevens van een evenement <b>automatisch en onomkeerbaar</b> "
            "verwijderd uit het dossier, de reservekopieën en de livesessiegegevens. Er wordt niet om "
            f"bevestiging gevraagd. Het meldingenoverzicht (🔔) kondigt dit {RETENTION_WARNING_DAYS} dagen "
            "van tevoren aan, zodat u op tijd kunt exporteren. De opkomstcijfers en verdelingen blijven als "
            f"geanonimiseerd overzicht bij het evenement bewaard. Langer dan {RETENTION_MAX_DAYS} dagen is "
            "niet mogelijk."
        )
        privacy_note.setTextFormat(Qt.TextFormat.RichText)
        privacy_note.setObjectName("hintLabel")
        privacy_note.setWordWrap(True)
        privacy_layout.addRow("Verwijderen na:", self.retention_days)
        privacy_layout.addRow(privacy_note)
        review_button = _make_button_compact(QPushButton("Nu controleren zonder te wissen"))
        review_button.setObjectName("secondaryButton")
        review_button.clicked.connect(parent.review_retention_cleanup)
        privacy_layout.addRow(review_button)
        content_layout.addWidget(privacy_group)

        appearance_group = QGroupBox("Weergave")
        appearance_layout = QFormLayout(appearance_group)
        self.dark_mode = QCheckBox("☾ Dark mode")
        self.dark_mode.setChecked(preferences["dark_mode"])
        appearance_layout.addRow("Thema:", self.dark_mode)
        content_layout.addWidget(appearance_group)
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self):
        return {
            "mode": str(self.startup_mode.currentData() or "relevant"),
            "upcoming_days": int(self.upcoming_days.currentData() or 30),
            "autosave_enabled": self.autosave_enabled.isChecked(),
            "autosave_delay_seconds": int(self.autosave_delay.currentData() or 3),
            "backups_enabled": self.backups_enabled.isChecked(),
            "backup_count": int(self.backup_count.currentData() or 5),
            "retention_days": clamp_retention_days(self.retention_days.currentData()),
            "dark_mode": self.dark_mode.isChecked(),
        }


class NewEventSourceDialog(QDialog):
    """Small first step for a new EventHub event."""

    def __init__(self, parent=None, templates_available=False):
        super().__init__(parent)
        self.choice = ""
        self.setWindowTitle("Nieuw evenement")
        _fit_dialog_to_screen(self, 560, 390, 480, 340)
        layout = QVBoxLayout(self)
        title = QLabel("Hoe wilt u het evenement aanmaken?")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        intro = QLabel("Kies een lege start, hergebruik een EventHub-template of neem gegevens over uit Rudder.")
        intro.setWordWrap(True)
        intro.setObjectName("hintLabel")
        layout.addWidget(intro)

        options = (
            ("empty", "Leeg evenement", "Vul naam, soort, datum en locatie zelf in."),
            ("template", "Vanuit EventHub-template", "Hergebruik taken en instellingen; pas vooral de datum aan."),
            ("rudder", "Eén evenement uit Rudder", "Open het Rudder-overzicht en neem één evenement met één klik over."),
            ("rudder_bulk", "Meerdere evenementen uit Rudder", "Filter in Rudder op uw eigen naam en haal alles in één keer binnen."),
        )
        for key, label, description in options:
            row = QFrame()
            row.setObjectName("toolbar")
            row_layout = QHBoxLayout(row)
            text_layout = QVBoxLayout()
            option_title = QLabel(label)
            option_title.setStyleSheet("font-weight: 700;")
            option_text = QLabel(description)
            option_text.setObjectName("hintLabel")
            option_text.setWordWrap(True)
            text_layout.addWidget(option_title)
            text_layout.addWidget(option_text)
            row_layout.addLayout(text_layout, 1)
            button = _make_button_compact(QPushButton("Kiezen"))
            button.setObjectName("primaryButton" if key == "empty" else "secondaryButton")
            button.setEnabled(key != "template" or templates_available)
            if key == "template" and not templates_available:
                button.setToolTip("Er zijn nog geen EventHub-templates opgeslagen.")
            button.clicked.connect(lambda _checked=False, selected=key: self._choose(selected))
            row_layout.addWidget(button)
            layout.addWidget(row)
        layout.addStretch()
        cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel.rejected.connect(self.reject)
        layout.addWidget(cancel)

    def _choose(self, choice):
        self.choice = choice
        self.accept()


class NewProjectDialog(QDialog):
    """Zelfstandig formulier voor het aanmaken en aanpassen van een evenement."""

    def __init__(self, parent=None, event: dict | None = None, project_templates: list[dict] | None = None, template_mode=False, template_only=False):
        super().__init__(parent)
        self.project_data = deepcopy(event) if event else None
        self.project_templates = deepcopy(project_templates or [])
        self.template_mode = bool(template_mode)
        self.template_only = bool(template_only)
        editing = self.project_data is not None
        self.setWindowTitle(
            "Evenement aanpassen" if editing else "Nieuw evenementtemplate" if self.template_mode else "Nieuw evenement"
        )
        self.setModal(True)
        _fit_dialog_to_screen(self, 700, 720 if editing else 500, 560, 360)
        layout = QVBoxLayout(self)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(12)
        intro = QLabel(
            "Pas de evenementgegevens aan. Gekoppelde deelnemers, taken en documenten blijven behouden."
            if editing else
            "Maak een template aan. De evenementdatum wordt ingevuld wanneer u een nieuw evenement vanuit dit template maakt."
            if self.template_mode else
            "Maak het evenement aan. Daarna opent direct het werkgebied voor "
            "deelnemerslijsten, nazorg, presentie, statistieken, taken en documenten."
        )
        intro.setWordWrap(True)
        content_layout.addWidget(intro)
        form = QFormLayout()
        if not editing and not self.template_mode:
            self.template_choice = ScrollSafeComboBox()
            if not self.template_only:
                self.template_choice.addItem("Leeg evenement", "")
            for template in self.project_templates:
                self.template_choice.addItem(
                    str(template.get("name", "Naamloos template") or "Naamloos template"),
                    str(template.get("id", "") or ""),
                )
            self.template_choice.currentIndexChanged.connect(self._template_changed)
            form.addRow("Evenementtemplate:", self.template_choice)
        self.name = QLineEdit(str((self.project_data or {}).get("name", "") or ""))
        if editing and not self.template_mode:
            self.template_link = ScrollSafeComboBox()
            self.template_link.addItem("Zonder template", "")
            for item in self.project_templates:
                self.template_link.addItem(item["name"], item["id"])
            current_id = str(self.project_data.get("template_id", ""))
            index = self.template_link.findData(current_id)
            if current_id and index < 0:
                self.template_link.addItem(
                    self.project_data.get("template_name", "Template") + " (niet beschikbaar)", current_id)
                index = self.template_link.count() - 1
            self.template_link.setCurrentIndex(max(0, index))
            self.template_link.setToolTip("Deze koppeling wijzigt geen evenementgegevens of taken.")
            form.addRow("Evenementtemplate:", self.template_link)
        self.name.setPlaceholderText("Bijvoorbeeld: Meeloopdag Drone Operaties")
        self.event_type = ScrollSafeComboBox()
        self.event_type.addItems(EVENT_TYPES)
        self.event_type.setCurrentText(str((self.project_data or {}).get("event_type", "Meeloopdag") or "Meeloopdag"))
        self.project_date = QLineEdit(str((self.project_data or {}).get("date", "") or ""))
        self.project_date.setPlaceholderText("dd-mm-jjjj")
        self.start_time = QLineEdit(str((self.project_data or {}).get("start_time", "") or ""))
        self.start_time.setPlaceholderText("09:00")
        self.end_time = QLineEdit(str((self.project_data or {}).get("end_time", "") or ""))
        self.end_time.setPlaceholderText("13:00")
        self.location = QLineEdit(str((self.project_data or {}).get("location", "") or ""))
        self.location.setPlaceholderText("Bijvoorbeeld: Gebouw IJsduiker, Den Helder")
        self.location_address = QLineEdit(str((self.project_data or {}).get("location_address", "") or ""))
        self.location_address.setPlaceholderText("Straat, huisnummer, postcode en plaats")
        self.maximum_registrants = QLineEdit(str((self.project_data or {}).get("maximum_registrants", "") or ""))
        self.maximum_registrants.setPlaceholderText("Bijvoorbeeld: 50")
        self.exclude_from_analysis = QCheckBox("Niet meetellen in Statistieken en Trends")
        self.exclude_from_analysis.setChecked(bool((self.project_data or {}).get("exclude_from_analysis", False)))
        self.exclude_from_analysis.setToolTip(
            "Gebruik dit bijvoorbeeld voor een testevenement. Deelnemers, presentie en taken blijven gewoon werken."
        )
        form.addRow("Naam*:", self.name)
        form.addRow("Soort evenement*:", self.event_type)
        if not self.template_mode:
            form.addRow("Datum*:", with_date_picker(self.project_date))
        time_row = QWidget()
        time_layout = QHBoxLayout(time_row)
        time_layout.setContentsMargins(0, 0, 0, 0)
        time_layout.setSpacing(8)
        time_layout.addWidget(with_time_picker(self.start_time))
        time_layout.addWidget(QLabel("tot"))
        time_layout.addWidget(with_time_picker(self.end_time))
        form.addRow("Tijd:", time_row)
        form.addRow("Locatie:", self.location)
        form.addRow("Adres:", self.location_address)
        form.addRow("Max. registraties:", self.maximum_registrants)
        form.addRow("Analyse:", self.exclude_from_analysis)
        if editing:
            self.region = QLineEdit(str(self.project_data.get("region", "") or ""))
            self.place = QLineEdit(str(self.project_data.get("place", "") or ""))
            self.external_contact = QLineEdit(str(self.project_data.get("external_contact", "") or ""))
            self.external_contact_reachability = QLineEdit(
                str(self.project_data.get("external_contact_reachability", "") or "")
            )
            self.status = ScrollSafeComboBox()
            # Zonder deze keuze kon een handmatige status niet blijven staan: de
            # automatische bepaling zette hem bij de eerstvolgende weergave terug.
            self.status.addItem(AUTOMATIC_STATUS, AUTOMATIC_STATUS)
            for value in EVENT_STATUSES:
                self.status.addItem(value, value)
            if self.project_data.get("status_manual"):
                self.status.setCurrentText(
                    str(self.project_data.get("status", "In voorbereiding") or "In voorbereiding")
                )
            else:
                self.status.setCurrentText(AUTOMATIC_STATUS)
            self.status.setToolTip(
                "Automatisch bepalen volgt de datum en de openstaande taken. Kies een vaste "
                "status om die te laten staan."
            )
            self.description = QPlainTextEdit()
            self.description.setPlainText(str(self.project_data.get("description", "") or ""))
            self.description.setMaximumHeight(90)
            self.target_audience = QPlainTextEdit()
            self.target_audience.setPlainText(str(self.project_data.get("target_audience", "") or ""))
            self.target_audience.setMaximumHeight(80)
            self.location_instructions = QPlainTextEdit()
            self.location_instructions.setPlainText(str(self.project_data.get("location_instructions", "") or ""))
            self.location_instructions.setMaximumHeight(80)
            form.addRow("Regio:", self.region)
            form.addRow("Plaats:", self.place)
            form.addRow("Externe contactpersoon:", self.external_contact)
            form.addRow("Bereikbaarheid contactpersoon:", self.external_contact_reachability)
            form.addRow("Locatie-instructies:", self.location_instructions)
            form.addRow("Status:", self.status)
            form.addRow("Korte beschrijving:", self.description)
            form.addRow("Doelgroep:", self.target_audience)
        content_layout.addLayout(form)
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setText(
            "Wijzigingen opslaan" if editing
            else "Template aanmaken" if self.template_mode
            else "Evenement aanmaken"
        )
        save_button.clicked.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.name.setFocus()
        if self.template_only and hasattr(self, "template_choice") and self.template_choice.count():
            self._template_changed()

    def _template_changed(self):
        if not hasattr(self, "template_choice"):
            return
        template_id = str(self.template_choice.currentData() or "")
        template = next(
            (item for item in self.project_templates if str(item.get("id", "") or "") == template_id),
            None,
        )
        if not template:
            self.name.clear()
            self.event_type.setCurrentText("Meeloopdag")
            self.location.clear()
            self.location_address.clear()
            self.start_time.clear()
            self.end_time.clear()
            self.maximum_registrants.clear()
            return
        source = template_event_data(template.get("event", {})) if isinstance(template.get("event"), dict) else {}
        self.name.setText(str(source.get("name", "") or template.get("name", "") or ""))
        self.event_type.setCurrentText(str(source.get("event_type", "Meeloopdag") or "Meeloopdag"))
        self.location.setText(str(source.get("location", "") or ""))
        self.location_address.setText(str(source.get("location_address", "") or ""))
        self.start_time.setText(str(source.get("start_time", "") or ""))
        self.end_time.setText(str(source.get("end_time", "") or ""))
        self.maximum_registrants.setText(str(source.get("maximum_registrants", "") or ""))
        self.project_date.clear()
        self.project_date.setFocus()

    def _validate_and_accept(self):
        if not self.name.text().strip():
            QMessageBox.information(self, "Naam ontbreekt", "Vul een naam voor het evenement in.")
            self.name.setFocus()
            return
        if not self.template_mode and not self.project_date.text().strip():
            QMessageBox.information(self, "Datum ontbreekt", "Vul de datum van het evenement in.")
            self.project_date.setFocus()
            return
        if not self.template_mode and parse_date(self.project_date.text()) is None:
            QMessageBox.information(self, "Datum ongeldig", "Gebruik bijvoorbeeld 29-09-2026.")
            self.project_date.setFocus()
            return
        if not valid_time_text(self.start_time.text()) or not valid_time_text(self.end_time.text()):
            QMessageBox.information(self, "Tijd ongeldig", "Gebruik voor tijden het formaat uu:mm, bijvoorbeeld 09:00 en 13:30.")
            (self.start_time if not valid_time_text(self.start_time.text()) else self.end_time).setFocus()
            return
        if self.start_time.text().strip() and self.end_time.text().strip() and self.end_time.text().strip() <= self.start_time.text().strip():
            QMessageBox.information(self, "Tijd ongeldig", "De eindtijd moet later zijn dan de starttijd.")
            self.end_time.setFocus()
            return
        maximum = self.maximum_registrants.text().strip()
        if maximum and (not maximum.isdigit() or int(maximum) <= 0):
            QMessageBox.information(self, "Maximum ongeldig", "Vul bij maximaal aantal registraties een positief geheel getal in.")
            self.maximum_registrants.setFocus()
            return
        if self.event_type.currentText() != "Online voorlichting" and not self.location.text().strip():
            QMessageBox.information(self, "Locatie ontbreekt", "Vul de locatie van het evenement in.")
            self.location.setFocus()
            return
        self.accept()

    def value(self):
        result = {
            "name": self.name.text().strip(),
            "event_type": self.event_type.currentText(),
            "date": self.project_date.text().strip(),
            "start_time": self.start_time.text().strip(),
            "end_time": self.end_time.text().strip(),
            "location": self.location.text().strip() or ("Online" if self.event_type.currentText() == "Online voorlichting" else ""),
            "location_address": self.location_address.text().strip(),
            "maximum_registrants": self.maximum_registrants.text().strip(),
            "exclude_from_analysis": self.exclude_from_analysis.isChecked(),
        }
        if self.project_data is not None:
            result.update({
                "region": self.region.text().strip(),
                "place": self.place.text().strip(),
                "external_contact": self.external_contact.text().strip(),
                "external_contact_reachability": self.external_contact_reachability.text().strip(),
                "status": (
                    str(self.project_data.get("status", "") or "Concept")
                    if self.status.currentText() == AUTOMATIC_STATUS
                    else self.status.currentText()
                ),
                "status_manual": self.status.currentText() != AUTOMATIC_STATUS,
                "description": self.description.toPlainText().strip(),
                "target_audience": self.target_audience.toPlainText().strip(),
                "location_instructions": self.location_instructions.toPlainText().strip(),
            })
        if hasattr(self, "template_link"):
            template_id = str(self.template_link.currentData() or "")
            linked = next((item for item in self.project_templates if item["id"] == template_id), None)
            result["template_id"] = template_id
            result["template_name"] = (linked["name"] if linked else
                str((self.project_data or {}).get("template_name", ""))) if template_id else ""
        return result

    def selected_template(self):
        if not hasattr(self, "template_choice"):
            return None
        template_id = str(self.template_choice.currentData() or "")
        return next(
            (deepcopy(item) for item in self.project_templates if str(item.get("id", "") or "") == template_id),
            None,
        )


class EventDialog(QDialog):
    def __init__(self, event: dict, parent=None):
        super().__init__(parent)
        self.project_data = deepcopy(event)
        self.setWindowTitle("Nieuw evenement" if not event.get("name") else "Evenement aanpassen")
        _fit_dialog_to_screen(self, 700, 670, 560, 360)
        layout = QVBoxLayout(self)
        scroll, content = _scroll_form_page()
        form = QFormLayout()
        self.name = QLineEdit(str(event.get("name", "") or ""))
        self.event_date = QLineEdit(str(event.get("date", "") or ""))
        self.event_date.setPlaceholderText("dd-mm-jjjj")
        self.region = QLineEdit(str(event.get("region", "") or ""))
        self.place = QLineEdit(str(event.get("place", "") or ""))
        self.location = QLineEdit(str(event.get("location", "") or ""))
        self.external_contact = QLineEdit(str(event.get("external_contact", "") or ""))
        self.external_contact_reachability = QLineEdit(str(event.get("external_contact_reachability", "") or ""))
        self.status = ScrollSafeComboBox()
        self.status.addItems(EVENT_STATUSES)
        self.status.setCurrentText(str(event.get("status", "Concept") or "Concept"))
        self.description = QPlainTextEdit(str(event.get("description", "") or ""))
        self.description.setMinimumHeight(95)
        self.target_audience = QPlainTextEdit(str(event.get("target_audience", "") or ""))
        self.target_audience.setMinimumHeight(80)
        self.exclude_from_analysis = QCheckBox("Niet meetellen in Statistieken en Trends")
        self.exclude_from_analysis.setChecked(bool(event.get("exclude_from_analysis", False)))
        form.addRow("Naam evenement*:", self.name)
        self.event_type = ScrollSafeComboBox()
        self.event_type.addItems(EVENT_TYPES)
        self.event_type.setCurrentText(str(event.get("event_type", "Meeloopdag") or "Meeloopdag"))
        form.addRow("Soort evenement:", self.event_type)
        form.addRow("Datum:", self.event_date)
        form.addRow("Regio:", self.region)
        form.addRow("Plaats:", self.place)
        form.addRow("Locatie:", self.location)
        form.addRow("Externe contactpersoon:", self.external_contact)
        form.addRow("Bereikbaarheid contactpersoon:", self.external_contact_reachability)
        form.addRow("Status:", self.status)
        form.addRow("Korte beschrijving:", self.description)
        form.addRow("Doelgroep:", self.target_audience)
        form.addRow("Analyse:", self.exclude_from_analysis)
        content.addLayout(form)
        content.addStretch()
        layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _try_accept(self):
        if not self.name.text().strip():
            QMessageBox.information(self, "Naam ontbreekt", "Geef het evenement een naam.")
            self.name.setFocus()
            return
        if self.event_date.text().strip() and parse_date(self.event_date.text()) is None:
            QMessageBox.information(
                self,
                "Datum ongeldig",
                "Gebruik voor de evenementdatum bijvoorbeeld 29-09-2026.",
            )
            self.event_date.setFocus()
            return
        self.accept()

    def value(self):
        result = deepcopy(self.project_data)
        result.update({
            "name": self.name.text().strip(),
            "event_type": self.event_type.currentText(),
            "date": self.event_date.text().strip(),
            "region": self.region.text().strip(),
            "place": self.place.text().strip(),
            "location": self.location.text().strip(),
            "external_contact": self.external_contact.text().strip(),
            "external_contact_reachability": self.external_contact_reachability.text().strip(),
            "status": self.status.currentText(),
            "description": self.description.toPlainText().strip(),
            "target_audience": self.target_audience.toPlainText().strip(),
            "exclude_from_analysis": self.exclude_from_analysis.isChecked(),
        })
        return result


class TaskDialog(QDialog):
    """Een taak instellen. Bij een standaardtaak hoort ook voor welke soorten
    evenementen hij meekomt; bij een taak van een evenement zelf niet."""

    def __init__(self, task: dict | None = None, parent=None, standaard: bool = False):
        super().__init__(parent)
        self.task = prepare_task(task)
        self.standaard = bool(standaard)
        self.type_boxes = {}
        self.setWindowTitle("Taak instellen")
        _fit_dialog_to_screen(self, 640, 430, 500, 340)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(self.task["title"])
        self.offset = QSpinBox()
        self.offset.setRange(0, 365)
        self.offset.setValue(self.task["offset_days"])
        self.relative = ScrollSafeComboBox()
        self.relative.addItem("vóór het evenement", "before")
        self.relative.addItem("na het evenement", "after")
        self.relative.setCurrentIndex(1 if self.task["relative"] == "after" else 0)
        self.reminder = QSpinBox()
        self.reminder.setRange(0, 365)
        self.reminder.setValue(self.task["reminder_days"])
        self.reminder.setSuffix(" dagen vooraf")
        self.notes = QPlainTextEdit(self.task["notes"])
        self.notes.setMinimumHeight(90)
        form.addRow("Taak*:", self.title)
        if self.standaard:
            gekozen = template_event_types(task or {})
            soorten_rij = QWidget()
            soorten_layout = QHBoxLayout(soorten_rij)
            soorten_layout.setContentsMargins(0, 0, 0, 0)
            soorten_layout.setSpacing(10)
            for soort in EVENT_TYPES:
                vak = QCheckBox(soort)
                vak.setChecked(soort in gekozen)
                self.type_boxes[soort] = vak
                soorten_layout.addWidget(vak)
            soorten_layout.addStretch(1)
            form.addRow("Geldt voor:", soorten_rij)
        deadline_row = QWidget()
        deadline_layout = QHBoxLayout(deadline_row)
        deadline_layout.setContentsMargins(0, 0, 0, 0)
        deadline_layout.addWidget(self.offset)
        deadline_layout.addWidget(self.relative, 1)
        form.addRow("Uitvoeren:", deadline_row)
        form.addRow("Melding tonen:", self.reminder)
        form.addRow("Notities:", self.notes)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self):
        result = deepcopy(self.task)
        result.update({
            "title": self.title.text().strip(),
            "offset_days": self.offset.value(),
            "relative": self.relative.currentData(),
            "reminder_days": self.reminder.value(),
            "notes": self.notes.toPlainText(),
        })
        if not self.standaard:
            return prepare_task(result)
        result["event_types"] = [soort for soort, vak in self.type_boxes.items() if vak.isChecked()]
        return prepare_template(result)


class FiveWhDialog(QDialog):
    def __init__(self, event: dict, profile: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"5WH invullen — {event.get('name', 'evenement')}")
        _fit_dialog_to_screen(self, 900, 720, 620, 420)
        self.data = deepcopy(event.get("fivewh", {}))
        self.data.setdefault("event_address", "\n".join(filter(None, [event.get("location", ""), event.get("place", "")])))
        self.data.setdefault("objective", event.get("description", ""))
        self.data.setdefault("target_audience", event.get("target_audience", ""))
        profile_name = " — ".join(filter(None, [profile.get("name", ""), profile.get("function", "")]))
        profile_contact = " | ".join(filter(None, [profile.get("email", ""), profile.get("phone", "")]))
        self.data.setdefault("poc_questions", "\n".join(filter(None, [profile_name, profile_contact])))
        layout = QVBoxLayout(self)
        intro = QLabel("Vul alleen de gegevens in die nodig zijn. De export gebruikt rechtstreeks het vaste 5WH-format.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        tabs = QTabWidget()
        groups = [
            ("Wat & wie", FIVEWH_FIELDS[:12]),
            ("Hoe", FIVEWH_FIELDS[12:22]),
            ("Steun & veiligheid", FIVEWH_FIELDS[22:]),
        ]
        self.editors = {}
        short_fields = {"build_time", "briefing_time", "event_time", "debrief_time", "teardown_time"}
        for title, fields in groups:
            scroll, content = _scroll_form_page()
            form = QFormLayout()
            for key, label in fields:
                if key in short_fields:
                    editor = QLineEdit(str(self.data.get(key, "") or ""))
                else:
                    editor = QPlainTextEdit(str(self.data.get(key, "") or ""))
                    editor.setMinimumHeight(68)
                self.editors[key] = editor
                form.addRow(label + ":", editor)
            content.addLayout(form)
            content.addStretch()
            tabs.addTab(scroll, title)
        layout.addWidget(tabs, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self):
        result = deepcopy(self.data)
        for key, editor in self.editors.items():
            result[key] = editor.text().strip() if isinstance(editor, QLineEdit) else editor.toPlainText().strip()
        return result


class EvaluationDialog(QDialog):
    def __init__(self, event: dict, profile: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Evaluatie invullen — {event.get('name', 'evenement')}")
        _fit_dialog_to_screen(self, 960, 740, 640, 420)
        self.data = deepcopy(event.get("evaluation", {}))
        defaults = {
            "date": event.get("date", ""), "event_name": event.get("name", ""),
            "region": event.get("region", ""), "place": event.get("place", ""),
            "location": event.get("location", ""), "external_contact": event.get("external_contact", ""),
            "external_contact_reachability": event.get("external_contact_reachability", ""),
            "description": event.get("description", ""), "target_audience": event.get("target_audience", ""),
            "filled_by": " — ".join(filter(None, [profile.get("name", ""), profile.get("function", "")])),
        }
        for key, value in defaults.items():
            self.data.setdefault(key, value)
        self.check_values = [bool(value) for value in self.data.get("checkboxes", [])]
        self.check_values.extend([False] * (76 - len(self.check_values)))
        self.check_values = self.check_values[:76]
        self.text_editors = {}
        self.exclusive_groups = []
        self.target_checkboxes = []

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        general_scroll, general_layout = _scroll_form_page()
        general_form = QFormLayout()
        for key, label, long_value in [
            ("date", "Datum evenement/beurs", False), ("event_name", "Naam evenement/beurs", False),
            ("region", "Regio", False), ("place", "Plaats", False), ("location", "Locatie", False),
            ("external_contact", "Contactpersoon externe organisatie", False),
            ("external_contact_reachability", "Bereikbaarheid contactpersoon", False),
            ("description", "Korte beschrijving", True), ("target_audience", "Doelgroep", True),
        ]:
            self._add_text(general_form, key, label, long_value)
        general_layout.addLayout(general_form)
        general_layout.addStretch()
        tabs.addTab(general_scroll, "Gegevens")

        reach_scroll, reach_layout = _scroll_form_page()
        reach_form = QFormLayout()
        self._add_choice(reach_form, "Bezoekersaantallen evenement/beurs", list(range(0, 6)),
                         ["< 100", "100-500", "500-1000", "1000-5000", "5000-10.000", "> 10.000"])
        self._add_text(reach_form, "event_visitors_estimate", "Geschat aantal bij > 10.000", False)
        self._add_choice(reach_form, "Bezoekersaantallen stand", list(range(6, 10)),
                         ["< 100", "100-250", "250-500", "> 500"])
        self._add_text(reach_form, "stand_visitors_estimate", "Geschat aantal bij > 500", False)
        self._add_choice(reach_form, "Belangstellenden voor baan", list(range(10, 15)),
                         ["< 25", "25-50", "50-100", "100-150", "> 150"])
        self._add_text(reach_form, "job_interest_estimate", "Geschat aantal bij > 150", False)
        for key, label in [
            ("age_under_16", "% jonger dan 16"), ("age_16_24", "% 16-24 jaar"),
            ("age_25_35", "% 25-35 jaar"), ("age_over_35", "% ouder dan 35"),
        ]:
            self._add_text(reach_form, key, label, False)
        reach_layout.addLayout(reach_form)
        targets = QGroupBox("Duidelijk aanwezige doelgroepen")
        targets_grid = QGridLayout(targets)
        for position, (index, label) in enumerate(EVALUATION_TARGET_GROUPS):
            checkbox = QCheckBox(label)
            checkbox.setChecked(self.check_values[index])
            self.target_checkboxes.append((index, checkbox))
            targets_grid.addWidget(checkbox, position // 2, position % 2)
        reach_layout.addWidget(targets)
        reach_form2 = QFormLayout()
        self._add_choice(reach_form2, "Piekmomenten", [29, 30], ["Nee", "Ja"])
        self._add_text(reach_form2, "peak_details", "Zo ja, namelijk", True)
        self._add_choice(reach_form2, "Eerder deze beurs gedraaid", [31, 32], ["Nee", "Ja"])
        self._add_text(reach_form2, "previous_experience", "Ervaringen t.o.v. vorige keer", True)
        self._add_choice(reach_form2, "Publiciteit organisatie", [33, 34, 35, 36], ["Goed", "Voldoende", "Matig", "Slecht"])
        reach_layout.addLayout(reach_form2)
        reach_layout.addStretch()
        tabs.addTab(reach_scroll, "Bereik & doelgroep")

        resources_scroll, resources_layout = _scroll_form_page()
        resources_form = QFormLayout()
        self._add_text(resources_form, "resources_general", "Evaluatie inzet en middelen", True)
        self._add_choice(resources_form, "Vorm van de stand", [37, 38, 39, 40, 41, 42],
                         ["Eilandstand", "Kopstand", "Afmeting", "Tent/paviljoen", "Inhuur ruimte", "Anders"])
        self._add_text(resources_form, "stand_width", "Breedte stand (m)", False)
        self._add_text(resources_form, "stand_depth", "Diepte stand (m)", False)
        self._add_text(resources_form, "stand_other", "Andere standvorm", False)
        self._add_choice(resources_form, "Locatie stand", [43, 44, 45, 46], ["Goed", "Voldoende", "Matig", "Slecht"])
        self._add_text(resources_form, "stand_location_suggestions", "Suggesties standlocatie", True)
        self._add_choice(resources_form, "Oppervlakte stand", [48, 49, 50], ["Te veel m²", "Precies goed", "Te weinig m²"])
        self._add_text(resources_form, "stand_surface_notes", "Opmerkingen oppervlakte", True)
        resources_layout.addLayout(resources_form)
        resources_layout.addStretch()
        tabs.addTab(resources_scroll, "Inzet & middelen")

        support_scroll, support_layout = _scroll_form_page()
        support_form = QFormLayout()
        self._add_choice(support_form, "Aangevraagd materieel aanwezig", [52, 53], ["Ja", "Nee"])
        self._add_text(support_form, "material_missing", "Ontbrekend materieel", True)
        self._add_text(support_form, "material_notes", "Opmerkingen materieel", True)
        self._add_choice(support_form, "Promotiemateriaal aanwezig", [56, 57], ["Ja", "Nee"])
        self._add_text(support_form, "promotion_missing", "Ontbrekend promotiemateriaal", True)
        self._add_text(support_form, "promotion_distributed", "Veel uitgedeeld aan doelgroep", True)
        self._add_text(support_form, "promotion_notes", "Opmerkingen promotiemateriaal", True)
        self._add_choice(support_form, "Voldoende wervingsmateriaal", [61, 62], ["Ja", "Nee"])
        self._add_text(support_form, "recruitment_material_missing", "Zo nee, namelijk", True)
        self._add_choice(support_form, "Wervingsmateriaal sloot aan", [63, 64], ["Ja", "Nee"])
        self._add_choice(support_form, "Al het personeel aanwezig", [65, 66], ["Nee", "Ja"])
        self._add_text(support_form, "personnel_missing", "Wie waren niet aanwezig", True)
        self._add_choice(support_form, "Publiciteit vanuit AMC", [68, 69], ["Ja", "Nee"])
        self._add_choice(support_form, "Wervingsondersteuning sloot aan", [70, 71], ["Ja", "Nee"])
        self._add_text(support_form, "support_reason", "Ja, omdat", True)
        self._add_text(support_form, "support_suggestions", "Suggesties", True)
        support_layout.addLayout(support_form)
        support_layout.addStretch()
        tabs.addTab(support_scroll, "Wervingsondersteuning")

        conclusion_scroll, conclusion_layout = _scroll_form_page()
        conclusion_form = QFormLayout()
        self._add_choice(conclusion_form, "Voor herhaling vatbaar", [73, 74, 75], ["Ja, omdat", "Ja, mits", "Nee, omdat"])
        self._add_text(conclusion_form, "repeat_yes_reason", "Ja, omdat", True)
        self._add_text(conclusion_form, "repeat_conditions", "Ja, mits", True)
        self._add_text(conclusion_form, "repeat_no_reason", "Nee, omdat", True)
        self._add_text(conclusion_form, "additional_comments", "Aanvullende opmerkingen en suggesties", True)
        self._add_text(conclusion_form, "filled_by", "Ingevuld door", False)
        conclusion_layout.addLayout(conclusion_form)
        conclusion_layout.addStretch()
        tabs.addTab(conclusion_scroll, "Conclusie")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add_text(self, form: QFormLayout, key: str, label: str, long_value: bool):
        if long_value:
            editor = QPlainTextEdit(str(self.data.get(key, "") or ""))
            editor.setMinimumHeight(75)
        else:
            editor = QLineEdit(str(self.data.get(key, "") or ""))
        self.text_editors[key] = editor
        form.addRow(label + ":", editor)

    def _add_choice(self, form: QFormLayout, label: str, indices: list[int], labels: list[str]):
        combo = ScrollSafeComboBox()
        combo.addItem("Niet ingevuld", None)
        for index, text_label in zip(indices, labels):
            combo.addItem(text_label, index)
        selected = next((index for index in indices if self.check_values[index]), None)
        if selected is not None:
            combo.setCurrentIndex(indices.index(selected) + 1)
        self.exclusive_groups.append((combo, indices))
        form.addRow(label + ":", combo)

    def value(self):
        result = deepcopy(self.data)
        for key, editor in self.text_editors.items():
            result[key] = editor.text().strip() if isinstance(editor, QLineEdit) else editor.toPlainText().strip()
        checks = [False] * 76
        for combo, indices in self.exclusive_groups:
            selected = combo.currentData()
            if selected in indices:
                checks[selected] = True
        for index, checkbox in self.target_checkboxes:
            checks[index] = checkbox.isChecked()
        marker_fields = {
            47: "stand_location_suggestions", 51: "stand_surface_notes", 54: "material_missing",
            55: "material_notes", 58: "promotion_missing", 59: "promotion_distributed",
            60: "promotion_notes", 67: "personnel_missing", 72: "support_suggestions",
        }
        for index, key in marker_fields.items():
            checks[index] = bool(str(result.get(key, "") or "").strip())
        result["checkboxes"] = checks
        return result
