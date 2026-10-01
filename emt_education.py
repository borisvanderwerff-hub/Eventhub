"""Opleidingsniveaus uit vrije tekst herkennen.

Opleiding en Profiel komen als vrije tekst uit de aanmeldlijsten. Daardoor
staan MBO 4, mbo-4, MBO niveau 4 en Mbo niv. 4 als vier verschillende waarden
in de statistieken. Deze module brengt ze samen onder een vaste noemer.

Twee bewuste grenzen:

* Er wordt niets in de gegevens zelf gewijzigd. De herkenning geldt alleen
  voor de weergave, zodat de bron blijft zoals hij is aangeleverd.
* Wat niet herkend wordt, blijft ongewijzigd zichtbaar. Onbekende waarden
  wegmoffelen onder Overig zou juist verbergen dat de bron rommelig is.
"""
from __future__ import annotations

import re
import unicodedata

ONBEKEND = "Onbekend"


def _bare(value) -> str:
    """Kleine letters, zonder accenten, leestekens of dubbele spaties."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"[._/\+-]+", " ", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    # Aan elkaar geschreven niveaus losmaken: mbo4 leest als mbo 4.
    text = re.sub(r"(?<=[a-z])(?=[0-9])", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Woorden die niets toevoegen aan het niveau zelf.
_NOISE = re.compile(r"\b(niveau|niv|nv|leerweg|leerjaar|opleiding|diploma|jaar|klas)\b")

# De losse letters zijn de gangbare afkortingen: VMBO-B, -K, -G en -T.
_VMBO_TRACKS = [
    (r"\b(b|bb|basis(beroepsgerichte)?|basisberoeps)\b", "VMBO Basis"),
    (r"\b(k|kb|kader(beroepsgerichte)?|kaderberoeps)\b", "VMBO Kader"),
    (r"\b(g|gl|gemengd(e)?)\b", "VMBO Gemengd"),
    (r"\b(t|tl|theoretisch(e)?|mavo)\b", "VMBO TL"),
]


def education_level(value) -> str:
    """Breng een opleidingsaanduiding terug tot een vaste noemer.

    Onherkenbare waarden komen ongewijzigd terug, zodat ze in de statistieken
    opvallen in plaats van te verdwijnen.
    """
    raw = str(value or "").strip()
    if not raw:
        return ONBEKEND
    bare = _NOISE.sub(" ", _bare(raw))
    bare = re.sub(r"\s+", " ", bare).strip()
    if not bare:
        return ONBEKEND

    if re.search(r"\b(onbekend|geen|nvt|n v t|unknown)\b", bare):
        return ONBEKEND

    # Mavo staat los van het woord vmbo maar hoort bij dezelfde leerweg.
    if re.search(r"\bmavo\b", bare) and not re.search(r"\bvmbo\b", bare):
        return "VMBO TL"

    if re.search(r"\bvmbo\b", bare):
        for pattern, label in _VMBO_TRACKS:
            if re.search(pattern, bare):
                return label
        return "VMBO"

    if re.search(r"\bmbo\b", bare):
        if re.search(r"\bentree\b", bare):
            return "MBO Entree"
        match = re.search(r"\bmbo\s*([1-4])\b", bare) or re.search(r"\b([1-4])\b", bare)
        return f"MBO {match.group(1)}" if match else "MBO"

    if re.search(r"\b(praktijkonderwijs|praktijkschool|pro|pro onderwijs)\b", bare):
        return "Praktijkonderwijs"

    if re.search(r"\b(havo)\b", bare) and re.search(r"\b(vwo|atheneum|gymnasium)\b", bare):
        return "HAVO/VWO"
    if re.search(r"\bhavo\b", bare):
        return "HAVO"
    if re.search(r"\b(vwo|atheneum|gymnasium)\b", bare):
        return "VWO"

    if re.search(r"\b(hbo|hogeschool|associate degree|ad)\b", bare):
        return "HBO"
    if re.search(r"\b(wo|universiteit|universitair|master|bachelor)\b", bare):
        # Bachelor en master zonder verdere aanduiding zeggen weinig; alleen
        # samen met wo of universiteit is het eenduidig.
        if re.search(r"\b(wo|universiteit|universitair)\b", bare):
            return "WO"
        return raw
    return raw


# Volgorde waarin niveaus logisch oplopen; onbekende namen sluiten achteraan
# aan, met Onbekend altijd als laatste.
_LEVEL_ORDER = [
    "Praktijkonderwijs",
    "VMBO", "VMBO Basis", "VMBO Kader", "VMBO Gemengd", "VMBO TL",
    "MBO", "MBO Entree", "MBO 1", "MBO 2", "MBO 3", "MBO 4",
    "HAVO", "VWO", "HAVO/VWO",
    "HBO", "WO",
]


def level_sort_key(label: str):
    if label == ONBEKEND:
        return (2, 0, "")
    if label in _LEVEL_ORDER:
        return (0, _LEVEL_ORDER.index(label), "")
    return (1, 0, _bare(label))


def profile_label(value, seen: dict | None = None) -> str:
    """Groepeer profielen op schrijfwijze, zonder een indeling te verzinnen.

    Profielen zijn te divers om onder vaste noemers te brengen; wel worden
    Techniek, techniek en TECHNIEK als één groep geteld. De eerste
    schrijfwijze die langskomt wordt de weergegeven naam.
    """
    raw = str(value or "").strip()
    if not raw:
        return ONBEKEND
    key = _bare(raw)
    if not key:
        return ONBEKEND
    if seen is None:
        return raw
    return seen.setdefault(key, raw)


OVERIG = "Overig"


def collapse_columns(data: dict, limit: int = 8) -> dict:
    """Bundel de staart van de profielen tot een kolom Overig.

    Een kruistabel van dertien niveaus bij achtentwintig profielen is in de
    praktijk voor ruim tachtig procent leeg: je leest een veld nullen om een
    handvol getallen te vinden. Door alleen de grootste profielen apart te
    tonen en de rest samen te nemen blijft het beeld leesbaar zonder dat er
    een deelnemer buiten de telling valt.

    Er wordt niets weggegooid: de gebundelde namen komen terug onder
    ``gebundeld``, en de aantallen zitten in de kolom Overig.
    """
    columns = list(data.get("columns", []))
    column_totals = data.get("column_totals", {})
    # Een enkele kolom bundelen levert niets op; dan is Overig (1) alleen maar
    # een omweg naar hetzelfde getal.
    if limit <= 0 or len(columns) <= limit + 1:
        return data

    ranked = sorted(columns, key=lambda name: (-column_totals.get(name, 0), _bare(name)))
    kept = set(ranked[:limit])
    tail = [name for name in columns if name not in kept]
    label = f"{OVERIG} ({len(tail)})"

    counts: dict = {}
    for (level, profile), value in data["counts"].items():
        target = profile if profile in kept else label
        counts[(level, target)] = counts.get((level, target), 0) + value

    totals = {name: column_totals[name] for name in columns if name in kept}
    totals[label] = sum(column_totals.get(name, 0) for name in tail)

    collapsed = dict(data)
    collapsed.update({
        "columns": [name for name in columns if name in kept] + [label],
        "counts": counts,
        "column_totals": totals,
        "gebundeld": sorted(tail, key=lambda name: (-column_totals.get(name, 0), _bare(name))),
    })
    return collapsed


def crosstab(records: list[dict]) -> dict:
    """Kruis opleidingsniveau met profiel.

    Levert de rijen, kolommen en aantallen, plus de totalen in de marge en de
    schrijfwijzen die onder één noemer zijn gebracht.
    """
    spellings: dict = {}
    counts: dict = {}
    row_totals: dict = {}
    column_totals: dict = {}
    merged: dict = {}

    for record in records:
        original = str(record.get("Opleiding", "") or "").strip()
        level = education_level(original)
        # Op de letterlijke schrijfwijze vergelijken, niet op de genormaliseerde:
        # anders blijven mbo-4 en MBO4 ongenoemd terwijl ze wel zijn samengevoegd.
        if original and original != level:
            merged.setdefault(level, set()).add(original)
        profile = profile_label(record.get("Profiel", ""), spellings)
        counts[(level, profile)] = counts.get((level, profile), 0) + 1
        row_totals[level] = row_totals.get(level, 0) + 1
        column_totals[profile] = column_totals.get(profile, 0) + 1

    rows = sorted(row_totals, key=level_sort_key)
    columns = sorted(
        column_totals,
        key=lambda name: (name == ONBEKEND, -column_totals[name], _bare(name)),
    )
    return {
        "rows": rows,
        "columns": columns,
        "counts": counts,
        "row_totals": row_totals,
        "column_totals": column_totals,
        "total": sum(row_totals.values()),
        "merged": {level: sorted(values) for level, values in merged.items()},
    }
