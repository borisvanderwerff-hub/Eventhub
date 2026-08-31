from __future__ import annotations

from copy import copy
from datetime import date, datetime
from pathlib import Path
import re
import unicodedata
import zipfile
from xml.sax.saxutils import escape as xml_escape

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.datetime import from_excel
import xlrd


STRING_FIELDS = [
    "Evenement", "Identifier", "GastVan", "Voornaam", "Tussenvoegsel", "Achternaam",
    "Email", "Telefoonnummer", "Geboortedatum", "Geboorteplaats", "Geslacht",
    "Opleiding", "Profiel", "Type", "Aanwezigheid", "Gebruik",
]

CALLBACK_STATUSES = [
    "Nog bellen",
    "Geen gehoor",
    "Voicemail",
    "Gesproken",
    "Terugbellen op verzoek",
    "WhatsApp verzonden",
    "Afgerond",
    "Niet meer benaderen",
]
CALLBACK_DONE_STATUSES = {"Gesproken", "WhatsApp verzonden", "Afgerond", "Niet meer benaderen"}

FIELD_ALIASES = {
    "Evenement": [
        "Evenement", "Event", "Naam evenement", "Evenementnaam", "Eventnaam",
        "Titel evenement", "Evenement titel", "Event title", "Eventtitel",
        "Naam event", "Activiteit", "Activiteitsnaam", "Bijeenkomst",
    ],
    "Identifier": ["Identifier", "ID", "Kandidaatnummer", "Registratienummer", "Registratie ID", "Registratie-ID"],
    "GastVan": ["Gast van", "Gastvan", "Guest of", "Introducé van", "Introducee van"],
    "Voornaam": ["Voornaam", "First name", "Firstname"],
    "Tussenvoegsel": ["Tussenvoegsel", "Prefix"],
    "Achternaam": ["Achternaam", "Last name", "Lastname"],
    "Email": ["E-mail", "Email", "E-mailadres"],
    "Telefoonnummer": ["Telefoonnummer", "Telefoon", "Mobiel", "Mobiele nummer", "Phone"],
    "Geboortedatum": ["Geboortedatum", "Date of birth", "Birth date"],
    "Geboorteplaats": [
        "Geboorteplaats", "Geboorte plaats", "Plaats van geboorte",
        "Plaats geboorte", "Geboortestad", "Geb. plaats", "Geb plaats",
        "Geboorteplaats volgens identiteitsbewijs", "Geboorteplaats ID",
        "Place of birth", "Birth place", "Birthplace", "Birth city",
        "City of birth", "Birth location",
    ],
    "Geslacht": ["Geslacht", "Gender"],
    "Opleiding": ["Opleiding", "Opleidingsniveau", "Niveau", "Education level"],
    "Profiel": [
        "Opleidingsrichting", "Profiel", "Studierichting",
        "Opleidingsprofiel", "Richting", "Study profile",
    ],
    "Type": ["Type"],
    "Aanwezigheid": [
        "Aanwezigheid", "Aanwezig", "Present", "Presence", "Attendance",
        "Opgekomen", "Show", "No show", "Noshow",
    ],
    "Gebruik": ["Gebruik"],
}

PRESENT_VALUES = {
    "ja", "yes", "y", "aanwezig", "present", "1", "true", "waar", "opgekomen", "gekomen", "show",
}
ABSENT_VALUES = {
    "nee", "no", "n", "afwezig", "absent", "0", "false", "onwaar",
    "noshow", "no-show", "nietopgekomen", "nietgekomen",
}


def infer_presence_from_text(value) -> bool | None:
    key = normalize(value)
    if not key:
        return None
    key = key.replace("-", "")
    if key in PRESENT_VALUES:
        return True
    if key in ABSENT_VALUES:
        return False
    return None


def is_introducee(record: dict) -> bool:
    return bool(text(record.get("GastVan", "")))


