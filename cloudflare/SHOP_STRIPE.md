# Shop, klantomgeving en Stripe — opbouw, configuratie en open punten

Status 30 oktober 2026: gebouwd en lokaal getest tegen een nagebootste Stripe. **Nog niets gedeployed, geen echte betalingen actief.**

## 1. Analyse: wat er al was en wat is hergebruikt

| Bestond al | Hergebruikt als |
|---|---|
| `customers` (KvK, btw, factuuradres, factuur-e-mail) | Het enige klantrecord, voor organisaties én particulieren/zzp. Nieuw: `customer_type`, `billing_company`, `stripe_customer_id`, `source`. |
| `customer_portal_accounts` (meerdere gebruikers per klant, uitnodigen per e-mail) | Het accountsysteem van de shop. Nieuw: `role` (`admin`/`member`), `email_verified_at`. Bestaande accounts worden `admin` en tellen als bevestigd. |
| Klantsessies, wachtwoordherstel, uitnodigingsmails, rate limits | Ongewijzigd hergebruikt; registratie gebruikt dezelfde tokens, mails en limieten. |
| `products` (alleen `eventhub`) | De producttabel van de shop (nieuw: slug, teksten, `published`, `shop_allowed`). `active` blijft de licentieschakelaar. EventHub is maatwerk en staat op `shop_allowed = 0`. |
| `licenses` + `/api/validate` (hash van de sleutel, één apparaat per sleutel) | Licentiesleutels bij een abonnement. Nieuw: `entitlement_id`; `/api/validate` geeft extra velden terug en blijft achterwaarts compatibel. |
| Functies en rechten van medewerkers | Nieuwe rechten: `shop.view`, `shop.manage`, `billing.view`, `billing.manage`. |
| Staffportaal (klantenlijst, klantdetail, cx-componenten) | Menu-item **Shop** en een sectie **Shop, abonnementen en betalingen** in het bestaande klantdetail, met dezelfde componenten. |
| Huisstijl van de website (tokens, knoppen, kaarten, topbar, footer) | Pagina's `/shop` en `/product?p=…`. |
| Cloudflare Email-binding, R2, D1 | E-mail voor registratie en uitnodigingen; R2 voor bestanden; dezelfde D1. |

Er waren **geen** betaal-, facturatie-, valuta-, btw- of downloadvoorzieningen. Die instellingen zijn dus niet overgenomen of verzonnen: ze staan hieronder als open keuze.

## 2. Architectuur

```
cohentra.digital (Pages)         ──GET──▶  shop-api.cohentra.digital  (worker cohentra-shop, publiek deel)
  /shop, /product                           catalogus · /shop-media · /download/<token> · /api/stripe/webhook
                                                     ▲
customer./staff.cohentra.digital ──▶ eventhub-licenses ──RPC (service binding SHOP)──┘
  klanten- en staffportaal            accounts, sessies, registratie, organisatiegebruikers,
                                      licentiesleutels, /api/validate
                        beide workers ──▶ D1 eventhub-licenses (één klantadministratie)
```

- **Licentie-worker (`eventhub-licenses`)**: accounts, sessies en licenties. Hij controleert elke sessie en geeft alleen een gecontroleerde klant of medewerker via RPC door. Bevat geen Stripe-sleutels.
- **Shop-worker (`cohentra-shop`, nieuw)**: catalogus, Checkout, abonnementen, Customer Portal, webhooks, facturen, downloads en productbeheer. Alleen deze worker kent de Stripe-sleutels. Zonder deze worker blijft de licentie-worker gewoon werken; shoproutes geven dan een nette 503.
- **Gedeeld**: `shared/entitlements.js`. Zo hanteren `/api/validate` en de shop exact dezelfde regels.

Bestanden: `shop-worker/` (worker.js, app.js, customer-api.js, admin-api.js, billing.js, stripe.js, wrangler.jsonc); `license-worker/` (accounts-shop.js, customer-portal.js, admin-shop-ui.js, wijzigingen in worker.js, migratie `0025_shop_billing.sql`); `cohentra-pages-upload/` (shop.html, product.html, shop.js, uitbreiding styles.css, Shop in de navigatie).

## 3. Rechten (entitlements): regels

Per klant en product is er één recht, met als bron een Stripe-abonnement, een eenmalige bestelling of een handmatige toekenning. Het recht legt plan, functies, maximaal aantal gebruikers en maximaal aantal activaties vast **op het moment van aankoop of planwissel**. Latere wijzigingen aan een plan raken bestaande klanten dus niet ongemerkt.

**Downloaden en gebruiken zijn aparte rechten.**

