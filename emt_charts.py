"""De trendgrafiek, één keer getekend en overal hergebruikt.

De grafiek zat in het teken-event van een widget. Daardoor was hij alleen op
het scherm te krijgen: een export moest hem opnieuw opbouwen, en dan wijkt hij
af. Hier staat het tekenen los van de widget, zodat exact dezelfde lijnen,
kleuren, assen en legenda terechtkomen in:

* de Trends-pagina zelf;
* het exportvoorbeeld;
* de PDF (rechtstreeks vectorieel);
* het Excel-dashboard (als hoogwaardige afbeelding);
* een losse PNG.

Gebruik `paint_trend_chart` om in een bestaande painter te tekenen en
`render_trend_image` voor een afbeelding op exporthoogte.
"""
from __future__ import annotations

from math import ceil
import hashlib

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter, QPen

# Dezelfde reeks kleuren als altijd; de volgorde bepaalt welke groep welke
# kleur krijgt, dus die mag niet veranderen.
TREND_PALETTE = [
    "#8b6cff", "#22c8dd", "#ff9f45", "#3ecf8e", "#ff6f9c",
    "#4da3ff", "#d4b74a", "#c98a6b", "#8fa3bd", "#c07de0",
]

PERCENTAGE_METRICS = {"opkomst_percentage", "noshow_percentage", "aandeel_percentage"}

LEEG_BERICHT = (
    "Nog geen cijfers beschikbaar.\n"
    "Evenementen krijgen cijfers zodra hun datum is geweest."
)

# Eén meetmoment is geen verloop. Zonder deze uitleg lijkt de grafiek stuk,
# terwijl er gewoon te weinig evenementen met afgeronde cijfers zijn.
EEN_MOMENT_BERICHT = "Eén meetmoment — een verloop vraagt er minstens twee"


def chart_colours(dark: bool) -> dict:
    """De vier kleuren van het grafiekvlak, per thema."""
    return {
        "surface": QColor("#111827" if dark else "#ffffff"),
        "grid": QColor("#26334a" if dark else "#e3e7ee"),
        "text": QColor("#f5f7fb" if dark else "#17233a"),
        "muted": QColor("#93a4ba" if dark else "#7b6d82"),
    }


