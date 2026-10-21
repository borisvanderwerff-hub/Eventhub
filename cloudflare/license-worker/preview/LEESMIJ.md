# Testversie van het medewerkersportaal

`testversie-medewerkersportaal.html` is een klikbare kopie van het
medewerkersportaal (staff.cohentra.digital) met verzonnen gegevens.
Dubbelklik het bestand; het opent in je browser. Inloggen is niet nodig.

Er gaat niets naar Cloudflare en er wordt niets bewaard. Verversen zet alles
terug naar de beginstand. Linksonder staat een balkje dat eraan herinnert dat
dit de testversie is.

## Belangrijk

**Dit is een kopie om naar te kijken, niet om in te werken.**
Wijzigingen in dit HTML-bestand doen helemaal niets voor de echte site. Het
portaal zelf staat in `../worker.js`, in het blok `ADMIN_HTML` (regel 37 tot
ongeveer 610). Aanpassingen horen daar, waarna je de testversie opnieuw bouwt:

    python maak-testversie.py

## Wat je kunt proberen

Met testgegevens gevuld: het overzicht, het klantenscherm met licenties en
groepen, portaalgebruikers, de supportlijst en Medewerkers & rechten.
Je kunt licenties uitgeven, verlengen, verplaatsen, intrekken, een nieuwe
sleutel maken en groepen toevoegen of hernoemen.

De verzonnen gegevens bevatten met opzet alle soorten gevallen: een klant die
vol zit (Stadsfeest Zwolle, 2 van 2), een gepauzeerde klant (Bakker & Co),
licenties die bijna verlopen, verlopen en ingetrokken zijn, onbeperkte
beheerderslicenties en de interne licenties onder "Cohentra (intern)".

Geen testgegevens: de e-mailtemplates, het openen van een los supportticket en
alles rond aanmelden en tweestapsverificatie. Daar verschijnt een melding in
plaats van een scherm.

## Voor een AI-assistent

Werk nooit in `testversie-medewerkersportaal.html`; dat bestand wordt bij elke
build overschreven. Het echte portaal is het blok `ADMIN_HTML` in
`../worker.js`. Twee regels die daar gelden:

- Het blok staat in `String.raw` backticks. Er mag dus geen backtick en geen
  `${` in de code die je toevoegt, anders loopt het hele bestand stuk.
- `worker.js` heeft Windows-regeleindes (CRLF). Lees en schrijf met
  `newline=""` en zet toegevoegde tekst om naar CRLF, anders verandert het
  hele bestand in één keer.

Boven in `worker.js` staat ook `SUPPORT_HTML` (regel 3 tot 18). Dat is oude,
ongebruikte code met een eigen inlogscherm. Negeer dat blok.