| Situatie | Gebruik (licentie geldig) | Downloaden |
|---|---|---|
| Abonnement actief of in proefperiode | ja | ja |
| Opgezegd (`cancel_at_period_end`) | ja, tot het einde van de periode | ja, tot het einde van de periode |
| Betaling mislukt (`past_due`) | ja (hersteltermijn) | nee |
| Hersteltermijn verstreken (`SHOP_GRACE_DAYS`, optioneel) / `unpaid` / gepauzeerd | nee | nee |
| Beëindigd of verlopen | nee | nee |
| Eenmalige aankoop betaald | ja, zonder einddatum | ja |
| Volledig terugbetaald | nee (ingetrokken) | nee |
| Gedeeltelijk terugbetaald | ja | ja |

- **Toegang komt alleen via de server.** Toegang ontstaat pas als een geverifieerde Stripe-webhook (of een opvraging door de server zelf) de betaling bevestigt. Terugkeren op de succespagina geeft geen toegang.
- **Volgorde en dubbele meldingen.** Elke melding haalt het actuele object opnieuw bij Stripe op, dus de eindstand is altijd juist, ook bij dubbele, vertraagde of verkeerd geordende meldingen. Gebeurtenis-ID's worden vastgelegd, zodat een melding niet twee keer wordt verwerkt.
- **Verlengingsmarge.** Een abonnement mag 48 uur over de periodegrens heen, zodat een vertraagde verlengingswebhook niemand buitensluit. Dit is een technische marge, geen zakelijke keuze.
- **Upgrade**: gaat direct in, met verrekening naar rato die direct wordt gefactureerd (`always_invoice`). Wijzigingen gaan met `pending_if_incomplete`: lukt de bijbetaling niet, dan blijft het oude plan staan. Een wissel van periode (maand ↔ jaar) gaat ook direct in.
- **Downgrade**: wordt via een Stripe Subscription Schedule gepland per het einde van de periode. Tot die datum blijven de huidige functies; er volgt geen terugbetaling. De klant kan de geplande wijziging annuleren.
- **Proefperiode**: optioneel per plan (`trial_days`), één keer per klant per product.
- **Handmatige uitzonderingen** (staff, recht `billing.manage`): verlengen tot een datum, opschorten, limieten aanpassen of functies toevoegen/verwijderen.
  - Een reden is verplicht, en elke uitzondering wordt vastgelegd met medewerker en tijd in de historie.
  - Uitzonderingen staan **los** van het recht dat Stripe bijwerkt; webhooks overschrijven ze nooit.
  - Opschorten gaat altijd voor; verlengen geeft toegang tot de gekozen datum, ook als het abonnement eerder stopt.
  - Medewerkers kunnen ook een recht zonder betaling toekennen, of een abonnement direct of per periode-einde beëindigen.
- **Activatielimiet**: aantal actieve licentiesleutels per recht. Elke sleutel werkt op één apparaat, zoals nu al. Een beheerder kan een apparaat vrijgeven of een sleutel intrekken.
- **Gebruikerslimiet**: het ruimste actieve recht bepaalt hoeveel portaalgebruikers een organisatie kan hebben. Uitnodigen buiten de limiet wordt aan de serverzijde geweigerd.

### Koppeling met de producten zelf

**EventHub is maatwerk en staat niet in de shop.** Het product heeft in de database `shop_allowed = 0`. De shop-API, de catalogus, het productbeheer en Checkout weigeren het, ook als iemand het per ongeluk op gepubliceerd zet; een test bewaakt dit. EventHub blijft lopen via de bestaande licenties en quota die Cohentra per klant toewijst, zonder wijziging. De uitbreiding hieronder is voor producten die wel via de shop worden verkocht.

`POST /api/validate` geeft naast de bestaande velden nu ook `product_id`, `plan`, `features`, `limits`, `entitlement_status` en `recheck_after_seconds` terug. Optioneel stuurt een client `product_id` mee; een sleutel van een ander product wordt dan geweigerd. Bestaande EventHub-installaties negeren de nieuwe velden en blijven werken; dat is getest met een bestaande klant met quotum.

**Offline gebruik.** Shopproducten kunnen hetzelfde model gebruiken als EventHub al doet. EventHub bewaart maximaal 7 dagen een DPAPI-versleutelde bevestiging, begrensd door `valid_until`. Bij abonnementen is `valid_until` het einde van de betaalperiode, dus na een verlenging moet de client weer online controleren. Tijdens een hersteltermijn adviseert de server elk uur opnieuw te controleren.

