# Context voor Claude — EventHub en Cohentra online

Communiceer in het Nederlands. Dit project bevat twee dingen: de desktopapp **EventHub** (Python/PySide6, Windows) en de **online omgeving van Cohentra Digital** onder `cloudflare/` en `cohentra-pages-upload/`.

## Online omgeving (stand 30 oktober 2026, alles live)

| Onderdeel | Map | Live adres |
|---|---|---|
| Worker `eventhub-licenses`: accounts, sessies, MFA, staffportaal, klantenportaal, support, licenties, `/api/validate` | `cloudflare/license-worker/` | admin./staff./customer./support.cohentra.digital en `eventhub-licenses.eventhub-license.workers.dev` |
| Worker `cohentra-shop`: catalogus, Stripe Checkout/Customer Portal, webhooks, facturen, downloads, productbeheer | `cloudflare/shop-worker/` | shop-api.cohentra.digital |
| Gedeelde rechtenlogica (entitlements) voor beide workers | `cloudflare/shared/entitlements.js` | — |
| Worker `cohentra-contact-intake`: contactformulier van de website | `cloudflare/contact-intake/` | contact-api.cohentra.digital |
| Website (Cloudflare Pages-project `cohentra-digital-site`), incl. `/shop` en `/product?p=…` | `cohentra-pages-upload/` | cohentra.digital |

- Beide workers delen de D1-database `eventhub-licenses` (id `68ffa97d-1965-4401-9ed4-89f34bb51629`). Migraties staan in `cloudflare/license-worker/migrations/`; 0025 (shop) is live.
- De licentie-worker is de voordeur. Hij controleert de login en geeft shopacties via service binding `SHOP` (RPC-entrypoint `ShopService`) door aan de shop-worker.
- Het R2-bucket `cohentra-product-files` (privé) is voor productafbeeldingen en downloads; `cohentra-staff-avatars` is voor profielfoto's van medewerkers.
- De volledige uitleg van shop, Stripe, rechtenregels, configuratie en open keuzes staat in **`cloudflare/SHOP_STRIPE.md`**.

## Afspraken met de gebruiker

- **EventHub is maatwerk en hoort niet in de shop.** In de database staat `products.shop_allowed = 0`. EventHub-klanten houden hun bestaande quotumlicenties via Cohentra, en het klantenportaal toont EventHub voor hen als "maatwerk". Shopproducten zijn andere, nog te bepalen producten.
- **Maak losse workers in plaats van de licentie-worker te laten vollopen.** Nieuwe commerce-functionaliteit hoort in de shop-worker; account- en licentiezaken horen in de licentie-worker. Accounts en sessies blijven op één plek (geen tweede accountsysteem).
- **Verzin geen zakelijke keuzes** zoals prijzen, valuta, btw, voorwaarden of hersteltermijnen. Markeer ze als open punt.
- **Zet niets live zonder akkoord van de gebruiker.** Bestellen staat uit (`SHOP_CHECKOUT_ENABLED=false`), en live betalen kan alleen met `STRIPE_ALLOW_LIVE=true`.

## Nog te doen

1. **Stripe koppelen.** Maak een testaccount aan, zet de Secrets `STRIPE_SECRET_KEY` (`sk_test_…` of `rk_test_…`) en `STRIPE_WEBHOOK_SECRET` op de worker `cohentra-shop`, en richt de webhook en de Customer Portal in. Zie `SHOP_STRIPE.md` §7.
2. **Open zakelijke keuzes vastleggen** (§8): valuta, btw/Stripe Tax, voorwaarden en herroepingsrecht, hersteltermijn, terugbetalingsbeleid, updates bij eenmalige aankoop, bewaartermijnen en privacyverklaring.
3. **Rechten toekennen.** Geef medewerkers in het staffportaal (Medewerkers & rechten) de rechten `shop.view`, `shop.manage`, `billing.view` en `billing.manage`. Standaard heeft alleen de eigenaar ze.
4. **Het eerste shopproduct aanmaken** in het staffportaal, onder het menu Shop. Daarna `SHOP_CHECKOUT_ENABLED` op `"true"` zetten.
5. **Niet getest:** het Shop-scherm met een echte medewerkerslogin (MFA), en de keten tegen de echte Stripe-testomgeving.
6. **Idee voor later, nog niet gestart.** De gebruiker overweegt verdere opsplitsing in workers: (a) de licentiecontrole `/api/validate` als kleine aparte worker (eerste keus), (b) de portaal-HTML als statische assets, (c) support met mailbox/STRATO plus contact-intake in een eigen worker, (d) een mailworker voor alle uitgaande e-mail en de verloopcron. Inloggen, sessies, MFA, rechten en accounts blijven in de licentie-worker.

## Werken en deployen

- **Tests**, uit te voeren vanuit `cloudflare/`:
  ```bash
  node --import ./tests/cf-register.mjs --test tests/shop-chain.test.mjs
  ```
  Dit zijn 20 scenario's met een nagebootste Stripe. Daarnaast zijn er regressietests in `cloudflare/license-worker/tests/` (`support-backend.py`, `support-frontend.cjs`, `support-mail.cjs`).
- **Lokale demo**: `node --import ./cloudflare/tests/cf-register.mjs cloudflare/tests/dev-server.mjs`. Dat geeft de website op `localhost:8790` en de portalen op `customer.localhost:8790`, `staff.localhost:8790` en `shop-api.localhost:8790`. De inloggegevens van de demo staan in de console.
- **Workers deployen**: `npx wrangler@4 deploy` in `cloudflare/license-worker` of `cloudflare/shop-worker`. Daarvoor moet je eerst inloggen met `npx wrangler@4 login` (account `f1e2bd4864afd528b5636c28857ecded`). Deploy de shop-worker vóór de licentie-worker, want die hangt via de service binding van de shop af.
- **Database-migraties**: maak eerst een D1 Time Travel-bookmark. Voer de SQL daarna uit via de Cloudflare-API of MCP en voeg een regel toe aan `d1_migrations`.
- **Website deployen**:
  ```bash
  npx wrangler@4 pages deploy cohentra-pages-upload --project-name cohentra-digital-site --branch main
  ```
  Live HTML wijkt altijd iets af door de e-mailbeveiliging van Cloudflare; dat is normaal.
- **Geheimen** staan alleen als Cloudflare Secrets, nooit in code of `wrangler.jsonc`.
