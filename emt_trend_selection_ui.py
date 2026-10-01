"""Explicit category selection shared by Trends and its report builder."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QDialogButtonBox)


class TrendGroupDialog(QDialog):
    def __init__(self, parent, dimension, groups, selected=None):
        super().__init__(parent)
        self.setWindowTitle(f"Groepen kiezen — {dimension}")
        self.resize(580, 530)
        layout = QVBoxLayout(self)
        hint = QLabel("Kies de groepen voor grafieken en bijbehorende tabellen. Kerncijfers blijven over alle geselecteerde evenementen gaan. Aandelen blijven berekend ten opzichte van het oorspronkelijke totaal.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        search = QLineEdit()
        search.setPlaceholderText("Zoek een groep…")
        layout.addWidget(search)
        self.list = QListWidget()
        for group in sorted(groups, key=str.casefold):
            item = QListWidgetItem(group)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if selected is None or group in selected else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.list.setWordWrap(True)
        layout.addWidget(self.list, 1)
        search.textChanged.connect(self.search)
        row = QHBoxLayout()
        for label, state in (("Alles selecteren", True), ("Alles uit", False)):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, value=state: self.check_all(value))
            row.addWidget(button)
        layout.addLayout(row)
        self.count = QLabel()
        layout.addWidget(self.count)
        self.list.itemChanged.connect(self.update_count)
        self.update_count()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Toepassen")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuleren")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self):
        return [self.list.item(i).text() for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def search(self, text):
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text.casefold() not in item.text().casefold())

    def check_all(self, checked):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def update_count(self, *_):
        self.count.setText(f"{len(self.selected())} van {self.list.count()} groepen geselecteerd (inclusief verborgen zoekresultaten)")
