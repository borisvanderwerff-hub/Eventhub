"""De brontekst van de bureaubladapplicatie als één tekst.

Een deel van de tests controleert de code zelf: staat een knop in dezelfde rij,
wordt een bestaande hulpfunctie gebruikt, enzovoort. Sinds de schermonderdelen
in eigen modules staan, is "de bureaubladcode" niet langer één bestand. Deze
functie plakt het hoofdbestand en die modules achter elkaar, zodat zulke tests
blijven kijken naar alles wat bij de applicatie hoort.
"""
from pathlib import Path

# Het hoofdbestand eerst; daarna de schermmodules die eruit zijn gehaald.
DESKTOP_FILES = (
    "bezoekerslijst_app.py",
    "emt_base.py",
    "emt_widgets.py",
    "emt_whatsapp_ui.py",
    "emt_dialogs.py",
    "emt_live_ui.py",
    "emt_trends_panel.py",
    "emt_trend_charts_ui.py",
    "emt_tutorial.py",
)


def desktop_source(root: Path) -> str:
    parts = []
    for name in DESKTOP_FILES:
        path = Path(root) / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)
