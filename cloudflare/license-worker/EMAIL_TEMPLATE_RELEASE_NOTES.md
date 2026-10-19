# Cohentra e-mailtemplates — wijzigingsoverzicht

## Implementatie

- Supportreacties, statusupdates, nieuwe supportaanvragen, klantenportaaluitnodigingen en wachtwoordherstel gebruiken aanpasbare instellingen die per template in D1 worden bewaard.
- Het medewerkersportaal krijgt een onderdeel **E-mailtemplates** met bewerkbare tekstvelden, een accentkleurkiezer en een preview met fictieve voorbeeldgegevens.
- De nieuwe toestemming `email.templates.manage` bepaalt wie deze instellingen kan bekijken en wijzigen. De migratie geeft dit recht standaard aan de functie Beheer; de eigenaar behoudt alle rechten.
- De preview verstuurt geen e-mail. Nieuwe e-mailteksten en accentkleur kunnen na de eerste Worker- en D1-update worden gewijzigd zonder opnieuw de volledige Worker-code te publiceren.
- De eerste ingebruikname vereist een Worker-update én migratie `0016_email_templates.sql`, omdat de editor en de D1-koppeling onderdeel zijn van de Worker-code.

## Productiepublicatie

Dit is lokale voorbereiding. Er is in deze stap niets naar Cloudflare gepubliceerd of op de productie-D1 uitgevoerd.
