from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import os
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_NS = "http://www.w3.org/XML/1998/namespace"
W = f"{{{W_NS}}}"

ET.register_namespace("w", W_NS)
ET.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")


EVALUATION_TEXT_FIELDS = {
    "Text2": "date",
    "Text3": "event_name",
    "Text4": "region",
    "Text5": "place",
    "Text6": "location",
    "Text7": "external_contact",
    "Text8": "external_contact_reachability",
    "Text1": "description",
    "Text9": "target_audience",
    "Text37": "event_visitors_estimate",
    "Text36": "stand_visitors_estimate",
    "Text35": "job_interest_estimate",
    "Text10": "age_under_16",
    "Text11": "age_16_24",
    "Text12": "age_25_35",
    "Text13": "age_over_35",
    "Text33": "peak_details",
    "Text34": "previous_experience",
    "Text14": "resources_general",
    "Text31": "stand_width",
    "Text32": "stand_depth",
    "Text30": "stand_other",
    "Text28": "stand_location_suggestions",
    "Text29": "stand_surface_notes",
    "Text27": "material_missing",
    "Text26": "material_notes",
    "Text23": "promotion_missing",
    "Text24": "promotion_distributed",
    "Text25": "promotion_notes",
    "Text21": "recruitment_material_missing",
    "Text22": "personnel_missing",
    "Text19": "support_reason",
    "Text20": "support_suggestions",
    "Text38": "repeat_yes_reason",
    "Text17": "repeat_conditions",
    "Text18": "repeat_no_reason",
    "Text16": "additional_comments",
    "Text15": "filled_by",
}