def callback_status(record: dict) -> str:
    status = text(record.get("Terugbelstatus", ""))
    if status in CALLBACK_STATUSES:
        return status
    return "Afgerond" if bool(record.get("Teruggebeld", False)) else "Nog bellen"


def callback_is_done(record: dict) -> bool:
    return callback_status(record) in CALLBACK_DONE_STATUSES


def record_events(record: dict) -> list[str]:
    return [value.strip() for value in text(record.get("Evenement", "")).split(";") if value.strip()]


def attendance_map(record: dict) -> dict:
    """Aanwezigheid per evenement, met migratie van het oude formaat.

    Tot bestandsversie 10 was ``Aanwezig`` één boolean voor de hele persoon.
    Bij een bezoeker die aan meerdere evenementen hangt overschreef elke
    livesessie daardoor de registratie van het vorige evenement. Vanaf
    versie 11 is het een dict per evenementnaam.

    Een oude boolean geldt bij het lezen voor alle gekoppelde evenementen:
    bij het gebruikelijke ene evenement is dat exact, bij meerdere is het de
    enige aanname die geen aanwezigheid verzint die er nooit was.
    """
    value = record.get("Aanwezig", False)
    if isinstance(value, dict):
        return {str(name): bool(present) for name, present in value.items()}
    return {name: bool(value) for name in record_events(record)}


def is_present(record: dict, event_name: str = "") -> bool:
    """Aanwezigheid bij één evenement, of bij welk evenement dan ook."""
    presence = attendance_map(record)
    if not event_name:
        return any(presence.values())
    wanted = normalize(event_name)
    return any(present for name, present in presence.items() if normalize(name) == wanted)


def is_present_in_scope(record: dict, scope_events) -> bool:
    """Aanwezigheid binnen de evenementen die nu in beeld zijn."""
    if not scope_events:
        return is_present(record)
    return any(is_present(record, name) for name in scope_events)


def set_present(record: dict, event_name: str, present: bool) -> bool:
    """Leg aanwezigheid vast voor één evenement. Geeft terug of er iets wijzigde."""
    event_name = str(event_name or "").strip()
    presence = attendance_map(record)
    if not event_name:
        record["Aanwezig"] = presence
        return False
    wanted = normalize(event_name)
    key = next((name for name in presence if normalize(name) == wanted), event_name)
    changed = bool(presence.get(key, False)) != bool(present)
    presence[key] = bool(present)
    record["Aanwezig"] = presence
    return changed


def rename_attendance_event(record: dict, old_name: str, new_name: str) -> None:
    """Houd de aanwezigheidsregistratie mee bij het hernoemen van een evenement."""
    presence = attendance_map(record)
    wanted = normalize(old_name)
    moved = {}
    for name, value in presence.items():
        moved[new_name if normalize(name) == wanted else name] = value
    record["Aanwezig"] = moved


def detach_event_from_records(records: list[dict], event_name: str) -> list[dict]:
    """Remove one event association while preserving multi-event visitors."""
    wanted = normalize(event_name)
    retained = []
    for record in records:
        linked_names = record_events(record)
        if not any(normalize(name) == wanted for name in linked_names):
            retained.append(record)
            continue
        remaining_names = [name for name in linked_names if normalize(name) != wanted]
        if remaining_names:
            record["Evenement"] = "; ".join(remaining_names)
            # Laat de aanwezigheid van het losgekoppelde evenement niet achter.
            record["Aanwezig"] = {
                name: value for name, value in attendance_map(record).items()
                if normalize(name) != wanted
            }
            retained.append(record)
    return retained


def matches_event_filter(record: dict, selected_events) -> bool:
    if not selected_events:
        return True
    return bool(set(record_events(record)) & set(selected_events))


def visitor_type(record: dict) -> str:
    return "Introducé" if is_introducee(record) else "Reguliere bezoeker"


