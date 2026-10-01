"""Event template editor and card browser, using the app's task editor and theme."""
from copy import deepcopy
from datetime import datetime
import uuid

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QFrame,
    QLabel, QLineEdit, QPlainTextEdit, QComboBox, QCheckBox, QPushButton,
    QDialogButtonBox, QListWidget, QAbstractItemView, QScrollArea, QWidget,
    QMenu, QMessageBox,
)
from emt_models import EVENT_TYPES, tasks_from_templates, task_timing_text
from emt_event_templates import template_event_data


def fit_template_dialog(dialog, width, height):
    area = dialog.screen().availableGeometry()
    dialog.resize(min(width, max(320, area.width() - 60)), min(height, max(300, area.height() - 80)))


class TemplateEditor(QDialog):
    def __init__(self, parent, task_editor, defaults, template=None, event=None):
        super().__init__(parent)
        self.setWindowTitle("Template aanpassen" if template else "Opslaan als template" if event else "Nieuw template")
        fit_template_dialog(self, 720, 700)
        self.task_editor, self.defaults = task_editor, defaults
        self.original = deepcopy(template or {})
        self.source = deepcopy(template.get("event", {})) if template else template_event_data(event or {})
        self.tasks = deepcopy(self.source.get("tasks", []))
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        form = QFormLayout()
        self.name = QLineEdit(str((template or {}).get("name", self.source.get("name", ""))))
        form.addRow("Templatenaam*:", self.name)
        self.fields = {}
        for key, label in (("name", "Standaard evenementnaam*"), ("location", "Locatie"), ("location_address", "Adres")):
            edit = QLineEdit(str(self.source.get(key, "")))
            self.fields[key] = edit
            form.addRow(label + ":", edit)
        self.event_type = QComboBox()
        self.event_type.addItems(EVENT_TYPES)
        self.event_type.setCurrentText(self.source.get("event_type") or EVENT_TYPES[0])
        form.addRow("Evenementsoort:", self.event_type)
        self.description = QPlainTextEdit(str(self.source.get("description", "")))
        self.description.setMaximumHeight(85)
        form.addRow("Beschrijving:", self.description)
        layout.addLayout(form)
        hint = QLabel("Datum en tijden kiest u bij het nieuwe evenement. Deelnemers, aanwezigheid, aftersales, livesessies en documenten worden niet overgenomen. Wijzigingen aan een template gelden voor nieuwe evenementen.")
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)
        self.include_tasks = QCheckBox("Taken overnemen" if event else "Standaardtaken gebruiken")
        self.include_tasks.setChecked(True)
        layout.addWidget(self.include_tasks)
        self.task_list = QListWidget()
        self.task_list.setMinimumHeight(150)
        self.task_list.setWordWrap(True)
        self.task_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.task_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        layout.addWidget(self.task_list)
        actions = QHBoxLayout()
        for label, callback in (("Taak toevoegen", lambda: self.edit_task()), ("Aanpassen", lambda: self.edit_task(True)), ("Verwijderen", self.remove_task), ("Standaardtaken overnemen", self.copy_defaults)):
            button = QPushButton(label)
            button.setObjectName("secondaryButton")
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.task_list.itemDoubleClicked.connect(lambda *_: self.edit_task(True))
        self.include_tasks.toggled.connect(self.task_list.setEnabled)
        self.link = QCheckBox("Dit evenement aan het nieuwe template koppelen")
        self.link.setChecked(True)
        self.link.setVisible(event is not None)
        layout.addWidget(self.link)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Opslaan")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuleren")
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.render_tasks()

    def render_tasks(self):
        from PySide6.QtWidgets import QListWidgetItem
        self.task_list.clear()
        for task in self.tasks:
            item = QListWidgetItem(f"{task['title']} · {task_timing_text(task)}")
            item.setData(Qt.ItemDataRole.UserRole, deepcopy(task))
            self.task_list.addItem(item)

    def ordered_tasks(self):
        return [self.task_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.task_list.count())]

    def edit_task(self, existing=False):
        self.tasks = self.ordered_tasks()
        row = self.task_list.currentRow() if existing else -1
        if existing and row < 0:
            return
        editor = self.task_editor(self.tasks[row] if existing else None, self)
        if editor.exec() == QDialog.DialogCode.Accepted:
            task = editor.value()
            if not task["title"].strip():
                return
            task.update(done=False, completed_on="", use_rudder_closing_date=False)
            if existing:
                self.tasks[row] = task
            else:
                self.tasks.append(task)
            self.render_tasks()

    def remove_task(self):
        row = self.task_list.currentRow()
        if row >= 0:
            self.task_list.takeItem(row)

    def copy_defaults(self):
        self.tasks = self.ordered_tasks()
        titles = {task["title"].casefold() for task in self.tasks}
        self.tasks.extend(task for task in tasks_from_templates(self.defaults, self.event_type.currentText()) if task["title"].casefold() not in titles)
        self.tasks = template_event_data({"tasks": self.tasks})["tasks"]
        self.include_tasks.setChecked(True)
        self.render_tasks()

    def validate(self):
        if not self.name.text().strip() or not self.fields["name"].text().strip():
            QMessageBox.information(self, "Naam ontbreekt", "Vul de templatenaam en standaard evenementnaam in.")
            return
        self.accept()

    def value(self):
        source = deepcopy(self.source)
        source.update({key: edit.text().strip() for key, edit in self.fields.items()})
        source.update(event_type=self.event_type.currentText(), description=self.description.toPlainText().strip())
        source["tasks"] = self.ordered_tasks() if self.include_tasks.isChecked() else []
        # Keep reusable task instructions entered in this editor.
        clean = template_event_data(source)
        for task, original in zip(clean["tasks"], source["tasks"]):
            task["notes"] = original.get("notes", "")
        return {
            "id": self.original.get("id") or uuid.uuid4().hex,
            "name": self.name.text().strip(),
            "created_at": self.original.get("created_at") or datetime.now().isoformat(timespec="seconds"),
            "event": clean,
        }


