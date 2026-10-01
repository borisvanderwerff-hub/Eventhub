"""After sales via WhatsApp: de wachtrij per kandidaat, het beheer van berichtsjablonen
en de kleuren van de contactstatussen.

De module werkt met de gegevens die het hoofdvenster aanlevert en opent zelf nooit
WhatsApp zonder dat de gebruiker daarop klikt.
"""
from __future__ import annotations

from datetime import date, datetime
from html import escape
import json
import re
import uuid

from PySide6.QtCore import QRectF, QUrl, QUrlQuery, Qt
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from bezoekerslijst_core import EVENT_NAME_DATE_SUFFIX, event_base_name, normalize
from emt_widgets import ScrollSafeComboBox, _fit_dialog_to_screen


WHATSAPP_STATUSES = ["Nog te sturen", "Geopend", "Verzonden", "Overgeslagen"]


WHATSAPP_DEFAULT_TEMPLATE = (
    "Beste [voornaam],\n\n"
    "Bedankt voor je aanmelding voor [evenement] op [datum].\n\n"
    "[Vul hier het bericht in]"
)


# Oude standaardtemplates bevatten de afsluiting al in de berichttekst.
# De actuele WhatsApp-flow voegt uitsluitend de profielhandtekening toe,
# zodat er nooit twee handtekeningen onder hetzelfde bericht staan.
WHATSAPP_LEGACY_SIGNATURE_SUFFIXES = (
    "Met vriendelijke groet,\n[contactpersoon]\nDCPL",
    "Met vriendelijke groet,\n[contactpersoon]",
)


WHATSAPP_PLACEHOLDER_HINT = (
    "Beschikbaar: [voornaam], [tussenvoegsel], [achternaam], [volledige naam], [evenement], "
    "[datum], [locatie], [plaats], [handtekening] en [contactnummer]."
)


WHATSAPP_TEMPLATES_SETTING = "whatsapp_templates"


WHATSAPP_TEMPLATE_NAME_MAX = 60


WHATSAPP_TEMPLATE_PICKER_ROWS = 8


# Contactstatussen in After sales krijgen een vaste kleur:
# groen = afgehandeld, oranje = opnieuw proberen, rood = stoppen, grijs = nog niets gedaan.
CALLBACK_STATUS_COLOURS = {
    "Gesproken": "#2f9e5b",
    "Afgerond": "#2f9e5b",
    "WhatsApp verzonden": "#2f9e5b",
    "Terugbellen op verzoek": "#e08a1e",
    "Voicemail": "#e08a1e",
    "Geen gehoor": "#e08a1e",
    "Niet meer benaderen": "#d64545",
    "Nog bellen": "#8c919a",
}


def _whatsapp_phone(value) -> str:
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = "31" + digits[1:]
    elif len(digits) == 9 and digits.startswith("6"):
        digits = "31" + digits
    return digits if 8 <= len(digits) <= 15 else ""


def _profile_signature(profile: dict) -> str:
    """Build the WhatsApp profile signature including email; omit the 06-number."""
    first_name = str(profile.get("signature_first_name", "") or "").strip()
    if not first_name:
        first_name = str(profile.get("name", "") or "").strip().split(" ", 1)[0]
    rank = str(profile.get("signature_rank", "") or "").strip()
    department = str(profile.get("signature_department", "") or "").strip()
    organization = str(
        profile.get("signature_organization", "Ministerie van Defensie")
        or "Ministerie van Defensie"
    ).strip()
    email = str(profile.get("email", "") or "").strip()
    return "\n".join(filter(None, [" ".join(filter(None, [rank, first_name])), department, organization, email]))


def whatsapp_event_name(name) -> str:
    """De evenementnaam voor een bericht, zonder de datum die EventHub erachter zet.

    De datum komt in het bericht al via [datum]; zonder deze opschoning stond
    hij er twee keer in. Een volgnummer als "(2)" achter die datum is intern
    en valt ook weg. Een naam zonder datumachtervoegsel blijft ongewijzigd.
    """
    raw = str(name or "").strip()
    sequence = re.search(r"\s+\(\d+\)\s*$", raw)
    if sequence and EVENT_NAME_DATE_SUFFIX.search(raw[:sequence.start()]):
        raw = raw[:sequence.start()]
    return event_base_name(raw)


