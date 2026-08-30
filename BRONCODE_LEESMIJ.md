# EventHub — broncode 2.16.2

Dit pakket bevat de bewerkbare broncode van EventHub 2.16.2. Het bevat geen echte
deelnemersgegevens, opgeslagen evenementen of Windows-runtime met duizenden
losse bestanden.

## Belangrijkste bestanden

- `bezoekerslijst_app.py`: vensters, tabbladen en gebruikersinteractie.
- `bezoekerslijst_core.py`: Excel-import, gegevensherkenning en Excel-export.
- `emt_models.py`: evenementen, taken, templates en meldingen.
- `emt_rudder.py`: veilige Rudder-URL's, gegevensvalidatie en veldmapping.
- `emt_documents.py`: 5WH- en evaluatie-export.
- `server/`: Event Control, gedeelde live sessies, lokale webinterface en database.
- `browser_extension/`: lokale Edge/Chrome-assistent voor Rudder-evenementen en aanwezigheidsregistratie.
- `templates/`: de drie vaste documenttemplates.
- `eventhub_logo.png`: transparant logo voor de applicatie-interface.
- `eventhub_icon.png` en `eventhub.ico`: pictogram met kader voor Windows en installers.
- `server/web/static/icons/`: favicon-, iOS- en PWA-pictogrammen voor de browserclient.

Houd de Python-bestanden, afbeeldingen en de mappen `templates`, `theme` en `server` altijd bij elkaar.

## Openen in een AI-code-editor

Open deze hele map in Cursor, VS Code/Cline of een vergelijkbare editor. Geef
opdrachten bij voorkeur klein en controleerbaar, bijvoorbeeld:

> Verander alleen de tekst van de knop WhatsApp-berichten naar Bericht sturen.
> Behoud compatibiliteit met bestaande .bvp-bestanden, voer een syntaxcontrole
> uit en laat eerst zien welke bestanden je gaat wijzigen.

Laat de editor niet werken met echte `.bvp`-bestanden, deelnemerslijsten of
exports met persoonsgegevens. Gebruik voor tests uitsluitend fictieve gegevens.

## Starten op macOS

Dubbelklik op `START_EMT_MAC.command`. Bij de eerste start wordt lokaal een
afgeschermde Python-omgeving aangemaakt en worden de drie benodigde pakketten
geïnstalleerd. Hiervoor is alleen bij die eerste installatie internet nodig.

Handmatig starten kan ook:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 bezoekerslijst_app.py
```

## Starten op Windows

Dubbelklik op `START_EMT_WINDOWS.bat`. De eerste start maakt een lokale
Python-omgeving en installeert de afhankelijkheden. Python 3.12 moet aanwezig
zijn en aan PATH zijn toegevoegd.

## Installer bouwen

Installeer Python 3.12 en Inno Setup 6 en dubbelklik daarna op
`BUILD_EVENTHUB_INSTALLER.bat`. Het script bouwt EventHub inclusief Event Control
en maakt vervolgens `installer\EventHub-Setup-v2.16.2.exe`.

## Veilig wijzigen

1. Maak vóór iedere wijziging een kopie of Git-commit.
2. Laat de AI eerst een plan maken.
3. Vraag om kleine wijzigingen per keer.
4. Laat na iedere wijziging syntax- en importcontroles uitvoeren.
5. Test altijd met een kopie van een fictief `.bvp`-bestand.
6. Controleer vooral import, autosave, bestaande dossiers en documentexports.
