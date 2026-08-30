# EventHub 2 — hoofdinterface preview

Deze preview bouwt verder op de vernieuwde Sessiebeheer/Event Control-interface.

Aangepast in deze build:
- nieuw command-center dashboard met prominente snelacties;
- sterkere visuele hiërarchie voor statistieken en evenementen;
- bredere, rustiger ingedeelde sidebar met secties Werkruimte en Beheer;
- moderne donkere EventHub 2-stijl als standaard voor nieuwe installaties;
- vernieuwde masthead met lokale-statusindicator;
- uniformere kaarten, tabbladen, tabellen, formulieren en actiekleuren;
- bestaande EventHub-functionaliteit en navigatieroutes behouden.

Let op: in de huidige Linux-testomgeving is PySide6 niet geïnstalleerd. De gewijzigde Python-bestanden zijn wel met `py_compile` op syntax gecontroleerd. De uiteindelijke visuele controle moet daarom in de Windows-build plaatsvinden.


## 2.18.0 — Evenementdossier
- Overzicht vervangen door een EventHub 2-werkruimte met zes cards.
- Deelnemers, Taken, After sales, Statistieken, Documenten en Rudder zijn direct bereikbaar.
- Cards tonen live context uit het geopende evenement.
- Nieuwe compacte evenementheader met statusbadge.
- Eventgegevens en snelle dossieracties zijn in één rustige kaart samengebracht.


## 2.18.1 — Rustiger evenementdossier
- Navigatiecards uit het overzicht verwijderd.
- Vier relevante KPI’s: deelnemers, open taken, after sales open en aanwezig.
- Overzicht in twee functionele panelen: evenementgegevens en acties/aandachtspunten.
- No-shows en ontbrekende gegevens alleen als aandachtspunt wanneer relevant.


## 2.19.2 — Automatische afronding & Rudder-gegevens

- Evenementen waarvan de datum is verstreken gaan vanaf de volgende kalenderdag automatisch naar **Afgerond**.
- **Geannuleerd** blijft altijd onaangetast door automatische statuswijzigingen.
- EventHub-evenementen hebben nu bewerkbare **starttijd**, **eindtijd**, **adres**, **maximumregistraties** en **locatie-instructies**.
- Datum en tijd zijn direct zichtbaar in de evenementkop en bij **Overzicht**.
- Een import uit Rudder vult deze kerngegevens automatisch in.
- Export naar Rudder neemt start- en eindtijd, maximumregistraties en locatie-instructies mee wanneer het evenement aan Rudder is gekoppeld.


## 2.19.1 — Evenementstatus & rustiger overzicht

- De card **Acties & aandachtspunten** is uit het evenementoverzicht verwijderd.
- Evenementgegevens krijgen de volledige beschikbare breedte.
- Bij **0 open taken** wordt de evenementstatus automatisch **Gereed**.
- Voeg je daarna een taak toe of heropen je er één, dan gaat **Gereed** automatisch terug naar **In voorbereiding**.
- **Afgerond** en **Geannuleerd** worden nooit automatisch overschreven.

## 2.19.0 — Taken
- Taken is nu een rustige centrale werkvoorraad in plaats van een verzameling cards.
- Compacte statusregel voor open, te laat, vandaag en binnenkort.
- Filter op Alle / Te laat / Vandaag / Binnenkort / Later.
- Tabel gebruikt de beschikbare ruimte; statuskleur alleen in de statuskolom.


## 2.20.0 — After sales werkruimte
- After sales opnieuw ingericht als compacte werkruimte met vier relevante KPI's.
- Nieuwe filters voor Actie nodig, Opvolging gepland en Afgehandeld.
- Zoeken prominenter gemaakt; kandidatenlijst houdt de meeste schermruimte.
- Opvolgafspraken worden apart geteld en blijven als actie zichtbaar, ook na eerder contact.
- Bestaande WhatsApp-wachtrij, kolomkeuze en bulkselectie blijven behouden.
