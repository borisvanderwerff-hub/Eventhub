"""Controleer de afbeeldingen en extensie vóór het verpakken van EventHub."""
from pathlib import Path
import sys


def verify(bundle):
    source = Path(__file__).resolve().parent
    required = [Path(name) for name in (
        "eventhub_logo.png", "eventhub_icon.png", "eventhub.ico", "settings_gear.png",
        "browser_extension/manifest.json",
    )]
    required.extend(path.relative_to(source) for path in (source / "assets").rglob("*") if path.is_file())
    missing = [str(path) for path in required
               if not any((root / path).is_file() for root in (bundle, bundle / "_internal"))]
    if missing:
        raise SystemExit("Onvolledige Windows-build; ontbrekende bestanden:\n" + "\n".join(missing))
    print(f"Windows-build gecontroleerd: {len(required)} bestanden aanwezig.")


if __name__ == "__main__":
    verify(Path(sys.argv[1] if len(sys.argv) > 1 else "dist/EventHub"))
