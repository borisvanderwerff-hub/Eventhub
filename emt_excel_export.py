"""Excel workbook exports for participant lists and statistics."""

from copy import copy
from pathlib import Path
import re
import zipfile
from xml.sax.saxutils import escape as xml_escape

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Imported on demand through visitorslijst_core's compatibility wrappers.
from bezoekerslijst_core import (
    ATTENDANCE_LABELS, KOP_VULLING, ONBEKEND, STRING_FIELDS, attendance_map,
    callback_status, date_text, initials_text, is_introducee, normalize,
    primary_visitor_name, registration_lookup, text, visitor_type,
)

def _style_sheet(worksheet, widths, wrap_columns=()):
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    worksheet.sheet_view.showGridLines = False
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True
    worksheet.print_options.horizontalCentered = True
    header_fill = PatternFill("solid", fgColor="071A33")
    alternate_fill = PatternFill("solid", fgColor="F7FAFC")
    for cell in worksheet[1]:
        cell.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")
    worksheet.row_dimensions[1].height = 24
    for column_index, width in enumerate(widths, 1):
        worksheet.column_dimensions[get_column_letter(column_index)].width = width
    for row_index in range(2, worksheet.max_row + 1):
        for column_index in range(1, worksheet.max_column + 1):
            cell = worksheet.cell(row_index, column_index)
            cell.font = Font(name="Segoe UI", size=10)
            cell.alignment = Alignment(vertical="top", wrap_text=column_index in wrap_columns)
            if row_index % 2 == 0:
                cell.fill = copy(alternate_fill)

def export_participant_template(
    records,
    event: dict,
    profile: dict,
    template_path: str | Path,
    output_path: str | Path,
):
    """Vul uitsluitend de daarvoor bedoelde cellen van de vaste DCPL-bezoekerslijst."""
    del event, profile
    template_path = Path(template_path)
    output_path = Path(output_path)
    if not template_path.is_file():
        raise FileNotFoundError(f"De deelnemerslijst-template ontbreekt: {template_path}")

    sorted_records = sorted(
        records,
        key=lambda row: (
            normalize(row.get("Achternaam")), normalize(row.get("Tussenvoegsel")),
            normalize(row.get("Voornaam")),
        ),
    )
    if not sorted_records:
        raise ValueError("Er zijn geen deelnemers om in de template te zetten.")

    data_start_row = 8
    last_data_row = data_start_row + len(sorted_records) - 1
    print_last_row = last_data_row

    with zipfile.ZipFile(template_path, "r") as source:
        entries = {item.filename: source.read(item.filename) for item in source.infolist()}
        infos = source.infolist()

    sheet_path = "xl/worksheets/sheet1.xml"
    workbook_path = "xl/workbook.xml"
    table_path = "xl/tables/table1.xml"
    if sheet_path not in entries or workbook_path not in entries or table_path not in entries:
        raise ValueError("De vaste deelnemerslijst-template is onvolledig.")

    sheet_xml = entries[sheet_path].decode("utf-8")
    workbook_xml = entries[workbook_path].decode("utf-8")
    table_xml = entries[table_path].decode("utf-8")
    if not all(f'r="{column}7"' in sheet_xml for column in "ABCDE"):
        raise ValueError("De vaste deelnemerslijst-template heeft een onverwachte kolomindeling.")

    def safe_xml_text(value) -> str:
        value = text(value)
        value = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)[:32767]
        preserve = ' xml:space="preserve"' if value != value.strip() else ""
        return f"<is><t{preserve}>{xml_escape(value)}</t></is>"

    def put_cell(xml: str, cell_ref: str, value) -> str:
        pattern = re.compile(rf'<c(?P<attrs>[^>]*\br="{re.escape(cell_ref)}"[^>]*)/>')

        def replacement(match):
            attrs = re.sub(r'\s+t="[^"]*"', "", match.group("attrs"))
            return f'<c{attrs} t="inlineStr">{safe_xml_text(value)}</c>'

        updated, count = pattern.subn(replacement, xml, count=1)
        if count != 1:
            raise ValueError(f"Invulveld {cell_ref} ontbreekt in de vaste deelnemerslijst-template.")
        return updated

    template_last_row = 181
    if last_data_row > template_last_row:
        for row_index in range(template_last_row + 1, last_data_row + 1):
            source_row_number = 180 if row_index % 2 == 0 else 181
            row_match = re.search(
                rf'(<row\s+r="{source_row_number}"(?=\s|>).*?</row>)',
                sheet_xml,
                flags=re.DOTALL,
            )
            if not row_match:
                raise ValueError("De vaste deelnemerslijst-template kan niet veilig worden uitgebreid.")
            new_row = re.sub(
                rf'\br="([A-Z]*){source_row_number}"',
                lambda match: f'r="{match.group(1)}{row_index}"',
                row_match.group(1),
            )
            sheet_xml = sheet_xml.replace("</sheetData>", new_row + "</sheetData>", 1)
        sheet_xml = sheet_xml.replace(
            '<dimension ref="A1:K181"/>',
            f'<dimension ref="A1:K{last_data_row}"/>',
            1,
        )
        table_xml = table_xml.replace('ref="A7:E181"', f'ref="A7:E{last_data_row}"', 2)

    for row_index, record in enumerate(sorted_records, data_start_row):
        values = (
            text(record.get("Achternaam", "")),
            text(record.get("Tussenvoegsel", "")),
            initials_text(record.get("Voornaam", "")),
            date_text(record.get("Geboortedatum", "")),
            text(record.get("Geboorteplaats", "")),
        )
        for column, value in zip("ABCDE", values):
            sheet_xml = put_cell(sheet_xml, f"{column}{row_index}", value)

    workbook_xml = re.sub(
        r'<definedName\s+name="_xlnm\.Print_Area"\s+localSheetId="0">.*?</definedName>',
        "",
        workbook_xml,
        flags=re.DOTALL,
    )
    print_area_xml = (
        '<definedName name="_xlnm.Print_Area" localSheetId="0">'
        f'Blad1!$A$1:$E${print_last_row}</definedName>'
    )
    if "</definedNames>" not in workbook_xml:
        raise ValueError("De vaste deelnemerslijst-template mist de Excel-naamdefinities.")
    workbook_xml = workbook_xml.replace("</definedNames>", print_area_xml + "</definedNames>", 1)

    entries[sheet_path] = sheet_xml.encode("utf-8")
    entries[workbook_path] = workbook_xml.encode("utf-8")
    entries[table_path] = table_xml.encode("utf-8")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w") as destination:
        for info in infos:
            destination.writestr(info, entries[info.filename])
    return {
        "participants": len(sorted_records),
        "last_data_row": last_data_row,
        "print_last_row": print_last_row,
        "print_area": f"A1:E{print_last_row}",
    }