def registration_lookup(records) -> dict[str, dict]:
    return {
        normalize(record.get("Identifier", "")): record
        for record in records
        if normalize(record.get("Identifier", ""))
    }


def primary_visitor_name(record: dict, lookup: dict[str, dict]) -> str:
    if not is_introducee(record):
        return ""
    primary = lookup.get(normalize(record.get("GastVan", "")))
    if not primary:
        return "Onbekende hoofdbezoeker"
    return " ".join(filter(None, [
        text(primary.get("Voornaam")),
        text(primary.get("Tussenvoegsel")),
        text(primary.get("Achternaam")),
    ]))


def normalize(value) -> str:
    value = unicodedata.normalize("NFD", str(value or "").strip().lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]", "", value)


def text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def date_text(value) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, date):
        return value.strftime("%d-%m-%Y")
    if isinstance(value, (int, float)):
        try:
            return from_excel(value).strftime("%d-%m-%Y")
        except (ValueError, OverflowError, TypeError):
            pass
    return text(value)


def initials_text(value) -> str:
    """Maak nette voorletters van een volledige voornaam."""
    parts = re.findall(r"[^\W\d_]+", text(value), flags=re.UNICODE)
    return "".join(f"{part[0].upper()}." for part in parts if part)


def participant_template_context(event: dict | None, profile: dict | None = None) -> dict[str, str]:
    event = event or {}
    profile = profile or {}
    fivewh = event.get("fivewh", {}) if isinstance(event.get("fivewh"), dict) else {}
    start = text(fivewh.get("event_time", ""))
    departure = text(fivewh.get("teardown_time", ""))
    if start and departure:
        times = f"{start} / vertrek {departure}"
    else:
        times = start or departure
    return {
        "event_name": text(event.get("name", "")),
        "event_date": date_text(event.get("date", "")),
        "event_times": times,
        "event_location": " — ".join(filter(None, [
            text(event.get("place", "")), text(event.get("location", "")),
        ])),
        "contact_name": text(event.get("external_contact", "")) or text(profile.get("name", "")),
        "contact_phone": text(event.get("external_contact_reachability", "")) or text(profile.get("phone", "")),
    }


def phone_text(value) -> str:
    result = text(value)
    if result.endswith(".0") and result[:-2].isdigit():
        result = result[:-2]
    if len(result) == 9 and result.isdigit() and not result.startswith("0"):
        result = f"0{result}"
    return result


def duplicate_key(record: dict) -> str:
    if record.get("Identifier"):
        return f"id:{normalize(record['Identifier'])}"
    if record.get("Email"):
        return f"mail:{normalize(record['Email'])}"
    digits = re.sub(r"\D", "", record.get("Telefoonnummer", ""))
    if len(digits) >= 8:
        return f"tel:{digits}"
    return "naam:" + normalize("|".join([
        record.get("Voornaam", ""), record.get("Tussenvoegsel", ""),
        record.get("Achternaam", ""), record.get("Geboortedatum", ""),
    ]))


HEADER_PATTERNS = {
    "Evenement": ("evenement", "eventnaam", "eventtitel", "eventtitle", "naamevent", "activiteitsnaam"),
    "Geboorteplaats": (
        "geboorteplaats", "plaatsvangeboorte", "plaatsgeboorte", "geboortestad",
        "gebplaats", "placeofbirth", "birthplace", "birthcity", "cityofbirth", "birthlocation",
    ),
}


def _first_column(value) -> int:
    if isinstance(value, list):
        return value[0] if value else -1
    return int(value)


def build_map(headers: dict[str, list[int] | int]) -> dict[str, int]:
    result = {}
    for field, aliases in FIELD_ALIASES.items():
        result[field] = -1
        for alias in aliases:
            key = normalize(alias)
            if key in headers:
                result[field] = _first_column(headers[key])
                break
        if result[field] < 0:
            patterns = HEADER_PATTERNS.get(field, ())
            for header, columns in headers.items():
                if any(pattern in header for pattern in patterns):
                    result[field] = _first_column(columns)
                    break
    return result


