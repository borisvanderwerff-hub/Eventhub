# EventHub — broncode 0.2.1 Beta

Dit pakket bevat de bewerkbare broncode van EventHub 0.2.1 Beta. Het bevat geen echte
deelnemersgegevens, opgeslagen evenementen of Windows-runtime met duizenden
losse bestanden.

## Codekaart: waar pas je iets aan?

Begin bij de functie of het scherm dat je wilt wijzigen. Deze kaart beschrijft de huidige indeling; bestanden met een `_ui`-achtervoegsel bevatten vooral vensters en bediening, terwijl de andere modules meestal gegevens, regels of exports afhandelen.

### Applicatie en hoofdvenster

- `bezoekerslijst_app.py`: startpunt, applicatie-instellingen en het hoofdvenster. De klasse `BezoekerslijstWindow` koppelt schermen en acties aan elkaar. Namen die eerder uit dit bestand zijn verhuisd, worden hier opnieuw geïmporteerd om bestaande imports te blijven ondersteunen.
- `emt_event_board.py`: evenementoverzicht en kaartweergave, sorteren, filteren, archiveren, eventselectie en recente activiteit. `EventBoardMixin` levert dit gedrag aan `BezoekerslijstWindow`; `event_name_with_date` blijft via `bezoekerslijst_app.py` beschikbaar.
- `emt_base.py`: appnaam en versie, standaardpaden, resources en algemene evenement-/datumhulpfuncties. Dit is de onderste gedeelde laag.
- `theme/styles.py`: centrale stylesheet en visuele basisstijl.

### Schermen en bediening

- `emt_widgets.py`: herbruikbare bedieningselementen, evenementkaarten en datum-/tijdkeuze.
- `emt_dialogs.py`: profiel-, instellingen-, evenement-, taak-, 5WH- en evaluatiedialogen.
- `emt_event_templates_ui.py`: beheer en koppeling van evenementtemplates.
- `emt_whatsapp_ui.py`: WhatsApp-sjablonen en berichtenwachtrij.
- `emt_live_ui.py`: live-incheckvensters, Rudder-koppeling en lokale browserbrug.
- `emt_live_manual.py`: inhoud van de handleiding voor live sessies.
- `emt_trends_panel.py`: het Trendscherm, filters en trendselectie.
- `emt_trend_charts_ui.py`: herbruikbare grafiek- en kruistabelwidgets voor Trends en Statistieken. De bestaande imports via `emt_trends_panel.py` blijven beschikbaar.
- `emt_trend_selection_ui.py`: keuzevenster voor trendgroepen.
- `emt_tutorial.py`: interactieve rondleiding door de interface.
- `emt_report_ui.py`: rapportbouwer en rapportvoorbeeld.
- `emt_report_layout.py`: opmaak en pagina-indeling van rapporten.

### Gegevens, regels en bestanden

- `bezoekerslijst_core.py`: compatibele ingang voor deelnemersrecords, evenement/deelnemer-samenvoeging en registratie-import. De bestaande importnamen blijven hier beschikbaar als compatibele doorverwijzingen.
- `emt_attendance.py`: aanwezigheidsstanden per evenement, migratie van oude waarden, terugbelstatus, normalisatie en algemene teksthulpfuncties. Begin hier bij wijzigingen aan aanwezigheids- of terugbelregels.
- `emt_registration_import.py`: herkenning van Excel-kolommen, lezen van `.xlsx`/`.xls`, koppelen aan evenementen, deelnemers aanvullen en dubbele registraties afhandelen. Begin hier bij wijzigingen aan deelnemersimport; bestaande aanroepen via `bezoekerslijst_core.py` blijven werken.
- `emt_excel_export.py`: export van deelnemerslijsten, vaste deelnemerslijsttemplates, statistiekwerkmappen en kruistabellen. Begin hier bij wijzigingen aan een Excel-uitvoer; de bestaande exports blijven via `bezoekerslijst_core.py` beschikbaar.
- `emt_models.py`: standaardstructuren en normalisatie van evenementen, taken, templates en profielgegevens.
- `emt_event_templates.py`: omzetting van templates naar evenementgegevens.
- `emt_rudder.py`: Rudder-URL's, validatie, veldmapping en synchronisatiegegevens.
- `emt_retention.py`: bewaartermijnen, opschoonplanning en anonimisering van gegevens.
- `emt_education.py`: herkenning en groepering van opleidingsniveaus en kruistabellen.
- `emt_history.py`: historische gegevens, verdelingen en doorsneden voor analyses.
- `emt_trends.py`: trendberekeningen, samenvattingen en opgeslagen analysebestanden.
- `emt_charts.py`: gedeelde teken- en opmaakfuncties voor grafieken.
- `emt_report.py`: rapportconfiguratie, tekstlabels en samenstelling van rapportinhoud.
- `emt_report_export.py`: PDF-, Excel- en afbeeldingsuitvoer van rapporten.
- `emt_documents.py`: invullen en exporteren van 5WH- en evaluatiedocumenten.

