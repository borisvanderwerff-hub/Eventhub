# Event Control

Event Control bevat in 2.16.2 drie onderdelen:

- **Live sessie**: start of hervat een lokale server en verbind meerdere apparaten via QR-code, netwerkadres en sessiecode.
- **Live dashboard**: open live opkomstcijfers en statistieken in de standaardbrowser.
- **Rudder**: exporteer de presentie rechtstreeks via een tijdelijke lokale koppeling, open de per evenement opgeslagen attendance-link en vul de pagina gecontroleerd met de Browserassistent.

De Browserassistent zet EventHub-aanwezigen op Yes en niet-aanwezigen op No. Een bestaande
Canceled-status blijft staan. Alle resterende Unknown-statussen worden in het controleoverzicht
expliciet aangekondigd voordat zij op No worden gezet. EventHub klikt nooit zelfstandig op
Aanwezigheid opslaan. De JSON-bestandsroute blijft beschikbaar als reserveoptie.

## Rudder-evenementgegevens (2.16.2)

Bij **Nieuw evenement** kunt u leeg starten, een EventHub-template gebruiken of een evenement
uit Rudder importeren. Een verse import opent eerst het Rudder-evenementenoverzicht. Nadat u daar
een evenement kiest, importeert de vaste knop op de bewerkpagina de afgesproken gegevens met één
klik. Daarna heet de EventHub-knop **Bijwerken uit Rudder** en opent hij direct de onthouden pagina.
Automatische e-mails en beveiligingsgegevens worden genegeerd. De gelijknamige EventHub-template
levert de taken; bestaande en afgeronde taken worden bij bijwerken niet gedupliceerd. Exporteren en
Openen zijn alleen zichtbaar bij een echte evenementkoppeling. Export wijzigt geen dynamische
keuzelijsten en laat de definitieve opslagklik altijd aan de gebruiker.

Bij het aanmaken van een live sessie worden naam, datum en locatie van het gekozen
EventHub-evenement vooraf ingevuld. De reeds ingeladen deelnemers worden automatisch
naar een nieuwe live sessie gekopieerd; zij starten altijd als niet ingecheckt.

Een andere EventHub Desktop-installatie kan via **Verbinden met bestaande sessie**
als native check-inclient deelnemen. Telefoons en tablets gebruiken dezelfde sessie via
de lokale browser. Internet is niet nodig; alle apparaten moeten wel op hetzelfde lokale
netwerk zitten.

## Windows-build

Installeer Python 3.12 en Inno Setup 6 en start `BUILD_EVENTHUB_INSTALLER.bat`.
De installer verschijnt als `installer\EventHub-Setup-v2.16.2.exe`.

De browserclient bevat een web-appmanifest, favicon en Apple-touch-icon. Open op iOS de live
check-inpagina in Safari en kies **Deel → Zet op beginscherm** om EventHub schermvullend te openen.

## Calamiteitenmodus (2.15.8)

- Alleen een eventmanager of beheerder kan de modus starten, instructies wijzigen of hem beëindigen.
- Iedereen die op het startmoment nog als binnen staat, wordt in een afzonderlijke calamiteitenregistratie opgenomen.
- Check-inmedewerkers kunnen personen veilig melden en daarbij een verzamelplaats en controleteam vastleggen.
- De gewone aanwezigheidsstatus verandert niet door deze controles.
- Alle verbonden browserapparaten krijgen live instructies en zien hoeveel personen nog gecontroleerd moeten worden.
- Na beëindiging blijven de incidentgegevens beschikbaar voor export naar Excel.

## Betrouwbare livesessies (2.10.0)

- Kies **Hubs zoeken** om een actieve hub op hetzelfde lokale netwerk automatisch te vinden.
- Browser- en desktopclients bewaren handelingen bij een korte netwerkstoring en synchroniseren automatisch.
- De serverbeheerder kan met **Inchecken pauzeren (freeze)** alle check-ins en check-outs tijdelijk blokkeren.
- Offline handelingen die tijdens een freeze zijn gedaan worden als conflict gemarkeerd en niet automatisch verwerkt.
- Tijdens een actieve server wordt iedere minuut automatisch een herstelkopie gemaakt; de laatste 20 blijven bewaard.
- Een vanuit een EventHub-evenement aangemaakte livesessie blijft daaraan gekoppeld. In- en uitchecken
  wordt automatisch teruggeschreven naar de kolom Aanwezig en door de gewone autosave opgeslagen.