def _looks_like_date_value(value) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    if isinstance(value, (int, float)):
        return 1 <= value <= 100000
    value = text(value)
    if not value:
        return False
    patterns = (
        r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$",
        r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$",
    )
    return any(re.match(pattern, value) for pattern in patterns)


def _duplicate_birthplace_column(headers, rows, header_row_index, mapping) -> int:
    if mapping.get("Geboorteplaats", -1) >= 0:
        return -1
    birthdate_columns = []
    for alias in FIELD_ALIASES["Geboortedatum"]:
        columns = headers.get(normalize(alias), [])
        if not isinstance(columns, list):
            columns = [columns]
        birthdate_columns.extend(columns)
    birthdate_columns = sorted(set(birthdate_columns))
    if len(birthdate_columns) < 2:
        return -1

    first_birthdate = mapping.get("Geboortedatum", birthdate_columns[0])
    candidates = [column for column in birthdate_columns if column != first_birthdate]
    candidates.sort(key=lambda column: (column != first_birthdate + 1, column))
    for column in candidates:
        values = []
        for row in rows[header_row_index + 1:header_row_index + 41]:
            if column < len(row) and text(row[column]):
                values.append(row[column])
        if not values:
            return column
        date_values = sum(_looks_like_date_value(value) for value in values)
        if date_values / len(values) < 0.5:
            return column
    return -1


def _xlsx_sheets(file_path: Path):
    workbook = load_workbook(file_path, read_only=True, data_only=True, keep_vba=False)
    try:
        for worksheet in workbook.worksheets:
            rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
            yield worksheet.title, rows
    finally:
        workbook.close()


def _xls_sheets(file_path: Path):
    workbook = xlrd.open_workbook(file_path)
    for worksheet in workbook.sheets():
        rows = []
        for row_index in range(worksheet.nrows):
            row = []
            for column_index in range(worksheet.ncols):
                cell = worksheet.cell(row_index, column_index)
                value = cell.value
                if cell.ctype == xlrd.XL_CELL_DATE:
                    value = datetime(*xlrd.xldate_as_tuple(value, workbook.datemode))
                row.append(value)
            rows.append(row)
        yield worksheet.name, rows


