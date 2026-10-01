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

Voor een diagnostische serverbuild kan tijdelijk `EVENTHUB_BUILD_CONSOLE=1`
worden ingesteld. Laat deze variabele bij productiebuilds weg. Gebruik voor
startcontroles altijd een aparte `EVENTHUB_SERVER_DATA`-map.

Deze wijziging verwijdert geen bestanden uit bestaande gebruikersinstallaties.
Oude, niet meer meegeleverde runtimebestanden kunnen bij een upgrade blijven
staan. Nieuwe installaties ontvangen alleen de nieuwe pakketinhoud. Er worden
geen evenementbestanden, instellingen of live-sessies opgeschoond.
