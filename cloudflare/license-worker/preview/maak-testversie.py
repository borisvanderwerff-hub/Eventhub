"""Bouwt een klikbare testversie van het medewerkersportaal.

Het portaal zit als tekstblok (ADMIN_HTML) in worker.js. Dit script haalt dat
blok eruit en zet er een laagje voor dat alle serveraanvragen onderschept en
verzonnen gegevens teruggeeft. Het resultaat is een los HTML-bestand dat je in
een browser kunt openen, zonder Cloudflare, zonder database en zonder inloggen.

Gebruik:   python maak-testversie.py
Resultaat: testversie-medewerkersportaal.html in deze map

Let op: het bestand is een kopie om naar te kijken en in te klikken.
Wijzigingen die iemand in de kopie maakt doen niets. Echte aanpassingen horen
in worker.js, waarna je dit script opnieuw draait.
"""

import base64
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORKER = HERE.parent / "worker.js"
UITVOER = HERE / "testversie-medewerkersportaal.html"

START = "const ADMIN_HTML = String.raw`"

# Het laagje dat de server vervangt. Staat in een eigen functie-omhulsel, zodat
# geen enkele naam hieruit kan botsen met de namen in het portaal zelf.
NEPSERVER = r"""<script>
/* ------------------------------------------------------------------ */
/*  TESTVERSIE. Alle namen, klanten en licenties hieronder zijn        */
/*  verzonnen. Er gaat niets naar Cloudflare en niets wordt bewaard:   */
/*  verversen zet alles terug naar deze beginstand.                    */
/* ------------------------------------------------------------------ */
(() => {
  "use strict";

  // Het portaal onthoudt je aanmelding in sessionStorage. Door daar alvast een
  // sleutel in te zetten begint de testversie meteen op het dashboard. Sommige
  // browsers blokkeren opslag bij een los bestand; dan nemen we een eenvoudig
  // vervangertje in het geheugen, zodat de testversie overal werkt.
  try {
    sessionStorage.setItem("eventhub-admin-token", "testversie");
  } catch {
    const onthouden = { "eventhub-admin-token": "testversie" };
    const vervanger = {
      getItem: (k) => (k in onthouden ? onthouden[k] : null),
      setItem: (k, v) => { onthouden[k] = String(v); },
      removeItem: (k) => { delete onthouden[k]; },
      clear: () => { for (const k of Object.keys(onthouden)) delete onthouden[k]; },
      key: (i) => Object.keys(onthouden)[i] ?? null,
      get length() { return Object.keys(onthouden).length; }
    };
    try {
      Object.defineProperty(window, "sessionStorage", { value: vervanger, configurable: true });
    } catch { /* dan begint de testversie op het inlogscherm */ }
  }

  const DAG = 864e5;
  const VANDAAG = new Date().toISOString().slice(0, 10);
  const over = (n) => new Date(Date.now() + n * DAG).toISOString().slice(0, 10);
  const terug = (n) => new Date(Date.now() - n * DAG).toISOString();

  const K1 = "aaaaaaaa-0000-0000-0000-000000000001";
  const K2 = "aaaaaaaa-0000-0000-0000-000000000002";
  const K3 = "aaaaaaaa-0000-0000-0000-000000000003";
  const groepId = (n) => "bbbbbbbb-0000-0000-0000-" + String(n).padStart(12, "0");
  const medewerkerId = (n) => "dddddddd-0000-0000-0000-" + String(n).padStart(12, "0");

  const leeg = {
    contact_role: "", phone: "", kvk_number: "", vat_number: "", website: "",
    invoice_email: "", street: "", postal_code: "", city: "", country: "Nederland", notes: ""
  };

  const db = {
    klanten: [
      { ...leeg, id: K1, customer_number: "CUS-0001", name: "DCPL", contact_name: "Ruben Smit",
        contact_email: "ruben@dcpl.nl", phone: "050 123 45 67", city: "Groningen",
        street: "Oosterstraat 12", postal_code: "9711 NR", status: "active", created_at: terug(120) },
      { ...leeg, id: K2, customer_number: "CUS-0002", name: "Stadsfeest Zwolle",
        contact_name: "Nadia el Amrani", contact_email: "nadia@stadsfeestzwolle.nl",
        city: "Zwolle", status: "active", created_at: terug(64) },
      { ...leeg, id: K3, customer_number: "CUS-0003", name: "Bakker & Co",
        contact_name: "Joost Bakker", contact_email: "joost@bakkerenco.nl",
        city: "Assen", status: "paused", created_at: terug(300) }
    ],
    groepen: [
      { id: groepId(1), customer_id: null, name: "Beheer" },
      { id: groepId(2), customer_id: null, name: "Testgebruikers" },
      { id: groepId(3), customer_id: K1, name: "Balie" },
      { id: groepId(4), customer_id: K1, name: "Regio Noord" },
      { id: groepId(5), customer_id: K2, name: "Vrijwilligers" }
    ],
    licenties: [],
    gebruikers: {
      [K1]: [
        { id: "eeee0001-0000-0000-0000-000000000001", name: "Ruben Smit", email: "ruben@dcpl.nl",
          username: "ruben@dcpl.nl", active: 1, disabled_at: null, created_at: terug(119), last_seen_at: terug(1) },
        { id: "eeee0001-0000-0000-0000-000000000002", name: "Esther de Vries", email: "esther@dcpl.nl",
          username: "esther@dcpl.nl", active: 1, disabled_at: null, created_at: terug(40), last_seen_at: terug(12) }
      ],
      [K2]: [
        { id: "eeee0002-0000-0000-0000-000000000001", name: "Nadia el Amrani",
          email: "nadia@stadsfeestzwolle.nl", username: "nadia@stadsfeestzwolle.nl", active: 0,
          disabled_at: null, created_at: terug(60), last_seen_at: null }
      ],
      [K3]: []
    }
  };

  // Licenties: een mix van gekoppeld, ongebruikt, bijna verlopen, verlopen,
  // ingetrokken en onbeperkt, zodat elk soort rij in het scherm te zien is.
  let teller = 0;
  const lic = (o) => db.licenties.push({
    id: "cccccccc-0000-0000-0000-" + String(++teller).padStart(12, "0"),
    product_id: "eventhub", label: "Zonder naam", license_type: "Gesloten beta",
    valid_from: terug(90), valid_until: over(70), created_at: terug(90),
    revoked_at: null, activated_at: null, last_seen_at: null,
    group_id: null, customer_id: null, expiry_notice_sent_at: null, ...o
  });

  // Intern (Cohentra zelf)
  lic({ label: "Laptop Boris", license_type: "Beheerder", valid_until: "9999-12-31",
        group_id: groepId(1), activated_at: terug(200), last_seen_at: terug(0) });
  lic({ label: "Werkstation kantoor", license_type: "Beheerder", valid_until: "9999-12-31",
        group_id: groepId(1), activated_at: terug(150), last_seen_at: terug(3) });
  lic({ label: "Tester 001", group_id: groepId(2), activated_at: terug(20), last_seen_at: terug(1) });
  lic({ label: "Tester 002", group_id: groepId(2), valid_until: over(9) });
  lic({ label: "Demo-tablet" });
  lic({ label: "Oude democomputer", revoked_at: terug(30) });

  // DCPL: 4 van 5 in gebruik, met een bijna verlopen en een verlopen licentie
  lic({ label: "Laptop Ruben", customer_id: K1, activated_at: terug(100), last_seen_at: terug(1) });
  lic({ label: "Balie iPad", customer_id: K1, group_id: groepId(3), valid_until: over(6),
        activated_at: terug(60), last_seen_at: terug(0) });
  lic({ label: "Balie reserve", customer_id: K1, group_id: groepId(3), valid_until: over(12),
        expiry_notice_sent_at: terug(2) });
  lic({ label: "Bus Noord", customer_id: K1, group_id: groepId(4), activated_at: terug(30), last_seen_at: terug(8) });
  lic({ label: "Oude telefoon", customer_id: K1, valid_until: over(-20) });

  // Stadsfeest Zwolle
  lic({ label: "Entree 1", customer_id: K2, group_id: groepId(5), activated_at: terug(10), last_seen_at: terug(0) });
  lic({ label: "Entree 2", customer_id: K2, group_id: groepId(5), valid_until: over(25) });

  // Bakker & Co (gepauzeerd)
  lic({ label: "Kassa", customer_id: K3, valid_until: over(40) });

  // De eigenaar staat niet in deze lijst: die heeft een eigen plek in het
  // scherm en zit in het echte systeem ook in een andere tabel.
  const medewerkers = [
    { id: medewerkerId(1), name: "Sanne Visser", first_name: "Sanne", username: "sanne@cohentra.digital",
      email: "sanne@cohentra.digital", role: "staff", created_at: terug(90), revoked_at: null,
      last_seen_at: terug(1), must_change_password: 0, mfa_enabled: 1, recovery_codes_left: 10,
      function_keys: ["support"] },
    { id: medewerkerId(2), name: "Tim Hofman", first_name: "Tim", username: "tim@cohentra.digital",
      email: "tim@cohentra.digital", role: "staff", created_at: terug(14), revoked_at: null,
      last_seen_at: null, must_change_password: 1, mfa_enabled: 0, recovery_codes_left: 0,
      function_keys: ["sales", "support"] }
  ];

  const functies = [
    { function_key: "beheer", name: "Beheer",
      permissions: ["customers.view", "customers.manage", "licenses.view", "licenses.issue", "licenses.manage"] },
    { function_key: "support", name: "Support",
      permissions: ["support.view", "support.reply", "support.status", "customers.view", "licenses.view"] },
    { function_key: "sales", name: "Sales", permissions: ["sales.view", "customers.view"] }
  ];

  const tickets = [
    { id: "ffff0000-0000-0000-0000-000000000001", reference: "SUP-1043", category: "license",
      subject: "Licentie werkt niet na nieuwe laptop", message: "Mijn oude laptop is stuk. Hoe zet ik de licentie over?",
      status: "new", created_at: terug(0), updated_at: terug(0), assigned_to: null, source: "portal",
      organization: "DCPL", request_type: null, customer_id: K1, created_by_staff_name: null,
      customer_name: "Ruben Smit", contact_email: "ruben@dcpl.nl", customer_org: "DCPL",
      assigned_name: null, customer_spoke_last: 1 },
    { id: "ffff0000-0000-0000-0000-000000000002", reference: "SUP-1041", category: "eventhub",
      subject: "Bezoekerslijst exporteren naar Excel", message: "Kan de lijst ook als Excel-bestand?",
      status: "in_progress", created_at: terug(2), updated_at: terug(1),
      assigned_to: medewerkerId(1), source: "email", organization: "Stadsfeest Zwolle",
      request_type: null, customer_id: K2, created_by_staff_name: null,
      customer_name: "Nadia el Amrani", contact_email: "nadia@stadsfeestzwolle.nl",
      customer_org: "Stadsfeest Zwolle", assigned_name: "Sanne Visser", customer_spoke_last: 0 },
    { id: "ffff0000-0000-0000-0000-000000000003", reference: "SUP-1036", category: "account",
      subject: "Extra gebruiker voor het portaal", message: "Graag Esther ook toegang geven.",
      status: "closed", created_at: terug(9), updated_at: terug(7),
      assigned_to: medewerkerId(1), source: "portal", organization: "DCPL", request_type: null,
      customer_id: K1, created_by_staff_name: null, customer_name: "Ruben Smit",
      contact_email: "ruben@dcpl.nl", customer_org: "DCPL", assigned_name: "Sanne Visser",
      customer_spoke_last: 0 }
  ];

  /* ---------------- hulpjes ---------------- */

  const antwoord = (data, status = 200) => Promise.resolve(new Response(
    JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } }));

  const inGebruik = (klant) => db.licenties.filter(
    (l) => l.customer_id === klant && !l.revoked_at && l.valid_until >= VANDAAG).length;

  const naarBuiten = (l) => ({
    ...l,
    unlimited: l.valid_until === "9999-12-31",
    valid_until: l.valid_until === "9999-12-31" ? null : l.valid_until,
    expired: !l.revoked_at && l.valid_until < VANDAAG
  });

  const bereik = (eigenaar) => ({
    groups: db.groepen.filter((g) => g.customer_id === eigenaar).map((g) => ({
      ...g, license_count: db.licenties.filter((l) => l.group_id === g.id && !l.revoked_at).length })),
    licenses: db.licenties.filter((l) => l.customer_id === eigenaar).map(naarBuiten)
  });

  const product = (klant) => ({
    product_id: "eventhub", name: "EventHub", product_active: 1,
    max_licenses: klant === K1 ? 5 : klant === K2 ? 2 : 3,
    allowed_license_types: ["beta", "admin"], enabled: klant === K3 ? 0 : 1, in_use: inGebruik(klant)
  });

  /* ---------------- de nepserver ---------------- */

  const echteFetch = window.fetch.bind(window);

  window.fetch = async (pad, opties = {}) => {
    if (typeof pad !== "string" || !pad.startsWith("/api/")) return echteFetch(pad, opties);

    const methode = (opties.method || "GET").toUpperCase();
    let body = {};
    try { body = opties.body ? JSON.parse(opties.body) : {}; } catch { body = {}; }
    let m;

    if (pad === "/api/admin/me") return antwoord({
      id: null, role: "owner", name: "Boris van der Werff", first_name: "Boris",
      username: "boris@cohentra.digital", email: "boris@cohentra.digital",
      recovery_codes_left: 8, permissions: ["*"], functions: [] });

    if (pad === "/api/support/inbox/sync") return antwoord({ linked: 0, more: false });
    if (pad === "/api/support/tickets" && methode === "GET") return antwoord({ tickets });

    if (pad === "/api/admin/customers" && methode === "GET") return antwoord({
      customers: db.klanten.map((k) => ({
        ...k, product_id: "eventhub", max_licenses: product(k.id).max_licenses,
        allowed_license_types: ["beta", "admin"], product_enabled: product(k.id).enabled,
        licenses_in_use: inGebruik(k.id),
        portal_users: (db.gebruikers[k.id] || []).length,
        open_tickets: tickets.filter((t) => t.customer_id === k.id && t.status !== "closed").length
      })) });

    if ((m = /^\/api\/admin\/customers\/([0-9a-f-]{36})$/i.exec(pad)) && methode === "GET") {
      const klant = db.klanten.find((k) => k.id === m[1]);
      if (!klant) return antwoord({ error: "Klant niet gevonden." }, 404);
      return antwoord({
        customer: klant, products: [product(klant.id)], catalog: [{ id: "eventhub", name: "EventHub" }],
        licenses: bereik(klant.id).licenses.filter((l) => !l.revoked_at),
        users: db.gebruikers[klant.id] || [],
        tickets: tickets.filter((t) => t.customer_id === klant.id)
      });
    }

    if ((m = /^\/api\/admin\/license-scope\/(intern|[0-9a-f-]{36})$/i.exec(pad)))
      return antwoord(bereik(m[1].toLowerCase() === "intern" ? null : m[1]));

    if (pad === "/api/admin/licenses/expiring") return antwoord({
      active: db.licenties.filter((l) => !l.revoked_at && l.valid_until >= VANDAAG).length,
      expiring: db.licenties
        .filter((l) => !l.revoked_at && l.valid_until >= VANDAAG && l.valid_until <= over(30))
        .sort((a, b) => a.valid_until < b.valid_until ? -1 : 1)
        .map((l) => ({
          ...l,
          customer_name: (db.klanten.find((k) => k.id === l.customer_id) || {}).name || null,
          group_name: (db.groepen.find((g) => g.id === l.group_id) || {}).name || null
        })) });

    if (pad === "/api/admin/licenses" && methode === "POST") {
      const max = body.customer_id ? product(body.customer_id).max_licenses : 0;
      if (body.customer_id && inGebruik(body.customer_id) + body.count > max)
        return antwoord({ error: "De klantlimiet is bereikt (" + inGebruik(body.customer_id) +
          " van " + max + " in gebruik)." }, 409);
      const uit = [];
      for (let i = 0; i < body.count; i++) {
        lic({
          label: body.count > 1
            ? (body.label || "Licentie") + " " + String(i + 1).padStart(3, "0")
            : (body.label || "Zonder naam"),
          customer_id: body.customer_id || null, group_id: body.group_id || null,
          license_type: body.license_type === "admin" ? "Beheerder" : "Gesloten beta",
          valid_until: body.license_type === "admin" ? "9999-12-31" : body.valid_until,
          created_at: new Date().toISOString()
        });
        uit.push({ label: db.licenties.at(-1).label, license_key: "EH-TEST-" + String(teller).padStart(4, "0") });
      }
      return antwoord({ licenses: uit }, 201);
    }

    if (pad === "/api/admin/licenses/extend" && methode === "POST") {
      let gelukt = 0, overgeslagen = 0;
      body.license_ids.forEach((id) => {
        const l = db.licenties.find((x) => x.id === id);
        if (l && !l.revoked_at && l.valid_until !== "9999-12-31") {
          l.valid_until = body.valid_until; l.expiry_notice_sent_at = null; gelukt++;
        } else overgeslagen++;
      });
      return antwoord({ ok: true, extended: gelukt, skipped: overgeslagen });
    }

    if (pad === "/api/admin/licenses/group" && methode === "POST") {
      let verplaatst = 0;
      body.license_ids.forEach((id) => {
        const l = db.licenties.find((x) => x.id === id);
        const g = body.group_id ? db.groepen.find((x) => x.id === body.group_id) : null;
        if (l && (!body.group_id || (g && g.customer_id === l.customer_id))) {
          l.group_id = body.group_id || null; verplaatst++;
        }
      });
      return antwoord({ ok: true, moved: verplaatst });
    }

    if ((m = /^\/api\/admin\/licenses\/([0-9a-f-]{36})\/(revoke|reset-activation|label|replace)$/i.exec(pad))) {
      const l = db.licenties.find((x) => x.id === m[1]);
      if (!l) return antwoord({ error: "Licentie niet gevonden." }, 404);
      if (m[2] === "revoke") l.revoked_at = new Date().toISOString();
      if (m[2] === "reset-activation") { l.activated_at = null; l.last_seen_at = null; }
      if (m[2] === "label") l.label = body.label;
      if (m[2] === "replace") {
        l.revoked_at = new Date().toISOString();
        lic({ ...l, id: undefined, revoked_at: null, activated_at: null, last_seen_at: null,
              created_at: new Date().toISOString() });
        db.licenties.at(-1).id = "cccccccc-0000-0000-0000-" + String(teller).padStart(12, "0");
        return antwoord({ ok: true, id: db.licenties.at(-1).id,
          license_key: "EH-NIEUW-" + String(teller).padStart(4, "0"), label: l.label }, 201);
      }
      return antwoord({ ok: true });
    }

    if (pad === "/api/admin/groups" && methode === "POST") {
      const eigenaar = body.customer_id || null;
      if (db.groepen.some((g) => g.customer_id === eigenaar &&
          g.name.toLowerCase() === String(body.name).toLowerCase()))
        return antwoord({ error: "Deze klant heeft al een groep met deze naam." }, 409);
      const id = groepId(100 + db.groepen.length);
      db.groepen.push({ id, customer_id: eigenaar, name: body.name });
      return antwoord({ id, name: body.name, customer_id: eigenaar }, 201);
    }

    if ((m = /^\/api\/admin\/groups\/([0-9a-f-]{36})$/i.exec(pad))) {
      const i = db.groepen.findIndex((g) => g.id === m[1]);
      if (i < 0) return antwoord({ error: "Groep niet gevonden." }, 404);
      if (methode === "PATCH") db.groepen[i].name = body.name;
      if (methode === "DELETE") {
        db.licenties.forEach((l) => { if (l.group_id === m[1]) l.group_id = null; });
        db.groepen.splice(i, 1);
      }
      return antwoord({ ok: true });
    }

    if (pad === "/api/admin/staff" && methode === "GET") return antwoord({ staff: medewerkers });
    if (pad === "/api/admin/functions" && methode === "GET") return antwoord({ functions: functies });

    if (pad.startsWith("/api/admin/email-templates")) return antwoord(
      { error: "De e-mailtemplates hebben geen testgegevens in deze testversie." }, 501);

    if (pad === "/api/auth/logout") return antwoord({ ok: true });

    // Alles wat hierboven niet staat: een vriendelijke melding in plaats van
    // een vastloper, zodat duidelijk is dat dit stuk geen testgegevens heeft.
    return antwoord({ error: "Deze actie heeft geen testgegevens. Kijk in worker.js voor de echte werking." }, 501);
  };

  /* ---------------- waarschuwingsbalkje ---------------- */

  document.addEventListener("DOMContentLoaded", () => {
    const balk = document.createElement("div");
    balk.textContent = "TESTVERSIE · verzonnen gegevens · niets wordt bewaard";
    balk.style.cssText = "position:fixed;left:10px;bottom:10px;z-index:99999;background:#17283a;" +
      "color:#fff;font:600 11px/1 system-ui,sans-serif;padding:7px 10px;border-radius:7px;" +
      "opacity:.88;pointer-events:none;letter-spacing:.02em";
    document.body.appendChild(balk);
    document.title = "TESTVERSIE · " + document.title;
  });
})();
</script>
"""


