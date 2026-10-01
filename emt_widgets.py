"""Losse schermonderdelen die overal in EventHub terugkomen: keuzelijsten die niet
meescrollen, de datum- en tijdkeuze, evenementkaarten en het evenementkeuzevenster.

Deze module bouwt alleen onderdelen; hij kent het hoofdvenster niet.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from PySide6.QtCore import QDate, QLocale, QPoint, QSize, QTime, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QTextCharFormat
from PySide6.QtWidgets import (
    QApplication, QCalendarWidget, QComboBox, QDialog, QDialogButtonBox, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSplashScreen, QTimeEdit, QToolButton,
    QVBoxLayout, QWidget,
)

from bezoekerslijst_core import normalize
from emt_models import EVENT_TYPES, parse_date, preparation_progress, preparation_summary
from emt_base import (
    APP_VERSION, LOGO_PATH, NEON_WAVES_PATH, event_activity_line, event_end_moment,
    event_has_passed, event_last_seen, event_recency_key,
)


class ScrollSafeComboBox(QComboBox):
    """Een scrollbeweging boven een gesloten keuzelijst scrolt de pagina."""

    def wheelEvent(self, event):
        event.ignore()


class FitWidthScrollArea(QScrollArea):
    """Scrollt alleen verticaal en is nooit smaller dan de inhoud.

    Zo drukt een laag venster of een hoge Windows-schaal de velden niet meer
    over elkaar heen: er verschijnt een schuifbalk. En een splitter kan het
    paneel niet zo smal maken dat knoppen rechts buiten beeld vallen.
    """

    def __init__(self, minimum_width: int = 0, parent=None):
        super().__init__(parent)
        self._minimum_width = minimum_width
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        content = self.widget()
        if content is None:
            return hint
        width = (content.minimumSizeHint().width()
                 + self.verticalScrollBar().sizeHint().width()
                 + 2 * self.frameWidth())
        return QSize(max(hint.width(), width, self._minimum_width), hint.height())

    def sizeHint(self):
        hint = super().sizeHint()
        content = self.widget()
        if content is None:
            return hint
        return QSize(max(hint.width(), self.minimumSizeHint().width()),
                     content.sizeHint().height() + 2 * self.frameWidth())


def _make_button_compact(button: QPushButton) -> QPushButton:
    """Keep an action button at its natural text width inside roomy layouts."""
    button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return button


def _picker_button(tooltip: str) -> QPushButton:
    button = QPushButton("📅")
    button.setObjectName("secondaryButton")
    # De gewone knopmarge van 14px aan weerszijden laat op deze breedte niets
    # over voor het teken; de stylesheet zet die marge terug via deze vlag.
    button.setProperty("picker", "true")
    button.setFixedWidth(34)
    button.setToolTip(tooltip)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return button


def _picker_dialog(owner: QWidget, title: str) -> QDialog:
    """Een klein, gewoon venster voor datum- of tijdkeuze.

    Eerder was dit een los uitklapvak rechtsonder de knop; bij een knop aan de
    rechterrand van het scherm viel dat buiten beeld.
    """
    # Een QDialog met een ouder blijft toch een eigen venster.
    dialog = QDialog(owner)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    return dialog


def _center_on_screen_near(dialog: QDialog, anchor: QWidget):
    """Midden boven het venster van de knop, en altijd volledig op het scherm."""
    dialog.adjustSize()
    size = dialog.sizeHint().expandedTo(dialog.minimumSizeHint())
    host = anchor.window()
    centre = host.mapToGlobal(host.rect().center()) if host is not None else anchor.mapToGlobal(anchor.rect().center())
    screen = QApplication.screenAt(centre) or anchor.screen() or QApplication.primaryScreen()
    x = centre.x() - size.width() // 2
    y = centre.y() - size.height() // 2
    if screen is not None:
        area = screen.availableGeometry()
        x = max(area.left(), min(x, area.right() - size.width() + 1))
        y = max(area.top(), min(y, area.bottom() - size.height() + 1))
    dialog.move(x, y)


def _style_calendar(calendar: QCalendarWidget, text_colour: QColor):
    """Nederlandse dagnamen die in het donkere én lichte thema leesbaar zijn."""
    calendar.setLocale(QLocale(QLocale.Language.Dutch, QLocale.Country.Netherlands))
    calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
    calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
    header = QTextCharFormat()
    header.setForeground(text_colour)
    header.setBackground(QColor(0, 0, 0, 0))
    header.setFontWeight(QFont.Weight.Bold)
    calendar.setHeaderTextFormat(header)
    weekend = QTextCharFormat()
    weekend.setForeground(QColor("#e8697a"))
    weekend.setFontWeight(QFont.Weight.Bold)
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        calendar.setWeekdayTextFormat(day, weekend)
    for name, arrow, tip in (("qt_calendar_prevmonth", "‹", "Vorige maand"),
                             ("qt_calendar_nextmonth", "›", "Volgende maand")):
        nav = calendar.findChild(QToolButton, name)
        if nav is not None:
            nav.setIcon(QIcon())
            nav.setText(arrow)
            nav.setToolTip(tip)
            nav.setStyleSheet(f"QToolButton {{ color: {text_colour.name()}; font-size: 16pt; font-weight: 800; padding: 0 10px; }}")


def with_date_picker(line_edit: QLineEdit) -> QWidget:
    """Zet een kalenderknop naast een datumveld.

    Het tekstveld blijft leidend: typen kan gewoon en leeg laten mag. Dat is
    de reden om geen QDateEdit te gebruiken, want die heeft altijd een waarde
    en kan dus niet leeg zijn.

    De kalender opent pas na een klik op de knop, zodat hij niet in de weg
    zit wanneer iemand de datum simpelweg intypt.
    """
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(line_edit, 1)
    button = _picker_button("Datum kiezen uit een kalender")
    layout.addWidget(button)

    def open_calendar():
        popup = _picker_dialog(holder, "Datum kiezen")
        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(12, 12, 12, 12)
        popup_layout.setSpacing(10)
        calendar = QCalendarWidget()
        calendar.setMinimumSize(320, 240)
        _style_calendar(calendar, line_edit.palette().color(line_edit.foregroundRole()))
        calendar.setGridVisible(True)
        calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        # Openen op de datum die er al staat; anders op vandaag.
        bestaand = parse_date(line_edit.text())
        calendar.setSelectedDate(
            QDate(bestaand.year, bestaand.month, bestaand.day) if bestaand else QDate.currentDate()
        )
        popup_layout.addWidget(calendar)

        def kies(date_value):
            line_edit.setText(date_value.toString("dd-MM-yyyy"))
            line_edit.editingFinished.emit()
            popup.accept()

        def wissen():
            line_edit.clear()
            line_edit.editingFinished.emit()
            popup.accept()

        calendar.clicked.connect(kies)
        calendar.activated.connect(kies)
        actions = QHBoxLayout()
        today_button = QPushButton("Vandaag")
        today_button.setObjectName("secondaryButton")
        today_button.clicked.connect(lambda: kies(QDate.currentDate()))
        clear_button = QPushButton("Leegmaken")
        clear_button.setObjectName("secondaryButton")
        clear_button.clicked.connect(wissen)
        cancel_button = QPushButton("Annuleren")
        cancel_button.clicked.connect(popup.reject)
        actions.addWidget(today_button)
        actions.addWidget(clear_button)
        actions.addStretch(1)
        actions.addWidget(cancel_button)
        popup_layout.addLayout(actions)
        _center_on_screen_near(popup, button)
        calendar.setFocus()
        popup.exec()

    button.clicked.connect(open_calendar)
    return holder


def with_time_picker(line_edit: QLineEdit) -> QWidget:
    """Zet een tijdknop naast een tijdveld.

    Zelfde opzet als bij de datum: het tekstveld blijft leidend en mag leeg
    blijven. De keuze gaat per kwartier, want dat is waar evenementtijden in
    de praktijk op vallen; afwijkende tijden typt u gewoon.
    """
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(line_edit, 1)
    button = _picker_button("Tijd kiezen")
    layout.addWidget(button)

    def open_times():
        popup = _picker_dialog(holder, "Tijd kiezen")
        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(12, 12, 12, 12)
        popup_layout.setSpacing(8)
        editor = QTimeEdit()
        editor.setDisplayFormat("HH:mm")
        huidig = QTime.fromString(str(line_edit.text() or "").strip(), "HH:mm")
        editor.setTime(huidig if huidig.isValid() else QTime(9, 0))
        popup_layout.addWidget(editor)
        confirm = QPushButton("Kiezen")
        confirm.setObjectName("primaryButton")
        popup_layout.addWidget(confirm)

        def kies():
            line_edit.setText(editor.time().toString("HH:mm"))
            line_edit.editingFinished.emit()
            popup.accept()

        confirm.clicked.connect(kies)
        confirm.setDefault(True)
        _center_on_screen_near(popup, button)
        popup.exec()

    button.clicked.connect(open_times)
    return holder


def valid_time_text(value: str) -> bool:
    """Accept an empty time or a 24-hour HH:MM value."""
    raw = str(value or "").strip()
    if not raw:
        return True
    return bool(re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", raw))


class NeonEdgeOverlay(QWidget):
    """Subtiele, muistransparante EventHub-decoratie boven het werkgebied."""

    def __init__(self, image_path: Path, dark_mode: bool, parent=None):
        super().__init__(parent)
        self.setObjectName("neonEdgeOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self._pixmap = QPixmap(str(image_path)) if image_path.exists() else QPixmap()
        self._dark_mode = bool(dark_mode)

    def set_dark_mode(self, enabled: bool):
        self._dark_mode = bool(enabled)
        self.update()

    def paintEvent(self, event):
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setOpacity(0.15 if self._dark_mode else 0.07)
        painter.drawPixmap(self.rect(), self._pixmap)


class StartupSplash(QSplashScreen):
    def __init__(self):
        canvas = QPixmap(560, 340)
        canvas.fill(QColor("#0d1117"))
        if NEON_WAVES_PATH.exists():
            waves = QPixmap(str(NEON_WAVES_PATH))
            if not waves.isNull():
                painter = QPainter(canvas)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.setOpacity(0.72)
                painter.drawPixmap(canvas.rect(), waves)
                painter.end()
        super().__init__(canvas, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedSize(560, 340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(42, 32, 42, 30)
        layout.setSpacing(10)

        logo = QLabel()
        if LOGO_PATH.exists():
            logo.setPixmap(QPixmap(str(LOGO_PATH)).scaled(
                100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            ))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel("EventHub")
        title.setObjectName("splashTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version = QLabel(f"Versie {APP_VERSION}")
        version.setObjectName("splashVersion")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage = QLabel("Programma voorbereiden…")
        self.stage.setObjectName("splashStage")
        self.stage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(3)
        self.progress.setTextVisible(False)

        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addStretch()
        layout.addWidget(self.stage)
        layout.addWidget(self.progress)
        self.setStyleSheet("""
            QLabel { color: #ffffff; background: transparent; font-family: 'Plus Jakarta Sans', 'Avenir Next', 'Segoe UI'; }
            QLabel#splashTitle { font-size: 20pt; font-weight: 700; }
            QLabel#splashVersion { color: #00d4ff; font-size: 10pt; font-weight: 600; }
            QLabel#splashStage { color: #a8b5c7; font-size: 9.5pt; }
            QProgressBar { background: #151c26; border: 1px solid #2d3a4b; border-radius: 6px; height: 12px; }
            QProgressBar::chunk { background: #6c2cff; border-radius: 5px; }
        """)

    def set_progress(self, value: int, message: str):
        self.progress.setValue(value)
        self.stage.setText(message)
        QApplication.processEvents()


class EventCard(QFrame):
    """Een evenement als kaart: naam, wanneer, en wanneer je er voor het laatst was."""

    gekozen = Signal(str)

    def __init__(self, event: dict, parent=None, aanmeldingen: str = ""):
        super().__init__(parent)
        self.event_id = str(event.get("id", "") or "")
        self.setObjectName("eventCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        # Een gekleurde rand links per status: dat maakt de kaarten uit elkaar
        # te houden en vertelt meteen hoe het ervoor staat.
        self.setProperty("eventStatus", normalize(event.get("status", "")) or "concept")
        self.setMinimumHeight(96)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)

        naam = QLabel(str(event.get("name", "") or "Onbenoemd evenement"))
        naam.setObjectName("eventCardTitle")
        vet = naam.font()
        vet.setBold(True)
        vet.setPointSize(max(11, vet.pointSize() + 1))
        naam.setFont(vet)
        naam.setWordWrap(True)
        layout.addWidget(naam)

        tijd = " – ".join(filter(None, [event.get("start_time", ""), event.get("end_time", "")]))
        regel = "  ·  ".join(filter(None, [
            str(event.get("date", "") or "Geen datum"),
            tijd,
            str(event.get("event_type", "") or ""),
            str(event.get("place", "") or event.get("location", "") or ""),
        ]))
        meta = QLabel(regel)
        meta.setObjectName("eventCardMeta")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        self.registrations_label = None
        if aanmeldingen:
            self.registrations_label = QLabel(aanmeldingen)
            self.registrations_label.setObjectName("eventCardMeta")
            self.registrations_label.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(self.registrations_label)

        laatste = QLabel(event_activity_line(event))
        laatste.setObjectName("eventCardFoot")
        layout.addWidget(laatste)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.gekozen.emit(self.event_id)
        super().mouseReleaseEvent(event)


class EventOverviewCard(QFrame):
    """Een evenement op het startscherm, groter dan in het keuzevenster.

    De kaart beantwoordt de vraag die bij dat evenement hoort: bij een
    evenement dat nog komt is dat hoe ver de voorbereiding is, bij een
    evenement dat is geweest hoe het liep. Alle tekst komt kant en klaar
    binnen; het venster rekent, de kaart tekent alleen.
    """

    geopend = Signal(str)
    aangeklikt = Signal(str)
    menu_gevraagd = Signal(str, QPoint)

    def __init__(self, event: dict, cijfers: str = "", voet: str = "",
                 geweest: bool = False, parent=None):
        super().__init__(parent)
        self.event_id = str(event.get("id", "") or "")
        self.setObjectName("eventOverviewCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        status = str(event.get("status", "") or "Concept")
        self.setProperty("eventStatus", normalize(status) or "concept")
        self.setProperty("gekozen", False)
        self.setMinimumHeight(132)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda punt: self.menu_gevraagd.emit(self.event_id, self.mapToGlobal(punt))
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 14, 12)
        layout.setSpacing(5)

        kop = QHBoxLayout()
        kop.setSpacing(8)
        soort = QLabel(str(event.get("event_type", "") or "Evenement").upper())
        soort.setObjectName("eventOverviewEyebrow")
        kop.addWidget(soort)
        kop.addStretch(1)
        chip = QLabel(status)
        chip.setObjectName("eventStatusChip")
        chip.setProperty("eventStatus", normalize(status) or "concept")
        if not event.get("status_manual"):
            chip.setToolTip("Deze status wordt automatisch bepaald uit de taken.")
        kop.addWidget(chip)
        self.menu_button = QPushButton("\u22ef")
        self.menu_button.setObjectName("cardMenuButton")
        self.menu_button.setFixedWidth(26)
        self.menu_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_button.setToolTip("Meer acties")
        self.menu_button.clicked.connect(self._vraag_menu)
        kop.addWidget(self.menu_button)
        layout.addLayout(kop)

        naam = QLabel(str(event.get("name", "") or "Onbenoemd evenement"))
        naam.setObjectName("eventOverviewTitle")
        naam.setWordWrap(True)
        layout.addWidget(naam)

        tijd = " \u2013 ".join(filter(None, [
            str(event.get("start_time", "") or ""), str(event.get("end_time", "") or "")
        ]))
        meta = QLabel("  \u00b7  ".join(filter(None, [
            str(event.get("date", "") or "Geen datum"),
            tijd,
            str(event.get("place", "") or event.get("location", "") or ""),
        ])))
        meta.setObjectName("eventOverviewMeta")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        # De balk hoort bij wat er nog moet gebeuren. Bij een evenement dat is
        # geweest zegt hij niets meer, dus daar staan de uitkomsten.
        self.preparation_bar = None
        if not geweest:
            percentage = int(round(preparation_progress(event) * 100))
            balkrij = QHBoxLayout()
            balkrij.setSpacing(8)
            kopje = QLabel("Voorbereiding")
            kopje.setObjectName("eventOverviewMeta")
            balkrij.addWidget(kopje)
            self.preparation_bar = QProgressBar()
            self.preparation_bar.setObjectName("preparationBar")
            self.preparation_bar.setRange(0, 100)
            self.preparation_bar.setValue(percentage)
            self.preparation_bar.setTextVisible(False)
            self.preparation_bar.setProperty(
                "vervallen", normalize(status) == normalize("Geannuleerd")
            )
            self.preparation_bar.setToolTip(preparation_summary(event))
            balkrij.addWidget(self.preparation_bar, 1)
            self.percentage_label = QLabel(f"{percentage}%")
            self.percentage_label.setObjectName("eventOverviewPercentage")
            self.percentage_label.setToolTip(preparation_summary(event))
            balkrij.addWidget(self.percentage_label)
            layout.addLayout(balkrij)

        if cijfers:
            regel = QLabel(cijfers)
            regel.setObjectName("eventOverviewFigures")
            regel.setTextFormat(Qt.TextFormat.RichText)
            regel.setWordWrap(True)
            layout.addWidget(regel)

        layout.addStretch(1)
        if voet:
            onder = QLabel(voet)
            onder.setObjectName("eventOverviewFoot")
            onder.setWordWrap(True)
            layout.addWidget(onder)

    def _vraag_menu(self):
        hoek = self.menu_button.mapToGlobal(QPoint(0, self.menu_button.height()))
        self.menu_gevraagd.emit(self.event_id, hoek)

    def markeer(self, gekozen: bool):
        self.setProperty("gekozen", bool(gekozen))
        self.style().unpolish(self)
        self.style().polish(self)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.aangeklikt.emit(self.event_id)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.geopend.emit(self.event_id)
        super().mouseDoubleClickEvent(event)


class EventPickerDialog(QDialog):
    """Kies een evenement uit kaarten in plaats van uit een lange lijst.

    Met tientallen evenementen in een keuzelijst scrol je langs alles wat je
    niet zoekt. Hier staan standaard de zes waar je het laatst was en de zes
    die eraan komen, en zodra je zoekt of filtert wordt het een enkele lijst
    met alles wat past.
    """

    KOLOMMEN = 2
    PER_GROEP = 8
    PER_PAGINA = 8

    def __init__(self, events, current_id: str = "", parent=None, allow_none: bool = False,
                 aanmeldingen: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Evenement kiezen")
        # Per evenement-id een korte regel als "12 aanmeldingen"; leeg = niet tonen.
        self.aanmeldingen = dict(aanmeldingen or {})
        _fit_dialog_to_screen(self, 860, 640, 640, 420)
        self.events = list(events or [])
        self.chosen_id = str(current_id or "")
        self.allow_none = bool(allow_none)
        self.page = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        filters = QHBoxLayout()
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Zoek op naam, plaats of locatie…")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._filters_changed)
        filters.addWidget(self.search_field, 1)

        self.type_filter = ScrollSafeComboBox()
        self.type_filter.addItem("Alle soorten", "")
        for soort in EVENT_TYPES:
            self.type_filter.addItem(soort, soort)
        self.type_filter.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(self.type_filter)

        self.period_filter = ScrollSafeComboBox()
        for label, waarde in (("Alle datums", ""), ("Komt nog", "toekomst"), ("Geweest", "verleden")):
            self.period_filter.addItem(label, waarde)
        self.period_filter.currentIndexChanged.connect(self._filters_changed)
        filters.addWidget(self.period_filter)

        self.date_field = QLineEdit()
        self.date_field.setPlaceholderText("dd-mm-jjjj")
        self.date_field.setClearButtonEnabled(True)
        self.date_field.setMaximumWidth(150)
        self.date_field.textChanged.connect(self._filters_changed)
        # Dezelfde kalenderknop als bij het aanpassen van een evenement.
        filters.addWidget(with_date_picker(self.date_field))
        layout.addLayout(filters)

        self.result_label = QLabel("")
        self.result_label.setObjectName("hintLabel")
        layout.addWidget(self.result_label)

        self.canvas = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_layout.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.canvas)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        if self.allow_none:
            clear_button = buttons.addButton(
                "×  Selectie wissen",
                QDialogButtonBox.ButtonRole.ResetRole,
            )
            clear_button.setObjectName("secondaryButton")
            _make_button_compact(clear_button)
            clear_button.setToolTip(
                "Wis de gedeelde evenementkeuze. Evenementgebonden acties worden dan uitgeschakeld."
            )
            clear_button.clicked.connect(self._wis_keuze)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._render()
        self.search_field.setFocus()

    def _matches(self, event) -> bool:
        naald = normalize(self.search_field.text())
        if naald:
            hooiberg = normalize(" ".join(str(event.get(veld, "") or "") for veld in
                                          ("name", "place", "location", "region", "event_type")))
            if naald not in hooiberg:
                return False
        soort = str(self.type_filter.currentData() or "")
        if soort and str(event.get("event_type", "") or "") != soort:
            return False
        periode = str(self.period_filter.currentData() or "")
        if periode:
            if event_end_moment(event) is None:
                return False
            if periode == "toekomst" and event_has_passed(event):
                return False
            if periode == "verleden" and not event_has_passed(event):
                return False
        gezocht = parse_date(self.date_field.text())
        if gezocht and parse_date(str(event.get("date", "") or "")) != gezocht:
            return False
        return True

    def _filters_changed(self, *_):
        """Een nieuw filter begint bij het begin, anders kijk je naar pagina vier van niets."""
        self.page = 0
        self._render()

    def _leeg(self):
        while self.canvas_layout.count():
            item = self.canvas_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Eerst verbergen: een zichtbare widget zonder ouder is een los
                # venster. Losknippen moet wel, want deleteLater alleen laat de
                # oude kaarten tot de volgende ronde in de boom staan, en dan
                # telt en toont het venster ze dubbel.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _groep(self, titel: str, events):
        if not events:
            return
        kop = QLabel(titel)
        kop.setObjectName("eventGroupTitle")
        self.canvas_layout.addWidget(kop)
        rooster = QWidget()
        grid = QGridLayout(rooster)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)
        for index, event in enumerate(events):
            kaart = EventCard(event, aanmeldingen=self.aanmeldingen.get(str(event.get("id", "")), ""))
            kaart.gekozen.connect(self._kies)
            if str(event.get("id", "")) == self.chosen_id:
                kaart.setProperty("huidig", "true")
            grid.addWidget(kaart, index // self.KOLOMMEN, index % self.KOLOMMEN)
        for kolom in range(self.KOLOMMEN):
            grid.setColumnStretch(kolom, 1)
        self.canvas_layout.addWidget(rooster)

    def _render(self, *_):
        self._leeg()
        passend = [event for event in self.events if self._matches(event)]
        zoekt = bool(normalize(self.search_field.text())) or bool(self.type_filter.currentData()) \
            or bool(self.period_filter.currentData()) or bool(parse_date(self.date_field.text()))
        if zoekt:
            gevonden = sorted(passend, key=event_recency_key)
            paginas = max(1, -(-len(gevonden) // self.PER_PAGINA))
            self.page = min(max(0, self.page), paginas - 1)
            begin = self.page * self.PER_PAGINA
            deel = gevonden[begin:begin + self.PER_PAGINA]
            self.result_label.setText(
                f"{len(gevonden)} evenement(en) gevonden."
                + (f" Pagina {self.page + 1} van {paginas}." if paginas > 1 else "")
            )
            self._groep("Gevonden", deel)
            if paginas > 1:
                self._bladerbalk(paginas)
        else:
            geopend = [event for event in passend if event_last_seen(event)]
            geopend.sort(key=lambda item: event_last_seen(item), reverse=True)
            komend = [event for event in passend if not event_has_passed(event)]
            komend.sort(key=lambda item: event_end_moment(item) or datetime.max)
            self.result_label.setText(
                f"{len(passend)} evenement(en). Zoek of filter hierboven om alles te zien."
            )
            self._groep("Laatst geopend", geopend[:self.PER_GROEP])
            self._groep("Eerstvolgende", komend[:self.PER_GROEP])
        self.canvas_layout.addStretch()

    def _bladerbalk(self, paginas: int):
        """Alleen zichtbaar als er iets te bladeren valt."""
        balk = QWidget()
        rij = QHBoxLayout(balk)
        rij.setContentsMargins(0, 0, 0, 0)
        vorige = QPushButton("← Vorige")
        vorige.setObjectName("secondaryButton")
        vorige.setEnabled(self.page > 0)
        vorige.clicked.connect(lambda: self._blader(-1))
        volgende = QPushButton("Volgende →")
        volgende.setObjectName("secondaryButton")
        volgende.setEnabled(self.page + 1 < paginas)
        volgende.clicked.connect(lambda: self._blader(1))
        rij.addWidget(vorige)
        rij.addStretch()
        rij.addWidget(QLabel(f"Pagina {self.page + 1} van {paginas}"))
        rij.addStretch()
        rij.addWidget(volgende)
        self.canvas_layout.addWidget(balk)

    def _blader(self, richting: int):
        self.page = max(0, self.page + richting)
        self._render()

    def _kies(self, event_id: str):
        self.chosen_id = str(event_id or "")
        self.accept()

    def _wis_keuze(self):
        self.chosen_id = ""
        self.accept()


class EventPickerButton(QPushButton):
    """Toont het gekozen evenement en opent het keuzevenster."""

    changed = Signal()

    def __init__(self, parent=None, allow_none: bool = False):
        super().__init__(parent)
        self.setObjectName("eventPickerButton")
        self._events = []
        self._current_id = ""
        self._allow_none = bool(allow_none)
        self._registration_counter = None
        self.setToolTip("Klik om een ander evenement te kiezen")
        self.clicked.connect(self._open)
        self._label()

    def set_events(self, events, current_id: str = ""):
        self._events = list(events or [])
        if current_id:
            self._current_id = str(current_id)
        elif self._allow_none:
            self._current_id = ""
        if not self._event_by_id(self._current_id) and self._events and not self._allow_none:
            self._current_id = str(self._events[0].get("id", "") or "")
        self._label()

    def current_id(self) -> str:
        return self._current_id

    def set_registration_counter(self, counter):
        """Functie die bij openen per evenement-id de aanmeldregel levert."""
        self._registration_counter = counter

    def set_current_id(self, event_id: str):
        self._current_id = str(event_id or "")
        self._label()

    def _event_by_id(self, event_id):
        return next((event for event in self._events if str(event.get("id", "")) == str(event_id)), None)

    def _label(self):
        event = self._event_by_id(self._current_id)
        if event is None:
            self.setText("Geen evenement geselecteerd  ·  kiezen…")
            return
        datum = str(event.get("date", "") or "")
        self.setText(f"{event.get('name', 'Onbenoemd evenement')}" + (f"   ·   {datum}" if datum else ""))

    def _open(self):
        if not self._events:
            QMessageBox.information(self, "Geen evenementen", "Maak eerst een evenement aan.")
            return
        aanmeldingen = self._registration_counter(self._events) if self._registration_counter else {}
        dialog = EventPickerDialog(
            self._events,
            self._current_id,
            self,
            allow_none=self._allow_none,
            aanmeldingen=aanmeldingen,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.chosen_id == self._current_id:
            return
        self._current_id = dialog.chosen_id
        self._label()
        self.changed.emit()


def _fit_dialog_to_screen(dialog: QDialog, preferred_width: int, preferred_height: int,
                          minimum_width: int = 480, minimum_height: int = 340):
    """Houd dialoogknoppen bereikbaar, ook op kleinere laptopschermen."""
    screen = QApplication.primaryScreen()
    if screen is None:
        dialog.resize(preferred_width, preferred_height)
        return
    available = screen.availableGeometry()
    width = min(preferred_width, max(minimum_width, available.width() - 80))
    height = min(preferred_height, max(minimum_height, available.height() - 100))
    dialog.setMinimumSize(min(minimum_width, width), min(minimum_height, height))
    dialog.resize(width, height)