def export_workbook(records, output_path: str | Path, reference_records=None):
    workbook = Workbook()
    workbook.remove(workbook.active)
    sorted_records = sorted(
        records,
        key=lambda row: (
            normalize(row.get("Achternaam")), normalize(row.get("Tussenvoegsel")),
            normalize(row.get("Voornaam")),
        ),
    )
    yes_no = lambda value: "Ja" if value else "Nee"
    lookup = registration_lookup(sorted_records if reference_records is None else reference_records)

    present = workbook.create_sheet("Deelnemerslijst")
    present.append([
        "Achternaam", "Tussenvoegsel", "Voornaam", "Geboortedatum",
        "Geboorteplaats", "Evenement", "Type bezoeker", "Introducé van",
    ])
    for row in sorted_records:
        present.append([
            row.get("Achternaam", ""), row.get("Tussenvoegsel", ""),
            row.get("Voornaam", ""), row.get("Geboortedatum", ""),
            row.get("Geboorteplaats", ""), row.get("Evenement", ""),
            visitor_type(row), primary_visitor_name(row, lookup),
        ])
    _style_sheet(present, [22, 16, 18, 16, 21, 30, 20, 28])

    raw = workbook.create_sheet("Ruwe aanmeldingen")
    raw.append(["Evenement", "Identifier", "Gast van", "Voornaam", "Tussenvoegsel", "Achternaam", "E-mail", "Telefoonnummer", "Geboortedatum", "Geboorteplaats", "Geslacht", "Opleiding", "Opleidingsrichting", "Type", "Aanwezigheid", "Gebruik"])
    for row in sorted_records:
        raw.append([row.get(field, "") for field in STRING_FIELDS])
    for cell in raw["H"]:
        cell.number_format = "@"
    _style_sheet(raw, [28, 18, 38, 18, 16, 22, 28, 18, 16, 21, 14, 22, 28, 16, 16, 16])

    callbacks = workbook.create_sheet("Nazorg")
    callbacks.append([
        "Evenement", "Voornaam", "Achternaam", "Telefoonnummer",
        "Opleidingsniveau", "Profiel", "Contactstatus", "Laatste contact",
        "Opnieuw contact op", "WhatsApp-status", "WhatsApp geopend",
        "WhatsApp verzonden", "Opmerkingen",
    ])
    for row in sorted_records:
        if is_introducee(row):
            continue
        last_name = " ".join(filter(None, [row.get("Tussenvoegsel", ""), row.get("Achternaam", "")]))
        callbacks.append([
            row.get("Evenement", ""), row.get("Voornaam", ""), last_name,
            row.get("Telefoonnummer", ""), row.get("Opleiding", ""),
            row.get("Profiel", ""), callback_status(row),
            row.get("LaatsteContact", ""), row.get("TerugbellenOp", ""),
            row.get("WhatsAppStatus", "Nog te sturen"), row.get("WhatsAppGeopendOp", ""),
            row.get("WhatsAppVerzondenOp", ""),
            row.get("Opmerkingen", ""),
        ])
    for cell in callbacks["D"]:
        cell.number_format = "@"
    _style_sheet(callbacks, [30, 18, 24, 18, 22, 30, 23, 18, 18, 20, 20, 20, 45], (13,))

    access = workbook.create_sheet("Presentie")
    access.append(["Voornaam", "Tussenvoegsel", "Achternaam", "Geboortedatum", "Geboorteplaats", "Aanwezig"])
    for row in sorted_records:
        stand = next((status for status in attendance_map(row).values() if status != ONBEKEND), ONBEKEND)
        access.append([row.get("Voornaam", ""), row.get("Tussenvoegsel", ""), row.get("Achternaam", ""), row.get("Geboortedatum", ""), row.get("Geboorteplaats", ""), ATTENDANCE_LABELS[stand]])
    _style_sheet(access, [19, 16, 24, 17, 23, 14])

    workbook.save(output_path)