def main() -> int:
    if not WORKER.exists():
        print("worker.js niet gevonden naast deze map:", WORKER)
        return 1

    bron = WORKER.read_text(encoding="utf-8")
    try:
        begin = bron.index(START) + len(START)
    except ValueError:
        print("Het blok 'const ADMIN_HTML = String.raw`' staat niet in worker.js.")
        return 1
    einde = bron.index("`;", begin)
    pagina = bron[begin:einde]

    # De logo's serveert de worker zelf onder /brand/. Voor de testversie zetten
    # we ze als losse bestanden in de map brand/ naast het HTML-bestand.
    merkmap = HERE / "brand"
    for naam, data in re.findall(r'"(cohentra-[a-z-]+\.png)": "([A-Za-z0-9+/=]+)"', bron):
        merkmap.mkdir(exist_ok=True)
        (merkmap / naam).write_bytes(base64.b64decode(data))
    pagina = pagina.replace('"/brand/', '"brand/').replace("(/brand/", "(brand/")

    plek = pagina.index("<script>")
    UITVOER.write_text(pagina[:plek] + NEPSERVER + pagina[plek:], encoding="utf-8")

    print("Testversie gebouwd:", UITVOER.name)
    print("Regels uit worker.js:", bron[:begin].count("\n") + 1, "tot", bron[:einde].count("\n") + 1)
    print("Grootte:", f"{UITVOER.stat().st_size / 1024:.0f} kB")
    print("Open het bestand in een browser. Inloggen is niet nodig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