def _write_modified_package(source: Path, output: Path, replacements: dict[str, bytes], skip: set[str] | None = None):
    output.parent.mkdir(parents=True, exist_ok=True)
    skip = skip or set()
    fd, temporary_name = tempfile.mkstemp(prefix="dcpl_doc_", suffix=output.suffix, dir=str(output.parent))
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with ZipFile(source, "r") as original, ZipFile(temporary, "w", ZIP_DEFLATED) as result:
            for item in original.infolist():
                if item.filename in skip:
                    continue
                payload = replacements.get(item.filename, original.read(item.filename))
                result.writestr(item, payload)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def _run_text(run: ET.Element, value: str):
    for child in list(run):
        if child.tag in {W + "t", W + "br", W + "tab"}:
            run.remove(child)
    parts = str(value or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for index, part in enumerate(parts):
        if index:
            ET.SubElement(run, W + "br")
        text_node = ET.SubElement(run, W + "t")
        if part[:1].isspace() or part[-1:].isspace():
            text_node.set(f"{{{XML_NS}}}space", "preserve")
        text_node.text = part


def _set_form_fields(document_root: ET.Element, text_values: dict[str, str], checkbox_values: list[bool]):
    checkbox_index = 0
    for paragraph in document_root.findall(".//" + W + "p"):
        children = list(paragraph)
        for start_index, child in enumerate(children):
            if child.tag != W + "r":
                continue
            begin = child.find(W + "fldChar")
            if begin is None or begin.get(W + "fldCharType") != "begin":
                continue
            ff_data = begin.find(W + "ffData")
            if ff_data is None:
                continue
            name_node = ff_data.find(W + "name")
            field_name = name_node.get(W + "val", "") if name_node is not None else ""
            checkbox = ff_data.find(W + "checkBox")
            if checkbox is not None:
                checked = checkbox.find(W + "checked")
                if checked is None:
                    checked = ET.SubElement(checkbox, W + "checked")
                value = checkbox_values[checkbox_index] if checkbox_index < len(checkbox_values) else False
                checked.set(W + "val", "1" if value else "0")
                checkbox_index += 1
                continue
            if ff_data.find(W + "textInput") is None:
                continue
            separate_index = None
            end_index = None
            for index in range(start_index + 1, len(children)):
                if children[index].tag != W + "r":
                    continue
                marker = children[index].find(W + "fldChar")
                if marker is None:
                    continue
                marker_type = marker.get(W + "fldCharType")
                if marker_type == "separate":
                    separate_index = index
                elif marker_type == "end":
                    end_index = index
                    break
            if separate_index is None or end_index is None:
                continue
            result_runs = [node for node in children[separate_index + 1:end_index] if node.tag == W + "r"]
            if result_runs:
                target = result_runs[0]
            else:
                target = ET.Element(W + "r")
                paragraph.insert(end_index, target)
            _run_text(target, text_values.get(field_name, ""))
            for extra in result_runs[1:]:
                _run_text(extra, "")


def _macro_free_content_types(payload: bytes) -> bytes:
    root = ET.fromstring(payload)
    for override in list(root):
        part_name = override.get("PartName", "")
        if (override.tag.endswith("Default") and override.get("Extension", "").lower() == "bin") or part_name == "/word/vbaProject.bin":
            root.remove(override)
        elif part_name == "/word/document.xml":
            override.set(
                "ContentType",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
            )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _macro_free_relationships(payload: bytes) -> bytes:
    root = ET.fromstring(payload)
    for relationship in list(root):
        if relationship.get("Target", "").endswith("vbaProject.bin"):
            root.remove(relationship)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def export_evaluation(template: str | Path, output: str | Path, event: dict, profile: dict, evaluation: dict):
    template = Path(template)
    output = Path(output)
    values = dict(evaluation or {})
    values.setdefault("date", event.get("date", ""))
    values.setdefault("event_name", event.get("name", ""))
    values.setdefault("region", event.get("region", ""))
    values.setdefault("place", event.get("place", ""))
    values.setdefault("location", event.get("location", ""))
    values.setdefault("external_contact", event.get("external_contact", ""))
    values.setdefault("external_contact_reachability", event.get("external_contact_reachability", ""))
    values.setdefault("description", event.get("description", ""))
    values.setdefault("target_audience", event.get("target_audience", ""))
    profile_line = " — ".join(filter(None, [profile.get("name", ""), profile.get("function", "")]))
    values.setdefault("filled_by", profile_line)
    text_values = {field: str(values.get(key, "") or "") for field, key in EVALUATION_TEXT_FIELDS.items()}
    if text_values.get("Text2"):
        text_values["Text2"] += " "
    checkboxes = [bool(value) for value in values.get("checkboxes", [])]
    if len(checkboxes) < 76:
        checkboxes.extend([False] * (76 - len(checkboxes)))

    with ZipFile(template, "r") as package:
        document_root = ET.fromstring(package.read("word/document.xml"))
        document_root.attrib.pop(
            "{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable", None
        )
        _set_form_fields(document_root, text_values, checkboxes)
        replacements = {
            "word/document.xml": ET.tostring(document_root, encoding="utf-8", xml_declaration=True),
        }
        skip = set()
        if template.suffix.lower() == ".docm":
            replacements["[Content_Types].xml"] = _macro_free_content_types(package.read("[Content_Types].xml"))
            replacements["word/_rels/document.xml.rels"] = _macro_free_relationships(
                package.read("word/_rels/document.xml.rels")
            )
            skip.add("word/vbaProject.bin")
    _write_modified_package(template, output, replacements, skip)
    return output


def _cell_text(cell: ET.Element, value: str):
    paragraph = cell.find(W + "p")
    if paragraph is None:
        paragraph = ET.SubElement(cell, W + "p")
    for child in list(paragraph):
        if child.tag == W + "r":
            paragraph.remove(child)
    run = ET.SubElement(paragraph, W + "r")
    _run_text(run, value)


def _fivewh_values(event: dict, profile: dict, data: dict) -> dict:
    values = dict(data or {})
    values.setdefault("event_name", event.get("name", ""))
    values.setdefault("date", event.get("date", ""))
    values.setdefault("event_address", "\n".join(filter(None, [event.get("location", ""), event.get("place", "")])) )
    values.setdefault("objective", event.get("description", ""))
    values.setdefault("target_audience", event.get("target_audience", ""))
    contact = " — ".join(filter(None, [profile.get("name", ""), profile.get("function", "")]))
    contact_details = " | ".join(filter(None, [profile.get("email", ""), profile.get("phone", "")]))
    values.setdefault("poc_questions", "\n".join(filter(None, [contact, contact_details])))
    return values


def export_fivewh(template: str | Path, output: str | Path, event: dict, profile: dict, fivewh: dict):
    template = Path(template)
    output = Path(output)
    values = _fivewh_values(event, profile, fivewh)
    with ZipFile(template, "r") as package:
        document_root = ET.fromstring(package.read("word/document.xml"))
        table = document_root.find(".//" + W + "tbl")
        if table is None:
            raise ValueError("Het 5WH-sjabloon bevat geen invultabel.")
        rows = table.findall(W + "tr")

        row_mapping = {
            1: "event_name",
            5: "date",
            6: "build_time",
            7: "briefing_time",
            8: "event_time",
            9: "debrief_time",
            10: "teardown_time",
            29: "poc_questions",
            30: "poc_location",
            32: "objective",
            33: "target_audience",
            35: "current_status",
            36: "defence_activities_map",
            37: "event_map",
            38: "support",
            39: "vacancies",
            40: "access",
            41: "attire",
            42: "catering",
            43: "route",
            44: "parking",
            45: "materials",
            46: "accommodation",
            47: "first_aid",
            48: "evaluation",
            49: "risks",
            50: "measures",
            51: "program",
        }
        for row_index, key in row_mapping.items():
            cells = rows[row_index].findall(W + "tc")
            if len(cells) >= 2:
                _cell_text(cells[-1], str(values.get(key, "") or ""))

        location_cells = rows[3].findall(W + "tc")
        if len(location_cells) >= 2:
            combined_locations = str(values.get("event_address", "") or "")
            briefing = str(values.get("briefing_address", "") or "")
            if briefing:
                combined_locations += "\n\n\n" + briefing
            _cell_text(location_cells[-1], combined_locations)

        roster = values.get("roster", [])
        if isinstance(roster, str):
            parsed = []
            for line in roster.splitlines():
                if not line.strip():
                    continue
                name, separator, task = line.partition("|")
                if not separator:
                    name, separator, task = line.partition("—")
                parsed.append({"name": name.strip(), "task": task.strip()})
            roster = parsed
        if not isinstance(roster, list):
            roster = []
        for offset, person in enumerate(roster[:15], start=13):
            cells = rows[offset].findall(W + "tc")
            if len(cells) >= 3:
                if isinstance(person, dict):
                    _cell_text(cells[1], str(person.get("name", "") or ""))
                    _cell_text(cells[2], str(person.get("task", "") or ""))

        replacements = {
            "word/document.xml": ET.tostring(document_root, encoding="utf-8", xml_declaration=True)
        }
    _write_modified_package(template, output, replacements)
    return output
