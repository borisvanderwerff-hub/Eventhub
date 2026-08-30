"""Trendanalyse over evenementen heen.

Werkt uitsluitend op de geaggregeerde momentopname die per evenement wordt
vastgelegd (zie ``_event_statistics_snapshot``). Die bevat aantallen en
verdelingen, geen enkele rij per persoon, en overleeft daarom het verstrijken
van de bewaartermijn. Trends blijven zo beschikbaar over evenementen waarvan
de deelnemersgegevens allang zijn verwijderd.

Omdat een momentopname anoniem is, kan hij ook los van een dossier worden
gedeeld: zo zijn trendanalyses te maken over evenementen van een collega
zonder dat daar persoonsgegevens bij komen kijken.

Qt-vrij gehouden zodat de rekenkant los te testen is.
"""
from __future__ import annotations

from datetime import date

from bezoekerslijst_core import normalize
from emt_models import parse_date

# Meetwaarden die uit een momentopname te halen zijn.
METRICS = (
    ("Aanmeldingen", "aangemeld"),
    ("Aanwezigen", "aanwezig"),
    ("No-shows", "noshows"),
    ("Opkomstpercentage", "opkomst_percentage"),
)

# Uitsplitsingen: de eerste komt uit de evenementgegevens zelf, de rest uit
# de verdelingen binnen de momentopname.
EVENT_DIMENSIONS = (
    ("Totaal", ""),
    ("Evenementsoort", "event_type"),
    ("Plaats", "place"),
    ("Locatie", "location"),
)
GROUP_DIMENSIONS = ("Opleidingsniveau", "Profiel", "Geslacht", "Leeftijdsgroep")

PERIODS = (
    ("Per evenement", "event"),
    ("Per maand", "month"),
    ("Per kwartaal", "quarter"),
    ("Per jaar", "year"),
)

MONTH_NAMES = [
    "jan", "feb", "mrt", "apr", "mei", "jun",
    "jul", "aug", "sep", "okt", "nov", "dec",
]


def event_summary(event: dict, source: str = "") -> dict | None:
    """Reduceer een evenement tot wat een trendanalyse nodig heeft.

    Levert None wanneer er nog geen momentopname is vastgelegd; zonder cijfers
    valt er niets te vergelijken.
    """
    snapshot = event.get("statistiek")
    if not isinstance(snapshot, dict) or not snapshot:
        return None
    return {
        "id": str(event.get("id", "") or ""),
        "name": str(event.get("name", "") or "Onbenoemd evenement"),
        "date": str(event.get("date", "") or ""),
        "event_type": str(event.get("event_type", "") or "Onbekend"),
        "place": str(event.get("place", "") or "Onbekend"),
        "location": str(event.get("location", "") or "Onbekend"),
        "source": source,
        "statistiek": snapshot,
    }


def collect_summaries(events: list[dict], source: str = "") -> list[dict]:
    summaries = [event_summary(event, source) for event in events or []]
    return [summary for summary in summaries if summary]


def anonymous_bundle(events: list[dict], label: str) -> dict:
    """Deelbaar pakket met alleen geaggregeerde cijfers, nooit deelnemers."""
    return {
        "format": "EventHub Trendgegevens",
        "version": 1,
        "label": label,
        "events": collect_summaries(events, source=label),
    }


def read_bundle(payload: dict, label: str = "") -> list[dict]:
    """Lees zowel een trendpakket als een volledig EventHub-dossier.

    Van een dossier worden uitsluitend de momentopnames overgenomen; de
    deelnemersrijen worden bewust genegeerd, zodat het importeren van
    andermans dossier nooit persoonsgegevens binnenhaalt.
    """
    if not isinstance(payload, dict):
        return []
    label = label or str(payload.get("label", "") or "Geïmporteerd")
    if payload.get("format") == "EventHub Trendgegevens":
        summaries = []
        for item in payload.get("events") or []:
            if isinstance(item, dict) and isinstance(item.get("statistiek"), dict):
                item = dict(item)
                item["source"] = label
                summaries.append(item)
        return summaries
    return collect_summaries(payload.get("events") or [], source=label)


def _snapshot_value(snapshot: dict, metric: str) -> float:
    if metric == "opkomst_percentage":
        registered = float(snapshot.get("aangemeld", 0) or 0)
        return round(float(snapshot.get("aanwezig", 0) or 0) / registered * 100, 1) if registered else 0.0
    return float(snapshot.get(metric, 0) or 0)


def _group_counts(snapshot: dict, dimension: str) -> dict:
    """Normaliseer beide vormen van een verdeling naar aangemeld/aanwezig.

    Momentopnames van vóór schema 2 bewaarden per groep alleen een totaal.
    Daar is de aanwezigheid per groep niet uit af te leiden; die geven None
    terug zodat de aanroeper het verschil kan tonen in plaats van nul.
    """
    raw = (snapshot.get("verdeling") or {}).get(dimension) or {}
    counts = {}
    for label, value in raw.items():
        if isinstance(value, dict):
            counts[str(label)] = {
                "aangemeld": int(value.get("aangemeld", 0) or 0),
                "aanwezig": int(value.get("aanwezig", 0) or 0),
            }
        else:
            counts[str(label)] = {"aangemeld": int(value or 0), "aanwezig": None}
    return counts


def _group_value(bucket: dict, metric: str):
    registered = bucket.get("aangemeld") or 0
    attended = bucket.get("aanwezig")
    if metric == "aangemeld":
        return float(registered)
    if attended is None:
        # Oude momentopname: aanwezigheid per groep is niet vastgelegd.
        return None
    if metric == "aanwezig":
        return float(attended)
    if metric == "noshows":
        return float(registered - attended)
    return round(attended / registered * 100, 1) if registered else 0.0