**Functies vrijgeven in de app.** Een product leest `features` uit en schakelt daarop functies vrij. Ook de server moet de toegang afdwingen waar het product serverfuncties heeft. Dit is geen volledige kopieerbeveiliging: lokaal geïnstalleerde software kan worden aangepast. Het doel is een eerlijke, controleerbare licentie.

**Per shopproduct te bouwen:** het product moet `features` uitlezen en daarop functies vrijschakelen. Voor EventHub is dat niet nodig.

## 4. Klantomgeving en aankoopstroom

1. De klant kiest op `/product?p=…` een abonnement en komt in het klantenportaal met `?buy=<prijs-id>`.
2. Aanmelden of registreren. Bij registratie kiest de klant *Particulier of zelfstandige* (ook eenmanszaak/zzp) of *Organisatie*. Pas na bevestiging van het e-mailadres ontstaat het klantrecord, dat direct in het bestaande klantoverzicht van het staffportaal staat.
3. De klant controleert de bestelling. Een particulier/zelfstandige kiest of de aankoop **privé** of **zakelijk** is; bij zakelijk vult hij bedrijfsnaam, btw- en KvK-nummer in zonder een organisatieaccount te krijgen. De keuze en factuurgegevens worden per bestelling vastgelegd.
4. De klant betaalt in Stripe Checkout en keert terug. Het portaal wacht dan op de bevestiging door de server en toont "wordt verwerkt", "betaald" of "mislukt".
5. Tabbladen in het portaal:
   - Mijn producten (functies, downloads met versienotities)
   - Abonnementen (wijzigen met ingangsdatum en verrekening, opzeggen, opzegging intrekken, Betaalgegevens beheren via de Stripe Customer Portal)
   - Licenties en activaties
   - Bestellingen en facturen
   - Account en factuurgegevens
   - Gebruikers (alleen organisatiebeheerders)
   - Support

   Alle bestaande functies (licentiequotum, tickets, wachtwoord) zijn behouden.
6. Een gewone organisatiegebruiker (`member`) kan gebruiken en downloaden, maar ziet geen facturen en beheert geen abonnementen, betaalmethoden of gebruikers. Dat wordt aan de serverzijde gecontroleerd.

**Koppelen aan een bestaand klantrecord** gebeurt alleen als het bevestigde e-mailadres exact het vastgelegde contactadres is en die klant nog geen portaalgebruikers heeft. Een bedrijfsnaam of een onbevestigd adres is nooit genoeg. Een tweede registratie met een bestaand adres levert geen tweede account op: de eigenaar krijgt een herstellink.

**Downloads** staan in een privé R2-bucket en zijn alleen bereikbaar via een tijdelijke link: 10 minuten geldig, maximaal 5 keer te gebruiken, alleen de hash wordt opgeslagen, en de link wordt aangemaakt na een rechtencontrole.

## 5. Facturen

Facturen komen **uitsluitend uit Stripe**: abonnementsfacturen, en bij eenmalige aankopen via `invoice_creation`. Het portaal bewaart alleen een verwijzing (`billing_invoices`) en toont de Stripe-link of PDF. Er is geen tweede facturatiesysteem, dus geen dubbele facturen. Stripe verstuurt de factuur- en betaalmails; het portaal stuurt zelf geen betaalmails.

**Bewaren:** klanten met bestellingen, facturen of rechten kunnen niet meer worden verwijderd, alleen gepauzeerd.

## 6. Tests

Uitvoeren vanuit `cloudflare/`:

```bash
node --import ./tests/cf-register.mjs --test tests/shop-chain.test.mjs
```

