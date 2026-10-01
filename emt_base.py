"""Gedeelde basis voor de EventHub-schermen: bestandslocaties, versie en de kleine
evenementhulpjes die zowel het hoofdvenster als de losse schermonderdelen gebruiken.

Deze module kent de rest van EventHub niet; iedereen mag hem importeren.
"""
from __future__ import annotations

from datetime import datetime, time
from pathlib import Path
import os
import sys

from PySide6.QtCore import QStandardPaths, QTime

from bezoekerslijst_core import normalize
from emt_models import parse_date


APP_NAME = "EventHub"


APP_VERSION = "0.2.4 Beta"


def bundled_resource(relative_path):
    """Vind meegeleverde bestanden in broncode én geïnstalleerde builds."""
    roots = [Path(__file__).resolve().parent]
    if getattr(sys, "frozen", False):
        installed = Path(sys.executable).resolve().parent
        roots = [installed, Path(getattr(sys, "_MEIPASS", installed / "_internal")), *roots]
    return next((root / relative_path for root in roots if (root / relative_path).exists()),
                roots[0] / relative_path)


LOGO_PATH = bundled_resource("eventhub_logo.png")


APP_ICON_PATH = bundled_resource("eventhub.ico")


SETTINGS_ICON_PATH = bundled_resource("settings_gear.png")


SIDEBAR_ICON_DIR = bundled_resource("assets/sidebar")


NEON_WAVES_PATH = bundled_resource("assets/backgrounds/neon_waves.png")


HEADER_WAVE_PATH = bundled_resource("assets/backgrounds/header_wave.png")


def event_last_seen(event: dict):
    """Wanneer dit evenement voor het laatst is geopend, of niets."""
    return parse_timestamp(event.get("last_opened_at", ""))


def event_last_touched(event: dict):
    """Wanneer er voor het laatst iets aan is veranderd, of niets."""
    return parse_timestamp(event.get("updated_at", ""))


def event_activity_line(event: dict) -> str:
    """De onderste regel van een kaart: wat weten we van het laatste gebruik?"""
    gewijzigd = event_last_touched(event)
    if gewijzigd:
        return f"Laatst gewijzigd: {gewijzigd.strftime('%d-%m-%Y %H:%M')}"
    geopend = event_last_seen(event)
    if geopend:
        return f"Laatst geopend: {geopend.strftime('%d-%m-%Y %H:%M')}"
    return "Nog niet geopend"


def event_end_moment(event: dict):
    """Het moment waarop dit evenement voorbij is, zo precies als bekend.

    Alleen op datum vergelijken zette een meeloopdag die om twaalf uur klaar
    was de rest van de dag nog onder 'komt nog'. Staat er een eindtijd, dan
    telt die; anders de starttijd; anders het einde van de dag.
    """
    datum = parse_date(str(event.get("date", "") or ""))
    if not datum:
        return None
    for veld in ("end_time", "start_time"):
        klok = QTime.fromString(str(event.get(veld, "") or "").strip(), "HH:mm")
        if klok.isValid():
            return datetime.combine(datum, time(klok.hour(), klok.minute()))
    return datetime.combine(datum, time(23, 59))


def event_has_passed(event: dict) -> bool:
    moment = event_end_moment(event)
    return bool(moment and moment < datetime.now())


def event_recency_key(event: dict):
    """Meest recent gebruikt eerst; wat nooit is aangeraakt sluit achteraan."""
    moment = event_last_touched(event) or event_last_seen(event)
    return (moment is None, -(moment.timestamp() if moment else 0), normalize(event.get("name", "")))


def parse_timestamp(value):
    """Een ISO-tijdstip uit het dossier, of niets als het er niet staat."""
    tekst = str(value or "").strip()
    if not tekst:
        return None
    try:
        return datetime.fromisoformat(tekst)
    except ValueError:
        return None


# Vaste naam van de map met applicatiegegevens: back-ups, herstelkopie,
# logboeken en cache.
APP_DATA_ORGANISATION = "DCPL"


def application_data_root():
    """De map met applicatiegegevens, altijd op dezelfde plek.

    Eerder werd dit uit QStandardPaths gehaald, maar dat leidt de naam af van
    de applicatienaam die pas in main() wordt gezet. Wie deze functie eerder
    aanriep, bijvoorbeeld vanuit een test of een los script, kreeg een map
    vernoemd naar het draaiende programma. Zo belandden logbestanden naast de
    installatiebestanden van Python.

    De locatie wordt daarom rechtstreeks bepaald, net als in server/paths.py.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Local"
        root = root / APP_DATA_ORGANISATION / APP_NAME
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / APP_DATA_ORGANISATION / APP_NAME
    else:
        base = os.environ.get("XDG_DATA_HOME")
        root = (Path(base) if base else Path.home() / ".local" / "share") / APP_DATA_ORGANISATION / APP_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def program_directory():
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        for parent in executable.parents:
            if parent.suffix == ".app":
                return parent.parent
        return executable.parent
    return Path(__file__).resolve().parent


def documents_directory():
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    base = Path(location) if location else Path.home() / "Documents"
    base.mkdir(parents=True, exist_ok=True)
    return base


def projects_directory():
    base = documents_directory() / "EventHub"
    base.mkdir(parents=True, exist_ok=True)
    return base


def exports_directory():
    base = projects_directory() / "Exports"
    base.mkdir(parents=True, exist_ok=True)
    return base
