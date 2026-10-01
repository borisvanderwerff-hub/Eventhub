"""Historische statistieken: alleen aggregaten, nooit nagebouwde deelnemers."""
from collections import Counter
from datetime import date, datetime

from bezoekerslijst_core import (AANWEZIG, AFWEZIG, AFGEMELD, ONBEKEND,
    attendance_status, attendance_counts, turnout_percentage, is_introducee,
    is_skipped, normalize, record_events, registrations)
from emt_education import education_level, profile_label, level_sort_key
from emt_models import parse_date
from emt_trends import age_group, age_on

STATUS_KEYS = {AANWEZIG: "aanwezig", AFWEZIG: "noshow", AFGEMELD: "afgemeld", ONBEKEND: "onbekend"}
DIMENSIONS = ("Opleidingsniveau", "Profiel", "Geslacht", "Leeftijdsgroep")


def snapshot_for_event(event, records):
    name = str(event.get("name", ""))
    visitors = [r for r in records if not is_skipped(r)
                and any(normalize(n) == normalize(name) for n in record_events(r))]
    if not visitors:
        return None
    reference = parse_date(event.get("date", "")) or date.today()

    def scope(rows):
        counts = attendance_counts(rows, name)
        result = dict(aangemeld=len(rows), aanwezig=counts[AANWEZIG], noshows=counts[AFWEZIG],
                      afgemeld=counts[AFGEMELD], onbekend=counts[ONBEKEND],
                      opkomst_percentage=turnout_percentage(counts),
                      verdeling={d: {} for d in DIMENSIONS}, kruistabel=[], inschrijvingen={})
        spellings, cross = {}, {}
        for row in rows:
            key = STATUS_KEYS[attendance_status(row, name)]
            labels = (education_level(row.get("Opleiding")), profile_label(row.get("Profiel"), spellings),
                      str(row.get("Geslacht", "") or "").strip() or "Onbekend",
                      age_group(age_on(row.get("Geboortedatum"), reference)))
            for dimension, label in zip(DIMENSIONS, labels):
                bucket = result["verdeling"][dimension].setdefault(label, Counter())
                bucket["aangemeld"] += 1
                bucket[key] += 1
            bucket = cross.setdefault(labels[:2], Counter())
            bucket["aangemeld"] += 1
            bucket[key] += 1
            for label in registrations(row):
                result["inschrijvingen"][label] = result["inschrijvingen"].get(label, 0) + 1
        # Expliciete nulwaarden onderscheiden gemeten nul van niet vastgelegd.
        for groups in [*result["verdeling"].values(), cross]:
            for label, bucket in groups.items():
                groups[label] = {k: int(bucket.get(k, 0)) for k in ("aangemeld", *STATUS_KEYS.values())}
        result["kruistabel"] = [dict(niveau=level, profiel=profile, **bucket)
                               for (level, profile), bucket in sorted(cross.items())]
        return result

    regular = [r for r in visitors if not is_introducee(r)]
    result = scope(visitors)
    result.update(schema=6, vastgelegd_op=datetime.now().isoformat(timespec="seconds"),
                  peildatum=reference.strftime("%d-%m-%Y"), introducees=len(visitors)-len(regular),
                  regulier=scope(regular))
    return result


def historical_scope(event, include_introducees=True):
    snapshot = event.get("statistiek") if event else None
    if not isinstance(snapshot, dict) or "aangemeld" not in snapshot:
        return None
    if include_introducees or not snapshot.get("introducees"):
        return snapshot
    return snapshot.get("regulier") if isinstance(snapshot.get("regulier"), dict) else None


def bucket_value(bucket, status="all"):
    if not isinstance(bucket, dict):
        return int(bucket) if status == "all" else None
    key = "aangemeld" if status == "all" else STATUS_KEYS[status]
    if key == "noshow" and "noshows" in bucket:
        key = "noshows"
    if key in bucket:
        return int(bucket[key])
    # Schema 2–5 bevatten geen onbekend per groep, maar soms wel alle eindstanden.
    if key == "onbekend" and all(k in bucket for k in ("aangemeld", "aanwezig", "noshow", "afgemeld")):
        residual = int(bucket["aangemeld"]) - sum(int(bucket[k]) for k in ("aanwezig", "noshow", "afgemeld"))
        return residual if residual >= 0 else None
    return None


def distribution(snapshot, dimension, status="all"):
    groups = (snapshot or {}).get("verdeling", {}).get(dimension)
    if not isinstance(groups, dict):
        return None
    counts, spellings = Counter(), {}
    for label, bucket in groups.items():
        value = bucket_value(bucket, status)
        if value is None:
            return None
        label = education_level(label) if dimension == "Opleidingsniveau" else (
            profile_label(label, spellings) if dimension == "Profiel" else label)
        counts[label] += value
    return sorted(counts.items(), key=lambda item: (-item[1], normalize(item[0])))


def cross_table(snapshot, status="all"):
    cells = (snapshot or {}).get("kruistabel")
    if not isinstance(cells, list):
        return None
    counts, rows, columns = Counter(), Counter(), Counter()
    for cell in cells:
        value = bucket_value(cell, status)
        if value is None:
            return None
        if value:
            level, profile = cell["niveau"], cell["profiel"]
            counts[level, profile] += value
            rows[level] += value
            columns[profile] += value
    return dict(rows=sorted(rows, key=level_sort_key), columns=sorted(columns, key=lambda n: (-columns[n], normalize(n))),
                counts=dict(counts), row_totals=dict(rows), column_totals=dict(columns), total=sum(rows.values()), merged={})


def export_dimensions(snapshot, status="all"):
    """Onbeschikbare historische statussen blijven leeg, niet nul."""
    result = []
    for dimension in DIMENSIONS:
        all_values = distribution(snapshot, dimension)
        if all_values is None:
            continue
        status_values = {s: distribution(snapshot, dimension, s) for s in STATUS_KEYS}
        mappings = {s: dict(v) if v is not None else None for s, v in status_values.items()}
        rows = []
        for label, total in all_values:
            values = [mappings[s].get(label, 0) if mappings[s] is not None else None for s in STATUS_KEYS]
            if status != "all":
                if mappings[status] is None:
                    continue
                total = mappings[status].get(label, 0)
                values = [total if s == status else 0 for s in STATUS_KEYS]
            rows.append((label, total, *values))
        if rows:
            result.append((dimension, rows))
    return result