**Getest (20 scenario's, allemaal geslaagd).** De test gebruikt de echte migraties in SQLite, de echte worker-code en een nagebootste Stripe-API met ondertekende webhooks:

- Productbeheer: product, functies, plannen, prijzen naar Stripe, publiceren, afbeelding, versie met bestand. Prijs zonder btw-keuze wordt geweigerd.
- Publieke catalogus zonder bestandslocaties; EventHub (maatwerk) kan niet in de shop komen.
- Registratie met e-mailbevestiging; geen dubbel account; koppeling aan een bestaand klantrecord alleen op bevestigd contactadres.
- Volledige keten: registratie → Checkout → webhook → klant in staffportaal → licentie → juiste functies in `/api/validate` → download.
- Succespagina geeft geen toegang; vervalste en verouderde handtekeningen geweigerd; dubbele meldingen; open sessie hergebruikt; dubbel abonnement en dubbele aankoop geweigerd.
- Afscherming tussen klanten: bestellingen, licenties, downloads, abonnementen en portalsessies.
- Upgrade (ook met mislukte bijbetaling), downgrade per periode-einde (inclusief terugval voor nieuwere Stripe-API-versies).
- Mislukte betaling met hersteltermijn, herstel, een verkeerd geordende oude melding, maximale hersteltermijn.
- Uitzonderingen die webhooks overleven.
- Opzeggen en intrekken van de opzegging, beëindiging, oude melding na beëindiging, verlenging door staff.
- Eenmalige aankoop met gedeeltelijke en volledige terugbetaling; verlopen Checkout.
- Organisatie: uitnodigen binnen de limiet, rechten van gewone gebruikers, laatste beheerder.
- Regressie voor bestaande klanten met EventHub-quotum.
- Live-meldingen genegeerd bij een testsleutel; Checkout dicht zonder schakelaar; live-sleutel geweigerd zonder `STRIPE_ALLOW_LIVE`.
- Pagina's laden en de browserscripts parsen.

Bestaande regressietests (`license-worker/tests/support-*.{py,cjs}`) slagen ook met migratie 0025.

Een controle met bewust ingebouwde fouten (opschorting negeren, handtekeningcontrole uit) liet 8 tests falen: de tests vangen echte fouten.

**Visueel gecontroleerd** met `tests/dev-server.mjs` (lokale demo): `/shop`, `/product` (tabel zonder horizontale overloop op 375 px), klantenportaal (desktop en mobiel), bestelcontrole, staffportaal Shop en de commerce-sectie bij een klant.

**Niet getest:**
- Tegen de echte Stripe-testomgeving: er zijn nog geen sleutels.
- De echte Stripe Checkout- en Customer Portal-pagina's, en echte Stripe-mails.
- Upload van grote bestanden en R2 op Cloudflare.
- Deploy en de service binding op Cloudflare.
- iDEAL/SEPA met vertraagde betaling (`async_payment_*` is gebouwd, alleen nagebootst getest).
- Stripe Tax.

## 7. Wat in Stripe en Cloudflare nog moet worden ingesteld

**Stripe (eerst in de testmodus):**

1. Een Stripe-account voor Cohentra Digital, met bedrijfsgegevens en uitbetaalrekening (in te vullen door jullie zelf).
2. Een API-sleutel. Bij voorkeur een *restricted key* (`rk_test_…`) met schrijfrechten op Customers, Checkout Sessions, Subscriptions, Subscription Schedules, Products, Prices, Billing Portal en Invoices (preview), en leesrechten op Charges en Tax IDs. Een `sk_test_…` werkt ook.
3. Webhook-endpoint `https://shop-api.cohentra.digital/api/stripe/webhook` met deze gebeurtenissen:
   - `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`
   - `customer.subscription.created`, `.updated`, `.deleted`, `.paused`, `.resumed`, `.trial_will_end`
   - `subscription_schedule.updated`, `.released`, `.canceled`, `.completed`
   - `invoice.paid`, `invoice.payment_failed`, `invoice.finalized`, `invoice.updated`, `invoice.voided`, `invoice.marked_uncollectible`, `invoice.payment_action_required`
   - `charge.refunded`, `refund.created`, `refund.updated`, `charge.dispute.created`

   Het ondertekeningsgeheim (`whsec_…`) wordt `STRIPE_WEBHOOK_SECRET`.
4. Customer Portal (Settings → Billing → Customer portal): betaalmethode bijwerken en facturen inzien aan. Abonnementen opzeggen en wijzigen kan via het eigen portaal; als je dat ook in de Stripe-portal toestaat, verwerken de webhooks het correct. Een eigen configuratie gebruik je met `STRIPE_PORTAL_CONFIGURATION_ID`.
5. Billing → Revenue recovery: het aantal betaalpogingen bij een mislukte betaling (dit bepaalt de hersteltermijn) en welke e-mails Stripe verstuurt.
6. Factuurinstellingen: nummering, factuurtekst, btw-weergave en een eventuele link naar voorwaarden.

**Cloudflare:**

1. D1: maak een Time Travel-bookmark en voer migratie `0025_shop_billing.sql` uit. Registreer hem in `d1_migrations`.
2. R2: maak de privé bucket `cohentra-product-files` aan.
3. Maak de worker `cohentra-shop` aan (`shop-worker/wrangler.jsonc`): D1, R2, custom domain `shop-api.cohentra.digital`, Secrets `STRIPE_SECRET_KEY` en `STRIPE_WEBHOOK_SECRET`.
4. Werk de worker `eventhub-licenses` bij met de service binding `SHOP` (entrypoint `ShopService`) en de nieuwe modules. De worker bestaat nu uit meerdere modules: `worker.js` importeert `accounts-shop.js`, `customer-portal.js`, `admin-shop-ui.js` en `../shared/entitlements.js`. Een upload via de MCP moet al die modules meesturen. Wrangler bundelt ze automatisch.
5. Pages: upload `shop.html`, `product.html`, `shop.js`, `styles.css`, `index.html` en `eventhub.html`.
6. Ken in het staffportaal (Medewerkers & rechten) de nieuwe rechten toe. Standaard heeft alleen de eigenaar ze.

**Veilige volgorde:** migratie → shop-worker → licentie-worker → website. Zet `SHOP_CHECKOUT_ENABLED` pas op `"true"` als de prijzen zijn goedgekeurd.

## 8. Open zakelijke keuzes (niet ingevuld)

- **Valuta en prijzen per abonnement**: worden pas vastgelegd bij het invoeren; er is geen standaardwaarde.
- **Btw**:
  - Prijs inclusief of exclusief btw (verplicht per prijs).
  - Stripe Tax gebruiken (`STRIPE_AUTOMATIC_TAX=true`, vereist activering in Stripe).
  - Verleggingsregeling bij zakelijke EU-klanten.
  - Welke landen jullie bedienen. De landcode wordt nu alleen afgeleid voor NL, BE, DE, FR, LU en GB; overige landen vraagt Stripe zelf uit.
- **Algemene voorwaarden en een herroepingsbeleid voor consumenten** bij digitale levering (en de aanvinkplicht, `STRIPE_REQUIRE_TERMS`). Er staan nog geen voorwaarden op de site.
- **Hersteltermijn na mislukte betaling**: standaard volgt de toegang Stripe's herhaalpogingen. Optioneel stel je een maximum in met `SHOP_GRACE_DAYS`.
- **Verrekening en ingangsdatum bij wijzigingen**: standaard wordt een upgrade direct gefactureerd naar rato en gaat een downgrade per periode-einde in. Instelbaar met `SHOP_UPGRADE_PRORATION` en `SHOP_DOWNGRADE_TIMING`.
- **Terugbetalingen**:
  - Of een gedeeltelijke terugbetaling de licentie laat staan (nu wel).
  - Of een terugbetaling op een abonnementsfactuur de toegang moet beëindigen (nu niet; medewerkers kunnen het abonnement beëindigen).
  - Wat er bij een betwisting gebeurt (nu alleen vastgelegd).
- **Eenmalige aankopen**: nu gebruik zonder einddatum en downloads van alle gepubliceerde versies. Kies of updates beperkt moeten worden, bijvoorbeeld tot 12 maanden.
- **Proefperiodes**: of en hoe lang, en of er een betaalmethode nodig is.
- **Plannen en limieten**: welke functies en hoeveel gebruikers en activaties per abonnement.
- **Bewaartermijnen**: hoe lang jullie bestel- en factuurgegevens bewaren. Verwijderen is nu geblokkeerd zodra er betaalhistorie is.
- **Privacyverklaring**: aanvullen met Stripe als verwerker en de nieuwe gegevens (factuurgegevens, bestellingen).

## 9. Van testbetalingen naar echte betalingen

1. Test de hele keten in de Stripe-testmodus met testkaarten, iDEAL-test, een mislukte betaling, een opzegging, een upgrade/downgrade en een terugbetaling. Controleer de meldingen onder Developers → Webhooks en het statusblok in staffportaal → Shop.
2. Leg de open keuzes uit §8 vast en laat de voorwaarden en het privacybeleid aanvullen.
3. Activeer het Stripe-account voor live gebruik (identiteit, bank).
4. Maak in de **live**-modus een nieuw webhook-endpoint en een nieuwe sleutel aan. Live- en testprijzen zijn verschillende objecten: maak de prijzen opnieuw aan via het staffportaal met de live-sleutel, of vul de live `price_…`-ID's in.
5. Vervang de Secrets `STRIPE_SECRET_KEY` en `STRIPE_WEBHOOK_SECRET` door de live-waarden en zet `STRIPE_ALLOW_LIVE=true`. Zonder die schakelaar weigert de worker een live-sleutel.
6. Doe één echte bestelling met een klein bedrag, controleer factuur, licentie en download, en betaal hem terug.
7. Zet daarna `SHOP_CHECKOUT_ENABLED=true` voor iedereen.

**Let op:** meldingen uit de andere modus worden genegeerd. Testbetalingen kunnen dus nooit live-toegang geven, en omgekeerd.
