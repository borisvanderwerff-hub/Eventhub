"""De Report Builder: de exportomgeving van Trends.

Vijf stappen — selectie, inhoud, vormgeving, exportvoorbeeld en exporteren —
rond dezelfde dataset. De keuzes staan in één ``ReportConfig``; het voorbeeld
en de PDF gebruiken dezelfde opmaak, zodat wat je ziet ook is wat je krijgt.

De rapportinhoud zelf staat in emt_report, de opmaak in emt_report_layout en
de uitvoer in emt_report_export. Hier staat alleen de bediening.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

import emt_report as report
from emt_trend_selection_ui import TrendGroupDialog
from emt_report_export import ExportError, export_excel, export_pdf
from emt_report_layout import ReportLayout

STAPPEN = ["Selectie", "Inhoud", "Vormgeving", "Exportvoorbeeld", "Exporteren"]


# --------------------------------------------------------------- voorbeeld

class ReportPreview(QWidget):
    """Eén rapportpagina, getekend met exact dezelfde opmaak als de PDF."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_engine: ReportLayout | None = None
        self.page = 0
        self.zoom = 1.0
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_layout_engine(self, engine: ReportLayout | None):
        self.layout_engine = engine
        self.page = min(self.page, max(0, (engine.page_count() - 1) if engine else 0))
        self._resize()

    def set_page(self, index: int):
        if self.layout_engine:
            self.page = max(0, min(index, self.layout_engine.page_count() - 1))
        self.update()

    def set_zoom(self, zoom: float):
        self.zoom = max(0.2, min(3.0, float(zoom)))
        self._resize()

    def fit(self, breedte: float, hoogte: float):
        if not self.layout_engine:
            return
        self.set_zoom(min(breedte / self.layout_engine.page_width,
                          hoogte / self.layout_engine.page_height))

    def _resize(self):
        if not self.layout_engine:
            self.setFixedSize(10, 10)
            return
        self.setFixedSize(int(self.layout_engine.page_width * self.zoom),
                          int(self.layout_engine.page_height * self.zoom))
        self.update()

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor("#8a8f99"))
            if not self.layout_engine:
                return
            painter.scale(self.zoom, self.zoom)
            self.layout_engine.paint_page(painter, self.page)
            painter.setPen(QColor("#5b6472"))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(0, 0, self.layout_engine.page_width - 1,
                                    self.layout_engine.page_height - 1))
        finally:
            painter.end()


# ------------------------------------------------------------- de omgeving