def group_colour(group: str) -> QColor:
    """Stable across metrics, filtering, exports and application restarts."""
    if group == "Totaal":
        return QColor(TREND_PALETTE[0])
    digest = hashlib.sha256(str(group).casefold().encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") / 65536.0
    return QColor.fromHsvF(hue, 0.68, 0.86)


def format_value(value: float, metric: str = "") -> str:
    return f"{value:g}%" if metric in PERCENTAGE_METRICS else f"{value:g}"


def nice_step(span: float) -> float:
    """Een ronde stapgrootte, zodat de as 20/40/60 toont in plaats van 17,2."""
    if span <= 0:
        return 1.0
    rough = span / 4
    magnitude = 1.0
    while magnitude * 10 <= rough:
        magnitude *= 10
    while magnitude > rough and magnitude > 1e-9:
        magnitude /= 10
    for multiplier in (1, 2, 2.5, 5, 10):
        if rough <= magnitude * multiplier:
            return magnitude * multiplier
    return magnitude * 10


LEGEND_MAX_GROUPS = 8
LEGEND_MAX_ROWS = 4
LEGEND_ROW_HEIGHT = 20
LEGEND_MARKER_SPACE = 26


def legend_layout(groups, metrics: QFontMetricsF, width: float) -> tuple[int, int]:
    """Hoeveel kolommen en rijen de legenda krijgt.

    Vier vaste kolommen kapten namen als "Mbo niveau 4 techniek" of een
    opleidingsprofiel halverwege af. Nu bepaalt de langste naam hoeveel
    kolommen er passen; alleen als het er dan te veel rijen worden gaan er
    weer kolommen bij.
    """
    zichtbaar = list(groups)[:LEGEND_MAX_GROUPS]
    if not zichtbaar:
        return 0, 0
    langste = max(metrics.horizontalAdvance(str(groep)) for groep in zichtbaar)
    nodig = langste + LEGEND_MARKER_SPACE
    kolommen = max(1, min(4, int(width // max(70.0, nodig)) or 1))
    rijen = ceil(len(zichtbaar) / kolommen)
    if rijen > LEGEND_MAX_ROWS:
        kolommen = ceil(len(zichtbaar) / LEGEND_MAX_ROWS)
        rijen = LEGEND_MAX_ROWS
    return kolommen, rijen


def has_values(series: dict | None) -> bool:
    """Valt er iets te tekenen? Gebruikt om lege secties over te slaan."""
    series = series or {}
    return bool(series.get("points")) and bool(series.get("groups"))


def paint_trend_chart(painter: QPainter, width: float, height: float,
                      series: dict, dark: bool = True,
                      with_background: bool = True) -> list:
    """Teken de grafiek in de painter, binnen (0, 0, width, height).

    Geeft de trefpunten terug: (x, y, periode, groep, waarde). De widget
    gebruikt die voor de tooltip; een export gooit ze weg.
    """
    series = series or {}
    kleuren = chart_colours(dark)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    if with_background:
        painter.fillRect(QRectF(0, 0, width, height), kleuren["surface"])
    painter.setFont(QFont("Segoe UI", 9))

    points = series.get("points") or []
    groups = series.get("groups") or []
    metric = str(series.get("display_metric", series.get("metric", "")) or "")
    if not points or not groups:
        painter.setPen(kleuren["muted"])
        painter.drawText(QRectF(0, 0, width, height), Qt.AlignmentFlag.AlignCenter, LEEG_BERICHT)
        painter.restore()
        return []

    def tekst(value: float) -> str:
        return format_value(value, metric)

    # De legenda krijgt een eigen strook; zonder die extra ruimte valt hij
    # bij meerdere groepen buiten beeld.
    left, top, right = 66, 22, 24
    plot_width = max(1, width - left - right)
    legend_columns, legend_rows = legend_layout(
        groups, QFontMetricsF(painter.font()), plot_width
    )
    bottom = 34 + legend_rows * LEGEND_ROW_HEIGHT
    plot_height = max(1, height - top - bottom)

    values = [value for point in points for value in point["values"].values()]
    highest = max(values + [0.0]) or 1.0
    step = nice_step(highest)
    top_value = step * (int(highest / step) + (1 if highest % step else 0)) or step

    painter.setPen(kleuren["grid"])
    ticks = int(round(top_value / step))
    for index in range(ticks + 1):
        value = step * index
        y = top + plot_height - round(plot_height * value / top_value)
        painter.drawLine(int(left), int(y), int(left + plot_width), int(y))
        painter.setPen(kleuren["muted"])
        painter.drawText(
            QRectF(0, y - 9, left - 10, 18),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            tekst(round(value, 1)),
        )
        painter.setPen(kleuren["grid"])

    count = len(points)
    spacing = plot_width / max(1, count - 1) if count > 1 else 0

    def x_for(index):
        return left + (plot_width / 2 if count == 1 else index * spacing)

    def y_for(value):
        return top + plot_height - (plot_height * value / top_value)

    trefpunten = []
    if count == 1:
        # Eén meetmoment: door één punt gaat geen lijn. Dan is dit geen
        # verloop maar een vergelijking tussen groepen, en die leest als
        # staven. Anders bleven er losse bolletjes over.
        vak_breedte = plot_width / max(1, len(groups))
        staaf_breedte = max(6.0, min(64.0, vak_breedte * 0.6))
        painter.setPen(Qt.PenStyle.NoPen)
        for group_index, group in enumerate(groups):
            value = points[0]["values"].get(group, 0.0)
            colour = group_colour(group)
            midden = left + vak_breedte * (group_index + 0.5)
            y = y_for(value)
            painter.setBrush(colour)
            painter.drawRoundedRect(
                QRectF(midden - staaf_breedte / 2, y, staaf_breedte,
                       max(1.0, top + plot_height - y)),
                3, 3,
            )
            trefpunten.append((midden, y, str(points[0]["label"]), str(group), value))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Bij een bewust gekozen statistiekweergave is één meetmoment geen
        # tekort maar de bedoeling; dan hoort er geen uitleg bij te staan.
        if series.get("period") != "total":
            painter.setPen(kleuren["muted"])
            painter.setFont(QFont("Segoe UI", 8))
            uitleg_metrics = QFontMetricsF(painter.font())
            painter.drawText(
                QRectF(left, 2, plot_width, 14),
                int(Qt.AlignmentFlag.AlignRight),
                uitleg_metrics.elidedText(EEN_MOMENT_BERICHT, Qt.TextElideMode.ElideRight,
                                          plot_width),
            )
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        for group_index, group in enumerate(groups):
            value = points[0]["values"].get(group, 0.0)
            painter.setPen(group_colour(group))
            midden = left + vak_breedte * (group_index + 0.5)
            painter.drawText(
                QRectF(midden - vak_breedte / 2, max(2.0, y_for(value) - 18),
                       vak_breedte, 16),
                int(Qt.AlignmentFlag.AlignCenter), tekst(value),
            )
        painter.setFont(QFont("Segoe UI", 9))
    else:
        for group_index, group in enumerate(groups):
            colour = group_colour(group)
            painter.setPen(QPen(colour, 2))
            previous = None
            for index, point in enumerate(points):
                x, y = x_for(index), y_for(point["values"].get(group, 0.0))
                trefpunten.append((x, y, str(point["label"]), str(group),
                                   point["values"].get(group, 0.0)))
                if previous is not None:
                    painter.drawLine(int(previous[0]), int(previous[1]), int(x), int(y))
                previous = (x, y)
            painter.setBrush(colour)
            painter.setPen(QPen(colour, 1))
            for index, point in enumerate(points):
                x, y = x_for(index), y_for(point["values"].get(group, 0.0))
                painter.drawEllipse(int(x) - 4, int(y) - 4, 8, 8)

        # Alleen de laatste waarde blijft permanent staan; de rest is
        # opvraagbaar via de tooltip. Zo overlappen cijfers van meerdere
        # lijnen niet.
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        label_boxes = []
        for group_index, group in enumerate(groups):
            painter.setPen(group_colour(group))
            value = points[-1]["values"].get(group, 0.0)
            x, y = x_for(count - 1), y_for(value)
            box_x = min(max(2, int(x) - 34), int(width) - 70)
            label_box = QRectF(box_x, max(2, int(y) - 22), 68, 16)
            if any(label_box.intersects(box) for box in label_boxes):
                continue
            label_boxes.append(label_box)
            painter.drawText(
                label_box,
                int(Qt.AlignmentFlag.AlignCenter), tekst(value),
            )
        painter.setFont(QFont("Segoe UI", 9))

    # Puntlabels onder de as, gedund zodat ze niet over elkaar vallen.
    painter.setPen(kleuren["muted"])
    as_metrics = QFontMetricsF(painter.font())
    every = max(1, count // max(1, int(plot_width / 110)))
    for index, point in enumerate(points):
        if index % every and index != count - 1:
            continue
        x = x_for(index)
        box_x = min(max(2, int(x) - 60), int(width) - 122)
        painter.drawText(
            QRectF(box_x, top + plot_height + 4, 120, 15),
            int(Qt.AlignmentFlag.AlignCenter),
            as_metrics.elidedText(str(point["label"]), Qt.TextElideMode.ElideRight, 118),
        )

    # Legenda in zoveel kolommen als de namen toelaten; maximaal acht reeksen
    # houdt hem leesbaar.
    if legend_rows and legend_columns:
        column_width = plot_width / legend_columns
        legend_metrics = QFontMetricsF(painter.font())
        beschikbaar = column_width - LEGEND_MARKER_SPACE
        for group_index, group in enumerate(groups[:LEGEND_MAX_GROUPS]):
            row, column = divmod(group_index, legend_columns)
            x = left + column * column_width
            y = top + plot_height + 20 + row * LEGEND_ROW_HEIGHT
            colour = group_colour(group)
            painter.setBrush(colour)
            painter.setPen(colour)
            painter.drawEllipse(int(x), int(y) + 4, 8, 8)
            painter.setPen(kleuren["text"])
            painter.drawText(
                QRectF(int(x) + 14, int(y), beschikbaar, 16),
                int(Qt.AlignmentFlag.AlignLeft),
                legend_metrics.elidedText(str(group), Qt.TextElideMode.ElideRight, beschikbaar),
            )

    painter.restore()
    return trefpunten


def render_trend_image(series: dict, width: int = 1000, height: int = 380,
                       dark: bool = False, scale: float = 2.0) -> QImage:
    """Dezelfde grafiek als een afbeelding, scherp genoeg voor document en dia.

    De maten blijven de gewone beeldmaten; alleen het aantal pixels gaat
    omhoog. Zo blijft de indeling identiek aan die op het scherm en wordt
    alleen de tekening fijner.
    """
    scale = max(1.0, float(scale))
    image = QImage(max(1, int(width * scale)), max(1, int(height * scale)),
                   QImage.Format.Format_RGB32)
    image.fill(chart_colours(dark)["surface"])
    painter = QPainter(image)
    try:
        painter.scale(scale, scale)
        paint_trend_chart(painter, width, height, series, dark)
    finally:
        painter.end()
    return image
