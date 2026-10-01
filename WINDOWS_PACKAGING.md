# Windows-pakketten

`BUILD_EVENTHUB_WINDOWS.bat` gebruikt de twee bijgehouden `.spec`-bestanden.
Wijzig de pakketinhoud daar; genereer deze bestanden niet opnieuw met losse
PyInstaller-opties. De bestaande controles van afbeeldingen blijven actief.

- `server.tests` wordt niet verzameld of gebundeld. Tests importeren de desktopapp
  en trokken daardoor onder andere de complete browserengine in de losse server.
- De desktopapp behoudt QtWebEngine voor Rudder. De zelfstandige server gebruikt
  geen QtWebEngine.
- Tijdens analyse wordt PATH beperkt tot Python en Windows. Hiermee worden geen
  conflicterende runtime-DLL's uit andere geïnstalleerde tools meegeleverd.
- `verify_windows_packages.py` controleert de inhoud van beide gebouwde pakketten.
- Afbeeldingen en Browserassistent worden door het Windows-buildscript in de
  distributie gezet; Inno Setup hoeft deze niet nogmaals afzonderlijk te kopiëren.

`BUILD_EVENTHUB_INSTALLER.bat` bouwt beide pakketten en daarna de installer.
De versie en uitvoernaam staan in `EventHub_Installer.iss`.

## Updates via GitHub Releases

- `emt_updater.py` controleert de openbare releases van `borisvanderwerff-hub/Eventhub`.
- Tijdens het opstartscherm wordt de controle op de achtergrond uitgevoerd; een netwerkstoring houdt EventHub niet tegen.
- Plaats per release één installer met een naam die begint met `EventHub-Setup` en eindigt op `.exe`. De versie in de GitHub-tag moet hoger zijn dan `APP_VERSION` in `emt_base.py`.
- Voor de huidige bètaversie `0.2.2 Beta` hoort bijvoorbeeld de tag `v0.2.2-beta` bij de installer `EventHub-Setup-v0.2.2 Beta.exe`.
- De updater toont alleen releases waarvan de GitHub API een SHA-256-digest voor de installer opgeeft. De download wordt volledig gecontroleerd vóór die kan worden gestart.
- De gebruiker start de installatie zelf via de klikbare tekst onderin EventHub. De link **Later** verbergt de melding voor die sessie; **Over EventHub** toont de beschikbare versie.
- Een update is alleen beschikbaar op Windows. De installatiemap blijft `{localappdata}\Programs\EventHub`; EventHub- en gebruikersbestanden staan daarbuiten.

Voor een diagnostische serverbuild kan tijdelijk `EVENTHUB_BUILD_CONSOLE=1`
worden ingesteld. Laat deze variabele bij productiebuilds weg. Gebruik voor
startcontroles altijd een aparte `EVENTHUB_SERVER_DATA`-map.

Deze wijziging verwijdert geen bestanden uit bestaande gebruikersinstallaties.
Oude, niet meer meegeleverde runtimebestanden kunnen bij een upgrade blijven
staan. Nieuwe installaties ontvangen alleen de nieuwe pakketinhoud. Er worden
geen evenementbestanden, instellingen of live-sessies opgeschoond.