def _titel(sheet, regel: int, tekst: str, grootte: int = 13):
    cel = sheet.cell(regel, 1, tekst)
    cel.font = Font(name="Segoe UI", size=grootte, bold=True)
    return cel

def _koprij(sheet, regel: int, koppen, breedtes):
    for offset, kop in enumerate(koppen):
        cel = sheet.cell(regel, 1 + offset, kop)
        cel.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
        cel.fill = KOP_VULLING
        cel.alignment = Alignment(vertical="center", horizontal="left" if offset == 0 else "right",
                                  wrap_text=True)
    for offset, breedte in enumerate(breedtes):
        sheet.column_dimensions[get_column_letter(1 + offset)].width = breedte
    sheet.row_dimensions[regel].height = 26

def _write_summary_sheet(workbook, summary: dict) -> None:
    """Het voorblad: waar gaat dit over en wat is de uitkomst.

    Stond hier eerst een zin zonder een enkel getal; juist het blad dat de kop
    van de zaak moet geven, gaf geen kop van de zaak.
    """
    sheet = workbook.create_sheet("Overzicht")
    sheet.sheet_view.showGridLines = False
    _titel(sheet, 1, str(summary.get("evenement", "") or "Statistieken"))
    ondertitel = " · ".join(str(deel) for deel in (summary.get("datum", ""), summary.get("locatie", "")) if deel)
    if ondertitel:
        cel = sheet.cell(2, 1, ondertitel)
        cel.font = Font(name="Segoe UI", size=10, color="5B6577")

    _koprij(sheet, 4, ["", "Aantal", "Aandeel"], [30, 12, 12])
    aangemeld = int(summary.get("aangemeld", 0))
    regels = [
        ("Aangemeld", summary.get("aangemeld", 0), None),
        ("Aanwezig geweest", summary.get("aanwezig", 0), aangemeld),
        ("Afwezig", summary.get("afwezig", 0), aangemeld),
        ("Afgemeld", summary.get("afgemeld", 0), None),
        ("Nog onbekend", summary.get("onbekend", 0), None),
    ]
    regel = 5
    for label, aantal, noemer in regels:
        sheet.cell(regel, 1, label).font = Font(name="Segoe UI", size=10)
        getal = sheet.cell(regel, 2, int(aantal or 0))
        getal.font = Font(name="Segoe UI", size=10)
        getal.alignment = Alignment(horizontal="right")
        if noemer:
            aandeel = sheet.cell(regel, 3, (int(aantal or 0) / noemer) if noemer else 0)
            aandeel.number_format = "0%"
            aandeel.alignment = Alignment(horizontal="right")
        regel += 1

    regel += 1
    _titel(sheet, regel, "Opkomst", grootte=11)
    uitkomst = sheet.cell(regel, 2, (int(summary.get("aanwezig", 0)) / aangemeld) if aangemeld else 0)
    uitkomst.number_format = "0%"
    uitkomst.font = Font(name="Segoe UI", size=11, bold=True)
    uitkomst.alignment = Alignment(horizontal="right")
    sheet.cell(regel + 1, 1, "Aanwezige deelnemers als aandeel van alle aanmeldingen.").font = Font(
        name="Segoe UI", size=9, color="5B6577")

    regel += 3
    for opmerking in summary.get("opmerkingen", []) or []:
        sheet.cell(regel, 1, str(opmerking)).font = Font(name="Segoe UI", size=9, color="5B6577")
        regel += 1

