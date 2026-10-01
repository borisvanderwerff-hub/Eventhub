"""De rapportopmaak: blokken over pagina's, en het tekenen van die pagina's.

Eén opmaak voor het exportvoorbeeld en de PDF. Het voorbeeld tekent dezelfde
pagina's op het scherm als de PDF op papier, met dezelfde marges, dezelfde
pagina-einden en dezelfde grafieken. Wat je ziet is wat je krijgt, omdat het
letterlijk dezelfde tekencode is.

Maten zijn punten (1/72 inch), zodat ze rechtstreeks op een PDF passen.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen

from emt_charts import paint_trend_chart
from emt_report import datum_tekst, page_orientation

# A4 in punten.
PAGE_SIZES = {"staand": (595.0, 842.0), "liggend": (842.0, 595.0)}
MARGIN = 46.0
HEADER_HEIGHT = 26.0
FOOTER_HEIGHT = 26.0

# De huisstijl van EventHub, op papier in de lichte variant: een rapport dat
# je uitprint hoort geen zwarte pagina's te hebben.
INK = "#17233a"
MUTED = "#637187"
ACCENT = "#6c2cff"
RULE = "#d8e0eb"
PANEL = "#f3f6fb"

TITLE_FONT = ("Segoe UI", 22, QFont.Weight.Bold)
SECTION_FONT = ("Segoe UI", 14, QFont.Weight.DemiBold)
SUB_FONT = ("Segoe UI", 11, QFont.Weight.DemiBold)
BODY_FONT = ("Segoe UI", 9.5, QFont.Weight.Normal)
SMALL_FONT = ("Segoe UI", 8, QFont.Weight.Normal)

# Een grafiek krijgt zoveel hoogte dat er drie op een staande pagina passen en
# twee op een liggende. Zo blijft er nooit een halve pagina wit achter.
CHART_HEIGHT = 200.0
CHART_HEIGHT_LANDSCAPE = 185.0
# Meer reeksen vragen meer hoogte: de legenda eet ruimte uit de grafiek, en bij
# acht groepen bleef er van de vaste hoogte een strook over waarin de lijnen
# over elkaar heen liepen.
CHART_EXTRA_PER_GROUP = 24.0
CHART_EXTRA_MAX = 150.0
CHART_TITLE_HEIGHT = 20.0
ROW_HEIGHT = 17.0
HEADER_ROW_HEIGHT = 20.0
KPI_HEIGHT = 46.0
KPI_COLUMNS = 3
KPI_GAP = 10.0
BLOCK_GAP = 14.0
MIN_TABLE_ROWS = 3


def _font(spec) -> QFont:
    familie, grootte, gewicht = spec
    font = QFont(familie)
    font.setPointSizeF(float(grootte))
    font.setWeight(gewicht)
    return font


class ReportLayout:
    """Verdeelt de rapportblokken over pagina's en tekent ze.

    Blokken zijn logische eenheden: een grafiek met zijn titel, een KPI-groep,
    een inzicht. Die worden nooit doorgesneden. Alleen een tabel mag over
    pagina's lopen, en dan herhaalt de kolomkop zich.
    """

    def __init__(self, model: dict, orientation: str = ""):
        self.model = model or {}
        self.orientation = orientation or page_orientation(self.model)
        self.page_width, self.page_height = PAGE_SIZES.get(
            self.orientation, PAGE_SIZES["staand"]
        )
        self.design = dict(self.model.get("vormgeving", {}) or {})
        self.chart_height = (CHART_HEIGHT_LANDSCAPE if self.orientation == "liggend"
                             else CHART_HEIGHT)
        self.pages = []
        self._build()

    # ------------------------------------------------------------- indeling

    @property
    def content_width(self) -> float:
        return self.page_width - 2 * MARGIN

    @property
    def content_top(self) -> float:
        return MARGIN + (HEADER_HEIGHT if self._has_header() else 0.0)

    @property
    def content_bottom(self) -> float:
        return self.page_height - MARGIN - (FOOTER_HEIGHT if self._has_footer() else 0.0)

    def _has_header(self) -> bool:
        return True

    def _has_footer(self) -> bool:
        return bool(self.design.get("paginanummers", True)
                    or self.design.get("datum", True))

    def _measure(self, blok: dict, metrics: dict) -> float:
        kind = blok["kind"]
        if kind == "paragraph":
            return self._text_height(blok["text"], metrics["body"], self.content_width)
        if kind == "subheading":
            return metrics["sub"].height() + 6
        if kind == "kpis":
            rijen = (len(blok["items"]) + KPI_COLUMNS - 1) // KPI_COLUMNS
            return rijen * KPI_HEIGHT + (rijen - 1) * KPI_GAP
        if kind == "chart":
            return CHART_TITLE_HEIGHT + self._chart_height_for(blok)
        if kind == "insight":
            hoogte = metrics["sub"].height() + 4
            return hoogte + self._text_height(blok["detail"], metrics["small"],
                                              self.content_width - 16) + 12
        if kind == "table":
            header, heights = self._table_heights(blok)
            return header + sum(heights)
        return 0.0

    def _table_heights(self, block):
        weights = block.get("weights") or [1] * len(block["columns"])
        widths = [self.content_width * weight / sum(weights) - 10 for weight in weights]
        def height(cells, font, minimum):
            metrics = QFontMetricsF(_font(font))
            return max([minimum] + [metrics.boundingRect(QRectF(0, 0, max(1, widths[i]), 100000),
                int(Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere), str(cell)).height() + 8
                for i, cell in enumerate(cells)])
        return (height(block["columns"], ("Segoe UI", 8.5, QFont.Weight.DemiBold), HEADER_ROW_HEIGHT),
                [height(row, BODY_FONT, ROW_HEIGHT) for row in block["rows"]])

    def _chart_height_for(self, blok: dict) -> float:
        """De hoogte die deze grafiek nodig heeft, naar het aantal reeksen.

        Twee lijnen passen prima in de basishoogte; bij acht wordt het knijpen
        omdat de legenda dan vier regels kost en de lijnen dicht op elkaar
        komen. Elke reeks daarboven krijgt wat hoogte terug, tot een grens die
        nog op één pagina past.
        """
        groepen = len((blok.get("series") or {}).get("groups") or [])
        extra = min(CHART_EXTRA_MAX, max(0, min(groepen, 10) - 2) * CHART_EXTRA_PER_GROUP)
        return self.chart_height + extra

    @staticmethod
    def _text_height(tekst: str, metrics: QFontMetricsF, breedte: float) -> float:
        vak = metrics.boundingRect(
            QRectF(0, 0, breedte, 10000),
            int(Qt.TextFlag.TextWordWrap), str(tekst or ""),
        )
        return max(metrics.height(), vak.height())

    def _metrics(self) -> dict:
        return {
            "title": QFontMetricsF(_font(TITLE_FONT)),
            "section": QFontMetricsF(_font(SECTION_FONT)),
            "sub": QFontMetricsF(_font(SUB_FONT)),
            "body": QFontMetricsF(_font(BODY_FONT)),
            "small": QFontMetricsF(_font(SMALL_FONT)),
        }

    def _build(self):
        metrics = self._metrics()
        self.pages = []
        pagina = {"items": [], "cover": False}
        y = self.content_top

        if self.design.get("voorblad", True):
            self.pages.append({"items": [], "cover": True})

        if self.design.get("inhoudsopgave", False):
            titels = [sectie["title"] for sectie in self.model.get("sections", [])]
            if titels:
                pagina["items"].append((MARGIN, y, self.content_width,
                                        metrics["section"].height() + 8,
                                        {"kind": "heading", "text": "Inhoud"}))
                y += metrics["section"].height() + 8 + 6
                for titel in titels:
                    pagina["items"].append((MARGIN, y, self.content_width, ROW_HEIGHT,
                                            {"kind": "toc", "text": titel}))
                    y += ROW_HEIGHT
                self.pages.append(pagina)
                pagina = {"items": [], "cover": False}
                y = self.content_top

        active_section = ""
        def nieuwe_pagina():
            nonlocal pagina, y
            if pagina["items"]:
                self.pages.append(pagina)
            pagina = {"items": [], "cover": False, "section": active_section}
            y = self.content_top

        for sectie in self.model.get("sections", []):
            active_section = sectie["title"]
            kop = {"kind": "heading", "text": sectie["title"]}
            kop_hoogte = metrics["section"].height() + 10
            # Elk onderdeel begint op een eigen pagina. Twee hoofdstukken onder
            # elkaar op één blad laten de lezer zoeken waar het ene ophoudt en
            # het andere begint.
            nieuwe_pagina()
            pagina["items"].append((MARGIN, y, self.content_width, kop_hoogte, kop))
            y += kop_hoogte + BLOCK_GAP

            for positie, blok in enumerate(sectie["blocks"]):
                hoogte = self._measure(blok, metrics)
                ruimte = self.content_bottom - y
                if blok["kind"] == "subheading":
                    # Een tussenkop hoort niet als laatste regel op een pagina
                    # te eindigen; hij moet met zijn eerste inhoud mee.
                    volgende = sectie["blocks"][positie + 1:positie + 2]
                    mee = min(self._measure(volgende[0], metrics),
                              HEADER_ROW_HEIGHT + MIN_TABLE_ROWS * ROW_HEIGHT) if volgende else 0.0
                    if hoogte + BLOCK_GAP + mee > ruimte:
                        nieuwe_pagina()
                        ruimte = self.content_bottom - y
                if blok["kind"] == "table" and hoogte > ruimte:
                    # Grote tabellen mogen breken; de kolomkop komt op elke
                    # nieuwe pagina terug.
                    rijen = list(blok["rows"])
                    while rijen:
                        ruimte = self.content_bottom - y
                        header, heights = self._table_heights(dict(blok, rows=rijen))
                        if header + heights[0] > ruimte:
                            nieuwe_pagina()
                            ruimte = self.content_bottom - y
                        passend, used = 0, header
                        for row_height in heights:
                            if passend and used + row_height > ruimte:
                                break
                            used += row_height
                            passend += 1
                        deel = rijen[:passend]
                        rijen = rijen[len(deel):]
                        stuk = dict(blok, rows=deel, vervolg=bool(rijen))
                        stuk_hoogte = header + sum(heights[:passend])
                        pagina["items"].append((MARGIN, y, self.content_width, stuk_hoogte, stuk))
                        y += stuk_hoogte + BLOCK_GAP
                        if rijen:
                            nieuwe_pagina()
                    continue
                if hoogte > ruimte:
                    nieuwe_pagina()
                pagina["items"].append((MARGIN, y, self.content_width, hoogte, blok))
                y += hoogte + BLOCK_GAP

        if pagina["items"]:
            self.pages.append(pagina)
        if not self.pages:
            self.pages.append({"items": [], "cover": False})

    def page_count(self) -> int:
        return len(self.pages)

    # -------------------------------------------------------------- tekenen

    def paint_page(self, painter: QPainter, index: int):
        """Teken pagina *index* in de painter, met (0,0) linksboven op de pagina."""
        if not 0 <= index < len(self.pages):
            return
        pagina = self.pages[index]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(QRectF(0, 0, self.page_width, self.page_height), QColor("#ffffff"))

        if pagina.get("cover"):
            self._paint_cover(painter)
        else:
            self._paint_header(painter, pagina.get("section", ""))
            for x, y, breedte, hoogte, blok in pagina["items"]:
                self._paint_block(painter, blok, QRectF(x, y, breedte, hoogte))
            self._paint_footer(painter, index)
        painter.restore()

    def _paint_cover(self, painter: QPainter):
        painter.fillRect(QRectF(0, 0, self.page_width, 10), QColor(ACCENT))
        midden = self.page_height / 2 - 90
        painter.setPen(QColor(ACCENT))
        painter.setFont(_font(SMALL_FONT))
        painter.drawText(QRectF(MARGIN, midden - 26, self.content_width, 18),
                         int(Qt.AlignmentFlag.AlignLeft), "EVENTHUB · TRENDS")
        painter.setPen(QColor(INK))
        painter.setFont(_font(TITLE_FONT))
        titel_hoogte = self._text_height(self.model.get("titel", ""),
                                         QFontMetricsF(_font(TITLE_FONT)), self.content_width)
        painter.drawText(QRectF(MARGIN, midden, self.content_width, titel_hoogte),
                         int(Qt.TextFlag.TextWordWrap), str(self.model.get("titel", "")))
        onder = midden + titel_hoogte + 8
        if self.model.get("subtitel"):
            painter.setPen(QColor(MUTED))
            painter.setFont(_font(SECTION_FONT))
            painter.drawText(QRectF(MARGIN, onder, self.content_width, 30),
                             int(Qt.TextFlag.TextWordWrap), str(self.model["subtitel"]))
            onder += 30
        painter.setPen(QColor(RULE))
        painter.drawLine(QRectF(MARGIN, onder + 12, self.content_width, 0).topLeft(),
                         QRectF(MARGIN, onder + 12, self.content_width, 0).topRight())
        painter.setPen(QColor(MUTED))
        painter.setFont(_font(BODY_FONT))
        regels = []
        if self.design.get("filters", True):
            regels.extend(f"{naam}: {waarde}" for naam, waarde in self.model.get("filters", []))
        else:
            regels.append(f"Rapportperiode: {self.model.get('periode', '')}")
        if self.model.get("bron"):
            regels.append(f"Bron: {self.model['bron']}")
        if self.design.get("datum", True):
            regels.append(f"Gegenereerd op {datum_tekst(date.today())}")
        y = onder + 24
        for regel in regels:
            height = max(16, self._text_height(regel, QFontMetricsF(painter.font()), self.content_width))
            painter.drawText(QRectF(MARGIN, y, self.content_width, height),
                             int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap), regel)
            y += height + 2
        # Trends rekent met geanonimiseerde aantallen; dat hoort in het
        # rapport te staan, zodat een lezer weet wat hij voor zich heeft.
        painter.setFont(_font(SMALL_FONT))
        painter.drawText(
            QRectF(MARGIN, self.page_height - MARGIN - 28, self.content_width, 16),
            int(Qt.AlignmentFlag.AlignLeft),
            "Deze rapportage bevat uitsluitend geanonimiseerde aantallen; geen namen "
            "of persoonsgegevens.",
        )

    def _paint_header(self, painter: QPainter, section=""):
        painter.setPen(QColor(MUTED))
        painter.setFont(_font(SMALL_FONT))
        title = " · ".join(filter(None, [section, self.model.get("selectie", {}).get("template_name", "")])) or str(self.model.get("titel", ""))
        painter.drawText(QRectF(MARGIN, MARGIN - 16, self.content_width * 0.6, 14),
                         int(Qt.AlignmentFlag.AlignLeft), QFontMetricsF(painter.font()).elidedText(title, Qt.TextElideMode.ElideRight, self.content_width * 0.6))
        if self.model.get("periode"):
            painter.drawText(QRectF(MARGIN + self.content_width * 0.62, MARGIN - 16, self.content_width * 0.38, 14),
                             int(Qt.AlignmentFlag.AlignRight), QFontMetricsF(painter.font()).elidedText(str(self.model["periode"]), Qt.TextElideMode.ElideRight, self.content_width * 0.38))
        painter.setPen(QPen(QColor(RULE), 0.7))
        painter.drawLine(MARGIN, MARGIN + 2, self.page_width - MARGIN, MARGIN + 2)

    def _paint_footer(self, painter: QPainter, index: int):
        if not self._has_footer():
            return
        y = self.page_height - MARGIN - 12
        painter.setPen(QPen(QColor(RULE), 0.7))
        painter.drawLine(MARGIN, y - 6, self.page_width - MARGIN, y - 6)
        painter.setPen(QColor(MUTED))
        painter.setFont(_font(SMALL_FONT))
        if self.design.get("datum", True):
            painter.drawText(QRectF(MARGIN, y, self.content_width, 14),
                             int(Qt.AlignmentFlag.AlignLeft),
                             f"Gegenereerd op {datum_tekst(date.today())}")
        if self.design.get("paginanummers", True):
            painter.drawText(QRectF(MARGIN, y, self.content_width, 14),
                             int(Qt.AlignmentFlag.AlignRight),
                             f"Pagina {index + 1} van {len(self.pages)}")

    def _paint_block(self, painter: QPainter, blok: dict, vak: QRectF):
        try:
            self._draw_block(painter, blok, vak)
        except Exception:  # noqa: BLE001
            # Eén blok dat niet te tekenen is mag de rest van de pagina niet
            # meenemen; er blijft dan simpelweg witruimte staan.
            painter.setPen(QColor(MUTED))
            painter.setFont(_font(SMALL_FONT))
            painter.drawText(vak, int(Qt.AlignmentFlag.AlignLeft),
                             "Dit onderdeel kon niet worden weergegeven.")

    def _draw_block(self, painter: QPainter, blok: dict, vak: QRectF):
        kind = blok["kind"]
        if kind == "heading":
            painter.setPen(QColor(INK))
            painter.setFont(_font(SECTION_FONT))
            painter.drawText(vak, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                             str(blok["text"]))
            painter.setPen(QPen(QColor(ACCENT), 1.5))
            painter.drawLine(vak.left(), vak.bottom() - 1, vak.left() + 46, vak.bottom() - 1)
        elif kind == "toc":
            painter.setPen(QColor(INK))
            painter.setFont(_font(BODY_FONT))
            painter.drawText(vak, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                             str(blok["text"]))
        elif kind == "subheading":
            painter.setPen(QColor(INK))
            painter.setFont(_font(SUB_FONT))
            painter.drawText(vak, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                             str(blok["text"]))
        elif kind == "paragraph":
            painter.setPen(QColor(INK))
            painter.setFont(_font(BODY_FONT))
            painter.drawText(vak, int(Qt.TextFlag.TextWordWrap), str(blok["text"]))
        elif kind == "kpis":
            self._paint_kpis(painter, blok, vak)
        elif kind == "chart":
            self._paint_chart(painter, blok, vak)
        elif kind == "insight":
            self._paint_insight(painter, blok, vak)
        elif kind == "table":
            self._paint_table(painter, blok, vak)

    def _paint_kpis(self, painter: QPainter, blok: dict, vak: QRectF):
        items = blok["items"]
        kolom_breedte = (vak.width() - (KPI_COLUMNS - 1) * KPI_GAP) / KPI_COLUMNS
        for index, (label, waarde) in enumerate(items):
            rij, kolom = divmod(index, KPI_COLUMNS)
            x = vak.left() + kolom * (kolom_breedte + KPI_GAP)
            y = vak.top() + rij * (KPI_HEIGHT + KPI_GAP)
            kaart = QRectF(x, y, kolom_breedte, KPI_HEIGHT)
            painter.setPen(QPen(QColor(RULE), 0.8))
            painter.setBrush(QColor(PANEL))
            painter.drawRoundedRect(kaart, 6, 6)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor(MUTED))
            painter.setFont(_font(SMALL_FONT))
            painter.drawText(kaart.adjusted(10, 5, -10, 0),
                             int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft), str(label))
            painter.setPen(QColor(INK))
            painter.setFont(_font(("Segoe UI", 15, QFont.Weight.Bold)))
            painter.drawText(kaart.adjusted(10, 0, -10, -5),
                             int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft), str(waarde))

    def _paint_chart(self, painter: QPainter, blok: dict, vak: QRectF):
        painter.setPen(QColor(INK))
        painter.setFont(_font(SUB_FONT))
        painter.drawText(QRectF(vak.left(), vak.top(), vak.width(), CHART_TITLE_HEIGHT),
                         int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                         str(blok.get("title", "")))
        grafiek = QRectF(vak.left(), vak.top() + CHART_TITLE_HEIGHT, vak.width(),
                         vak.height() - CHART_TITLE_HEIGHT)
        painter.setPen(QPen(QColor(RULE), 0.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(grafiek, 6, 6)
        painter.save()
        painter.translate(grafiek.left(), grafiek.top())
        # Dezelfde tekencode als op het scherm; rechtstreeks vectorieel, dus
        # scherp op elke zoom en in de PDF.
        paint_trend_chart(painter, grafiek.width(), grafiek.height(),
                          blok.get("series", {}), dark=False, with_background=False)
        painter.restore()

    def _paint_insight(self, painter: QPainter, blok: dict, vak: QRectF):
        painter.setPen(QPen(QColor(RULE), 0.8))
        painter.setBrush(QColor(PANEL))
        painter.drawRoundedRect(vak, 6, 6)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(ACCENT), 2))
        painter.drawLine(vak.left() + 1, vak.top() + 6, vak.left() + 1, vak.bottom() - 6)
        binnen = vak.adjusted(12, 6, -10, -6)
        painter.setPen(QColor(INK))
        painter.setFont(_font(SUB_FONT))
        kop_hoogte = QFontMetricsF(_font(SUB_FONT)).height()
        painter.drawText(QRectF(binnen.left(), binnen.top(), binnen.width(), kop_hoogte),
                         int(Qt.AlignmentFlag.AlignLeft), str(blok.get("title", "")))
        painter.setPen(QColor(MUTED))
        painter.setFont(_font(SMALL_FONT))
        painter.drawText(QRectF(binnen.left(), binnen.top() + kop_hoogte + 2,
                                binnen.width(), binnen.height() - kop_hoogte - 2),
                         int(Qt.TextFlag.TextWordWrap), str(blok.get("detail", "")))

    def _paint_table(self, painter: QPainter, blok: dict, vak: QRectF):
        header_height, row_heights = self._table_heights(blok)
        kolommen = blok["columns"]
        gewichten = blok.get("weights") or [1] * len(kolommen)
        totaal = sum(gewichten) or 1
        breedtes = [vak.width() * gewicht / totaal for gewicht in gewichten]

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PANEL))
        painter.drawRect(QRectF(vak.left(), vak.top(), vak.width(), header_height))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        kop_font = _font(("Segoe UI", 8.5, QFont.Weight.DemiBold))
        painter.setFont(kop_font)
        kop_metrics = QFontMetricsF(kop_font)
        painter.setPen(QColor(INK))
        x = vak.left()
        for index, kop in enumerate(kolommen):
            uitlijning = (Qt.AlignmentFlag.AlignRight if index and index >= len(kolommen) - 3
                          else Qt.AlignmentFlag.AlignLeft)
            painter.drawText(
                QRectF(x + 5, vak.top() + 4, breedtes[index] - 10, header_height - 8),
                int(uitlijning | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere),
                # Ook een kolomkop mag niet buiten zijn kolom lopen.
                str(kop),
            )
            x += breedtes[index]

        painter.setFont(_font(BODY_FONT))
        metrics = QFontMetricsF(_font(BODY_FONT))
        y = vak.top() + header_height
        for rij_index, rij in enumerate(blok["rows"]):
            row_height = row_heights[rij_index]
            if rij_index % 2:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#fafbfd"))
                painter.drawRect(QRectF(vak.left(), y, vak.width(), row_height))
                painter.setBrush(Qt.BrushStyle.NoBrush)
            x = vak.left()
            painter.setPen(QColor(INK))
            for index, cel in enumerate(rij):
                uitlijning = (Qt.AlignmentFlag.AlignRight if index and index >= len(kolommen) - 3
                              else Qt.AlignmentFlag.AlignLeft)
                painter.drawText(QRectF(x + 5, y + 4, breedtes[index] - 10, row_height - 8),
                                 int(uitlijning | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere), str(cel))
                x += breedtes[index]
            y += row_height
        painter.setPen(QPen(QColor(RULE), 0.6))
        painter.drawRect(QRectF(vak.left(), vak.top(), vak.width(),
                                header_height + sum(row_heights)))
        if blok.get("vervolg"):
            painter.setPen(QColor(MUTED))
            painter.setFont(_font(SMALL_FONT))
            painter.drawText(QRectF(vak.left(), vak.bottom() + 1, vak.width(), 12),
                             int(Qt.AlignmentFlag.AlignRight), "wordt vervolgd")
