"""Het rapportmodel achter de Report Builder van Trends.

Hier staat wát er in een rapport komt, niet hoe het eruitziet of hoe het op
papier belandt. Deze module kent geen Qt: hij zet de Trends-gegevens die er al
zijn om in blokken die de opmaak vervolgens over pagina's verdeelt.

De opzet is bewust:

* ``SECTIONS`` beschrijft de mogelijke rapportonderdelen;
* elk onderdeel dat een grafiek bevat verwijst naar een bestaande
  Trends-analyse (meetwaarde, uitsplitsing, tijdseenheid) - er wordt dus geen
  analyse verzonnen die je in Trends zelf niet kunt maken;
* ``build_report_model`` levert genummerde blokken op;
* ``ReportLayout`` in emt_report_layout verdeelt die blokken over pagina's.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from emt_models import parse_date
from emt_trends import (
    PERIODS,
    available_dimensions,
    build_series,
    compare_periods,
    filter_summaries,
    generate_insights,
    overview_kpis,
    participant_scope,
    ranked_events,
    series_totals,
    select_series_groups,
)

# ---------------------------------------------------------------- opmaakhulp

MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni",
           "juli", "augustus", "september", "oktober", "november", "december"]


def getal(waarde) -> str:
    """1842 wordt 1.842; de puntscheiding die ook elders in EventHub staat."""
    try:
        return f"{int(round(float(waarde))):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def procent(waarde, decimalen: int = 1) -> str:
    try:
        tekst = f"{float(waarde):.{decimalen}f}"
    except (TypeError, ValueError):
        return "0,0%"
    return tekst.replace(".", ",") + "%"


def punten(waarde, decimalen: int = 1) -> str:
    """Procentpunten, met teken, voor een vergelijking."""
    try:
        getal_waarde = float(waarde)
    except (TypeError, ValueError):
        return "0,0"
    teken = "+" if getal_waarde > 0 else ""
    return teken + f"{getal_waarde:.{decimalen}f}".replace(".", ",")


def meervoud(aantal, enkelvoud: str, meervoudsvorm: str) -> str:
    """"1 evenement" leest beter dan "1 evenementen"."""
    return f"{getal(aantal)} {enkelvoud if int(aantal or 0) == 1 else meervoudsvorm}"


def datum_tekst(moment: date | None) -> str:
    if not moment:
        return ""
    return f"{moment.day} {MAANDEN[moment.month - 1]} {moment.year}"


def periode_tekst(since: date | None, until: date | None) -> str:
    if since and until:
        return f"{datum_tekst(since)} t/m {datum_tekst(until)}"
    if since:
        return f"vanaf {datum_tekst(since)}"
    if until:
        return f"tot en met {datum_tekst(until)}"
    return "Alle beschikbare perioden"


def safe_file_name(naam: str, standaard: str = "Trendsrapport") -> str:
    """Een bestandsnaam die Windows accepteert, zonder de extensie."""
    schoon = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(naam or "")).strip(" .")
    schoon = re.sub(r"\s+", " ", schoon)
    # Namen die Windows voor apparaten reserveert.
    if not schoon or schoon.upper().split(".")[0] in {
        "CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)),
        *(f"LPT{n}" for n in range(1, 10)),
    }:
        return standaard
    return schoon[:120]


# ------------------------------------------------------------- de onderdelen

# Elke grafiek is een bestaande Trends-analyse: meetwaarde en uitsplitsing
# zijn precies de keuzes die de Trends-pagina zelf aanbiedt. De tijdseenheid
# kiest de gebruiker één keer voor het hele rapport; anders zou een
# uitsplitsing naar groep op één punt uitkomen en viel er niets te volgen.
SECTIONS = [
    {"key": "voorblad", "title": "Voorblad", "charts": []},
    {"key": "huidige_analyse", "title": "Geselecteerde analyse", "charts": []},
    {"key": "samenvatting", "title": "Managementsamenvatting", "charts": []},
    {"key": "kerncijfers", "title": "Kerncijfers", "charts": []},
    {"key": "ontwikkeling", "title": "Ontwikkeling door de tijd", "charts": [
        {"key": "aanmeldingen_tijd", "title": "Aanmeldingen door de tijd",
         "metric": "aangemeld", "dimension": ""},
        {"key": "aanwezigen_tijd", "title": "Aanwezigen door de tijd",
         "metric": "aanwezig", "dimension": ""},
    ]},
    {"key": "opkomst", "title": "Opkomst", "charts": [
        {"key": "opkomst_tijd", "title": "Opkomstpercentage door de tijd",
         "metric": "opkomst_percentage", "dimension": ""},
        {"key": "noshow_tijd", "title": "No-showpercentage door de tijd",
         "metric": "noshow_percentage", "dimension": ""},
        {"key": "opkomst_soort", "title": "Opkomst per evenementsoort",
         "metric": "opkomst_percentage", "dimension": "event_type"},
        {"key": "opkomst_locatie", "title": "Opkomst per locatie",
         "metric": "opkomst_percentage", "dimension": "location"},
    ]},
    {"key": "vergelijking", "title": "Vergelijking met de vorige periode", "charts": []},
    {"key": "evenementsoort", "title": "Evenementsoorten", "charts": [
        {"key": "aanmeldingen_soort", "title": "Aanmeldingen per evenementsoort",
         "metric": "aangemeld", "dimension": "event_type"},
    ]},
    {"key": "locaties", "title": "Locaties", "charts": [
        {"key": "aanmeldingen_locatie", "title": "Aanmeldingen per locatie",
         "metric": "aangemeld", "dimension": "location"},
    ]},
    {"key": "leeftijd", "title": "Leeftijd", "charts": [
        {"key": "leeftijd_aanmeldingen", "title": "Aanmeldingen per leeftijdsgroep",
         "metric": "aangemeld", "dimension": "Leeftijdsgroep"},
        {"key": "leeftijd_noshows", "title": "No-shows per leeftijdsgroep",
         "metric": "noshows", "dimension": "Leeftijdsgroep"},
        {"key": "leeftijd_afmeldingen", "title": "Afmeldingen per leeftijdsgroep",
         "metric": "afgemeld", "dimension": "Leeftijdsgroep"},
        {"key": "leeftijd_opkomst", "title": "Opkomst per leeftijdsgroep",
         "metric": "opkomst_percentage", "dimension": "Leeftijdsgroep"},
    ]},
    {"key": "geslacht", "title": "Geslacht", "charts": [
        {"key": "geslacht_aanmeldingen", "title": "Aanmeldingen per geslacht",
         "metric": "aangemeld", "dimension": "Geslacht"},
        {"key": "geslacht_noshows", "title": "No-shows per geslacht",
         "metric": "noshows", "dimension": "Geslacht"},
        {"key": "geslacht_afmeldingen", "title": "Afmeldingen per geslacht",
         "metric": "afgemeld", "dimension": "Geslacht"},
        {"key": "geslacht_opkomst", "title": "Opkomst per geslacht",
         "metric": "opkomst_percentage", "dimension": "Geslacht"},
    ]},
    {"key": "opleidingsniveau", "title": "Opleidingsniveau", "charts": [
        {"key": "niveau_aanmeldingen", "title": "Aanmeldingen per opleidingsniveau",
         "metric": "aangemeld", "dimension": "Opleidingsniveau"},
        {"key": "niveau_noshows", "title": "No-shows per opleidingsniveau",
         "metric": "noshows", "dimension": "Opleidingsniveau"},
        {"key": "niveau_afmeldingen", "title": "Afmeldingen per opleidingsniveau",
         "metric": "afgemeld", "dimension": "Opleidingsniveau"},
        {"key": "niveau_opkomst", "title": "Opkomst per opleidingsniveau",
         "metric": "opkomst_percentage", "dimension": "Opleidingsniveau"},
    ]},
    {"key": "profiel", "title": "Opleidingsprofielen", "charts": [
        {"key": "profiel_aanmeldingen", "title": "Aanmeldingen per profiel",
         "metric": "aangemeld", "dimension": "Profiel"},
        {"key": "profiel_noshows", "title": "No-shows per profiel",
         "metric": "noshows", "dimension": "Profiel"},
        {"key": "profiel_afmeldingen", "title": "Afmeldingen per profiel",
         "metric": "afgemeld", "dimension": "Profiel"},
    ]},
    {"key": "inzichten", "title": "Trends-inzichten", "charts": []},
    {"key": "evenementen", "title": "Overzicht evenementen", "charts": []},
    {"key": "detailtabellen", "title": "Detailtabellen", "charts": []},
]

SECTION_BY_KEY = {sectie["key"]: sectie for sectie in SECTIONS}

# Welke uitsplitsing hoort bij welk onderdeel? Zonder gegevens voor die
# verdeling heeft het onderdeel niets te melden.
SECTION_DIMENSION = {
    "leeftijd": "Leeftijdsgroep",
    "geslacht": "Geslacht",
    "opleidingsniveau": "Opleidingsniveau",
    "profiel": "Profiel",
}

PRESETS = [
    ("huidige_analyse", "Huidige analyse", ["voorblad", "huidige_analyse"]),
    ("managementrapport", "Managementrapport", [
        "voorblad", "samenvatting", "kerncijfers", "ontwikkeling",
        "vergelijking", "inzichten",
    ]),
    ("volledig", "Volledig analyserapport", [
        "voorblad", "samenvatting", "kerncijfers", "ontwikkeling", "opkomst",
        "vergelijking", "evenementsoort", "locaties", "leeftijd", "geslacht",
        "opleidingsniveau", "profiel", "inzichten", "evenementen", "detailtabellen",
    ]),
    ("opkomst", "Opkomstrapport", [
        "voorblad", "samenvatting", "kerncijfers", "opkomst", "vergelijking",
        "evenementen",
    ]),
    ("aangepast", "Aangepast rapport", []),
]

PRESET_BY_KEY = {sleutel: keys for sleutel, _label, keys in PRESETS}


# ------------------------------------------------------------ de instellingen

def default_design() -> dict:
    return {
        "voorblad": True,
        "datum": True,
        "filters": True,
        "paginanummers": True,
        "inhoudsopgave": False,
        "orientatie": "auto",
    }


def default_selection() -> dict:
    return {"since": None, "until": None, "event_type": "", "location": "",
            "event_id": "", "template_id": "", "template_name": "", "bron": "", "periode": "month",
            "include_introducees": False, "percentage_of_total": False,
            "weergave": VERLOOP, "group_selections": {},
            "analysis_metric": "opkomst_percentage", "analysis_dimension": ""}


PERIOD_LABELS = dict((waarde, label) for label, waarde in PERIODS)

# Twee manieren om naar dezelfde cijfers te kijken. Statistieken vatten de hele
# selectie samen in één beeld per grafiek; verloop zet ze uit in de tijd.
STATISTIEKEN = "statistieken"
VERLOOP = "verloop"
DISPLAY_LABELS = {
    STATISTIEKEN: "Statistieken (hele selectie in één beeld)",
    VERLOOP: "Verloop (ontwikkeling door de tijd)",
}


def selected_display(selectie: dict | None) -> str:
    gekozen = str((selectie or {}).get("weergave", "") or VERLOOP)
    return gekozen if gekozen in DISPLAY_LABELS else VERLOOP


def chart_period(selectie: dict | None) -> str:
    """De tijdseenheid waarmee de grafieken worden opgebouwd.

    Bij statistieken valt alles in één emmer; de grafiek toont dan staven per
    groep in plaats van lijnen door de tijd.
    """
    if selected_display(selectie) == STATISTIEKEN:
        return "total"
    return selected_period(selectie)


def selected_period(selectie: dict | None) -> str:
    """De tijdseenheid van de ontwikkelingsgrafieken."""
    gekozen = str((selectie or {}).get("periode", "") or "month")
    return gekozen if gekozen in PERIOD_LABELS else "month"


def sections_for_preset(preset: str, beschikbaar=None) -> list[dict]:
    """De onderdelenlijst zoals een profiel hem instelt.

    Alle onderdelen blijven in de lijst staan, in de vaste volgorde; het
    profiel bepaalt alleen wat aan staat. Zo hoeft de gebruiker niets terug te
    zoeken wanneer hij van profiel wisselt.
    """
    aan = set(PRESET_BY_KEY.get(preset, []))
    beschikbaar = None if beschikbaar is None else set(beschikbaar)
    onderdelen = []
    for sectie in SECTIONS:
        actief = sectie["key"] in aan
        if beschikbaar is not None and sectie["key"] not in beschikbaar:
            actief = False
        onderdelen.append({
            "key": sectie["key"],
            "aan": actief,
            "grafieken": {grafiek["key"]: True for grafiek in sectie["charts"]},
        })
    return onderdelen


def default_config(preset: str = "managementrapport") -> dict:
    return {
        "preset": preset,
        "titel": "",
        "subtitel": "",
        "selectie": default_selection(),
        "secties": sections_for_preset(preset),
        "vormgeving": default_design(),
    }


def prepare_config(source: dict | None = None) -> dict:
    """Een configuratie met alle sleutels op hun plek.

    Een opgeslagen sjabloon van een oudere versie kan onderdelen missen die er
    inmiddels zijn; die komen er hier uitgeschakeld bij te staan.
    """
    source = dict(source or {})
    config = default_config(str(source.get("preset", "aangepast") or "aangepast"))
    config["titel"] = str(source.get("titel", "") or "")
    config["subtitel"] = str(source.get("subtitel", "") or "")

    selectie = dict(default_selection())
    selectie.update({sleutel: waarde for sleutel, waarde in
                     dict(source.get("selectie") or {}).items() if sleutel in selectie})
    config["selectie"] = selectie

    vormgeving = default_design()
    for sleutel, waarde in dict(source.get("vormgeving") or {}).items():
        if sleutel in vormgeving:
            vormgeving[sleutel] = waarde
    if vormgeving["orientatie"] not in {"auto", "staand", "liggend"}:
        vormgeving["orientatie"] = "auto"
    config["vormgeving"] = vormgeving

    bewaard = {str(item.get("key", "")): item for item in (source.get("secties") or [])
               if isinstance(item, dict)}
    volgorde = [str(item.get("key", "")) for item in (source.get("secties") or [])
                if isinstance(item, dict) and str(item.get("key", "")) in SECTION_BY_KEY]
    for sectie in SECTIONS:
        if sectie["key"] not in volgorde:
            volgorde.append(sectie["key"])
    onderdelen = []
    for sleutel in volgorde:
        opgeslagen = bewaard.get(sleutel, {})
        grafieken = dict(opgeslagen.get("grafieken") or {})
        onderdelen.append({
            "key": sleutel,
            "aan": bool(opgeslagen.get("aan", False)),
            "grafieken": {grafiek["key"]: bool(grafieken.get(grafiek["key"], True))
                          for grafiek in SECTION_BY_KEY[sleutel]["charts"]},
        })
    config["secties"] = onderdelen
    return config


def template_payload(name: str, config: dict) -> dict:
    """Wat er in een eigen sjabloon wordt bewaard.

    Bewust zonder de periode en zonder gegevens: een sjabloon beschrijft de
    vorm van het rapport, zodat je hem later op een nieuwe periode loslaat.
    """
    config = prepare_config(config)
    return {
        "naam": str(name or "").strip(),
        "preset": config["preset"],
        "titel": config["titel"],
        "subtitel": config["subtitel"],
        "secties": config["secties"],
        "vormgeving": config["vormgeving"],
    }


def config_from_template(template: dict, selectie: dict | None = None) -> dict:
    config = prepare_config(template)
    config["selectie"] = dict(selectie or default_selection())
    return config


# ------------------------------------------------------------ beschikbaarheid

def selected_summaries(summaries: list[dict], selectie: dict | None) -> list[dict]:
    """De dataset waar het hele rapport op rust."""
    selectie = selectie or {}
    return filter_summaries(summaries, {
        "since": selectie.get("since"),
        "until": selectie.get("until"),
        "event_type": selectie.get("event_type", ""),
        "template_id": selectie.get("template_id", ""),
        "location": selectie.get("location", ""),
        "event_id": selectie.get("event_id", ""),
    })


def data_range(summaries: list[dict]) -> tuple:
    """De periode die de gegevens zelf beslaan: oudste tot nieuwste evenement."""
    datums = sorted(
        moment for moment in
        (parse_date(str(item.get("date", "") or "")) for item in summaries)
        if moment is not None
    )
    return (datums[0], datums[-1]) if datums else (None, None)


def effective_range(summaries: list[dict], selectie: dict | None) -> tuple:
    """De periode van het rapport, en of die is afgeleid.

    Niets invullen betekent: alles wat bekend is. Zonder deze aanvulling wist
    het rapport niet welke periode het beslaat, en verdween juist het deel dat
    een ontwikkeling laat zien.
    """
    selectie = dict(selectie or {})
    since, until = selectie.get("since"), selectie.get("until")
    if since and until:
        return since, until, False
    binnen_selectie = selected_summaries(summaries, dict(selectie, since=None, until=None))
    eerste, laatste = data_range(binnen_selectie)
    return (since or eerste), (until or laatste), True


def compare_within(summaries: list[dict], since: date, until: date) -> dict:
    """Vergelijk de tweede helft van de periode met de eerste.

    Beslaat een rapport alles wat bekend is, dan is er per definitie geen
    voorgaande periode om mee te vergelijken. De ontwikkeling binnen de
    periode is dan het eerlijke alternatief.
    """
    midden = since + (until - since) / 2
    vergelijking = compare_periods(summaries, midden + timedelta(days=1), until, since, midden)
    vergelijking["halves"] = True
    return vergelijking


def available_sections(summaries: list[dict]) -> set:
    """Welke onderdelen binnen deze dataset iets te melden hebben."""
    if not summaries:
        return set()
    beschikbaar = {"voorblad", "samenvatting", "kerncijfers", "evenementen", "detailtabellen", "huidige_analyse"}
    kpis = overview_kpis(summaries)
    if kpis["aangemeld"]:
        beschikbaar.update({"ontwikkeling", "opkomst", "evenementsoort", "locaties"})
    if len(summaries) >= 2:
        beschikbaar.add("vergelijking")
        if generate_insights(summaries):
            beschikbaar.add("inzichten")
    verdelingen = set(available_dimensions(summaries))
    for sleutel, dimensie in SECTION_DIMENSION.items():
        if dimensie in verdelingen:
            beschikbaar.add(sleutel)
    return beschikbaar


def available_charts(summaries: list[dict], section_key: str,
                     periode: str = "month") -> set:
    """Welke grafieken binnen dit onderdeel daadwerkelijk waarden opleveren."""
    gevonden = set()
    for grafiek in SECTION_BY_KEY.get(section_key, {}).get("charts", []):
        reeks = build_series(summaries, grafiek["metric"], grafiek["dimension"], periode)
        if reeks.get("points") and reeks.get("groups"):
            gevonden.add(grafiek["key"])
    return gevonden


# ------------------------------------------------------ de samenvattende tekst

def management_summary(summaries: list[dict], vergelijking: dict | None = None) -> str:
    """Een samenvatting die volledig uit de cijfers volgt.

    Geen taalmodel: alleen vaste zinnen met berekende waarden erin. Verbanden
    worden als samenhang benoemd, niet als oorzaak.
    """
    if not summaries:
        return "Voor de gekozen selectie zijn geen evenementen met cijfers beschikbaar."
    kpis = overview_kpis(summaries)
    zinnen = [
        f"In de geselecteerde periode {'is' if kpis['evenementen'] == 1 else 'zijn'} "
        f"{meervoud(kpis['evenementen'], 'evenement', 'evenementen')} georganiseerd met in totaal "
        f"{meervoud(kpis['aangemeld'], 'aanmelding', 'aanmeldingen')}. "
        f"Hiervan {'was' if kpis['aanwezig'] == 1 else 'waren'} "
        f"{meervoud(kpis['aanwezig'], 'deelnemer', 'deelnemers')} aanwezig. "
        f"Dit resulteert in een gemiddeld opkomstpercentage van {procent(kpis['opkomst_percentage'])}."
    ]
    if kpis["noshows"]:
        zinnen.append(
            f"Er waren {getal(kpis['noshows'])} no-shows, oftewel "
            f"{procent(kpis['noshow_percentage'])} van de aanmeldingen."
        )
    # Zonder evenementen in de vorige periode valt er niets te vergelijken; een
    # sprong van nul naar het huidige percentage zegt dan niets.
    if vergelijking and vergelijking.get("previous", {}).get("evenementen"):
        verschil = vergelijking.get("changes", {}).get("opkomst_percentage", {})
        stap = verschil.get("percentage_points")
        waarmee = ("de eerste helft van de periode" if vergelijking.get("halves")
                   else "de voorgaande vergelijkbare periode")
        aanhef = ("In de tweede helft van de periode ligt" if vergelijking.get("halves")
                  else "Ten opzichte van de voorgaande vergelijkbare periode is")
        if stap is not None and stap:
            richting = ("hoger" if stap > 0 else "lager") if vergelijking.get("halves") else (
                "gestegen" if stap > 0 else "gedaald")
            staart = (f" dan in {waarmee}." if vergelijking.get("halves") else ".")
            zinnen.append(
                f"{aanhef} het gemiddelde opkomstpercentage "
                f"{procent(abs(stap))[:-1]} procentpunt {richting}{staart}"
            )
        elif stap is not None:
            zinnen.append(
                f"Het gemiddelde opkomstpercentage is gelijk aan dat in {waarmee}."
            )
    beste = ranked_events(summaries)
    if len(beste) >= 2 and beste[0]["turnout"] > 0:
        zinnen.append(
            f"De hoogste opkomst had {beste[0].get('name', 'een evenement')} "
            f"met {procent(beste[0]['turnout'])}; de laagste {beste[-1].get('name', 'een evenement')} "
            f"met {procent(beste[-1]['turnout'])}. Dit is een waarneming, geen verklaring."
        )
    return " ".join(zinnen)


def default_title(selectie: dict | None) -> str:
    """Een logische titel die de gebruiker daarna zelf mag aanpassen."""
    selectie = selectie or {}
    since, until = selectie.get("since"), selectie.get("until")
    if since and until and since.year == until.year:
        kwartaal_start = (since.month - 1) // 3
        if since.month == kwartaal_start * 3 + 1 and until.month == kwartaal_start * 3 + 3:
            return f"Trendsrapport Q{kwartaal_start + 1} {since.year}"
        if since.month == 1 and until.month == 12:
            return f"Trendsrapport {since.year}"
        return f"Trendsrapport {MAANDEN[since.month - 1]}–{MAANDEN[until.month - 1]} {since.year}"
    if until:
        return f"Trendsrapport tot {datum_tekst(until)}"
    return "Trendsrapport"


def dataset_summary(summaries: list[dict], selectie: dict | None) -> list[tuple[str, str]]:
    """De compacte beschrijving van de dataset boven aan stap 1."""
    selectie = selectie or {}
    kpis = overview_kpis(summaries)
    keuzes = " · ".join([
        selectie.get("template_name") or (selectie.get("template_id") and "Geselecteerd template") or "Alle templates",
        selectie.get("event_type") or "Alle evenementsoorten",
        selectie.get("location") or "Alle locaties",
    ])
    eerste, laatste, afgeleid = effective_range(summaries, dict(selectie, since=None, until=None)) \
        if not (selectie.get("since") and selectie.get("until")) \
        else (selectie["since"], selectie["until"], False)
    periode = periode_tekst(eerste, laatste) + (" (alles wat bekend is)" if afgeleid else "")
    return [
        ("Rapportperiode", periode),
        ("Selectie", keuzes),
        ("Dataset", f"{meervoud(kpis['evenementen'], 'evenement', 'evenementen')} · "
                    f"{meervoud(kpis['aangemeld'], 'aanmelding', 'aanmeldingen')}"),
        ("Groepswaarden", "Percentage van totaal én aantal" if selectie.get("percentage_of_total") else "Aantallen"),
        *([("Getoonde groepen", "; ".join(f"{dimension}: {', '.join(groups) or 'geen'}" for dimension, groups in selectie["group_selections"].items()) + ". Kerncijfers en noemers blijven over de volledige evenementselectie.")] if selectie.get("group_selections") else []),
        ("Weergave", DISPLAY_LABELS[selected_display(selectie)]),
        *([] if selected_display(selectie) == STATISTIEKEN
          else [("Tijdseenheid", PERIOD_LABELS[selected_period(selectie)])]),
        ("Deelnemers", "Inclusief introducees" if selectie.get("include_introducees") else "Reguliere deelnemers"),
    ]


# ------------------------------------------------------------------- blokken

def _kpi_block(summaries: list[dict]) -> dict:
    kpis = overview_kpis(summaries)
    return {"kind": "kpis", "items": [
        ("Evenementen", getal(kpis["evenementen"])),
        ("Aanmeldingen", getal(kpis["aangemeld"])),
        ("Aanwezigen", getal(kpis["aanwezig"])),
        ("No-shows", getal(kpis["noshows"])),
        ("Afmeldingen", getal(kpis.get("afgemeld", 0))),
        ("Gem. opkomst", procent(kpis["opkomst_percentage"])),
        ("No-showpercentage", procent(kpis["noshow_percentage"])),
    ]}


def _comparison_block(vergelijking: dict) -> dict:
    labels = [
        ("evenementen", "Evenementen", getal),
        ("aangemeld", "Aanmeldingen", getal),
        ("aanwezig", "Aanwezigen", getal),
        ("noshows", "No-shows", getal),
        ("afgemeld", "Afmeldingen", getal),
        ("opkomst_percentage", "Gem. opkomst", procent),
        ("noshow_percentage", "No-showpercentage", procent),
    ]
    rijen = []
    nu_kop = "Tweede helft" if vergelijking.get("halves") else "Deze periode"
    eerder_kop = "Eerste helft" if vergelijking.get("halves") else "Vorige periode"
    for sleutel, label, opmaak in labels:
        nu = vergelijking["current"][sleutel]
        eerder = vergelijking["previous"][sleutel]
        verschil = vergelijking["changes"][sleutel]
        if sleutel.endswith("percentage"):
            verandering = f"{punten(verschil['absolute'])} procentpunt"
        elif verschil["percentage"] is None:
            verandering = punten(verschil["absolute"], 0)
        else:
            verandering = f"{punten(verschil['absolute'], 0)} ({punten(verschil['percentage'])}%)"
        rijen.append([label, opmaak(nu), opmaak(eerder), verandering])
    return {"kind": "table", "columns": ["Kerncijfer", nu_kop, eerder_kop, "Verandering"],
            "rows": rijen, "weights": [3, 2, 2, 2]}


def _event_rows(summaries: list[dict]) -> list[list[str]]:
    rijen = []
    for item in ranked_events(summaries):
        stats = item.get("statistiek", {})
        rijen.append([
            str(item.get("name", "")),
            str(item.get("date", "")),
            " · ".join(filter(None, [str(item.get("event_type", "")),
                                     str(item.get("location", "") or item.get("place", ""))])),
            getal(stats.get("aangemeld", 0)),
            getal(stats.get("aanwezig", 0)),
            procent(item["turnout"]),
        ])
    return rijen


DISTRIBUTION_COLUMNS = ["Aanmeldingen", "Aandeel", "Aanwezig", "No-shows",
                        "Afmeldingen", "Opkomst"]


def _distribution_rows(summaries: list[dict], dimensie: str,
                       percentage_of_total: bool = False) -> list[list[str]]:
    """Per groep de vier standen, zodat te zien is waar de uitval zit.

    Een momentopname van voor schema 4 kent geen afmeldingen per groep; die
    cel blijft dan leeg in plaats van ten onrechte nul te tonen.
    """
    totalen = sorted(series_totals(build_series(summaries, "aangemeld", dimensie, "year")),
                     key=lambda item: item[1], reverse=True)
    per_stand = {
        stand: dict(series_totals(build_series(summaries, stand, dimensie, "year")))
        for stand in ("aanwezig", "noshows", "afgemeld", "opkomst_percentage")
    }
    alles = sum(waarde for _naam, waarde in totalen) or 1
    stand_totalen = {
        stand: sum(value or 0 for value in waarden.values())
        for stand, waarden in per_stand.items()
        if stand != "opkomst_percentage"
    }

    def cel(stand, naam, opmaak=getal):
        waarde = per_stand[stand].get(naam)
        if waarde is None:
            return "—"
        if percentage_of_total and stand != "opkomst_percentage":
            totaal = stand_totalen.get(stand, 0)
            aandeel = waarde / totaal * 100 if totaal else 0
            return f"{opmaak(waarde)} ({procent(aandeel)})"
        return opmaak(waarde)

    return [[naam, getal(waarde), procent(waarde / alles * 100),
             cel("aanwezig", naam), cel("noshows", naam), cel("afgemeld", naam),
             cel("opkomst_percentage", naam, procent)]
            for naam, waarde in totalen]


def build_report_model(summaries: list[dict], config: dict) -> dict:
    """Zet de gekozen dataset en configuratie om in rapportblokken.

    Levert de secties in de ingestelde volgorde, elk met hun blokken. Een
    sectie zonder bruikbare inhoud verdwijnt; zo blijven er geen lege koppen
    in het rapport staan.
    """
    config = prepare_config(config)
    selectie = config["selectie"]
    summaries = participant_scope(
        summaries, bool(selectie.get("include_introducees", True))
    )
    gekozen = selected_summaries(summaries, selectie)
    vormgeving = config["vormgeving"]
    tijdseenheid = chart_period(selectie)

    since, until, afgeleid = effective_range(summaries, selectie)
    vergelijking = None
    if since and until and gekozen:
        try:
            # Bij een zelfgekozen periode is er een echte vorige periode; bij
            # 'alles wat bekend is' bestaat die niet en kijken we binnen de
            # periode zelf.
            vergelijking = (compare_within(gekozen, since, until) if afgeleid
                            else compare_periods(selected_summaries(summaries, dict(selectie, since=None, until=None)), since, until))
        except (TypeError, ValueError, ZeroDivisionError):
            vergelijking = None

    # Welke uitsplitsingen krijgen al een eigen hoofdstuk met tabel? Die hoeven
    # onder Detailtabellen niet nog eens.
    al_getoond = {
        SECTION_DIMENSION[item["key"]] for item in config["secties"]
        if item.get("aan") and item["key"] in SECTION_DIMENSION
    }

    secties = []
    seen_single_series = set()
    for onderdeel in config["secties"]:
        if not onderdeel.get("aan"):
            continue
        sleutel = onderdeel["key"]
        definitie = SECTION_BY_KEY[sleutel]
        try:
            blokken = _section_blocks(
                sleutel, definitie, onderdeel, gekozen, vergelijking, tijdseenheid,
                bool(selectie.get("percentage_of_total")), al_getoond,
            )
            selections = selectie.get("group_selections") or {}
            if sleutel == "huidige_analyse":
                from emt_trends import METRICS
                metric = selectie.get("analysis_metric", "opkomst_percentage")
                dimension = selectie.get("analysis_dimension", "")
                series = select_series_groups(build_series(gekozen, metric, dimension, tijdseenheid,
                    percentage_of_total=bool(selectie.get("percentage_of_total"))), selections)
                title = dict((key, label) for label, key in METRICS).get(metric, metric)
                value_title = "Aandeel / aantal" if series.get("percentage_of_total") else title
                if series.get("percentage_of_total"):
                    title = "Aandeel " + title.lower()
                title += f" — {dimension}" if dimension else ""
                title += " (hele selectie)" if tijdseenheid == "total" else " door de tijd"
                blokken = [{"kind": "chart", "title": title, "series": series, "chart_key": "huidige_analyse"}]
                values = [[point["label"], group,
                           (procent(point["values"][group]) + f" ({getal(point['raw_values'][group])})") if series.get("percentage_of_total") else
                           procent(point["values"][group]) if series["display_metric"].endswith("percentage") else getal(point["values"][group])]
                          for point in series["points"] for group in series["groups"]]
                blokken.append({"kind": "table", "columns": ["Periode", "Groep", value_title], "rows": values, "weights": [3, 4, 3]})
            for block in blokken:
                if block["kind"] == "chart":
                    block["series"] = select_series_groups(block["series"], selections)
                elif block["kind"] == "table" and block.get("dimension") in selections:
                    block["rows"] = [row for row in block["rows"] if row[0] in selections[block["dimension"]]]
            blokken = [block for block in blokken if not
                       (block["kind"] == "chart" and not block["series"].get("groups")) and not
                       (block["kind"] == "table" and not block["rows"])]
            unique = []
            for block in blokken:
                series = block.get("series", {})
                if block["kind"] == "chart" and len(series.get("groups", [])) == 1 and series.get("dimension", "") in {"", "event_type", "place", "location"}:
                    signature = (series["metric"], series["period"], tuple((point["label"], tuple(point["values"].values())) for point in series["points"]))
                    if signature in seen_single_series:
                        continue
                    seen_single_series.add(signature)
                unique.append(block)
            blokken = unique
        except Exception:  # noqa: BLE001
            # Liever een rapport zonder dit onderdeel dan helemaal geen
            # rapport; de overige secties zijn nog gewoon bruikbaar.
            blokken = []
        if blokken:
            titel = definitie["title"]
            if sleutel == "vergelijking" and (vergelijking or {}).get("halves"):
                titel = "Ontwikkeling binnen de periode"
            secties.append({"key": sleutel, "title": titel, "blocks": blokken})

    kpis = overview_kpis(gekozen)
    return {
        "bron": str(selectie.get("bron", "") or ""),
        "titel": config["titel"] or default_title(dict(selectie, since=since, until=until)),
        "subtitel": config["subtitel"],
        "periode": periode_tekst(since, until) + (" (alles wat bekend is)" if afgeleid else ""),
        "filters": dataset_summary(gekozen, selectie),
        "vormgeving": vormgeving,
        "kpis": kpis,
        "sections": secties,
        "summaries": gekozen,
        "selectie": selectie,
        "preset": config["preset"],
        "vergelijking": vergelijking,
    }


def _section_blocks(sleutel, definitie, onderdeel, gekozen, vergelijking,
                    tijdseenheid: str = "month", percentage_of_total: bool = False,
                    al_getoond=()) -> list[dict]:
    """De blokken van één rapportonderdeel.

    ``al_getoond`` bevat de uitsplitsingen die al een eigen hoofdstuk met
    tabel hebben. Detailtabellen slaat die over: dezelfde tabel twee keer in
    één rapport voegt niets toe en laat de lezer zoeken naar het verschil.
    """
    blokken = []

    if sleutel == "voorblad":
        return []  # het voorblad regelt de opmaak zelf
    if sleutel == "samenvatting":
        blokken.append({"kind": "paragraph", "text": management_summary(gekozen, vergelijking)})
    elif sleutel == "kerncijfers":
        blokken.append(_kpi_block(gekozen))
    elif sleutel == "vergelijking" and vergelijking and vergelijking["previous"]["evenementen"]:
        if vergelijking.get("halves"):
            blokken.append({"kind": "paragraph", "text":
                            "Er is geen voorgaande periode om mee te vergelijken, dus staat hier "
                            "de ontwikkeling binnen de periode zelf. Tweede helft: "
                            f"{periode_tekst(*vergelijking['current_range'])}. Eerste helft: "
                            f"{periode_tekst(*vergelijking['previous_range'])}."})
        else:
            blokken.append({"kind": "paragraph", "text":
                            f"Deze periode: {periode_tekst(*vergelijking['current_range'])}. "
                            f"Vorige periode: {periode_tekst(*vergelijking['previous_range'])}."})
        blokken.append(_comparison_block(vergelijking))
    elif sleutel == "inzichten":
        for inzicht in generate_insights(gekozen):
            blokken.append({"kind": "insight", "title": inzicht["title"],
                            "detail": inzicht["detail"]})
    elif sleutel == "evenementen":
        rijen = _event_rows(gekozen)
        if rijen:
            blokken.append({"kind": "table",
                            "columns": ["Evenement", "Datum", "Soort / locatie",
                                        "Aanmeldingen", "Aanwezig", "Opkomst"],
                            "rows": rijen, "weights": [4, 2, 3, 2, 2, 2]})
    elif sleutel == "detailtabellen":
        for dimensie, titel in (("Opleidingsniveau", "Opleidingsniveau"),
                                ("Profiel", "Opleidingsprofiel"),
                                ("Geslacht", "Geslacht"),
                                ("Leeftijdsgroep", "Leeftijdsgroep")):
            if dimensie not in available_dimensions(gekozen) or dimensie in al_getoond:
                continue
            rijen = _distribution_rows(gekozen, dimensie, percentage_of_total)
            if rijen:
                blokken.append({"kind": "subheading", "text": titel})
                blokken.append({"kind": "table",
                                "dimension": dimensie,
                                "columns": [titel, *DISTRIBUTION_COLUMNS],
                                "rows": rijen, "weights": [4, 2, 2, 2, 2, 2, 2]})
    elif sleutel in SECTION_DIMENSION:
        rijen = _distribution_rows(
            gekozen, SECTION_DIMENSION[sleutel], percentage_of_total
        )
        if rijen:
            blokken.append({"kind": "table",
                            "columns": [definitie["title"], *DISTRIBUTION_COLUMNS],
                            "dimension": SECTION_DIMENSION[sleutel],
                            "rows": rijen, "weights": [4, 2, 2, 2, 2, 2, 2]})

    for grafiek in definitie["charts"]:
        if not onderdeel["grafieken"].get(grafiek["key"], True):
            continue
        reeks = build_series(
            gekozen, grafiek["metric"], grafiek["dimension"], tijdseenheid,
            percentage_of_total=percentage_of_total,
        )
        if not (reeks.get("points") and reeks.get("groups")):
            continue
        blokken.insert(
            len([blok for blok in blokken if blok["kind"] in {"paragraph", "kpis", "chart"}]),
            {"kind": "chart", "title": grafiek["title"], "series": reeks,
             "chart_key": grafiek["key"]},
        )
    return blokken


def landscape_advised(model: dict) -> bool:
    """Liggend zodra een tabel echt te breed is voor een staande pagina.

    Zes kolommen passen prima staand; pas daarboven wordt het knijpen. Staand
    is verder prettiger, want er passen meer grafieken onder elkaar.
    """
    for sectie in model.get("sections", []):
        for blok in sectie["blocks"]:
            if blok["kind"] == "table" and len(blok["columns"]) >= 7:
                return True
    return False


def page_orientation(model: dict) -> str:
    keuze = str(model.get("vormgeving", {}).get("orientatie", "auto") or "auto")
    if keuze in {"staand", "liggend"}:
        return keuze
    return "liggend" if landscape_advised(model) else "staand"