def export_statistics_workbook(dimensions, output_path: str | Path,
                               summary: dict | None = None, crosstab: dict | None = None):
    """Schrijf de statistieken naar een .xlsx die je van links naar rechts leest.

    ``dimensions`` is een lijst van (titel, rijen), waarbij elke rij
    ``(categorie, aangemeld, aanwezig, niet_gekomen, afgemeld)`` is.

    Eerder stonden alle deelnemers, de aanwezigen en de no-shows als drie
    blokken naast elkaar, elk apart gesorteerd. Op dezelfde regel stonden dan
    drie verschillende categorieen, zodat je niet kon aflezen hoeveel van een
    groep was komen opdagen: je moest de naam in het volgende blok opzoeken.
    Nu staat elke categorie een keer, met de uitsplitsing als kolommen.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)

    if summary:
        _write_summary_sheet(workbook, summary)

    koppen = ["Categorie", "Aangemeld", "Aanwezig", "Afwezig", "Afgemeld", "Onbekend", "Opkomst"]
    breedtes = [34, 12, 11, 14, 11, 12, 11]
    for titel, rijen in dimensions or []:
        naam = re.sub(r"[\[\]\*\?/\\:]", " ", str(titel))[:31] or "Statistiek"
        sheet = workbook.create_sheet(naam)
        sheet.sheet_view.showGridLines = False
        _titel(sheet, 1, str(titel))
        _koprij(sheet, 3, koppen, breedtes)

        eerste = 4
        for index, rij in enumerate(rijen or []):
            categorie, aangemeld, aanwezig, afwezig, afgemeld, onbekend = (list(rij) + [0, 0, 0, 0, 0])[:6]
            regel = eerste + index
            sheet.cell(regel, 1, str(categorie)).font = Font(name="Segoe UI", size=10)
            for offset, waarde in enumerate((aangemeld, aanwezig, afwezig, afgemeld, onbekend), start=2):
                cel = sheet.cell(regel, offset, int(waarde or 0))
                cel.font = Font(name="Segoe UI", size=10)
                cel.alignment = Alignment(horizontal="right")
            totaal_aangemeld = int(aangemeld or 0)
            opkomst = sheet.cell(regel, 7)
            opkomst.alignment = Alignment(horizontal="right")
            if totaal_aangemeld:
                # De vraag waarvoor je de tabel opent: van deze groep, hoeveel kwam er?
                opkomst.value = int(aanwezig or 0) / totaal_aangemeld
                opkomst.number_format = "0%"
            opkomst.font = Font(name="Segoe UI", size=10)

        laatste = eerste + len(rijen or []) - 1
        if not rijen:
            sheet.cell(eerste, 1, "Geen gegevens").font = Font(name="Segoe UI", size=10)
            continue

        totaal = laatste + 1
        sheet.cell(totaal, 1, "Totaal").font = Font(name="Segoe UI", size=10, bold=True)
        for kolom in range(2, 7):
            cel = sheet.cell(totaal, kolom, f"=SUM({get_column_letter(kolom)}{eerste}:{get_column_letter(kolom)}{laatste})")
            cel.font = Font(name="Segoe UI", size=10, bold=True)
            cel.alignment = Alignment(horizontal="right")
        slot = sheet.cell(totaal, 7, f"=IF(B{totaal}=0,\"\",C{totaal}/B{totaal})")
        slot.number_format = "0%"
        slot.font = Font(name="Segoe UI", size=10, bold=True)
        slot.alignment = Alignment(horizontal="right")
        sheet.freeze_panes = f"A{eerste}"

        # Een horizontale grafiek houdt ook lange profielnamen volledig leesbaar.
        # De hoogte groeit mee, zodat Excel geen labels of dunne balken wegdrukt.
        chart = BarChart()
        chart.type = "bar"
        chart.grouping = "clustered"
        chart.overlap = 0
        # De bladnaam en legenda vertellen al wat de assen en kleuren betekenen.
        # Extra as-titels en een lange grafiektitel gingen in compacte grafieken
        # door de categorieën en legenda heen lopen.
        chart.title = str(titel)
        chart.title.overlay = False
        chart.height = max(9, min(26, 4 + len(rijen or []) * 0.75))
        chart.width = 22
        # Zonder deze twee legt Excel de legenda over het tekenvlak heen, dwars
        # door de balken.
        chart.legend.position = "b"
        chart.legend.overlay = False
        for axis, positie in ((chart.x_axis, "l"), (chart.y_axis, "b")):
            axis.delete = False
            axis.axPos = positie
            axis.majorTickMark = "out"
            axis.minorTickMark = "none"
            axis.tickLblPos = "nextTo"
        # De waarde-as telt personen. Excel kiest bij kleine aantallen anders
        # tussenstappen als 2,5; halve deelnemers bestaan niet.
        chart.y_axis.majorUnit = 1
        chart.y_axis.numFmt = "0"
        # Alleen de verticale tekenrichting omkeren: zo staat de eerste reeks
        # bovenaan, zonder de waarde-as en labels te verplaatsen.
        chart.x_axis.scaling.orientation = "maxMin"
        chart.x_axis.tickLblSkip = 1
        # Houd de gevraagde volgorde aan, ook al staan de bronkolommen voor de
        # tabel anders: Aanwezig (C), Afgemeld (E), Afwezig (D).
        reeksen = (
            (3, "2E7D32"),  # Aanwezig — groen
            (5, "F28C28"),  # Afgemeld — oranje
            (4, "C62828"),  # Afwezig — rood
        )
        for kolom, kleur in reeksen:
            chart.add_data(
                Reference(sheet, min_col=kolom, max_col=kolom, min_row=3, max_row=laatste),
                titles_from_data=True,
            )
            serie = chart.series[-1]
            serie.graphicalProperties.solidFill = kleur
            serie.graphicalProperties.line.solidFill = kleur
        chart.set_categories(Reference(sheet, min_col=1, min_row=eerste, max_row=laatste))
        sheet.add_chart(chart, f"A{totaal + 2}")

    if crosstab and crosstab.get("rows"):
        _write_crosstab_sheet(workbook, crosstab, KOP_VULLING)

    if not workbook.sheetnames:
        workbook.create_sheet("Statistiek")

    workbook.save(output_path)

def _heatmap_fill(fraction: float) -> PatternFill:
    """Van bijna wit naar vol paars, in dezelfde kleuren als op het scherm."""
    leeg = (244, 240, 248)
    vol = (108, 44, 255)
    share = 0.18 + 0.82 * max(0.0, min(1.0, fraction))
    kleur = "".join(f"{int(a + (b - a) * share):02X}" for a, b in zip(leeg, vol))
    return PatternFill("solid", fgColor=kleur)

def _write_crosstab_sheet(workbook, crosstab: dict, header_fill) -> None:
    """Zet opleidingsniveau tegen profiel in een aparte kruistabel.

    De losse verdelingen laten zien hoeveel MBO'ers er waren en hoeveel
    technische profielen, maar niet welke profielen bij welk niveau horen.
    Daar is deze tabel voor.

    Het raster is in de praktijk voor het overgrote deel leeg. Een cel zonder
    deelnemers blijft daarom leeg in plaats van een nul te tonen, en de kleur
    zegt hoe groot het aantal is. Onder de aantallen staat hetzelfde raster als
    aandeel binnen het niveau, want daar gaat de vraag meestal over.
    """
    sheet = workbook.create_sheet("Niveau x profiel")
    sheet.sheet_view.showGridLines = False
    rows = crosstab["rows"]
    columns = crosstab["columns"]
    counts = crosstab["counts"]
    row_totals = crosstab["row_totals"]

    kop = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
    vet = Font(name="Segoe UI", size=10, bold=True)
    midden = Alignment(horizontal="center", vertical="center")
    maximum = max(counts.values(), default=0) or 1

    def schrijf_koppen(regel: int, titel: str, laatste_kop: str = "Totaal"):
        for offset, label in enumerate([titel, *columns, laatste_kop]):
            cell = sheet.cell(regel, 1 + offset, label)
            cell.font = kop
            cell.fill = header_fill
            cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        sheet.row_dimensions[regel].height = 32

    sheet.cell(1, 1, "Opleidingsniveau x profiel").font = Font(name="Segoe UI", size=13, bold=True)
    sheet.column_dimensions["A"].width = 22
    for offset in range(len(columns) + 1):
        sheet.column_dimensions[get_column_letter(2 + offset)].width = 13

    schrijf_koppen(3, "Aantallen")
    for row_index, level in enumerate(rows, start=4):
        sheet.cell(row_index, 1, level).font = vet
        for column_index, profile in enumerate(columns, start=2):
            value = counts.get((level, profile), 0)
            cell = sheet.cell(row_index, column_index)
            cell.alignment = midden
            if value:
                cell.value = value
                cell.fill = _heatmap_fill(value / maximum)
        total = sheet.cell(row_index, len(columns) + 2, row_totals.get(level, 0))
        total.font = vet
        total.alignment = midden

    total_row = len(rows) + 4
    sheet.cell(total_row, 1, "Totaal").font = vet
    for column_index, profile in enumerate(columns, start=2):
        cell = sheet.cell(total_row, column_index, crosstab["column_totals"].get(profile, 0))
        cell.font = vet
        cell.alignment = midden
    laatste = sheet.cell(total_row, len(columns) + 2, crosstab.get("total", 0))
    laatste.font = vet
    laatste.alignment = midden

    # Hetzelfde raster als aandeel binnen het niveau. Absolute aantallen
    # verbergen dat een klein niveau heel eenzijdig kan zijn.
    aandeel_kop = total_row + 2
    schrijf_koppen(aandeel_kop, "Aandeel per niveau", "Aantal")
    for row_index, level in enumerate(rows, start=aandeel_kop + 1):
        sheet.cell(row_index, 1, level).font = vet
        total = row_totals.get(level, 0)
        for column_index, profile in enumerate(columns, start=2):
            value = counts.get((level, profile), 0)
            cell = sheet.cell(row_index, column_index)
            cell.alignment = midden
            if value and total:
                cell.value = value / total
                cell.number_format = "0%"
                cell.fill = _heatmap_fill(value / total)
        # Een rijverdeling telt per definitie altijd op tot 100%. Dat steeds
        # herhalen zegt niets; het aantal deelnemers geeft wel nuttige context.
        sluit = sheet.cell(row_index, len(columns) + 2, total)
        sluit.font = vet
        sluit.alignment = midden

    # Subtiele lijnen maken het brede raster met veel witte, lege cellen
    # navolgbaar zonder de rustige heatmapopmaak te overheersen.
    dunne_lijn = Side(style="thin", color="D9DCE3")
    rasterrand = Border(
        left=dunne_lijn, right=dunne_lijn, top=dunne_lijn, bottom=dunne_lijn
    )
    for begin, einde in (
        (3, total_row),
        (aandeel_kop, aandeel_kop + len(rows)),
    ):
        for rij in sheet.iter_rows(
            min_row=begin, max_row=einde, min_col=1, max_col=len(columns) + 2
        ):
            for cell in rij:
                cell.border = rasterrand

    note_row = aandeel_kop + len(rows) + 2

    # Welke profielen zijn samengenomen tot Overig, zodat de lezer weet dat er
    # niets is weggelaten.
    bundled = crosstab.get("gebundeld") or []
    if bundled:
        sheet.cell(note_row, 1, "Gebundeld onder Overig").font = vet
        sheet.cell(note_row, 2, ", ".join(bundled))
        note_row += 2

    # Welke schrijfwijzen zijn samengevoegd, zodat zichtbaar blijft dat de
    # weergave iets met de aangeleverde waarden doet.
    merged = crosstab.get("merged") or {}
    if merged:
        sheet.cell(note_row, 1, "Samengevoegde schrijfwijzen").font = vet
        for offset, (level, spellings) in enumerate(sorted(merged.items()), start=1):
            sheet.cell(note_row + offset, 1, level)
            sheet.cell(note_row + offset, 2, ", ".join(spellings))