### Event Control en browserassistent

- `server/paths.py`, `server/network.py`, `server/logging_setup.py`: paden, netwerkconfiguratie en logging van de lokale server.
- `server/database.py`, `server/registry.py`, `server/events_hub.py`: sessiedatabase, registratie en gedeelde evenement-/sessietoestand.
- `server/importer.py`, `server/registration_import.py`, `server/exporter.py`, `server/qrgen.py`: deelnemersimport, registratie-import, exports en QR-codes.
- `server/services/`: serverregels per onderwerp: sessies, deelnemers, clientverbindingen, statistieken en noodmeldingen.
- `server/manager/`: desktopvenster waarmee Event Control wordt beheerd; `manager_window.py` bevat het hoofdscherm.
- `server/web/`: lokale webserver en browserinterface. De pagina's staan in `server/web/templates/`, de stijlen en scripts in `server/web/static/`.
- `browser_extension/`: Edge-/Chrome-assistent. `rudder_scrape.js` en `event_bulk.js` verzorgen ophalen van evenementgegevens; `event_edit.js`, `event_list.js` en `event_registrations.js` ondersteunen de evenement- en aanwezigheidsacties; `background.js` en `content.js` koppelen de extensie aan de browserpagina.
- `templates/`: vaste Word- en Excel-documenttemplates. `assets/` bevat interface-afbeeldingen en `server/assets/` serverafbeeldingen.
- `server/tests/`: automatische controles en regressietests voor server- en applicatiegedrag.

Houd de Python-bestanden, afbeeldingen en de mappen `templates`, `theme` en `server` bij elkaar. De buildbestanden verwijzen naar deze structuur.

### Import- en wijzigingsrichting

De gedeelde schermlaag loopt van `emt_base` naar `emt_widgets`, daarna naar de losse scherm- en functiemodules, en eindigt bij `bezoekerslijst_app`. `emt_event_board` is een mixin die het hoofdvenster uitbreidt; hij importeert het hoofdvenster zelf niet. Importeer `bezoekerslijst_app` dus nooit vanuit een `emt_`-module, want dat kan een kringverwijzing veroorzaken.

Bij een schermwijziging begin je meestal bij de bijbehorende `_ui`-module. Voor gegevensregels kijk je in `bezoekerslijst_core.py`, `emt_models.py` of de domeinmodule die hierboven genoemd is. Voor rapportinhoud en -opmaak zijn `emt_report.py`, `emt_report_layout.py` en `emt_report_export.py` gescheiden verantwoordelijkheden. Werk een modulekaart bij wanneer je later een onderdeel verplaatst of een nieuwe module toevoegt.

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
en maakt vervolgens `installer\EventHub-Setup-v0.2.1 Beta.exe`.

## Veilig wijzigen

1. Maak vóór iedere wijziging een kopie of Git-commit.
2. Laat de AI eerst een plan maken.
3. Vraag om kleine wijzigingen per keer.
4. Laat na iedere wijziging syntax- en importcontroles uitvoeren.
5. Test altijd met een kopie van een fictief `.bvp`-bestand.
6. Controleer vooral import, autosave, bestaande dossiers en documentexports.
