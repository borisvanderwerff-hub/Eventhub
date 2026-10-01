"""Reusable chart widgets used by the Trends and Statistics screens."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QPushButton, QToolTip, QVBoxLayout, QWidget,
)

from emt_base import exports_directory
from emt_charts import (
    TREND_PALETTE,
    format_value as format_chart_value,
    has_values as chart_has_values,
    nice_step as chart_nice_step,
    paint_trend_chart,
    render_trend_image,
)
from emt_report_export import ExportError, export_chart_png
from emt_widgets import _make_button_compact

STATISTICS_CHART_TYPES = [
    ("Horizontale balken", "horizontal"),
    ("Verticale balken", "vertical"),
    ("Donutdiagram", "donut"),
]

class StatisticsChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: list[tuple[str, int]] = []
        self.chart_type = "horizontal"
        self.setMinimumHeight(220)

    def set_data(self, data):
        self.data = list(data)
        self._update_minimum_height()
        self.update()

    def set_chart_type(self, chart_type: str):
        allowed = {value for _, value in STATISTICS_CHART_TYPES}
        self.chart_type = chart_type if chart_type in allowed else "horizontal"
        self._update_minimum_height()
        self.update()

    def _row_columns(self) -> int:
        """Bij veel waarden naast elkaar; anders wordt de kaart onwerkbaar lang."""
        return 2 if len(self.data) > 10 and self.width() > 520 else 1

    def _update_minimum_height(self):
        if self.chart_type == "horizontal":
            rijen = -(-len(self.data) // max(1, self._row_columns()))
            self.setMinimumHeight(max(220, 34 * rijen + 36))
        else:
            self.setMinimumHeight(290)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 9))
        if not self.data:
            painter.setPen(QColor("#7b6d82"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Nog geen gegevens beschikbaar")
            return

        if self.chart_type == "vertical":
            self._paint_vertical(painter)
        elif self.chart_type == "donut":
            self._paint_donut(painter)
        else:
            self._paint_horizontal(painter)

    def _paint_horizontal(self, painter: QPainter):

        maximum = max(value for _, value in self.data) or 1
        columns = self._row_columns()
        column_width = self.width() / columns
        per_column = -(-len(self.data) // columns)
        label_width = min(190, max(95, column_width / 3))
        bar_left = label_width + 18
        bar_width = max(60, column_width - bar_left - 45)
        row_height = max(24, min(38, (self.height() - 18) / max(1, per_column)))
        metrics = painter.fontMetrics()
        for index, (label, value) in enumerate(self.data):
            column, row = divmod(index, per_column)
            offset = column * column_width
            y = 12 + row * row_height
            text_rect = QRectF(offset + 8, y, label_width, row_height - 8)
            painter.setPen(QColor("#46324f"))
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                metrics.elidedText(str(label), Qt.TextElideMode.ElideRight, label_width - 4),
            )
            background = QRectF(offset + bar_left, y + 5, bar_width, row_height - 14)
            painter.setBrush(QColor("#eee6f2"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(background, 5, 5)
            filled = QRectF(offset + bar_left, y + 5, max(4, bar_width * value / maximum), row_height - 14)
            painter.setBrush(QColor("#6c2cff"))
            painter.drawRoundedRect(filled, 5, 5)
            painter.setPen(QColor("#386bff"))
            painter.drawText(
                QRectF(offset + bar_left + bar_width + 8, y, 35, row_height - 8),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                str(value),
            )

    def _paint_vertical(self, painter: QPainter):
        maximum = max(value for _, value in self.data) or 1
        chart_left = 34
        chart_top = 24
        chart_bottom = self.height() - 72
        chart_width = max(120, self.width() - chart_left - 12)
        chart_height = max(100, chart_bottom - chart_top)
        slot_width = chart_width / max(1, len(self.data))
        bar_width = max(12.0, min(54.0, slot_width * 0.62))
        metrics = painter.fontMetrics()

        painter.setPen(QPen(QColor("#d9cfe0"), 1))
        painter.drawLine(chart_left, chart_bottom, chart_left + chart_width, chart_bottom)
        for index, (label, value) in enumerate(self.data):
            center_x = chart_left + slot_width * (index + 0.5)
            height = max(4.0, chart_height * value / maximum)
            bar = QRectF(center_x - bar_width / 2, chart_bottom - height, bar_width, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#6c2cff"))
            painter.drawRoundedRect(bar, 5, 5)
            painter.setPen(QColor("#386bff"))
            painter.drawText(
                QRectF(center_x - slot_width / 2, chart_bottom - height - 22, slot_width, 20),
                Qt.AlignmentFlag.AlignCenter,
                str(value),
            )
            label_width = max(28, int(slot_width - 4))
            painter.setPen(QColor("#46324f"))
            painter.drawText(
                QRectF(center_x - slot_width / 2, chart_bottom + 6, slot_width, 48),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                metrics.elidedText(str(label), Qt.TextElideMode.ElideRight, label_width),
            )

    def _paint_donut(self, painter: QPainter):
        total = sum(value for _, value in self.data)
        if total <= 0:
            return
        palette = [
            QColor("#6c2cff"), QColor("#00d4ff"), QColor("#e8b84c"), QColor("#386bff"),
            QColor("#b84b72"), QColor("#7a6ccf"), QColor("#5d8c45"), QColor("#b15e35"),
            QColor("#4a9c9c"), QColor("#8b6a50"),
        ]
        size = min(self.height() - 38, max(140, int(self.width() * 0.46)))
        donut = QRectF(18, (self.height() - size) / 2, size, size)
        start_angle = 90 * 16
        for index, (_, value) in enumerate(self.data):
            span = -int(round(360 * 16 * value / total))
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.setBrush(palette[index % len(palette)])
            painter.drawPie(donut, start_angle, span)
            start_angle += span
        hole_size = size * 0.52
        hole = QRectF(
            donut.center().x() - hole_size / 2,
            donut.center().y() - hole_size / 2,
            hole_size,
            hole_size,
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(hole)
        painter.setPen(QColor("#46324f"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        painter.drawText(hole, Qt.AlignmentFlag.AlignCenter, str(total))

        painter.setFont(QFont("Segoe UI", 9))
        legend_left = int(donut.right() + 20)
        legend_width = max(80, self.width() - legend_left - 10)
        row_height = min(28, max(20, (self.height() - 20) // max(1, len(self.data))))
        metrics = painter.fontMetrics()
        top = max(8, (self.height() - row_height * len(self.data)) // 2)
        for index, (label, value) in enumerate(self.data):
            y = top + index * row_height
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette[index % len(palette)])
            painter.drawRoundedRect(QRectF(legend_left, y + 4, 13, 13), 3, 3)
            painter.setPen(QColor("#46324f"))
            text = f"{label} — {value} ({value / total:.0%})"
            painter.drawText(
                QRectF(legend_left + 20, y, legend_width - 20, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                metrics.elidedText(text, Qt.TextElideMode.ElideRight, legend_width - 22),
            )

class CrosstabHeatmap(QWidget):
    """Opleidingsniveau tegen profiel als heatmap met randtotalen.

    De kruistabel is in de praktijk vrijwel leeg: van de honderden cellen is
    maar een fractie gevuld. Als tabel lees je vooral nullen. Hier krijgt een
    lege cel geen inkt en zegt de kleur hoe groot het aantal is, met de
    verdeling per niveau rechts en die per profiel onderaan. Zo staan de twee
    losse verdelingen en hun samenhang in een beeld.
    """

    LEEG = QColor("#f4f0f8")
    VOL = QColor("#6c2cff")
    TEKST = QColor("#46324f")
    RAND = QColor("#d9cfe0")
    MARGE = QColor("#386bff")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data: dict = {}
        self.mode = "aantallen"
        self._cells: list = []
        self.setMouseTracking(True)
        self.setMinimumHeight(260)

    def set_data(self, data: dict, mode: str = "aantallen"):
        self.data = data or {}
        self.mode = mode if mode in ("aantallen", "percentage") else "aantallen"
        rows = len(self.data.get("rows", []))
        self.setMinimumHeight(max(260, 110 + 30 * rows))
        self.setToolTip("")
        self.update()

    def _value(self, level: str, profile: str) -> float:
        """Het getal in de cel: een aantal, of het aandeel binnen dit niveau."""
        count = self.data["counts"].get((level, profile), 0)
        if self.mode == "aantallen":
            return float(count)
        total = self.data["row_totals"].get(level, 0)
        return (count / total * 100) if total else 0.0

    def _cell_text(self, level: str, profile: str) -> str:
        count = self.data["counts"].get((level, profile), 0)
        if not count:
            return ""
        if self.mode == "aantallen":
            return str(count)
        return f"{self._value(level, profile):.0f}%"

    def _blend(self, fraction: float) -> QColor:
        """Van bijna leeg naar vol paars; ook een enkeling blijft zichtbaar."""
        share = 0.18 + 0.82 * max(0.0, min(1.0, fraction))
        return QColor(
            int(self.LEEG.red() + (self.VOL.red() - self.LEEG.red()) * share),
            int(self.LEEG.green() + (self.VOL.green() - self.LEEG.green()) * share),
            int(self.LEEG.blue() + (self.VOL.blue() - self.LEEG.blue()) * share),
        )

    def mouseMoveEvent(self, event):
        """Het precieze aantal blijft bereikbaar zonder de cel vol te schrijven."""
        position = event.position()
        for rect, level, profile, count, share in self._cells:
            if rect.contains(position):
                total = self.data["row_totals"].get(level, 0)
                self.setToolTip(f"{level} x {profile}: {count} van {total} ({share:.0f}% van dit niveau)")
                return
        self.setToolTip("")

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 9))
        self._cells = []

        rows = self.data.get("rows", [])
        columns = self.data.get("columns", [])
        if not rows or not columns:
            painter.setPen(QColor("#7b6d82"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Nog geen gegevens beschikbaar")
            return

        label_width = min(150.0, max(96.0, self.width() / 6))
        header_height = 58.0
        totals_width = 78.0
        footer_height = 42.0
        grid_left = label_width + 10
        grid_width = max(120.0, self.width() - grid_left - totals_width - 10)
        cell_width = grid_width / len(columns)
        available = self.height() - header_height - footer_height - 10
        cell_height = max(22.0, min(34.0, available / len(rows)))
        maximum = max(
            (self._value(level, profile) for level in rows for profile in columns),
            default=0.0,
        ) or 1.0

        painter.setFont(QFont("Segoe UI", 8))
        metrics = painter.fontMetrics()
        for index, profile in enumerate(columns):
            rect = QRectF(grid_left + index * cell_width + 1, 6, cell_width - 2, header_height - 12)
            painter.setPen(self.TEKST)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap,
                metrics.elidedText(str(profile), Qt.TextElideMode.ElideRight, int(cell_width * 2.4)),
            )
        painter.setPen(QPen(self.RAND, 1))
        painter.drawLine(int(grid_left), int(header_height - 2), int(grid_left + grid_width), int(header_height - 2))

        row_maximum = max(self.data["row_totals"].get(level, 0) for level in rows) or 1
        for row_index, level in enumerate(rows):
            top = header_height + row_index * cell_height
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(self.TEKST)
            painter.drawText(
                QRectF(4, top, label_width - 8, cell_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                painter.fontMetrics().elidedText(str(level), Qt.TextElideMode.ElideRight, int(label_width - 10)),
            )
            painter.setFont(QFont("Segoe UI", 9))
            for column_index, profile in enumerate(columns):
                rect = QRectF(
                    grid_left + column_index * cell_width + 1.5,
                    top + 1.5,
                    cell_width - 3,
                    cell_height - 3,
                )
                count = self.data["counts"].get((level, profile), 0)
                row_total = self.data["row_totals"].get(level, 0)
                share = (count / row_total * 100) if row_total else 0.0
                self._cells.append((rect, level, profile, count, share))
                if not count:
                    # Een lege cel krijgt geen inkt; dat is het hele punt.
                    continue
                fill = self._blend(self._value(level, profile) / maximum)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fill)
                painter.drawRoundedRect(rect, 3, 3)
                painter.setPen(QColor("#ffffff") if fill.lightness() < 150 else self.TEKST)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._cell_text(level, profile))

            total = self.data["row_totals"].get(level, 0)
            bar = QRectF(grid_left + grid_width + 8, top + cell_height / 2 - 5, 40 * total / row_maximum, 10)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.MARGE)
            painter.drawRoundedRect(bar, 3, 3)
            painter.setPen(self.MARGE)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(
                QRectF(grid_left + grid_width + 52, top, 26, cell_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                str(total),
            )

        base = header_height + len(rows) * cell_height
        painter.setPen(QPen(self.RAND, 1))
        painter.drawLine(int(grid_left), int(base + 3), int(grid_left + grid_width), int(base + 3))
        column_maximum = max(self.data["column_totals"].get(profile, 0) for profile in columns) or 1
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        for index, profile in enumerate(columns):
            total = self.data["column_totals"].get(profile, 0)
            height = 20 * total / column_maximum
            bar = QRectF(grid_left + index * cell_width + cell_width / 2 - 7, base + 7, 14, height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.MARGE)
            painter.drawRoundedRect(bar, 3, 3)
            painter.setPen(self.MARGE)
            painter.drawText(
                QRectF(grid_left + index * cell_width, base + 9 + height, cell_width, 14),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                str(total),
            )

class TrendChart(QWidget):
    """Verloop over tijd, met één lijn per groep.

    Het tekenen zelf staat in emt_charts, zodat het scherm, het
    exportvoorbeeld, de PDF, het Excel-dashboard en een losse PNG allemaal
    dezelfde grafiek opleveren.
    """

    PALETTE = TREND_PALETTE

    # EventHub draait standaard donker; de grafiek tekent zelf en kan de
    # stylesheet dus niet volgen.
    dark = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self.series = {"groups": [], "points": [], "metric": "aangemeld"}
        self._hit_points = []
        self.setMouseTracking(True)
        # De ouder bepaalt de beschikbare hoogte. Een hoge vaste ondergrens
        # duwde op kleinere schermen de onderkant van Trends buiten beeld.
        self.setMinimumHeight(180)

    def set_series(self, series: dict):
        self.series = series or {"groups": [], "points": [], "metric": "aangemeld"}
        self.update()

    def set_dark_mode(self, dark: bool):
        self.dark = bool(dark)
        self.update()

    def _formatted(self, value: float) -> str:
        metric = self.series.get("display_metric", self.series.get("metric", ""))
        return format_chart_value(value, str(metric or ""))

    @staticmethod
    def _nice_step(span: float) -> float:
        return chart_nice_step(span)

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        try:
            self._hit_points = paint_trend_chart(
                painter, self.width(), self.height(), self.series, self.dark
            )
        finally:
            painter.end()

    def image(self, width: int = 1000, height: int = 380, scale: float = 2.0) -> QImage:
        """Deze grafiek als exportwaardige afbeelding, in de lichte huisstijl."""
        return render_trend_image(self.series, width, height, dark=False, scale=scale)

    def export_png(self):
        """Deze ene grafiek als afbeelding wegschrijven.

        Geen schermafdruk van het venster: dezelfde tekencode als op het
        scherm, alleen op documentresolutie en met een rustige achtergrond.
        """
        if not chart_has_values(self.series):
            QMessageBox.information(self, "Geen grafiek",
                                    "Deze grafiek heeft nog geen waarden om te exporteren.")
            return
        standaard = exports_directory() / f"EventHub grafiek {date.today():%Y-%m-%d}.png"
        bestand, _filter = QFileDialog.getSaveFileName(
            self, "Grafiek exporteren", str(standaard), "PNG-afbeelding (*.png)"
        )
        if not bestand:
            return
        if not bestand.lower().endswith(".png"):
            bestand += ".png"
        try:
            export_chart_png(self.series, bestand)
        except (ExportError, OSError) as fout:
            QMessageBox.warning(self, "Export mislukt",
                                f"De grafiek kon niet worden opgeslagen.\n\n{fout}")
            return
        QMessageBox.information(self, "Export gereed",
                                f"De grafiek is opgeslagen als:\n{bestand}")

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        exporteren = menu.addAction("Exporteren als PNG…")
        exporteren.setEnabled(chart_has_values(self.series))
        if menu.exec(event.globalPos()) is exporteren:
            self.export_png()

    def mouseMoveEvent(self, event):
        if not self._hit_points:
            return super().mouseMoveEvent(event)
        position = event.position()
        nearest = min(
            self._hit_points,
            key=lambda point: (point[0] - position.x()) ** 2 + (point[1] - position.y()) ** 2,
        )
        distance = (nearest[0] - position.x()) ** 2 + (nearest[1] - position.y()) ** 2
        if distance <= 12 ** 2:
            _x, _y, period, group, value = nearest
            detail = f"{period}\n{group}: {self._formatted(value)}"
            if self.series.get("percentage_of_total"):
                point = next(
                    (item for item in self.series.get("points", []) if str(item.get("label")) == period),
                    {},
                )
                count = float(point.get("raw_values", {}).get(group, 0) or 0)
                total = float(point.get("raw_total", 0) or 0)
                detail += f" · {count:g} van {total:g}"
            QToolTip.showText(
                event.globalPosition().toPoint(),
                detail,
                self,
            )
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

class TrendChartDialog(QDialog):
    """Een stabiele schermvullende weergave zonder de Trends-pagina te verbouwen."""

    def __init__(self, series: dict, dark: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Trends — grafiek op volledig scherm")
        self.setModal(True)
        layout = QVBoxLayout(self)
        heading = QLabel("Trends — beweeg over een bolletje voor de exacte waarde")
        heading.setObjectName("statisticsTitle")
        layout.addWidget(heading)
        self.chart = TrendChart()
        self.chart.setMinimumHeight(400)
        self.chart.set_dark_mode(dark)
        self.chart.set_series(series)
        layout.addWidget(self.chart, 1)
        actions = QHBoxLayout()
        png_button = _make_button_compact(QPushButton("Exporteren als PNG"))
        png_button.setObjectName("secondaryButton")
        png_button.clicked.connect(self.chart.export_png)
        actions.addWidget(png_button)
        actions.addStretch()
        close_button = _make_button_compact(QPushButton("Terug naar Trends"))
        close_button.setObjectName("primaryButton")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)