class ReportBuilderDialog(QDialog):
    """De exportomgeving van Trends."""

    def __init__(self, summaries, selectie: dict, settings, parent=None,
                 bron: str = "", status_callback=None, folder=None,
                 werkgebied: str = ""):
        super().__init__(parent)
        # Het werkgebied in de titel: er is één exportknop voor twee
        # werkgebieden, dus moet zichtbaar zijn welke er nu in gaat.
        self.setWindowTitle(
            f"Rapport samenstellen — {werkgebied}" if werkgebied else "Rapport samenstellen"
        )
        self.summaries = list(summaries or [])
        self.settings = settings
        self.bron = bron
        self.status_callback = status_callback
        self.config = report.default_config("managementrapport")
        self.config["selectie"].update(selectie or {})
        self.config["selectie"]["bron"] = bron
        self.config["titel"] = report.default_title(self.config["selectie"])
        self._laden = True
        self.layout_engine: ReportLayout | None = None

        scherm = parent.screen() if parent and parent.screen() else None
        if scherm:
            beschikbaar = scherm.availableGeometry()
            self.resize(min(1180, int(beschikbaar.width() * 0.92)),
                        min(820, int(beschikbaar.height() * 0.92)))
        else:
            self.resize(1180, 820)

        buiten = QVBoxLayout(self)
        buiten.setContentsMargins(18, 14, 18, 14)
        buiten.setSpacing(12)
        buiten.addWidget(self._build_stepper())

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_selection_page())
        self.pages.addWidget(self._build_content_page())
        self.pages.addWidget(self._build_design_page())
        self.pages.addWidget(self._build_preview_page())
        self.pages.addWidget(self._build_export_page())
        buiten.addWidget(self.pages, 1)

        knoppen = QHBoxLayout()
        self.hint = QLabel("")
        self.hint.setObjectName("hintLabel")
        self.hint.setWordWrap(True)
        knoppen.addWidget(self.hint, 1)
        self.back_button = QPushButton("← Vorige")
        self.back_button.setObjectName("secondaryButton")
        self.back_button.clicked.connect(lambda: self.go_to(self.pages.currentIndex() - 1))
        self.next_button = QPushButton("Volgende →")
        self.next_button.setObjectName("primaryButton")
        self.next_button.clicked.connect(lambda: self.go_to(self.pages.currentIndex() + 1))
        sluiten = QPushButton("Sluiten")
        sluiten.setObjectName("secondaryButton")
        sluiten.clicked.connect(self.reject)
        for knop in (sluiten, self.back_button, self.next_button):
            knoppen.addWidget(knop)
        buiten.addLayout(knoppen)

        self._laden = False
        self._display_changed()
        self.set_folder(folder or Path.home())
        self._apply_preset("huidige_analyse" if "analysis_metric" in (selectie or {}) else "managementrapport")
        self.go_to(0)

    # ------------------------------------------------------------- stepper

    def _build_stepper(self) -> QWidget:
        balk = QFrame()
        balk.setObjectName("toolbar")
        rij = QHBoxLayout(balk)
        rij.setContentsMargins(14, 8, 14, 8)
        rij.setSpacing(6)
        self.step_labels = []
        for index, naam in enumerate(STAPPEN):
            label = QLabel(f"{index + 1}. {naam}")
            label.setObjectName("reportStep")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.mouseReleaseEvent = (
                lambda _event, doel=index: self.go_to(doel)
            )
            self.step_labels.append(label)
            rij.addWidget(label, 1)
            if index < len(STAPPEN) - 1:
                pijl = QLabel("›")
                pijl.setObjectName("hintLabel")
                rij.addWidget(pijl)
        return balk

    def _mark_step(self, index: int):
        for positie, label in enumerate(self.step_labels):
            label.setProperty("actief", "true" if positie == index else "false")
            label.setProperty("gedaan", "true" if positie < index else "false")
            label.style().unpolish(label)
            label.style().polish(label)

    def go_to(self, index: int):
        index = max(0, min(index, self.pages.count() - 1))
        self.pages.setCurrentIndex(index)
        self._mark_step(index)
        self.back_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < self.pages.count() - 1)
        if index == 3:
            self._rebuild_preview()
        if index == 4:
            self._refresh_export_page()
        self.hint.setText({
            0: "De filters van Trends staan al ingevuld; pas ze hier aan als het rapport een andere periode moet beslaan.",
            1: "Vink aan wat in het rapport komt en sleep de onderdelen in de gewenste volgorde.",
            2: "Titel, voorblad en pagina-instellingen.",
            3: "Dit is hoe het rapport eruitziet; de PDF gebruikt exact dezelfde opmaak.",
            4: "Kies het formaat en de bestandsnaam.",
        }.get(index, ""))

    # ------------------------------------------------------ stap 1: selectie

    def _build_selection_page(self) -> QWidget:
        pagina = QWidget()
        buiten = QVBoxLayout(pagina)
        buiten.setSpacing(12)

        vak = QGroupBox("Welke gegevens gaan het rapport in?")
        vorm = QFormLayout(vak)
        self.since_field = QLineEdit()
        self.until_field = QLineEdit()
        for veld in (self.since_field, self.until_field):
            veld.setPlaceholderText("dd-mm-jjjj")
            veld.textChanged.connect(self._selection_changed)
        selectie = self.config["selectie"]
        if selectie.get("since"):
            self.since_field.setText(selectie["since"].strftime("%d-%m-%Y"))
        if selectie.get("until"):
            self.until_field.setText(selectie["until"].strftime("%d-%m-%Y"))
        periode = QWidget()
        periode_rij = QHBoxLayout(periode)
        periode_rij.setContentsMargins(0, 0, 0, 0)
        periode_rij.addWidget(QLabel("van"))
        periode_rij.addWidget(self.since_field, 1)
        periode_rij.addWidget(QLabel("tot en met"))
        periode_rij.addWidget(self.until_field, 1)
        vorm.addRow("Periode:", periode)

        self.type_filter = QComboBox()
        self.event_template_filter = QComboBox()
        self.location_filter = QComboBox()
        self.event_filter = QComboBox()
        for combo, sleutel, leeg in (
            (self.type_filter, "event_type", "Alle evenementsoorten"),
            (self.event_template_filter, "template_id", "Alle templates"),
            (self.location_filter, "location", "Alle locaties"),
            (self.event_filter, "event_id", "Alle evenementen"),
        ):
            combo.addItem(leeg, "")
            combo.currentIndexChanged.connect(self._selection_changed)
        for waarde in sorted({str(item.get("event_type", "") or "") for item in self.summaries} - {""}):
            self.type_filter.addItem(waarde, waarde)
        templates = {str(item["template_id"]): str(item.get("template_name") or "Template")
                     for item in self.summaries if item.get("template_id")}
        for ident, name in sorted(templates.items(), key=lambda item: item[1].casefold()):
            self.event_template_filter.addItem(name, ident)
        for waarde in sorted({str(item.get("location", "") or item.get("place", "") or "")
                              for item in self.summaries} - {""}):
            self.location_filter.addItem(waarde, waarde)
        for item in sorted(self.summaries, key=lambda regel: str(regel.get("name", ""))):
            self.event_filter.addItem(str(item.get("name", "")), str(item.get("id", "")))
        for combo, sleutel in ((self.type_filter, "event_type"),
                               (self.event_template_filter, "template_id"),
                               (self.location_filter, "location"),
                               (self.event_filter, "event_id")):
            positie = combo.findData(selectie.get(sleutel, ""))
            if positie >= 0:
                combo.setCurrentIndex(positie)
        vorm.addRow("Evenementsoort:", self.type_filter)
        vorm.addRow("Template:", self.event_template_filter)
        vorm.addRow("Locatie:", self.location_filter)
        vorm.addRow("Evenement:", self.event_filter)

        self.display_choice = QComboBox()
        for waarde, label in report.DISPLAY_LABELS.items():
            self.display_choice.addItem(label, waarde)
        huidige_weergave = self.display_choice.findData(report.selected_display(selectie))
        self.display_choice.setCurrentIndex(max(0, huidige_weergave))
        self.display_choice.setToolTip(
            "Statistieken vatten de hele selectie samen in staven per groep. "
            "Verloop zet dezelfde cijfers uit in de tijd."
        )
        self.display_choice.currentIndexChanged.connect(self._display_changed)
        vorm.addRow("Weergave:", self.display_choice)

        # Dezelfde tijdseenheden als op de Trends-pagina zelf.
        self.period_choice = QComboBox()
        for waarde, label in report.PERIOD_LABELS.items():
            self.period_choice.addItem(label, waarde)
        huidig = self.period_choice.findData(report.selected_period(selectie))
        self.period_choice.setCurrentIndex(max(0, huidig))
        self.period_choice.setToolTip(
            "Geldt voor de grafieken die een ontwikkeling laten zien; een "
            "totaal per groep blijft een totaal."
        )
        self.period_choice.currentIndexChanged.connect(self._selection_changed)
        vorm.addRow("Tijdseenheid:", self.period_choice)

        self.percentage_choice = QCheckBox("Als percentage van totaal")
        self.percentage_choice.setToolTip(
            "Toon groepswaarden als aandeel van het totaal, met het aantal erbij."
        )
        self.percentage_choice.setChecked(bool(selectie.get("percentage_of_total")))
        self.percentage_choice.stateChanged.connect(self._selection_changed)
        vorm.addRow("Groepswaarden:", self.percentage_choice)
        self.groups_button = QPushButton("Groepen kiezen…")
        self.groups_button.clicked.connect(self._choose_groups)
        vorm.addRow("Getoonde groepen:", self.groups_button)
        buiten.addWidget(vak)

        self.dataset_box = QGroupBox("Deze dataset gebruikt het hele rapport")
        # Onder elkaar liep de opsomming buiten beeld zodra er filters bij
        # kwamen; in twee kolommen past hij op één scherm.
        self.dataset_layout = QGridLayout(self.dataset_box)
        self.dataset_layout.setHorizontalSpacing(28)
        self.dataset_layout.setVerticalSpacing(6)
        buiten.addWidget(self.dataset_box)
        buiten.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(pagina)
        return scroll

    def _selection_changed(self, *_):
        if self._laden:
            return
        from emt_models import parse_date

        self.config["selectie"].update({
            "since": parse_date(self.since_field.text()),
            "until": parse_date(self.until_field.text()),
            "event_type": str(self.type_filter.currentData() or ""),
            "template_id": str(self.event_template_filter.currentData() or ""),
            "template_name": self.event_template_filter.currentText() if self.event_template_filter.currentData() else "",
            "location": str(self.location_filter.currentData() or ""),
            "event_id": str(self.event_filter.currentData() or ""),
            "periode": str(self.period_choice.currentData() or "month"),
            "weergave": str(self.display_choice.currentData() or report.VERLOOP),
            "percentage_of_total": self.percentage_choice.isChecked(),
        })
        self._refresh_dataset_summary()
        self._refresh_section_availability()

    def _choose_groups(self):
        from PySide6.QtWidgets import QMenu
        selected = report.selected_summaries(self.summaries, self.config["selectie"])
        menu = QMenu(self)
        for dimension in report.available_dimensions(selected):
            if not dimension:
                continue
            action = menu.addAction(dimension)
            action.setData(dimension)
        action = menu.exec(self.groups_button.mapToGlobal(self.groups_button.rect().bottomLeft()))
        if action is None:
            return
        dimension = action.data()
        groups = report.build_series(selected, "aangemeld", dimension, "total").get("groups", [])
        selections = self.config["selectie"].setdefault("group_selections", {})
        dialog = TrendGroupDialog(self, dimension, groups, selections.get(dimension))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chosen = dialog.selected()
            if set(chosen) == set(groups):
                selections.pop(dimension, None)
            else:
                selections[dimension] = chosen
            self._selection_changed()

    def _display_changed(self, *_):
        """Bij statistieken zegt de tijdseenheid niets meer."""
        verloop = str(self.display_choice.currentData() or report.VERLOOP) == report.VERLOOP
        self.period_choice.setEnabled(verloop)
        self._selection_changed()

    def selected_summaries(self) -> list:
        return report.selected_summaries(self.summaries, self.config["selectie"])

    DATASET_KOLOMMEN = 2

    def _refresh_dataset_summary(self):
        while self.dataset_layout.count():
            item = self.dataset_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        gekozen = self.selected_summaries()
        regels = list(report.dataset_summary(gekozen, self.config["selectie"]))
        if self.bron:
            regels.append(("Bron", self.bron))

        # Kolomsgewijs vullen: eerst de linkerkolom vol, dan de rechter. Zo
        # blijft de leesvolgorde van boven naar beneden.
        per_kolom = max(1, -(-len(regels) // self.DATASET_KOLOMMEN))
        for index, (naam, waarde) in enumerate(regels):
            regel = QLabel(f"<b>{escape(str(naam))}</b><br>{escape(str(waarde))}")
            regel.setTextFormat(Qt.TextFormat.RichText)
            regel.setWordWrap(True)
            self.dataset_layout.addWidget(regel, index % per_kolom, index // per_kolom)
        for kolom in range(self.DATASET_KOLOMMEN):
            self.dataset_layout.setColumnStretch(kolom, 1)

        if not gekozen:
            waarschuwing = QLabel("Deze selectie levert geen evenementen met cijfers op.")
            waarschuwing.setObjectName("hintLabel")
            self.dataset_layout.addWidget(waarschuwing, per_kolom, 0, 1,
                                          self.DATASET_KOLOMMEN)

    # -------------------------------------------------------- stap 2: inhoud

    def _build_content_page(self) -> QWidget:
        pagina = QWidget()
        buiten = QVBoxLayout(pagina)
        buiten.setSpacing(10)

        bovenaan = QHBoxLayout()
        bovenaan.addWidget(QLabel("Rapportprofiel:"))
        self.preset_choice = QComboBox()
        for sleutel, label, _keys in report.PRESETS:
            self.preset_choice.addItem(label, sleutel)
        self.preset_choice.currentIndexChanged.connect(
            lambda: self._apply_preset(str(self.preset_choice.currentData() or "aangepast"))
        )
        bovenaan.addWidget(self.preset_choice)
        bovenaan.addSpacing(18)
        bovenaan.addWidget(QLabel("Eigen sjabloon:"))
        self.template_choice = QComboBox()
        self.template_choice.currentIndexChanged.connect(self._load_template)
        bovenaan.addWidget(self.template_choice, 1)
        for tekst, handler in (("Opslaan", self._save_template),
                               ("Hernoemen", self._rename_template),
                               ("Verwijderen", self._delete_template)):
            knop = QPushButton(tekst)
            knop.setObjectName("secondaryButton")
            knop.clicked.connect(handler)
            bovenaan.addWidget(knop)
        buiten.addLayout(bovenaan)

        body = QHBoxLayout()
        links = QVBoxLayout()
        uitleg = QLabel("Sleep om de volgorde te bepalen. Onderdelen zonder gegevens staan uit.")
        uitleg.setObjectName("hintLabel")
        links.addWidget(uitleg)
        self.section_list = QListWidget()
        self.section_list.setObjectName("dashboardTable")
        self.section_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.section_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.section_list.itemChanged.connect(self._section_toggled)
        self.section_list.currentRowChanged.connect(lambda _row: self._refresh_chart_list())
        self.section_list.model().rowsMoved.connect(lambda *_: self._store_section_order())
        links.addWidget(self.section_list, 1)
        body.addLayout(links, 3)

        rechts = QVBoxLayout()
        self.chart_title = QLabel("Grafieken")
        self.chart_title.setObjectName("hintLabel")
        rechts.addWidget(self.chart_title)
        self.chart_list = QListWidget()
        self.chart_list.setObjectName("dashboardTable")
        self.chart_list.itemChanged.connect(self._chart_toggled)
        rechts.addWidget(self.chart_list, 1)
        body.addLayout(rechts, 2)
        buiten.addLayout(body, 1)
        self._refresh_templates()
        return pagina

    def _apply_preset(self, preset: str):
        if self._laden:
            return
        if preset != "aangepast":
            self.config["preset"] = preset
            self.config["secties"] = report.sections_for_preset(preset)
        else:
            self.config["preset"] = "aangepast"
        self._refresh_section_availability()

    def _refresh_section_availability(self):
        gekozen = self.selected_summaries()
        self.beschikbaar = report.available_sections(gekozen)
        self._laden = True
        try:
            self.section_list.clear()
            for onderdeel in self.config["secties"]:
                definitie = report.SECTION_BY_KEY[onderdeel["key"]]
                item = QListWidgetItem(definitie["title"])
                item.setData(Qt.ItemDataRole.UserRole, onderdeel["key"])
                bruikbaar = onderdeel["key"] in self.beschikbaar
                vlaggen = (Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                           | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsDragEnabled)
                if not bruikbaar:
                    onderdeel["aan"] = False
                    vlaggen = Qt.ItemFlag.ItemIsSelectable
                    item.setText(f"{definitie['title']}  —  geen gegevens")
                item.setFlags(vlaggen)
                item.setCheckState(Qt.CheckState.Checked if onderdeel["aan"]
                                   else Qt.CheckState.Unchecked)
                self.section_list.addItem(item)
            if self.section_list.count():
                self.section_list.setCurrentRow(0)
        finally:
            self._laden = False
        self._refresh_chart_list()
        self._refresh_dataset_summary()

    def _section_at(self, key: str) -> dict:
        return next(item for item in self.config["secties"] if item["key"] == key)

    def _section_toggled(self, item: QListWidgetItem):
        if self._laden:
            return
        sleutel = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self._section_at(sleutel)["aan"] = item.checkState() == Qt.CheckState.Checked
        self._mark_custom()

    def _store_section_order(self):
        if self._laden:
            return
        volgorde = [str(self.section_list.item(rij).data(Qt.ItemDataRole.UserRole))
                    for rij in range(self.section_list.count())]
        self.config["secties"] = sorted(
            self.config["secties"], key=lambda item: volgorde.index(item["key"])
        )
        self._mark_custom()

    def _mark_custom(self):
        self.config["preset"] = "aangepast"
        positie = self.preset_choice.findData("aangepast")
        if positie >= 0 and self.preset_choice.currentIndex() != positie:
            self._laden = True
            self.preset_choice.setCurrentIndex(positie)
            self._laden = False

    def _refresh_chart_list(self):
        self._laden = True
        try:
            self.chart_list.clear()
            item = self.section_list.currentItem()
            if item is None:
                self.chart_title.setText("Grafieken")
                return
            sleutel = str(item.data(Qt.ItemDataRole.UserRole) or "")
            definitie = report.SECTION_BY_KEY[sleutel]
            self.chart_title.setText(f"Grafieken in {definitie['title']}")
            if not definitie["charts"]:
                self.chart_list.addItem(QListWidgetItem("Dit onderdeel heeft geen grafieken."))
                return
            bruikbaar = report.available_charts(
                self.selected_summaries(), sleutel,
                report.selected_period(self.config["selectie"]),
            )
            onderdeel = self._section_at(sleutel)
            for grafiek in definitie["charts"]:
                regel = QListWidgetItem(grafiek["title"])
                regel.setData(Qt.ItemDataRole.UserRole, (sleutel, grafiek["key"]))
                if grafiek["key"] in bruikbaar:
                    regel.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    aan = onderdeel["grafieken"].get(grafiek["key"], True)
                else:
                    regel.setFlags(Qt.ItemFlag.ItemIsSelectable)
                    regel.setText(f"{grafiek['title']}  —  geen waarden")
                    aan = False
                regel.setCheckState(Qt.CheckState.Checked if aan else Qt.CheckState.Unchecked)
                self.chart_list.addItem(regel)
        finally:
            self._laden = False

    def _chart_toggled(self, item: QListWidgetItem):
        if self._laden:
            return
        gegevens = item.data(Qt.ItemDataRole.UserRole)
        if not gegevens:
            return
        sectie, grafiek = gegevens
        self._section_at(sectie)["grafieken"][grafiek] = item.checkState() == Qt.CheckState.Checked
        self._mark_custom()

    # ------------------------------------------------------- eigen sjablonen

    def _templates(self) -> list:
        try:
            opgeslagen = json.loads(self.settings.value("report_templates", "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return [item for item in opgeslagen if isinstance(item, dict) and item.get("naam")]

    def _write_templates(self, sjablonen):
        self.settings.setValue("report_templates", json.dumps(sjablonen, ensure_ascii=False))

    def _refresh_templates(self, kies: str = ""):
        self._laden = True
        try:
            self.template_choice.clear()
            self.template_choice.addItem("— geen sjabloon —", "")
            for sjabloon in self._templates():
                self.template_choice.addItem(sjabloon["naam"], sjabloon["naam"])
            positie = self.template_choice.findData(kies)
            self.template_choice.setCurrentIndex(max(0, positie))
        finally:
            self._laden = False

    def _load_template(self, *_):
        if self._laden:
            return
        naam = str(self.template_choice.currentData() or "")
        if not naam:
            return
        sjabloon = next((item for item in self._templates() if item["naam"] == naam), None)
        if not sjabloon:
            return
        self.config = report.config_from_template(sjabloon, self.config["selectie"])
        self._laden = True
        try:
            self.title_field.setText(self.config["titel"])
            self.subtitle_field.setText(self.config["subtitel"])
            for sleutel, vak in self.design_boxes.items():
                vak.setChecked(bool(self.config["vormgeving"].get(sleutel, True)))
            positie = self.orientation_choice.findData(self.config["vormgeving"]["orientatie"])
            self.orientation_choice.setCurrentIndex(max(0, positie))
            keuze = self.preset_choice.findData(self.config.get("preset", "aangepast"))
            self.preset_choice.setCurrentIndex(max(0, keuze))
        finally:
            self._laden = False
        self._refresh_section_availability()

    def _save_template(self):
        huidig = str(self.template_choice.currentData() or "")
        naam, akkoord = QInputDialog.getText(self, "Sjabloon opslaan",
                                             "Naam van het sjabloon:", text=huidig)
        naam = str(naam or "").strip()
        if not akkoord or not naam:
            return
        sjablonen = [item for item in self._templates() if item["naam"] != naam]
        if len(sjablonen) != len(self._templates()):
            antwoord = QMessageBox.question(
                self, "Sjabloon overschrijven",
                f"Er bestaat al een sjabloon '{naam}'. Wilt u het overschrijven?",
            )
            if antwoord != QMessageBox.StandardButton.Yes:
                return
        self._sync_design()
        sjablonen.append(report.template_payload(naam, self.config))
        self._write_templates(sorted(sjablonen, key=lambda item: item["naam"].lower()))
        self._refresh_templates(naam)

    def _rename_template(self):
        naam = str(self.template_choice.currentData() or "")
        if not naam:
            QMessageBox.information(self, "Geen sjabloon", "Kies eerst een sjabloon.")
            return
        nieuw, akkoord = QInputDialog.getText(self, "Sjabloon hernoemen", "Nieuwe naam:", text=naam)
        nieuw = str(nieuw or "").strip()
        if not akkoord or not nieuw or nieuw == naam:
            return
        sjablonen = []
        for sjabloon in self._templates():
            if sjabloon["naam"] == naam:
                sjabloon = dict(sjabloon, naam=nieuw)
            sjablonen.append(sjabloon)
        self._write_templates(sorted(sjablonen, key=lambda item: item["naam"].lower()))
        self._refresh_templates(nieuw)

    def _delete_template(self):
        naam = str(self.template_choice.currentData() or "")
        if not naam:
            QMessageBox.information(self, "Geen sjabloon", "Kies eerst een sjabloon.")
            return
        if QMessageBox.question(self, "Sjabloon verwijderen",
                                f"Wilt u '{naam}' verwijderen?") != QMessageBox.StandardButton.Yes:
            return
        self._write_templates([item for item in self._templates() if item["naam"] != naam])
        self._refresh_templates()

    # ---------------------------------------------------- stap 3: vormgeving

    def _build_design_page(self) -> QWidget:
        pagina = QWidget()
        buiten = QVBoxLayout(pagina)
        buiten.setSpacing(12)

        tekst_vak = QGroupBox("Titel")
        vorm = QFormLayout(tekst_vak)
        self.title_field = QLineEdit(self.config["titel"])
        self.title_field.textChanged.connect(self._sync_design)
        self.subtitle_field = QLineEdit(self.config["subtitel"])
        self.subtitle_field.setPlaceholderText("Optioneel")
        self.subtitle_field.textChanged.connect(self._sync_design)
        vorm.addRow("Rapporttitel:", self.title_field)
        vorm.addRow("Subtitel:", self.subtitle_field)
        buiten.addWidget(tekst_vak)

        opties = QGroupBox("Rapportopties")
        opties_layout = QVBoxLayout(opties)
        self.design_boxes = {}
        for sleutel, label in (
            ("voorblad", "Voorblad met titel en periode"),
            ("datum", "Datum van genereren vermelden"),
            ("filters", "Actieve filters vermelden"),
            ("paginanummers", "Paginanummers"),
            ("inhoudsopgave", "Inhoudsopgave"),
        ):
            vak = QCheckBox(label)
            vak.setChecked(bool(self.config["vormgeving"].get(sleutel, True)))
            vak.stateChanged.connect(self._sync_design)
            self.design_boxes[sleutel] = vak
            opties_layout.addWidget(vak)
        richting = QHBoxLayout()
        richting.addWidget(QLabel("Pagina-indeling:"))
        self.orientation_choice = QComboBox()
        for label, waarde in (("Automatisch", "auto"), ("Staand", "staand"), ("Liggend", "liggend")):
            self.orientation_choice.addItem(label, waarde)
        self.orientation_choice.currentIndexChanged.connect(self._sync_design)
        richting.addWidget(self.orientation_choice)
        richting.addStretch(1)
        opties_layout.addLayout(richting)
        buiten.addWidget(opties)

        stijl = QLabel(
            "Het rapport gebruikt de huisstijl van EventHub: dezelfde kleuren, "
            "typografie en grafieken als op het scherm, in een lichte variant die "
            "op papier leesbaar blijft."
        )
        stijl.setObjectName("hintLabel")
        stijl.setWordWrap(True)
        buiten.addWidget(stijl)
        buiten.addStretch(1)
        return pagina

    def _sync_design(self, *_):
        if self._laden:
            return
        self.config["titel"] = self.title_field.text().strip()
        self.config["subtitel"] = self.subtitle_field.text().strip()
        for sleutel, vak in self.design_boxes.items():
            self.config["vormgeving"][sleutel] = vak.isChecked()
        self.config["vormgeving"]["orientatie"] = str(self.orientation_choice.currentData() or "auto")

    # ------------------------------------------------- stap 4: exportvoorbeeld

    def _build_preview_page(self) -> QWidget:
        pagina = QWidget()
        buiten = QVBoxLayout(pagina)
        buiten.setSpacing(8)

        balk = QHBoxLayout()
        for tekst, handler in (("← Terug naar inhoud", lambda: self.go_to(1)),
                               ("Terug naar vormgeving", lambda: self.go_to(2))):
            knop = QPushButton(tekst)
            knop.setObjectName("secondaryButton")
            knop.clicked.connect(handler)
            balk.addWidget(knop)
        balk.addStretch(1)
        self.prev_page_button = QPushButton("‹")
        self.prev_page_button.setObjectName("secondaryButton")
        self.prev_page_button.clicked.connect(lambda: self._step_page(-1))
        self.page_label = QLabel("—")
        self.page_label.setObjectName("hintLabel")
        self.next_page_button = QPushButton("›")
        self.next_page_button.setObjectName("secondaryButton")
        self.next_page_button.clicked.connect(lambda: self._step_page(1))
        balk.addWidget(self.prev_page_button)
        balk.addWidget(self.page_label)
        balk.addWidget(self.next_page_button)
        balk.addSpacing(16)
        for tekst, handler in (("−", lambda: self._zoom(0.8)),
                               ("+", lambda: self._zoom(1.25)),
                               ("Passend", self._fit_preview)):
            knop = QPushButton(tekst)
            knop.setObjectName("secondaryButton")
            knop.clicked.connect(handler)
            balk.addWidget(knop)
        buiten.addLayout(balk)

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(False)
        self.preview_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview = ReportPreview()
        self.preview_scroll.setWidget(self.preview)
        buiten.addWidget(self.preview_scroll, 1)
        return pagina

    def build_model(self) -> dict:
        self._sync_design()
        return report.build_report_model(self.summaries, self.config)

    def _rebuild_preview(self):
        model = self.build_model()
        try:
            self.layout_engine = ReportLayout(model)
        except Exception:  # noqa: BLE001 - een rapport mag nooit de app omleggen
            self.layout_engine = None
            self.page_label.setText("Het voorbeeld kon niet worden opgebouwd.")
            return
        self.preview.set_layout_engine(self.layout_engine)
        self._fit_preview()
        self._update_page_label()

    def _update_page_label(self):
        if not self.layout_engine:
            self.page_label.setText("—")
            return
        self.page_label.setText(
            f"Pagina {self.preview.page + 1} van {self.layout_engine.page_count()}"
        )
        self.prev_page_button.setEnabled(self.preview.page > 0)
        self.next_page_button.setEnabled(
            self.preview.page < self.layout_engine.page_count() - 1
        )

    def _step_page(self, richting: int):
        self.preview.set_page(self.preview.page + richting)
        self._update_page_label()

    def _zoom(self, factor: float):
        self.preview.set_zoom(self.preview.zoom * factor)

    def _fit_preview(self):
        gebied = self.preview_scroll.viewport().size()
        self.preview.fit(gebied.width() - 24, gebied.height() - 24)

    # --------------------------------------------------- stap 5: exporteren

    def _build_export_page(self) -> QWidget:
        pagina = QWidget()
        buiten = QVBoxLayout(pagina)
        buiten.setSpacing(12)

        vak = QGroupBox("Exporteren")
        vorm = QFormLayout(vak)
        self.format_choice = QComboBox()
        self.format_choice.addItem("PDF-rapport (*.pdf)", "pdf")
        self.format_choice.addItem("Excel-werkmap met dashboard en data (*.xlsx)", "xlsx")
        self.format_choice.currentIndexChanged.connect(self._refresh_export_page)
        vorm.addRow("Formaat:", self.format_choice)
        self.file_field = QLineEdit()
        vorm.addRow("Bestandsnaam:", self.file_field)
        vak_map = QWidget()
        map_rij = QHBoxLayout(vak_map)
        map_rij.setContentsMargins(0, 0, 0, 0)
        self.folder_label = QLabel("")
        self.folder_label.setObjectName("hintLabel")
        self.folder_label.setWordWrap(True)
        map_rij.addWidget(self.folder_label, 1)
        kies = QPushButton("Andere map…")
        kies.setObjectName("secondaryButton")
        kies.clicked.connect(self._choose_folder)
        map_rij.addWidget(kies)
        vorm.addRow("Map:", vak_map)
        buiten.addWidget(vak)

        self.export_overview = QLabel("")
        self.export_overview.setObjectName("hintLabel")
        self.export_overview.setWordWrap(True)
        buiten.addWidget(self.export_overview)

        self.export_button = QPushButton("Rapport exporteren")
        self.export_button.setObjectName("primaryButton")
        self.export_button.clicked.connect(self._export)
        buiten.addWidget(self.export_button, 0, Qt.AlignmentFlag.AlignLeft)
        buiten.addStretch(1)
        return pagina

    def set_folder(self, map_pad):
        self.folder = Path(map_pad)
        self.folder_label.setText(str(self.folder))

    def _choose_folder(self):
        gekozen = QFileDialog.getExistingDirectory(self, "Map kiezen", str(self.folder))
        if gekozen:
            self.set_folder(gekozen)

    def _refresh_export_page(self, *_):
        model = self.build_model()
        standaard = report.safe_file_name(
            self.config["titel"] or report.default_title(self.config["selectie"])
        ).replace(" ", "_")
        if not self.file_field.text().strip():
            self.file_field.setText(standaard)
        try:
            paginas = ReportLayout(model).page_count()
        except Exception:  # noqa: BLE001
            paginas = 0
        onderdelen = [sectie["title"] for sectie in model.get("sections", [])]
        soort = str(self.format_choice.currentData() or "pdf")
        self.export_overview.setText(
            f"{'PDF' if soort == 'pdf' else 'Excel'} · "
            f"{report.meervoud(len(onderdelen), 'onderdeel', 'onderdelen')} · "
            f"{report.meervoud(paginas, 'pagina', 'pagina' + chr(39) + 's')} · "
            f"{report.meervoud(model['kpis']['evenementen'], 'evenement', 'evenementen')}.\n"
            + (" · ".join(onderdelen) if onderdelen else "Er is niets geselecteerd om te exporteren.")
        )
        self.export_button.setEnabled(bool(onderdelen))

    def _export(self):
        model = self.build_model()
        if not model.get("sections"):
            QMessageBox.information(self, "Niets te exporteren",
                                    "Kies bij Inhoud minimaal één onderdeel.")
            return
        soort = str(self.format_choice.currentData() or "pdf")
        naam = report.safe_file_name(self.file_field.text())
        doel = self.folder / f"{naam}.{'pdf' if soort == 'pdf' else 'xlsx'}"
        if doel.exists():
            antwoord = QMessageBox.question(
                self, "Bestand bestaat al",
                f"{doel.name} bestaat al. Wilt u het overschrijven?",
            )
            if antwoord != QMessageBox.StandardButton.Yes:
                return
        try:
            if soort == "pdf":
                export_pdf(model, doel)
            else:
                export_excel(model, doel)
        except ExportError as fout:
            QMessageBox.warning(self, "Export mislukt", str(fout))
            return
        except Exception as fout:  # noqa: BLE001 - liever een nette melding
            QMessageBox.warning(
                self, "Export mislukt",
                "Het rapport kon niet worden weggeschreven.\n\n"
                f"{type(fout).__name__}: {fout}",
            )
            return
        if self.status_callback:
            self.status_callback(f"Rapport geëxporteerd: {doel}")
        self.exported_path = doel
        QMessageBox.information(self, "Export gereed",
                                f"Het rapport is opgeslagen als:\n{doel}")
        self.accept()