class TemplateCard(QFrame):
    opened = Signal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.opened.emit()
        super().mouseDoubleClickEvent(event)


class LinkEventsDialog(QDialog):
    """An explicit checked selection works for cards, tables and archived events."""
    def __init__(self, parent, events, templates, current_id=""):
        super().__init__(parent)
        from PySide6.QtWidgets import QListWidgetItem
        self.setWindowTitle("Evenementen aan template koppelen")
        fit_template_dialog(self, 760, 650)
        layout = QVBoxLayout(self)
        hint = QLabel("Selecteer de evenementen die bij hetzelfde template horen. Gegevens, deelnemers en taken blijven behouden; alleen de templatekoppeling verandert.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.template = QComboBox()
        for item in templates:
            self.template.addItem(item["name"], item["id"])
        layout.addWidget(self.template)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Zoek op naam, datum, locatie of huidig template…")
        layout.addWidget(self.search)
        self.events = QListWidget()
        self.events.setWordWrap(True)
        for event in events:
            item = QListWidgetItem(" · ".join(filter(None, [event.get("name"), event.get("date"), event.get("location"), event.get("template_name") or "Zonder template"])))
            item.setData(Qt.ItemDataRole.UserRole, event["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if event["id"] == current_id else Qt.CheckState.Unchecked)
            self.events.addItem(item)
        layout.addWidget(self.events, 1)
        self.search.textChanged.connect(self.filter_items)
        self.count = QLabel()
        self.events.itemChanged.connect(self.update_count)
        layout.addWidget(self.count)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.apply_button.setText("Koppelen")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuleren")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_count()

    def selected_ids(self):
        return [self.events.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.events.count())
                if self.events.item(i).checkState() == Qt.CheckState.Checked]

    def filter_items(self, text):
        for i in range(self.events.count()):
            item = self.events.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())
        self.update_count()

    def update_count(self, *_):
        selected = len(self.selected_ids())
        hidden = sum(self.events.item(i).isHidden() and self.events.item(i).checkState() == Qt.CheckState.Checked for i in range(self.events.count()))
        self.count.setText(f"{selected} evenementen geselecteerd" + (f" · {hidden} buiten het zoekresultaat" if hidden else ""))
        self.apply_button.setEnabled(selected > 0 and self.template.count() > 0)


class TemplateManager(QDialog):
    def __init__(self, parent, templates, task_editor, defaults, save):
        super().__init__(parent)
        self.setWindowTitle("Templatebeheer")
        fit_template_dialog(self, 850, 650)
        self.templates, self.task_editor, self.defaults, self.save = templates, task_editor, defaults, save
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Zoek een template…")
        self.search.textChanged.connect(self.refresh_cards)
        bar.addWidget(self.search)
        add = QPushButton("Nieuw template")
        add.setObjectName("primaryButton")
        add.clicked.connect(lambda: self.edit())
        bar.addWidget(add)
        layout.addLayout(bar)
        hint = QLabel("Dubbelklik om een template te bewerken. Bestaande evenementen behouden hun eigen instellingen en taken.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.scroll, 1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.button(QDialogButtonBox.StandardButton.Close).setText("Sluiten")
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.refresh_cards()

    def refresh_cards(self):
        content = QWidget()
        grid = QGridLayout(content)
        selected = [item for item in self.templates if self.search.text().casefold() in item['name'].casefold()]
        for i, template in enumerate(selected):
            card = TemplateCard()
            card.setObjectName("eventCard")
            card.setProperty("eventStatus", "concept")
            card.setMinimumHeight(130)
            card.opened.connect(lambda t=template: self.edit(t))
            inner = QVBoxLayout(card)
            title_row = QHBoxLayout()
            title = QLabel(template['name'])
            title.setTextFormat(Qt.TextFormat.PlainText)
            title.setObjectName("eventCardTitle")
            title.setWordWrap(True)
            title_row.addWidget(title, 1)
            more = QPushButton("•••")
            more.setFixedWidth(40)
            more.setToolTip("Meer acties")
            more.setStyleSheet("QPushButton { padding: 2px; } QPushButton::menu-indicator { image: none; width: 0px; }")
            menu = QMenu(more)
            menu.addAction("Aanpassen", lambda checked=False, t=template: self.edit(t))
            menu.addAction("Dupliceren", lambda checked=False, t=template: self.edit(t, True))
            menu.addAction("Verwijderen", lambda checked=False, t=template: self.remove(t))
            more.setMenu(menu)
            title_row.addWidget(more)
            inner.addLayout(title_row)
            source = template.get("event", {})
            label = QLabel(f"{source.get('event_type', '')}\n{source.get('location') or 'Geen standaardlocatie'}\n{len(source.get('tasks', []))} standaardtaken")
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            inner.addWidget(label)
            grid.addWidget(card, i // 2, i % 2)
        if not selected:
            empty = QLabel("Geen templates gevonden. Maak een template aan of sla een bestaand evenement op als template.")
            empty.setWordWrap(True)
            grid.addWidget(empty, 0, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch((len(selected) + 1) // 2 + 1, 1)
        old = self.scroll.takeWidget()
        if old:
            old.hide()
            old.deleteLater()
        self.scroll.setWidget(content)

    def edit(self, template=None, duplicate=False):
        source = deepcopy(template) if template else None
        if duplicate:
            source.update(id="", name=source["name"] + " (kopie)", created_at="")
        editor = TemplateEditor(self, self.task_editor, self.defaults, template=source)
        while editor.exec() == QDialog.DialogCode.Accepted:
            value = editor.value()
            if any(t['id'] != value['id'] and t['name'].casefold() == value['name'].casefold() for t in self.templates):
                QMessageBox.information(self, "Naam bestaat al", "Kies een andere templatenaam.")
                continue
            if template and not duplicate:
                template.clear()
                template.update(value)
            else:
                self.templates.append(value)
            self.save()
            self.refresh_cards()
            break

    def remove(self, template):
        if QMessageBox.question(self, "Template verwijderen", f"Wilt u '{template['name']}' verwijderen? Bestaande evenementen blijven behouden.") != QMessageBox.StandardButton.Yes:
            return
        self.templates.remove(template)
        self.save()
        self.refresh_cards()