def read_registration_file(file_path: str | Path):
    file_path = Path(file_path)
    sheets = list(_xls_sheets(file_path) if file_path.suffix.lower() == ".xls" else _xlsx_sheets(file_path))
    best = None
    for sheet_index, (sheet_name, rows) in enumerate(sheets):
        for row_index, row in enumerate(rows[:25]):
            headers = {}
            for column_index, value in enumerate(row):
                key = normalize(value)
                if key:
                    headers.setdefault(key, []).append(column_index)
            mapping = build_map(headers)
            if mapping["Voornaam"] < 0 or mapping["Achternaam"] < 0:
                continue
            repaired_birthplace_column = _duplicate_birthplace_column(headers, rows, row_index, mapping)
            if repaired_birthplace_column >= 0:
                mapping["Geboorteplaats"] = repaired_birthplace_column
            score = sum(index >= 0 for index in mapping.values())
            if best is None or score > best["score"]:
                best = {
                    "sheet_index": sheet_index,
                    "sheet_name": sheet_name,
                    "row_index": row_index,
                    "rows": rows,
                    "mapping": mapping,
                    "score": score,
                    "repaired_birthplace_header": repaired_birthplace_column >= 0,
                }
    if best is None:
        raise ValueError("Geen werkblad met de kolommen Voornaam en Achternaam gevonden.")

    records = []
    fallback_events = 0
    missing_birth_places = 0
    presence_detected = 0
    fallback_event = file_path.stem
    mapping = best["mapping"]

    for source in best["rows"][best["row_index"] + 1:]:
        def get(field):
            column = mapping[field]
            return source[column] if 0 <= column < len(source) else ""

        first_name = text(get("Voornaam"))
        last_name = text(get("Achternaam"))
        if not first_name and not last_name:
            continue
        record = {field: text(get(field)) for field in STRING_FIELDS}
        record.update({
            "Voornaam": first_name,
            "Achternaam": last_name,
            "Geboortedatum": date_text(get("Geboortedatum")),
            "Telefoonnummer": phone_text(get("Telefoonnummer")),
            "Teruggebeld": False,
            "Terugbelstatus": "Nog bellen",
            "LaatsteContact": "",
            "TerugbellenOp": "",
            "Opmerkingen": "",
            "WhatsAppStatus": "Nog te sturen",
            "WhatsAppGeopendOp": "",
            "WhatsAppVerzondenOp": "",
            "Aanwezig": {},
        })
        if not record["Evenement"]:
            record["Evenement"] = fallback_event
            fallback_events += 1
        # Pas na het vaststellen van het evenement: aanwezigheid wordt per
        # evenement vastgelegd en heeft die naam dus nodig.
        detected_presence = infer_presence_from_text(record.get("Aanwezigheid", ""))
        if detected_presence is not None:
            for event_name in record_events(record):
                set_present(record, event_name, detected_presence)
            presence_detected += 1
        if not record["Geboorteplaats"]:
            missing_birth_places += 1
        records.append(record)

    return {
        "records": records,
        "report": {
            "file_name": file_path.name,
            "sheet_name": best["sheet_name"],
            "introducees": sum(is_introducee(record) for record in records),
            "fallback_events": fallback_events,
            "missing_birth_places": missing_birth_places,
            "presence_detected": presence_detected,
            "repaired_birthplace_header": best.get("repaired_birthplace_header", False),
        },
    }


def _enrich_record(target: dict, incoming: dict) -> bool:
    changed = False
    for field in STRING_FIELDS:
        current = text(target.get(field))
        new_value = text(incoming.get(field))
        if not new_value:
            continue
        if not current:
            target[field] = new_value
            changed = True
        elif field == "Evenement":
            current_events = {normalize(value) for value in current.split(";") if value.strip()}
            if normalize(new_value) not in current_events:
                target[field] = f"{current}; {new_value}"
                changed = True
    return changed


def import_registration_files(file_paths, existing_records=None):
    records = list(existing_records or [])
    keyed_records = {duplicate_key(record): record for record in records}
    added = []
    duplicates = 0
    enriched = 0
    reports = []
    errors = []
    for file_path in file_paths:
        try:
            result = read_registration_file(file_path)
            reports.append(result["report"])
            for record in result["records"]:
                key = duplicate_key(record)
                if key in keyed_records:
                    duplicates += 1
                    if _enrich_record(keyed_records[key], record):
                        enriched += 1
                    continue
                keyed_records[key] = record
                added.append(record)
        except Exception as exc:
            errors.append(f"{Path(file_path).name}: {exc}")
    return {
        "records": added,
        "duplicates": duplicates,
        "enriched": enriched,
        "reports": reports,
        "errors": errors,
    }


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
        access.append([row.get("Voornaam", ""), row.get("Tussenvoegsel", ""), row.get("Achternaam", ""), row.get("Geboortedatum", ""), row.get("Geboorteplaats", ""), yes_no(is_present(row))])
    _style_sheet(access, [19, 16, 24, 17, 23, 14])

    workbook.save(output_path)