def period_label(event_date: date | None, period: str) -> str:
    if event_date is None:
        return "Zonder datum"
    if period == "month":
        return f"{MONTH_NAMES[event_date.month - 1]} {event_date.year}"
    if period == "quarter":
        return f"K{(event_date.month - 1) // 3 + 1} {event_date.year}"
    if period == "year":
        return str(event_date.year)
    return ""


def _period_sort_key(event_date: date | None, period: str):
    if event_date is None:
        return (1, 0, 0)
    if period == "month":
        return (0, event_date.year, event_date.month)
    if period == "quarter":
        return (0, event_date.year, (event_date.month - 1) // 3)
    if period == "year":
        return (0, event_date.year, 0)
    return (0, event_date.toordinal(), 0)


def _aggregate(metric: str, registered: float, attended: float, values: list[float]) -> float:
    """Percentages worden herberekend, aantallen opgeteld.

    Het gemiddelde van percentages is niet het percentage van het geheel: een
    evenement met vier deelnemers zou dan even zwaar wegen als een met
    tweehonderd.
    """
    if metric == "opkomst_percentage":
        return round(attended / registered * 100, 1) if registered else 0.0
    return round(sum(values), 1)


def build_series(
    summaries: list[dict],
    metric: str = "aangemeld",
    dimension: str = "",
    period: str = "event",
    since: date | None = None,
    until: date | None = None,
) -> dict:
    """Bereken één trendreeks.

    Zonder uitsplitsing levert dit één reeks over de tijd. Met een
    uitsplitsing levert het één reeks per groep, zodat bijvoorbeeld te zien is
    of de aanmeldingen onder hbo'ers toenemen of bij welke groep de no-shows
    zitten.
    """
    selected = []
    for summary in summaries:
        event_date = parse_date(summary.get("date", ""))
        if since and (event_date is None or event_date < since):
            continue
        if until and (event_date is None or event_date > until):
            continue
        selected.append((event_date, summary))
    selected.sort(key=lambda item: _period_sort_key(item[0], period))

    buckets: dict[str, dict] = {}
    order: list[str] = []
    incomplete = False

    for event_date, summary in selected:
        snapshot = summary["statistiek"]
        label = period_label(event_date, period) if period != "event" else summary["name"]
        if label not in buckets:
            buckets[label] = {}
            order.append(label)

        if dimension in {"", "event_type", "place", "location"}:
            key = "Totaal" if not dimension else str(summary.get(dimension, "") or "Onbekend")
            entry = buckets[label].setdefault(key, {"values": [], "registered": 0.0, "attended": 0.0})
            entry["values"].append(_snapshot_value(snapshot, metric))
            entry["registered"] += float(snapshot.get("aangemeld", 0) or 0)
            entry["attended"] += float(snapshot.get("aanwezig", 0) or 0)
            continue

        counts = _group_counts(snapshot, dimension)
        if not counts:
            continue
        for group, bucket in counts.items():
            value = _group_value(bucket, metric)
            if value is None:
                incomplete = True
                continue
            entry = buckets[label].setdefault(group, {"values": [], "registered": 0.0, "attended": 0.0})
            entry["values"].append(value)
            entry["registered"] += float(bucket.get("aangemeld") or 0)
            entry["attended"] += float(bucket.get("aanwezig") or 0)

    groups = sorted(
        {group for bucket in buckets.values() for group in bucket},
        key=lambda name: (
            -sum(sum(bucket.get(name, {}).get("values", [])) for bucket in buckets.values()),
            normalize(name),
        ),
    )
    points = []
    for label in order:
        row = {"label": label, "values": {}}
        for group in groups:
            entry = buckets[label].get(group)
            row["values"][group] = (
                _aggregate(metric, entry["registered"], entry["attended"], entry["values"])
                if entry else 0.0
            )
        points.append(row)

    return {
        "metric": metric,
        "dimension": dimension,
        "period": period,
        "groups": groups,
        "points": points,
        "events": len(selected),
        "incomplete": incomplete,
    }


def series_totals(series: dict) -> list[tuple[str, float]]:
    """Totaal per groep over de hele reeks, voor een staaf- of donutweergave."""
    totals = []
    for group in series["groups"]:
        values = [point["values"].get(group, 0.0) for point in series["points"]]
        if series["metric"] == "opkomst_percentage":
            usable = [value for value in values if value]
            totals.append((group, round(sum(usable) / len(usable), 1) if usable else 0.0))
        else:
            totals.append((group, round(sum(values), 1)))
    return totals


def describe_change(series: dict, group: str | None = None) -> str:
    """Verwoord de ontwikkeling tussen het eerste en het laatste punt."""
    points = series["points"]
    if len(points) < 2:
        return "Te weinig punten voor een ontwikkeling."
    group = group or (series["groups"][0] if series["groups"] else None)
    if not group:
        return "Geen gegevens."
    first = points[0]["values"].get(group, 0.0)
    last = points[-1]["values"].get(group, 0.0)
    unit = "%" if series["metric"] == "opkomst_percentage" else ""
    difference = round(last - first, 1)
    if not difference:
        return f"{group}: gelijk gebleven op {last:g}{unit}."
    richting = "toename" if difference > 0 else "afname"
    return (
        f"{group}: {richting} van {first:g}{unit} naar {last:g}{unit} "
        f"({difference:+g}{unit}) tussen {points[0]['label']} en {points[-1]['label']}."
    )
