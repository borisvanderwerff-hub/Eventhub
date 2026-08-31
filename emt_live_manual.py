"""Handleiding livesessies, als deelbaar document.

Los van de applicatiecode gehouden zodat de tekst zonder Qt te controleren is
en de handleiding meegroeit met de werkelijke schermen. Bevat geen
persoonsgegevens en mag dus vrij worden meegestuurd naar medewerkers.
"""
from __future__ import annotations

from datetime import date

MANUAL_TITLE = "Livesessie: samen inchecken met EventHub"

# De stappen volgen de echte schermen: apparaatnaam en viercijferige
# sessiecode op de verbindpagina, en de rol die een beheerder toekent.
_SECTIONS = [
    (
        "Wat u nodig heeft",
        [
            "Een laptop waarop EventHub draait. Die is de host van de sessie.",
            "Telefoons, tablets of laptops voor de medewerkers die inchecken.",
            "Eén gedeeld netwerk. Alle apparaten moeten op hetzelfde wifi zitten.",
            "Internet is niet nodig: het verkeer blijft binnen het lokale netwerk.",
        ],
    ),
    (
        "1. De sessie starten (host)",
        [
            "Open in EventHub het evenement en ga naar Event Control, tabblad Live sessie.",
            "Kies Live sessie starten. Naam, datum, locatie en de al ingeladen deelnemers "
            "worden uit het evenement overgenomen.",
            "Iedereen begint als niet ingecheckt, ook wie eerder aanwezig was.",
            "Het venster toont een QR-code, een netwerkadres en een sessiecode van vier cijfers. "
            "Laat dit scherm openstaan zolang de sessie loopt.",
        ],
    ),
    (
        "2. Een apparaat aanmelden (medewerker)",
        [
            "Scan de QR-code, of typ het getoonde netwerkadres in de browser.",
            "Vul een herkenbare apparaatnaam in, bijvoorbeeld Balie 1 of Ingang Noord. "
            "Die naam ziet de host terug bij de verbonden apparaten.",
            "Vul de sessiecode van vier cijfers in en kies Verbinden.",
            "Op een iPhone of iPad kunt u de pagina via Deel en Zet op beginscherm "
            "schermvullend openen; dat werkt prettiger dan een browsertabblad.",
        ],
    ),
    (
        "3. Eerst een rol laten toekennen",
        [
            "Een nieuw apparaat start als Viewer en kan dan alleen meekijken.",
            "De host wijst de rol Check-in toe via Apparaten in de Server Manager.",
            "Kunt u niemand inchecken? Dan staat het apparaat vrijwel zeker nog op Viewer.",
        ],
    ),
    (
        "4. Inchecken",
        [
            "Zoek de bezoeker op naam, geboortedatum of geboorteplaats.",
            "Kies Inchecken bij de juiste persoon. Alle apparaten zien de wijziging direct.",
            "Vergissing? Kies Ongedaan maken bij dezelfde persoon.",
            "Vertrekt iemand tussentijds, dan kunt u Uitchecken gebruiken. Die persoon telt "
            "nog steeds als aanwezig geweest.",
            "Staat iemand niet op de lijst? Meld dat bij de host; toevoegen gebeurt op de "
            "hostlaptop, niet op het apparaat.",
        ],
    ),
    (
        "5. Als er iets misgaat",
        [
            "Netwerk even weg? Blijf gewoon doorwerken. Het apparaat bewaart de handelingen "
            "en verstuurt ze zodra de verbinding terug is.",
            "Twijfelt u of alles is aangekomen? Kies Nu synchroniseren.",
            "Loopt een apparaat vast, sluit de pagina en meld opnieuw aan met dezelfde "
            "sessiecode. Er gaat niets verloren.",
            "De host kan het inchecken tijdelijk stilleggen met Inchecken pauzeren, "
            "bijvoorbeeld tijdens een telling.",
        ],
    ),
    (
        "6. Calamiteitenmodus",
        [
            "Alleen een eventmanager of beheerder kan deze modus starten en beëindigen.",
            "Iedereen die op dat moment binnen is, komt op een aparte controlelijst.",
            "Alle verbonden apparaten tonen schermvullend de instructie.",
            "Meld personen veilig via Personen controleren en leg de verzamelplaats vast.",
            "De gewone aanwezigheidsregistratie verandert hier niet door.",
        ],
    ),
    (
        "7. Na afloop",
        [
            "De host beëindigt het inchecken en sluit de sessie.",
            "In- en uitchecken loopt automatisch terug naar de aanwezigheid in het "
            "evenementdossier.",
            "Presentie, statistieken en de export naar Rudder sluiten daarop aan.",
        ],
    ),
]

_PRIVACY = (
    "Persoonsgegevens van bezoekers blijven binnen EventHub en worden na de ingestelde "
    "bewaartermijn automatisch verwijderd. Exporteer alleen wat nodig is en ruim "
    "geëxporteerde bestanden zelf op tijd op."
)


def manual_sections() -> list[tuple[str, list[str]]]:
    return [(title, list(items)) for title, items in _SECTIONS]


def manual_html(prepared_by: str = "", today: date | None = None) -> str:
    """Bouw de handleiding op als afdrukbaar document."""
    today = today or date.today()
    blocks = []
    for title, items in _SECTIONS:
        steps = "".join(f"<li>{item}</li>" for item in items)
        blocks.append(f'<h2>{title}</h2><ul>{steps}</ul>')
    footer = f"EventHub, {today:%d-%m-%Y}"
    if prepared_by:
        footer += f" — opgesteld door {prepared_by}"
    return f"""
        <html><head><style>
        body {{ font-family: 'Segoe UI'; color: #17233a; font-size: 10pt; }}
        h1 {{ font-size: 18pt; margin-bottom: 2px; }}
        p.lead {{ color: #55637a; margin-top: 0; font-size: 10pt; }}
        h2 {{ font-size: 12pt; margin-top: 16px; margin-bottom: 4px; color: #2f2478; }}
        ul {{ margin-top: 0; }}
        li {{ margin-bottom: 4px; }}
        p.note {{ background: #f2f4f9; padding: 8px; font-size: 9pt; margin-top: 18px; }}
        p.footer {{ color: #7b8798; font-size: 8pt; margin-top: 14px; }}
        </style></head><body>
        <h1>{MANUAL_TITLE}</h1>
        <p class="lead">Voor medewerkers die op locatie bezoekers inchecken met een telefoon,
        tablet of laptop. Bewaar deze pagina bij de hand tijdens het evenement.</p>
        {''.join(blocks)}
        <p class="note"><b>Privacy.</b> {_PRIVACY}</p>
        <p class="footer">{footer}</p>
        </body></html>
    """