def export_statistics_workbook(dimension_sections, output_path: str | Path, scope_description: str = ""):
    """Write statistics breakdowns with readable bar charts to an .xlsx file.

    dimension_sections: list of (dimension_title, groups) where groups is a list of
    (group_label, [(category_label, count), ...]) — up to 3 groups per dimension are
    placed side by side (e.g. Alle deelnemers / Aanwezig geweest / No-shows).
    """
    workbook = Workbook()
    workbook.remove(workbook.active)

    if scope_description:
        overview = workbook.create_sheet("Overzicht")
        overview.append(["Statistieken export"])
        overview.append([scope_description])
        overview["A1"].font = Font(name="Segoe UI", size=13, bold=True)
        overview["A2"].font = Font(name="Segoe UI", size=10)
        overview["A2"].alignment = Alignment(wrap_text=True)
        overview.column_dimensions["A"].width = 90
        overview.row_dimensions[2].height = 30

    header_fill = PatternFill("solid", fgColor="071A33")
    block_start_columns = [1, 5, 9]
    chart_anchor_row = 22

    for dimension_title, groups in dimension_sections:
        sheet_name = re.sub(r"[\[\]\*\?/\\:]", " ", dimension_title)[:31] or "Statistiek"
        sheet = workbook.create_sheet(sheet_name)
        sheet.sheet_view.showGridLines = False

        for group_index, (group_label, data) in enumerate(groups[:len(block_start_columns)]):
            start_col = block_start_columns[group_index]
            col_letter = get_column_letter(start_col)
            sheet.column_dimensions[col_letter].width = 26
            sheet.column_dimensions[get_column_letter(start_col + 1)].width = 12
            sheet.column_dimensions[get_column_letter(start_col + 2)].width = 14

            title_cell = sheet.cell(1, start_col, group_label)
            title_cell.font = Font(name="Segoe UI", size=11, bold=True)

            headers = ["Categorie", "Aantal", "Percentage"]
            for offset, header in enumerate(headers):
                cell = sheet.cell(2, start_col + offset, header)
                cell.font = Font(name="Segoe UI", size=10, bold=True, color="FFFFFF")
                cell.fill = header_fill

            total = sum(count for _, count in data)
            row = 3
            for label, count in data:
                sheet.cell(row, start_col, label)
                sheet.cell(row, start_col + 1, count)
                percentage_cell = sheet.cell(row, start_col + 2, (count / total) if total else 0)
                percentage_cell.number_format = "0.0%"
                row += 1

            if data:
                last_data_row = row - 1
                sheet.cell(row, start_col, "Totaal").font = Font(name="Segoe UI", size=10, bold=True)
                sheet.cell(row, start_col + 1, total).font = Font(name="Segoe UI", size=10, bold=True)
                total_percentage_cell = sheet.cell(row, start_col + 2, 1.0 if total else 0)
                total_percentage_cell.font = Font(name="Segoe UI", size=10, bold=True)
                total_percentage_cell.number_format = "0.0%"

                if total:
                    chart = BarChart()
                    chart.type = "col"
                    chart.title = f"{dimension_title} — {group_label}"
                    chart.y_axis.title = "Aantal"
                    chart.x_axis.title = dimension_title
                    chart.legend = None
                    chart.height = 8
                    chart.width = 12
                    # Zonder deze instellingen tekent Excel wel de balken maar
                    # geen aslabels: openpyxl laat tickLblPos leeg en zet de
                    # streepjes op none, en de categorie-as belandt links in
                    # plaats van onder de balken.
                    for axis, position in ((chart.x_axis, "b"), (chart.y_axis, "l")):
                        axis.delete = False
                        axis.axPos = position
                        axis.majorTickMark = "out"
                        axis.minorTickMark = "none"
                        axis.tickLblPos = "nextTo"
                    categories = Reference(sheet, min_col=start_col, min_row=3, max_row=last_data_row)
                    values = Reference(sheet, min_col=start_col + 1, min_row=2, max_row=last_data_row)
                    chart.add_data(values, titles_from_data=True)
                    chart.set_categories(categories)
                    sheet.add_chart(chart, f"{col_letter}{chart_anchor_row}")
            else:
                sheet.cell(row, start_col, "Geen gegevens")

    if not workbook.sheetnames:
        workbook.create_sheet("Statistiek")

    workbook.save(output_path)

