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

from datetime import date, datetime, timedelta
import re

from bezoekerslijst_core import normalize
from emt_models import parse_date

# Meetwaarden die uit een momentopname te halen zijn.
METRICS = (
    ("Aanmeldingen", "aangemeld"),
    ("Aanwezigen", "aanwezig"),
    ("No-shows", "noshows"),
    ("Afmeldingen", "afgemeld"),
    ("Opkomstpercentage", "opkomst_percentage"),
    ("No-showpercentage", "noshow_percentage"),
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


AGE_GROUPS = ("Jonger dan 18", "18–20", "21–24", "25–29", "30–39", "40 en ouder", "Onbekend")


def age_on(birth_text, reference: date | None = None) -> int | None:
    """Leeftijd in jaren op de peildatum, of None bij een onbruikbare datum."""
    born = parse_date(birth_text)
    if born is None:
        return None
    reference = reference or date.today()
    age = reference.year - born.year - ((reference.month, reference.day) < (born.month, born.day))
    return age if 0 <= age <= 120 else None


def age_group(age: int | None) -> str:
    """Eén definitie van de leeftijdsgroepen.

    Eigen en ingeladen gegevens moeten dezelfde indeling gebruiken; anders
    worden in een trend groepen vergeleken die niet hetzelfde betekenen.
    """
    if age is None:
        return "Onbekend"
    if age < 18:
        return "Jonger dan 18"
    if age <= 20:
        return "18–20"
    if age <= 24:
        return "21–24"
    if age <= 29:
        return "25–29"
    if age <= 39:
        return "30–39"
    return "40 en ouder"


def summarise_records(records: list[dict], event_name: str, event_date=None) -> dict:
    """Reken een bezoekerslijst om naar geaggregeerde cijfers.

    Wordt gebruikt bij het inladen van losse bezoekerslijsten. De
    deelnemersrijen worden hierna weggegooid: de trendanalyse werkt uitsluitend
    op aantallen, zodat het inladen van een lijst geen nieuwe verzameling
    persoonsgegevens oplevert die buiten de bewaartermijn valt.
    """
    from bezoekerslijst_core import (
        AANWEZIG, AFWEZIG, AFGEMELD, ONBEKEND, attendance_counts,
        is_cancelled, is_introducee, is_no_show, is_present,
    )

    reference = parse_date(event_date) or date.today()
    def grouped(scope_records, labeller):
        # Ook no-shows en afmeldingen per groep: anders is achteraf niet te
        # zien bij welke groep ze zaten, en zou een afmelding als no-show
        # meetellen omdat alleen aangemeld min aanwezig bekend is.
        buckets: dict[str, dict] = {}
        for record in scope_records:
            bucket = buckets.setdefault(
                labeller(record),
                {"aangemeld": 0, "aanwezig": 0, "noshow": 0, "afgemeld": 0},
            )
            bucket["aangemeld"] += 1
            bucket["aanwezig"] += is_present(record, event_name)
            bucket["noshow"] += is_no_show(record, event_name)
            bucket["afgemeld"] += is_cancelled(record, event_name)
        return dict(sorted(buckets.items(), key=lambda item: (-item[1]["aangemeld"], normalize(item[0]))))

    def field(name):
        return lambda record: str(record.get(name, "") or "").strip() or "Onbekend"

    def scope_snapshot(scope_records):
        statuses = attendance_counts(scope_records, event_name)
        registered = len(scope_records)
        attended = statuses[AANWEZIG]
        return {
            "aangemeld": registered,
            "aanwezig": attended,
            "noshows": statuses[AFWEZIG],
            "afgemeld": statuses[AFGEMELD],
            "onbekend": statuses[ONBEKEND],
            "opkomst_percentage": round(attended / registered * 100, 1) if registered else 0.0,
            "verdeling": {
                "Opleidingsniveau": grouped(scope_records, field("Opleiding")),
                "Profiel": grouped(scope_records, field("Profiel")),
                "Geslacht": grouped(scope_records, field("Geslacht")),
                "Leeftijdsgroep": grouped(scope_records,
                lambda record: age_group(age_on(record.get("Geboortedatum", ""), reference))
                ),
            },
        }

    snapshot = scope_snapshot(records)
    regular = [record for record in records if not is_introducee(record)]
    snapshot.update({
        # 5: reguliere deelnemers zijn apart geaggregeerd. Daarmee kunnen
        # introducees ook na de AVG-opschoning worden uitgesloten zonder te
        # bewaren welke persoon introducé was.
        "schema": 5,
        "vastgelegd_op": date.today().isoformat(),
        "peildatum": reference.strftime("%d-%m-%Y"),
        "introducees": len(records) - len(regular),
        "regulier": scope_snapshot(regular),
    })
    return snapshot


def summaries_from_records(records: list[dict], dates: dict | None = None, source: str = "") -> list[dict]:
    """Groepeer een ingeladen bezoekerslijst per evenement en vat elk groepje samen.

    Eén bestand kan deelnemers van meerdere evenementen bevatten; het veld
    Evenement is leidend. ``dates`` koppelt een evenementnaam aan een datum,
    want een bezoekerslijst bevat die zelf niet.
    """
    from bezoekerslijst_core import record_events

    dates = dates or {}
    grouped: dict[str, list] = {}
    for record in records:
        for name in record_events(record) or ["Onbekend evenement"]:
            grouped.setdefault(name, []).append(record)

    summaries = []
    for name, group in grouped.items():
        event_date = dates.get(name) or dates.get(normalize(name)) or ""
        summaries.append({
            "id": f"import:{normalize(name)}",
            "name": name,
            "date": str(event_date or ""),
            "event_type": "Onbekend",
            "place": "Onbekend",
            "location": "Onbekend",
            "source": source,
            "statistiek": summarise_records(group, name, event_date),
        })
    return sorted(summaries, key=lambda item: normalize(item["name"]))


def event_summary(event: dict, source: str = "") -> dict | None:
    """Reduceer een evenement tot wat een trendanalyse nodig heeft.

    Levert None wanneer er nog geen momentopname is vastgelegd; zonder cijfers
    valt er niets te vergelijken.
    """
    if event.get("exclude_from_analysis"):
        return None
    snapshot = event.get("statistiek")
    if not isinstance(snapshot, dict) or not snapshot:
        return None
    # Een lege/testimport is geen historische meting en mag KPI's zoals het
    # aantal evenementen of het gemiddelde opkomstpercentage niet vertekenen.
    if int(snapshot.get("aangemeld", 0) or 0) <= 0:
        return None
    # Vanaf schema 3 is 'onbekend' expliciet beschikbaar. Zolang daar nog
    # deelnemers staan is de presentieregistratie niet definitief. Oude
    # momentopnames missen dit veld en blijven voor compatibiliteit bruikbaar.
    if int(snapshot.get("onbekend", 0) or 0) > 0 and not event.get("persoonsgegevens_gewist"):
        return None
    return {
        "id": str(event.get("id", "") or ""),
        "template_id": str(event.get("template_id", "") or ""),
        "historisch": bool(event.get("persoonsgegevens_gewist")),
        "template_name": str(event.get("template_name", "") or ""),
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


ANALYSIS_FORMAT = "EventHub trendanalyse"
ANALYSIS_VERSION = 1


def analysis_file_name(name: str) -> str:
    """Een bestandsnaam die op elk besturingssysteem mag."""
    veilig = re.sub(r"[<>:\"/\\|?*]+", "-", str(name or "").strip()).strip(" .")
    return (veilig or "Analyse") + ".json"


def analysis_payload(name: str, sources) -> dict:
    """Wat er van een losse analyse op schijf gaat.

    Uitsluitend de geaggregeerde cijfers, net als in de analyse zelf: de
    deelnemersrijen zijn bij het inladen al weggegooid en horen ook hier niet
    thuis.
    """
    return {
        "format": ANALYSIS_FORMAT,
        "version": ANALYSIS_VERSION,
        "naam": str(name or "").strip(),
        "bijgewerkt": datetime.now().isoformat(timespec="seconds"),
        "sources": [
            {"label": str(source.get("label", "") or ""), "summaries": list(source.get("summaries", []))}
            for source in sources or []
            if str(source.get("label", "") or "").strip()
        ],
    }


def read_analysis(payload: dict) -> tuple[str, list]:
    """Lees een bewaarde analyse terug; onbruikbare inhoud levert niets op."""
    if not isinstance(payload, dict) or payload.get("format") != ANALYSIS_FORMAT:
        return "", []
    sources = []
    for source in payload.get("sources", []) or []:
        if not isinstance(source, dict):
            continue
        label = str(source.get("label", "") or "").strip()
        summaries = source.get("summaries", [])
        if label and isinstance(summaries, list):
            sources.append({"label": label, "summaries": summaries})
    return str(payload.get("naam", "") or "").strip(), sources


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
    if metric in {"opkomst_percentage", "noshow_percentage"}:
        registered = float(snapshot.get("aangemeld", 0) or 0)
        numerator = snapshot.get("aanwezig", 0) if metric == "opkomst_percentage" else snapshot.get("noshows", 0)
        return round(float(numerator or 0) / registered * 100, 1) if registered else 0.0
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
                "noshows": (
                    int(value.get("noshow", value.get("noshows", 0)) or 0)
                    if "noshow" in value or "noshows" in value else None
                ),
                "afgemeld": int(value.get("afgemeld", 0) or 0) if "afgemeld" in value else None,
            }
        else:
            counts[str(label)] = {"aangemeld": int(value or 0), "aanwezig": None,
                                  "noshows": None, "afgemeld": None}
    return counts


def _group_value(bucket: dict, metric: str):
    registered = bucket.get("aangemeld") or 0
    attended = bucket.get("aanwezig")
    if metric == "aangemeld":
        return float(registered)
    if metric == "afgemeld":
        # Alleen momentopnames vanaf schema 4 kennen afmeldingen per groep.
        afgemeld = bucket.get("afgemeld")
        return None if afgemeld is None else float(afgemeld)
    if attended is None:
        # Oude momentopname: aanwezigheid per groep is niet vastgelegd.
        return None
    if metric == "aanwezig":
        return float(attended)
    if metric == "noshows":
        return float(bucket.get("noshows")) if bucket.get("noshows") is not None else float(registered - attended)
    if metric == "noshow_percentage":
        noshows = bucket.get("noshows")
        if noshows is None:
            noshows = registered - attended
        return round(noshows / registered * 100, 1) if registered else 0.0
    return round(attended / registered * 100, 1) if registered else 0.0


def regular_scope_available(summaries: list[dict]) -> bool:
    """Kan elke set met introducees betrouwbaar tot regulier worden beperkt?"""
    return all(
        not int(item.get("statistiek", {}).get("introducees", 0) or 0)
        or isinstance(item.get("statistiek", {}).get("regulier"), dict)
        for item in summaries or []
    )


def participant_scope(summaries: list[dict], include_introducees: bool) -> list[dict]:
    """Selecteer alleen een geaggregeerde scope; nooit individuele deelnemers."""
    if include_introducees:
        return list(summaries or [])
    scoped = []
    for item in summaries or []:
        snapshot = item.get("statistiek", {})
        regular = snapshot.get("regulier")
        if isinstance(regular, dict):
            copy = dict(item)
            copy["statistiek"] = regular
            scoped.append(copy)
        elif not int(snapshot.get("introducees", 0) or 0):
            scoped.append(item)
    return scoped


def period_label(event_date: date | None, period: str) -> str:
    # 'total' gooit alles op één hoop: dan telt niet wanneer iets gebeurde,
    # maar alleen hoe de selectie als geheel eruitziet.
    if period == "total":
        return "Hele selectie"
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
    if period == "total":
        return (0, 0, 0)
    if event_date is None:
        return (1, 0, 0)
    if period == "month":
        return (0, event_date.year, event_date.month)
    if period == "quarter":
        return (0, event_date.year, (event_date.month - 1) // 3)
    if period == "year":
        return (0, event_date.year, 0)
    return (0, event_date.toordinal(), 0)


def _aggregate(metric: str, registered: float, attended: float, noshows: float, values: list[float]) -> float:
    """Percentages worden herberekend, aantallen opgeteld.

    Het gemiddelde van percentages is niet het percentage van het geheel: een
    evenement met vier deelnemers zou dan even zwaar wegen als een met
    tweehonderd.
    """
    if metric == "opkomst_percentage":
        return round(attended / registered * 100, 1) if registered else 0.0
    if metric == "noshow_percentage":
        return round(noshows / registered * 100, 1) if registered else 0.0
    return round(sum(values), 1)


def build_series(
    summaries: list[dict],
    metric: str = "aangemeld",
    dimension: str = "",
    period: str = "event",
    since: date | None = None,
    until: date | None = None,
    percentage_of_total: bool = False,
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
            entry = buckets[label].setdefault(key, {"values": [], "registered": 0.0, "attended": 0.0, "noshows": 0.0, "event_ids": []})
            entry["values"].append(_snapshot_value(snapshot, metric))
            entry["registered"] += float(snapshot.get("aangemeld", 0) or 0)
            entry["attended"] += float(snapshot.get("aanwezig", 0) or 0)
            entry["noshows"] += float(snapshot.get("noshows", 0) or 0)
            entry["event_ids"].append(str(summary.get("id", "") or ""))
            continue

        counts = _group_counts(snapshot, dimension)
        if not counts:
            continue
        for group, bucket in counts.items():
            value = _group_value(bucket, metric)
            if value is None:
                incomplete = True
                continue
            entry = buckets[label].setdefault(group, {"values": [], "registered": 0.0, "attended": 0.0, "noshows": 0.0, "event_ids": []})
            entry["values"].append(value)
            entry["registered"] += float(bucket.get("aangemeld") or 0)
            entry["attended"] += float(bucket.get("aanwezig") or 0)
            entry["noshows"] += float(bucket.get("noshows") or 0)
            entry["event_ids"].append(str(summary.get("id", "") or ""))

    groups = sorted(
        {group for bucket in buckets.values() for group in bucket},
        key=lambda name: (
            -sum(sum(bucket.get(name, {}).get("values", [])) for bucket in buckets.values()),
            normalize(name),
        ),
    )
    points = []
    totals: dict[str, dict] = {group: {"registered": 0.0, "attended": 0.0, "noshows": 0.0, "values": []} for group in groups}
    for label in order:
        row = {"label": label, "values": {}, "event_ids": []}
        for group in groups:
            entry = buckets[label].get(group)
            row["values"][group] = (
                _aggregate(metric, entry["registered"], entry["attended"], entry["noshows"], entry["values"])
                if entry else 0.0
            )
            if entry:
                row["event_ids"].extend(entry["event_ids"])
                totals[group]["registered"] += entry["registered"]
                totals[group]["attended"] += entry["attended"]
                totals[group]["noshows"] += entry["noshows"]
                totals[group]["values"].extend(entry["values"])
        row["event_ids"] = list(dict.fromkeys(filter(None, row["event_ids"])))
        points.append(row)

    raw_totals = {
        group: _aggregate(metric, data["registered"], data["attended"], data["noshows"], data["values"])
        for group, data in totals.items()
    }
    percentage_enabled = bool(
        percentage_of_total and dimension and metric in {
            "aangemeld", "aanwezig", "noshows", "afgemeld"
        }
    )
    if percentage_enabled:
        for row in points:
            raw_values = dict(row["values"])
            denominator = sum(raw_values.values())
            row["raw_values"] = raw_values
            row["raw_total"] = denominator
            row["values"] = {
                group: round(value / denominator * 100, 1) if denominator else 0.0
                for group, value in raw_values.items()
            }
        total_denominator = sum(raw_totals.values())
        displayed_totals = {
            group: round(value / total_denominator * 100, 1) if total_denominator else 0.0
            for group, value in raw_totals.items()
        }
    else:
        displayed_totals = raw_totals

    return {
        "metric": metric,
        "display_metric": "aandeel_percentage" if percentage_enabled else metric,
        "percentage_of_total": percentage_enabled,
        "dimension": dimension,
        "period": period,
        "groups": groups,
        "points": points,
        "events": len(selected),
        "incomplete": incomplete,
        "selected": [summary for _event_date, summary in selected],
        "totals": displayed_totals,
        "raw_totals": raw_totals,
    }


def select_series_groups(series: dict, selections: dict | None = None) -> dict:
    """Select visible categories, retaining the original population/denominators."""
    from copy import deepcopy
    chosen = (selections or {}).get(series.get("dimension"))
    if chosen is None:
        return series
    result = deepcopy(series)
    result["groups"] = [group for group in series.get("groups", []) if group in chosen]
    for point in result.get("points", []):
        for key in ("values", "raw_values"):
            if key in point:
                point[key] = {group: value for group, value in point[key].items() if group in result["groups"]}
    for key in ("totals", "raw_totals"):
        if key in result:
            result[key] = {group: value for group, value in result[key].items() if group in result["groups"]}
    return result


def series_totals(series: dict) -> list[tuple[str, float]]:
    """Totaal per groep over de hele reeks, voor een staaf- of donutweergave."""
    if isinstance(series.get("totals"), dict):
        return [(group, float(series["totals"].get(group, 0.0))) for group in series["groups"]]
    totals = []
    for group in series["groups"]:
        values = [point["values"].get(group, 0.0) for point in series["points"]]
        if series["metric"] in {"opkomst_percentage", "noshow_percentage"}:
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
    unit = "%" if series.get("display_metric", series["metric"]) in {
        "opkomst_percentage", "noshow_percentage", "aandeel_percentage"
    } else ""
    difference = round(last - first, 1)
    if not difference:
        return f"{group}: gelijk gebleven op {last:g}{unit}."
    richting = "toename" if difference > 0 else "afname"
    return (
        f"{group}: {richting} van {first:g}{unit} naar {last:g}{unit} "
        f"({difference:+g}{unit}) tussen {points[0]['label']} en {points[-1]['label']}."
    )


def available_dimensions(summaries: list[dict]) -> list[str]:
    """Alleen dimensies tonen waarvoor ten minste één echte waarde bestaat."""
    available = [""]
    for key in ("event_type", "place", "location"):
        if any(str(item.get(key, "") or "").strip() not in {"", "Onbekend"} for item in summaries):
            available.append(key)
    for dimension in GROUP_DIMENSIONS:
        if any((item.get("statistiek", {}).get("verdeling", {}).get(dimension) or {}) for item in summaries):
            available.append(dimension)
    return available


def filter_summaries(summaries: list[dict], filters: dict | None = None) -> list[dict]:
    """Combineer uitsluitend evenementniveau-filters; die blijven exact op aggregaten."""
    filters = filters or {}
    since, until = filters.get("since"), filters.get("until")
    selected = []
    for summary in summaries or []:
        event_date = parse_date(summary.get("date", ""))
        if since and (event_date is None or event_date < since):
            continue
        if until and (event_date is None or event_date > until):
            continue
        if filters.get("event_type") and summary.get("event_type") != filters["event_type"]:
            continue
        if filters.get("template_id") and str(summary.get("template_id", "")) != str(filters["template_id"]):
            continue
        if filters.get("location") and summary.get("location") != filters["location"]:
            continue
        if filters.get("event_id") and str(summary.get("id", "")) != str(filters["event_id"]):
            continue
        selected.append(summary)
    return selected


def overview_kpis(summaries: list[dict]) -> dict:
    registered = sum(int(item.get("statistiek", {}).get("aangemeld", 0) or 0) for item in summaries)
    attended = sum(int(item.get("statistiek", {}).get("aanwezig", 0) or 0) for item in summaries)
    noshows = sum(int(item.get("statistiek", {}).get("noshows", 0) or 0) for item in summaries)
    cancelled = sum(int(item.get("statistiek", {}).get("afgemeld", 0) or 0) for item in summaries)
    return {
        "evenementen": len(summaries), "aangemeld": registered, "aanwezig": attended,
        "noshows": noshows, "afgemeld": cancelled,
        "opkomst_percentage": round(attended / registered * 100, 1) if registered else 0.0,
        "noshow_percentage": round(noshows / registered * 100, 1) if registered else 0.0,
    }


def compare_periods(summaries: list[dict], since: date, until: date,
                    previous_since: date | None = None, previous_until: date | None = None) -> dict:
    """Vergelijk twee inclusieve perioden met aantallen, procenten en procentpunten."""
    days = max(1, (until - since).days + 1)
    previous_until = previous_until or (since - timedelta(days=1))
    previous_since = previous_since or (previous_until - timedelta(days=days - 1))
    current = overview_kpis(filter_summaries(summaries, {"since": since, "until": until}))
    previous = overview_kpis(filter_summaries(summaries, {"since": previous_since, "until": previous_until}))
    changes = {}
    for key, value in current.items():
        old = previous[key]
        changes[key] = {
            "absolute": round(value - old, 1),
            "percentage": round((value - old) / old * 100, 1) if old else None,
            "percentage_points": round(value - old, 1) if key.endswith("percentage") else None,
        }
    return {"current": current, "previous": previous, "changes": changes,
            "current_range": (since, until), "previous_range": (previous_since, previous_until)}


def ranked_events(summaries: list[dict]) -> list[dict]:
    result = []
    for item in summaries:
        stats = item.get("statistiek", {})
        registered = int(stats.get("aangemeld", 0) or 0)
        attended = int(stats.get("aanwezig", 0) or 0)
        result.append({**item, "turnout": round(attended / registered * 100, 1) if registered else 0.0})
    return sorted(result, key=lambda item: (-item["turnout"], -int(item.get("statistiek", {}).get("aangemeld", 0) or 0), normalize(item.get("name", ""))))


def generate_insights(summaries: list[dict]) -> list[dict]:
    """Deterministische signalen met de gebruikte evenementen als onderbouwing."""
    if len(summaries) < 2:
        return []
    insights = []
    ordered = sorted(summaries, key=lambda item: parse_date(item.get("date", "")) or date.min)
    midpoint = max(1, len(ordered) // 2)
    earlier, later = overview_kpis(ordered[:midpoint]), overview_kpis(ordered[midpoint:])
    delta = round(later["opkomst_percentage"] - earlier["opkomst_percentage"], 1)
    if delta:
        direction = "hoger" if delta > 0 else "lager"
        insights.append({"title": f"Opkomst {abs(delta):g} procentpunt {direction}",
                         "detail": "Vergelijking van de recentste evenementen met de eerdere helft; dit is geen causale verklaring.",
                         "event_ids": [str(item.get("id", "")) for item in ordered]})
    for dimension, label in (("event_type", "evenementsoort"), ("location", "locatie")):
        series = build_series(summaries, "opkomst_percentage", dimension, "year")
        totals = sorted(series_totals(series), key=lambda item: item[1], reverse=True)
        if len(totals) >= 2 and totals[0][1] - totals[-1][1] >= 10:
            insights.append({"title": f"Verschil naar {label}: {totals[0][0]} scoort hoger",
                             "detail": f"{totals[0][1]:g}% tegenover {totals[-1][1]:g}% voor {totals[-1][0]}. Samenhang, geen causaliteit.",
                             "event_ids": [str(item.get("id", "")) for item in summaries]})
    return insights[:4]