def default_whatsapp_templates() -> list[dict]:
    return [{"id": "standaard", "name": "Bedankt voor je aanmelding", "text": WHATSAPP_DEFAULT_TEMPLATE}]


def normalize_whatsapp_templates(raw) -> list[dict]:
    """Maak een opgeslagen sjabloonlijst veilig bruikbaar; onbruikbare regels vallen weg."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if not isinstance(raw, list):
        return []
    templates, seen_ids = [], set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = " ".join(str(entry.get("name", "") or "").split())[:WHATSAPP_TEMPLATE_NAME_MAX]
        text = str(entry.get("text", "") or "").strip()
        if not name or not text:
            continue
        template_id = str(entry.get("id", "") or "").strip()
        if not template_id or template_id in seen_ids:
            template_id = uuid.uuid4().hex
        seen_ids.add(template_id)
        templates.append({"id": template_id, "name": name, "text": text})
    return templates


def load_whatsapp_templates(settings) -> list[dict]:
    """Nog nooit opgeslagen: één voorbeeldsjabloon. Bewust leeggemaakt blijft leeg."""
    stored = settings.value(WHATSAPP_TEMPLATES_SETTING, None)
    if stored is None or stored == "":
        return default_whatsapp_templates()
    return normalize_whatsapp_templates(stored)


def save_whatsapp_templates(settings, templates: list[dict]) -> list[dict]:
    cleaned = normalize_whatsapp_templates(templates)
    settings.setValue(WHATSAPP_TEMPLATES_SETTING, json.dumps(cleaned, ensure_ascii=False))
    return cleaned


def callback_status_colour(status: str) -> str:
    return CALLBACK_STATUS_COLOURS.get(str(status or ""), CALLBACK_STATUS_COLOURS["Nog bellen"])


_CALLBACK_STATUS_ICON_CACHE: dict[str, QIcon] = {}


def callback_status_icon(status: str) -> QIcon:
    """Een gekleurde stip voor een contactstatus, scherp op geschaalde schermen."""
    colour = callback_status_colour(status)
    cached = _CALLBACK_STATUS_ICON_CACHE.get(colour)
    if cached is not None:
        return cached
    icon = QIcon()
    for scale in (1, 2, 3):
        size = 12 * scale
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colour))
        margin = 1.5 * scale
        painter.drawEllipse(QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
        painter.end()
        # Ook in een geselecteerde rij de echte kleur tonen, niet de getinte variant.
        icon.addPixmap(pixmap, QIcon.Mode.Normal)
        icon.addPixmap(pixmap, QIcon.Mode.Selected)
        icon.addPixmap(pixmap, QIcon.Mode.Active)
    _CALLBACK_STATUS_ICON_CACHE[colour] = icon
    return icon


class WhatsAppTemplatesDialog(QDialog):
    """Beheer de WhatsApp-sjablonen die in de WhatsApp-wachtrij te kiezen zijn."""

    def __init__(self, templates: list[dict], parent=None):
        super().__init__(parent)
        self.templates = [dict(template) for template in templates]
        self._loading = False
        self.setWindowTitle("WhatsApp-sjablonen beheren")
        _fit_dialog_to_screen(self, 820, 560, 620, 420)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Sjablonen verschijnen in de WhatsApp-wachtrij onder After sales. De volgorde hier is de "
            "volgorde in de keuzelijst."
        )
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        body = QHBoxLayout()
        left = QVBoxLayout()
        self.template_list = QListWidget()
        self.template_list.setMinimumWidth(240)
        self.template_list.currentRowChanged.connect(self._show_template)
        left.addWidget(self.template_list, 1)
        list_actions = QGridLayout()
        self.add_button = QPushButton("Nieuw")
        self.add_button.setObjectName("primaryButton")
        self.add_button.clicked.connect(self._add_template)
        self.duplicate_button = QPushButton("Dupliceren")
        self.duplicate_button.setObjectName("secondaryButton")
        self.duplicate_button.clicked.connect(self._duplicate_template)
        self.remove_button = QPushButton("Verwijderen")
        self.remove_button.setObjectName("secondaryButton")
        self.remove_button.clicked.connect(self._remove_template)
        self.up_button = QPushButton("Omhoog")
        self.up_button.clicked.connect(lambda: self._move_template(-1))
        self.down_button = QPushButton("Omlaag")
        self.down_button.clicked.connect(lambda: self._move_template(1))
        list_actions.addWidget(self.add_button, 0, 0)
        list_actions.addWidget(self.duplicate_button, 0, 1)
        list_actions.addWidget(self.up_button, 1, 0)
        list_actions.addWidget(self.down_button, 1, 1)
        list_actions.addWidget(self.remove_button, 2, 0, 1, 2)
        left.addLayout(list_actions)
        body.addLayout(left, 0)

        editor = QVBoxLayout()
        name_label = QLabel("Naam in de keuzelijst")
        name_label.setObjectName("hintLabel")
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(WHATSAPP_TEMPLATE_NAME_MAX)
        self.name_edit.setPlaceholderText("Bijvoorbeeld: Uitnodiging vervolgdag")
        self.name_edit.textChanged.connect(self._name_changed)
        text_label = QLabel("Berichttekst")
        text_label.setObjectName("hintLabel")
        placeholder_label = QLabel(WHATSAPP_PLACEHOLDER_HINT)
        placeholder_label.setObjectName("hintLabel")
        placeholder_label.setWordWrap(True)
        self.text_edit = QPlainTextEdit()
        self.text_edit.textChanged.connect(self._text_changed)
        editor.addWidget(name_label)
        editor.addWidget(self.name_edit)
        editor.addWidget(text_label)
        editor.addWidget(placeholder_label)
        editor.addWidget(self.text_edit, 1)
        signature_note = QLabel("De handtekening uit uw profiel wordt in de wachtrij apart toegevoegd.")
        signature_note.setObjectName("hintLabel")
        signature_note.setWordWrap(True)
        editor.addWidget(signature_note)
        body.addLayout(editor, 1)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Opslaan")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuleren")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        for template in self.templates:
            self.template_list.addItem(template["name"])
        self.template_list.setCurrentRow(0 if self.templates else -1)
        self._update_state()

    def _current_index(self) -> int:
        row = self.template_list.currentRow()
        return row if 0 <= row < len(self.templates) else -1

    def _show_template(self, row: int):
        self._loading = True
        try:
            template = self.templates[row] if 0 <= row < len(self.templates) else None
            self.name_edit.setText(template["name"] if template else "")
            self.text_edit.setPlainText(template["text"] if template else "")
        finally:
            self._loading = False
        self._update_state()

    def _update_state(self):
        index = self._current_index()
        has_selection = index >= 0
        self.name_edit.setEnabled(has_selection)
        self.text_edit.setEnabled(has_selection)
        self.duplicate_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)
        self.up_button.setEnabled(index > 0)
        self.down_button.setEnabled(has_selection and index < len(self.templates) - 1)

    def _name_changed(self, value: str):
        index = self._current_index()
        if self._loading or index < 0:
            return
        self.templates[index]["name"] = value
        self.template_list.item(index).setText(value.strip() or "Naamloos sjabloon")

    def _text_changed(self):
        index = self._current_index()
        if self._loading or index < 0:
            return
        self.templates[index]["text"] = self.text_edit.toPlainText()

    def _insert_template(self, template: dict, position: int):
        self.templates.insert(position, template)
        self.template_list.insertItem(position, template["name"])
        self.template_list.setCurrentRow(position)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _unique_name(self, base: str) -> str:
        existing = {normalize(template["name"]) for template in self.templates}
        name, sequence = base, 2
        while normalize(name) in existing:
            name = f"{base} ({sequence})"
            sequence += 1
        return name[:WHATSAPP_TEMPLATE_NAME_MAX]

    def _add_template(self):
        template = {"id": uuid.uuid4().hex, "name": self._unique_name("Nieuw sjabloon"),
                    "text": WHATSAPP_DEFAULT_TEMPLATE}
        self._insert_template(template, len(self.templates))

    def _duplicate_template(self):
        index = self._current_index()
        if index < 0:
            return
        source = self.templates[index]
        template = {"id": uuid.uuid4().hex, "name": self._unique_name(f"{source['name'].strip()} (kopie)"),
                    "text": source["text"]}
        self._insert_template(template, index + 1)

    def _remove_template(self):
        index = self._current_index()
        if index < 0:
            return
        name = self.templates[index]["name"].strip() or "Naamloos sjabloon"
        answer = QMessageBox.question(
            self, "Sjabloon verwijderen", f"Sjabloon '{name}' verwijderen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.templates.pop(index)
        self.template_list.takeItem(index)
        if self.templates:
            self.template_list.setCurrentRow(min(index, len(self.templates) - 1))
        else:
            self._show_template(-1)

    def _move_template(self, step: int):
        index = self._current_index()
        target = index + step
        if index < 0 or not 0 <= target < len(self.templates):
            return
        self.templates[index], self.templates[target] = self.templates[target], self.templates[index]
        item = self.template_list.takeItem(index)
        self.template_list.insertItem(target, item)
        self.template_list.setCurrentRow(target)

    def _accept_if_valid(self):
        seen = set()
        for row, template in enumerate(self.templates):
            name = " ".join(template["name"].split())
            problem = ""
            if not name:
                problem = "Geef ieder sjabloon een naam."
            elif normalize(name) in seen:
                problem = f"De naam '{name}' komt meer dan eens voor. Kies unieke namen."
            elif not template["text"].strip():
                problem = f"Sjabloon '{name}' heeft nog geen berichttekst."
            if problem:
                self.template_list.setCurrentRow(row)
                QMessageBox.warning(self, "Sjabloon controleren", problem)
                return
            seen.add(normalize(name))
        self.accept()

    def value(self) -> list[dict]:
        return normalize_whatsapp_templates(self.templates)


class WhatsAppQueueDialog(QDialog):
    def __init__(self, records: list[dict], event: dict, profile: dict, parent=None,
                 templates: list[dict] | None = None):
        super().__init__(parent)
        self.records = records
        self.templates = normalize_whatsapp_templates(templates or [])
        self.event_data = event
        self.profile = profile
        self.index = 0
        self.changed = False
        self.original_template = str(event.get("whatsapp_template", "") or WHATSAPP_DEFAULT_TEMPLATE)
        # Migreer alleen de bekende oude standaardafsluitingen. Eigen handmatig
        # geschreven berichttekst blijft onaangeroerd. De profielhandtekening
        # wordt hieronder één keer toegevoegd en bevat standaard geen 06-nummer.
        for legacy_suffix in WHATSAPP_LEGACY_SIGNATURE_SUFFIXES:
            suffix = legacy_suffix.strip()
            if self.original_template.strip().endswith(suffix):
                self.original_template = self.original_template.strip()[:-len(suffix)].rstrip()
                break
        self.setWindowTitle("WhatsApp-wachtrij — After sales")
        _fit_dialog_to_screen(self, 900, 720, 660, 480)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        intro = QLabel(
            "WhatsApp; markeer het daarna hier als verzonden. Openen is namelijk nog geen verzenden — zelfs Meta "
                        "kan geen verzending bevestigen."
        )
        intro.setObjectName("hintLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.progress_label = QLabel()
        self.progress_label.setObjectName("sectionTitle")
        self.person_label = QLabel()
        self.person_label.setWordWrap(True)
        layout.addWidget(self.progress_label)
        person_row = QHBoxLayout()
        person_row.setSpacing(10)
        person_row.addWidget(self.person_label, 1)
        template_picker_label = QLabel("Sjabloon")
        template_picker_label.setObjectName("hintLabel")
        self.template_picker = ScrollSafeComboBox()
        self.template_picker.setObjectName("whatsappTemplatePicker")
        # Nooit breder dan nodig en nooit een lijst over het hele scherm:
        # vanaf WHATSAPP_TEMPLATE_PICKER_ROWS sjablonen verschijnt een schuifbalk.
        self.template_picker.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.template_picker.setMinimumContentsLength(18)
        self.template_picker.setMaximumWidth(260)
        self.template_picker.setMaxVisibleItems(WHATSAPP_TEMPLATE_PICKER_ROWS)
        self.template_picker.setStyleSheet("QComboBox#whatsappTemplatePicker { combobox-popup: 0; }")
        self.template_picker.view().setTextElideMode(Qt.TextElideMode.ElideRight)
        self.template_picker.view().setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        if self.templates:
            self.template_picker.addItem("Kies een sjabloon…", "")
            for template in self.templates:
                self.template_picker.addItem(template["name"], template["id"])
                self.template_picker.setItemData(
                    self.template_picker.count() - 1, template["name"], Qt.ItemDataRole.ToolTipRole
                )
            self.template_picker.setToolTip("Kies een sjabloon als berichttekst. Beheren kan via Instellingen → WhatsApp-sjablonen.")
        else:
            self.template_picker.addItem("Geen sjablonen", "")
            self.template_picker.setEnabled(False)
            self.template_picker.setToolTip("Voeg sjablonen toe via Instellingen → WhatsApp-sjablonen.")
        person_row.addWidget(template_picker_label, 0, Qt.AlignmentFlag.AlignVCenter)
        person_row.addWidget(self.template_picker, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(person_row)

        template_group = QGroupBox("Berichtsjabloon voor dit evenement")
        template_layout = QVBoxLayout(template_group)
        placeholder_label = QLabel(WHATSAPP_PLACEHOLDER_HINT)
        placeholder_label.setWordWrap(True)
        placeholder_label.setObjectName("hintLabel")
        self.template_edit = QPlainTextEdit(self.original_template)
        self.template_edit.setMinimumHeight(150)
        self.template_edit.textChanged.connect(self._update_preview)
        template_layout.addWidget(placeholder_label)
        template_layout.addWidget(self.template_edit)
        self.add_signature = QCheckBox("Handtekening uit mijn profiel toevoegen")
        self.add_signature.setChecked(True)
        self.add_signature.toggled.connect(self._update_preview)
        template_layout.addWidget(self.add_signature)
        layout.addWidget(template_group)

        preview_group = QGroupBox("Voorbeeld voor de huidige kandidaat")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(120)
        preview_layout.addWidget(self.preview)
        layout.addWidget(preview_group, 1)

        navigation = QHBoxLayout()
        self.previous_button = QPushButton("Vorige")
        self.previous_button.clicked.connect(self._previous)
        self.open_button = QPushButton("WhatsApp openen")
        self.open_button.setObjectName("primaryButton")
        self.open_button.clicked.connect(self._open_whatsapp)
        self.sent_button = QPushButton("Verzonden → volgende")
        self.sent_button.setObjectName("secondaryButton")
        self.sent_button.clicked.connect(self._mark_sent)
        self.skip_button = QPushButton("Overslaan → volgende")
        self.skip_button.clicked.connect(self._skip)
        self.next_button = QPushButton("Volgende")
        self.next_button.clicked.connect(self._next)
        close_button = QPushButton("Sluiten")
        close_button.clicked.connect(self.accept)
        navigation.addWidget(self.previous_button)
        navigation.addWidget(self.open_button)
        navigation.addWidget(self.sent_button)
        navigation.addWidget(self.skip_button)
        navigation.addWidget(self.next_button)
        navigation.addStretch()
        navigation.addWidget(close_button)
        layout.addLayout(navigation)
        self._select_matching_template()
        self.template_picker.activated.connect(self._apply_picked_template)
        self._render_current()

    def _select_matching_template(self):
        """Toon welk sjabloon al als berichttekst staat, als dat er één is."""
        current = self.template_edit.toPlainText().strip()
        for template in self.templates:
            if template["text"].strip() == current:
                self.template_picker.setCurrentIndex(self.template_picker.findData(template["id"]))
                return
        self.template_picker.setCurrentIndex(0)

    def _apply_picked_template(self, index: int):
        template_id = self.template_picker.itemData(index)
        template = next((item for item in self.templates if item["id"] == template_id), None)
        if template is None:
            return
        current = self.template_edit.toPlainText().strip()
        known_texts = {item["text"].strip() for item in self.templates} | {WHATSAPP_DEFAULT_TEMPLATE.strip(), ""}
        if current != template["text"].strip() and current not in known_texts:
            answer = QMessageBox.question(
                self, "Berichttekst vervangen",
                f"De huidige berichttekst is aangepast. Vervangen door sjabloon '{template['name']}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._select_matching_template()
                return
        self.template_edit.setPlainText(template["text"])

    def _person_name(self, record: dict) -> str:
        return " ".join(filter(None, [
            str(record.get("Voornaam", "") or "").strip(),
            str(record.get("Tussenvoegsel", "") or "").strip(),
            str(record.get("Achternaam", "") or "").strip(),
        ])) or "Onbekende kandidaat"

    def _message_for(self, record: dict) -> str:
        full_name = self._person_name(record)
        location = " — ".join(filter(None, [
            str(self.event_data.get("place", "") or "").strip(),
            str(self.event_data.get("location", "") or "").strip(),
        ]))
        replacements = {
            "[voornaam]": str(record.get("Voornaam", "") or "").strip(),
            "[tussenvoegsel]": str(record.get("Tussenvoegsel", "") or "").strip(),
            "[achternaam]": str(record.get("Achternaam", "") or "").strip(),
            "[volledige naam]": full_name,
            "[evenement]": whatsapp_event_name(self.event_data.get("name", "") or record.get("Evenement", "")),
            "[datum]": str(self.event_data.get("date", "") or "").strip(),
            "[locatie]": location,
            "[plaats]": str(self.event_data.get("place", "") or "").strip(),
            "[handtekening]": _profile_signature(self.profile),
            # Backward compatibility for already saved templates.
            "[contactpersoon]": _profile_signature(self.profile),
            "[contactnummer]": str(self.profile.get("phone", "") or "").strip(),
        }
        message = self.template_edit.toPlainText()
        for placeholder, value in replacements.items():
            message = re.sub(re.escape(placeholder), lambda _match, value=value: value, message, flags=re.IGNORECASE)
        message = message.strip()
        if self.add_signature.isChecked():
            signature = _profile_signature(self.profile)
            if signature:
                message = f"{message}\n\n{signature}" if message else signature
        return message

    def _current(self) -> dict:
        return self.records[self.index]

    def _render_current(self):
        record = self._current()
        phone = str(record.get("Telefoonnummer", "") or "").strip()
        whatsapp_status = str(record.get("WhatsAppStatus", "Nog te sturen") or "Nog te sturen")
        self.progress_label.setText(f"Kandidaat {self.index + 1} van {len(self.records)}")
        self.person_label.setText(
            f"<b>{escape(self._person_name(record))}</b> &nbsp; • &nbsp; {escape(phone)} &nbsp; • &nbsp; "
            f"WhatsApp-status: <b>{escape(whatsapp_status)}</b>"
        )
        self.previous_button.setEnabled(self.index > 0)
        self.next_button.setEnabled(self.index < len(self.records) - 1)
        self.skip_button.setText("Overslaan → volgende" if self.index < len(self.records) - 1 else "Overslaan")
        self.sent_button.setText("Verzonden → volgende" if self.index < len(self.records) - 1 else "Verzonden")
        self._update_preview()

    def _update_preview(self):
        if self.records:
            self.preview.setPlainText(self._message_for(self._current()))

    def _open_whatsapp(self):
        record = self._current()
        phone = _whatsapp_phone(record.get("Telefoonnummer", ""))
        if not phone:
            QMessageBox.warning(self, "Ongeldig telefoonnummer", "Dit telefoonnummer kan niet als WhatsApp-nummer worden geopend.")
            return
        message = self._message_for(record)
        if not message:
            QMessageBox.information(self, "Leeg bericht", "Vul eerst een bericht in.")
            return
        if re.search(r"\[vul hier", message, flags=re.IGNORECASE):
            QMessageBox.information(
                self,
                "Bericht nog niet ingevuld",
                "Vervang eerst '[Vul hier het bericht in]' door de daadwerkelijke tekst.",
            )
            return
        url = QUrl(f"https://wa.me/{phone}")
        query = QUrlQuery()
        query.addQueryItem("text", message)
        url.setQuery(query)
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "WhatsApp niet geopend", "WhatsApp of WhatsApp Web kon niet worden geopend.")
            return
        record["WhatsAppStatus"] = "Geopend"
        record["WhatsAppGeopendOp"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        self.changed = True
        self._render_current()

    def _mark_sent(self):
        record = self._current()
        record["WhatsAppStatus"] = "Verzonden"
        record["WhatsAppVerzondenOp"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        record["Terugbelstatus"] = "WhatsApp verzonden"
        record["Teruggebeld"] = True
        if not str(record.get("LaatsteContact", "") or "").strip():
            record["LaatsteContact"] = date.today().strftime("%d-%m-%Y")
        self.changed = True
        if self.index < len(self.records) - 1:
            self.index += 1
        self._render_current()

    def _skip(self):
        self._current()["WhatsAppStatus"] = "Overgeslagen"
        self.changed = True
        if self.index < len(self.records) - 1:
            self.index += 1
        self._render_current()

    def _previous(self):
        if self.index > 0:
            self.index -= 1
            self._render_current()

    def _next(self):
        if self.index < len(self.records) - 1:
            self.index += 1
            self._render_current()

    def done(self, result: int):
        template = self.template_edit.toPlainText().strip()
        if template != self.original_template.strip():
            self.event_data["whatsapp_template"] = template
            self.changed = True
        super().done(result)
