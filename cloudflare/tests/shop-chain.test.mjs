// Ketentest: registratie → bestelling via (nagebootste) Stripe → betaalbevestiging → klantrecord in staffportaal
// → licentie → juiste functies → download. Plus organisaties, rechten, verlopen, mislukte betalingen, up-/downgrades,
// opzeggen, terugbetalen, dubbele/verkeerd geordende meldingen en afscherming tussen klanten.
// Uitvoeren vanuit de map cloudflare:  node --import ./tests/cf-register.mjs --test tests/shop-chain.test.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { createD1, createR2, createEmail, createFakeStripe, stripeEvent, signPayload } from "./harness.mjs";
import licenseWorker from "../license-worker/worker.js";
import { CUSTOMER_PORTAL_HTML } from "../license-worker/customer-portal.js";
import { handlePublic, handleCustomer, handleAdmin, safely } from "../shop-worker/app.js";
import vm from "node:vm";

const DB = createD1(), EMAIL = createEmail(), FILES = createR2(), stripe = createFakeStripe();
const WEBHOOK_SECRET = "whsec_test_secret";
const shopEnv = { DB, PRODUCT_FILES: FILES, STRIPE_SECRET_KEY: "sk_test_123", STRIPE_WEBHOOK_SECRET: WEBHOOK_SECRET, SHOP_CHECKOUT_ENABLED: "true", PUBLIC_SHOP_API_URL: "https://shop-api.cohentra.digital" };
const licenseEnv = {
  DB, EMAIL,
  SHOP: { customer: (request, identity) => safely(() => handleCustomer(request, shopEnv, identity)), admin: (request, actor) => safely(() => handleAdmin(request, shopEnv, actor)) }
};
const realFetch = globalThis.fetch;
globalThis.fetch = (url, init) => (String(url).startsWith("https://api.stripe.com") ? stripe.fetch(String(url), init) : realFetch(url, init));

async function parse(res) { const text = await res.text(); try { return JSON.parse(text); } catch { return text; } }
async function call(host, method, path, { token, body, headers = {} } = {}) {
  const init = { method, headers: { ...headers } };
  if (token) init.headers.Authorization = "Bearer " + token;
  if (body !== undefined) {
    if (body instanceof Uint8Array || typeof body === "string") init.body = body;
    else { init.body = JSON.stringify(body); init.headers["Content-Type"] = init.headers["Content-Type"] || "application/json"; }
  }
  const res = await licenseWorker.fetch(new Request(`https://${host}${path}`, init), licenseEnv);
  return { status: res.status, data: await parse(res), headers: res.headers };
}
const portal = (method, path, options) => call("customer.cohentra.digital", method, path, options);
const staff = (method, path, options) => call("staff.cohentra.digital", method, path, options);
async function shopApi(method, path, init = {}) { const res = await handlePublic(new Request("https://shop-api.cohentra.digital" + path, { method, ...init }), shopEnv); return { status: res.status, res, data: res.headers.get("Content-Type")?.includes("json") ? await parse(res) : null }; }
async function webhook(event, { secret = WEBHOOK_SECRET, signature } = {}) {
  const payload = JSON.stringify(event);
  const res = await handlePublic(new Request("https://shop-api.cohentra.digital/api/stripe/webhook", { method: "POST", body: payload, headers: { "Stripe-Signature": signature || signPayload(payload, secret) } }), shopEnv);
  return { status: res.status, data: await parse(res) };
}
const deviceId = () => crypto.randomUUID();
const validate = (key, device, product) => call("eventhub-licenses.eventhub-license.workers.dev", "POST", "/api/validate", { body: { license_key: key, device_id: device, ...(product ? { product_id: product } : {}) } });
const row = (sql, ...args) => { const r = DB.raw.prepare(sql).get(...args); return r ? { ...r } : null; };

async function staffSession({ role = "owner", functions = [] } = {}) {
  const token = crypto.randomUUID().replace(/-/g, "") + crypto.randomUUID().replace(/-/g, "");
  const hash = Buffer.from(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(token))).toString("hex");
  const now = new Date().toISOString();
  let staffId = null;
  if (role !== "owner") {
    staffId = crypto.randomUUID();
    DB.raw.prepare("INSERT INTO staff_access_tokens (id, name, token_hash, role, created_at, mfa_enabled) VALUES (?, 'Test medewerker', ?, 'support', ?, 1)").run(staffId, "x" + staffId, now);
    for (const f of functions) DB.raw.prepare("INSERT INTO staff_function_assignments (staff_id, function_key, assigned_at) VALUES (?, ?, ?)").run(staffId, f, now);
  }
  DB.raw.prepare("INSERT INTO staff_sessions (id, token_hash, staff_id, actor_role, created_at, expires_at, last_seen_at, mfa_verified) VALUES (?, ?, ?, ?, ?, ?, ?, 1)").run(crypto.randomUUID(), hash, staffId, role === "owner" ? "owner" : "support", now, Date.now() + 3600e3, now);
  return token;
}

async function registerAndVerify({ type, name, email, company }) {
  const r = await portal("POST", "/api/customer/auth/register", { body: { customer_type: type, name, email, company_name: company, password: "een-sterk-wachtwoord" } });
  assert.equal(r.status, 202, JSON.stringify(r.data));
  const mail = EMAIL.last(email);
  const token = /flow=verify&token=([a-f0-9]{64})/.exec(mail.text)[1];
  const v = await portal("POST", "/api/customer/auth/verify-email", { body: { token } });
  assert.equal(v.status, 200, JSON.stringify(v.data));
  return v.data.session_token;
}

async function buy(token, priceId, extra = {}) {
  const c = await portal("POST", "/api/customer/checkout", { token, body: { price_id: priceId, purchase_context: extra.context || "private", billing: extra.billing || { street: "Teststraat 1", postal_code: "1234 AB", city: "Utrecht", country: "Nederland" } } });
  assert.equal(c.status, 201, JSON.stringify(c.data));
  const order = row("SELECT * FROM shop_orders WHERE id = ?", c.data.order_id);
  return { order, session: stripe.state.sessions[order.stripe_checkout_session_id], url: c.data.url };
}

async function confirmCheckout(session, options) {
  stripe.completeCheckout(session.id, options);
  const r = await webhook(stripeEvent("checkout.session.completed", { id: session.id, object: "checkout.session" }));
  assert.equal(r.status, 200, JSON.stringify(r.data));
}
const summary = async (token) => (await portal("GET", "/api/customer/shop/summary", { token })).data;

const ctx = {};

test("staff zet een product met abonnementen, prijzen, functies en een download op", async () => {
  ctx.owner = await staffSession();
  const create = await staff("POST", "/api/admin/shop/products", { token: ctx.owner, body: { id: "planner", name: "Planner" } });
  assert.equal(create.status, 201, JSON.stringify(create.data));
  const features = await staff("PUT", "/api/admin/shop/products/planner/features", { token: ctx.owner, body: { features: [{ key: "export", name: "Exporteren", kind: "flag" }, { key: "max_events", name: "Evenementen", kind: "limit" }, { key: "live", name: "Live sessies", kind: "flag" }] } });
  assert.equal(features.status, 200, JSON.stringify(features.data));
  const plan = async (body) => { const r = await staff("POST", "/api/admin/shop/products/planner/plans", { token: ctx.owner, body }); assert.equal(r.status, 201, JSON.stringify(r.data)); return r.data.id; };
  ctx.basic = await plan({ code: "basis", name: "Basis", billing_type: "recurring", rank: 1, max_users: 1, max_activations: 1, features: { max_events: 10, onbekend: true } });
  ctx.pro = await plan({ code: "pro", name: "Pro", billing_type: "recurring", rank: 2, max_users: 3, max_activations: 3, features: { export: true, live: true, max_events: "unlimited" } });
  ctx.perpetual = await plan({ code: "los", name: "Losse licentie", billing_type: "one_time", rank: 0, max_activations: 1, features: { export: true } });
  const price = async (planId, body) => { const r = await staff("POST", `/api/admin/shop/plans/${planId}/prices`, { token: ctx.owner, body }); assert.equal(r.status, 201, JSON.stringify(r.data)); assert.equal(r.data.stripe_error, undefined); return r.data.id; };
  // Ontbrekende zakelijke keuzes worden niet ingevuld: zonder valuta of btw-keuze wordt de prijs geweigerd.
  const noTax = await staff("POST", `/api/admin/shop/plans/${ctx.basic}/prices`, { token: ctx.owner, body: { currency: "eur", unit_amount: 1000, interval: "month" } });
  assert.equal(noTax.status, 400);
  ctx.basicPrice = await price(ctx.basic, { currency: "eur", unit_amount: 1000, interval: "month", interval_count: 1, tax_behavior: "exclusive" });
  ctx.proPrice = await price(ctx.pro, { currency: "eur", unit_amount: 2500, interval: "month", interval_count: 1, tax_behavior: "exclusive" });
  ctx.perpetualPrice = await price(ctx.perpetual, { currency: "eur", unit_amount: 9900, tax_behavior: "inclusive" });
  assert.ok(row("SELECT stripe_price_id FROM plan_prices WHERE id = ?", ctx.basicPrice).stripe_price_id.startsWith("price_"));
  assert.deepEqual(JSON.parse(row("SELECT features_json FROM product_plans WHERE id = ?", ctx.basic).features_json), { max_events: 10 }, "onbekende functies worden genegeerd");
  // Publiceren vóór een gepubliceerd plan mag niet.
  const early = await staff("PATCH", "/api/admin/shop/products/planner", { token: ctx.owner, body: { name: "Planner", slug: "planner", published: true } });
  assert.equal(early.status, 409);
  for (const id of [ctx.basic, ctx.pro, ctx.perpetual]) {
    const p = row("SELECT * FROM product_plans WHERE id = ?", id);
    const r = await staff("PATCH", `/api/admin/shop/plans/${id}`, { token: ctx.owner, body: { name: p.name, rank: p.rank, max_users: p.max_users ?? "", max_activations: p.max_activations ?? "", features: JSON.parse(p.features_json), published: true } });
    assert.equal(r.status, 200, JSON.stringify(r.data));
  }
  const pub = await staff("PATCH", "/api/admin/shop/products/planner", { token: ctx.owner, body: { name: "Planner", slug: "planner", tagline: "Plannen zonder gedoe", description: "Uitleg", published: true } });
  assert.equal(pub.status, 200, JSON.stringify(pub.data));
  const png = new Uint8Array([137, 80, 78, 71, 1, 2, 3]);
  const img = await staff("POST", "/api/admin/shop/products/planner/images?alt=Planner", { token: ctx.owner, body: png, headers: { "Content-Type": "image/png" } });
  assert.equal(img.status, 201, JSON.stringify(img.data));
  const rel = await staff("POST", "/api/admin/shop/products/planner/releases", { token: ctx.owner, body: { version: "1.0.0", platform: "Windows", notes: "Eerste versie" } });
  assert.equal(rel.status, 201);
  ctx.release = rel.data.id;
  const notYet = await staff("PATCH", `/api/admin/shop/releases/${ctx.release}`, { token: ctx.owner, body: { published: true } });
  assert.equal(notYet.status, 409, "zonder bestand niet publiceren");
  const file = new TextEncoder().encode("installer-bytes");
  const up = await staff("PUT", `/api/admin/shop/releases/${ctx.release}/file?name=Planner%20Setup.exe`, { token: ctx.owner, body: file, headers: { "Content-Type": "application/octet-stream", "Content-Length": String(file.length) } });
  assert.equal(up.status, 200, JSON.stringify(up.data));
  assert.equal((await staff("PATCH", `/api/admin/shop/releases/${ctx.release}`, { token: ctx.owner, body: { published: true, notes: "Eerste versie" } })).status, 200);
});

test("EventHub is maatwerk: niet in productbeheer, niet te publiceren en niet in de catalogus", async () => {
  const list = await staff("GET", "/api/admin/shop/products", { token: ctx.owner });
  assert.ok(!list.data.products.some((p) => p.id === "eventhub"));
  assert.equal((await staff("PATCH", "/api/admin/shop/products/eventhub", { token: ctx.owner, body: { name: "EventHub", slug: "eventhub", published: true } })).status, 403);
  assert.equal((await staff("POST", "/api/admin/shop/products/eventhub/plans", { token: ctx.owner, body: { code: "x", name: "X", billing_type: "recurring" } })).status, 403);
  DB.raw.prepare("UPDATE products SET published = 1 WHERE id = 'eventhub'").run();
  assert.equal((await shopApi("GET", "/api/public/shop/products/eventhub")).status, 404, "zelfs gepubliceerd blijft maatwerk buiten de shop");
  DB.raw.prepare("UPDATE products SET published = 0 WHERE id = 'eventhub'").run();
});

test("publieke catalogus toont product, abonnementen, prijzen en functievergelijking; geen bestanden", async () => {
  const list = await shopApi("GET", "/api/public/shop/products");
  assert.equal(list.status, 200);
  assert.equal(list.data.products.length, 1);
  const detail = await shopApi("GET", "/api/public/shop/products/planner");
  assert.equal(detail.data.product.plans.length, 3);
  assert.equal(detail.data.product.features.length, 3);
  assert.equal(detail.data.product.latest_release.version, "1.0.0");
  assert.ok(!JSON.stringify(detail.data).includes("releases/"), "geen R2-sleutels in de publieke catalogus");
  assert.ok(detail.data.product.images[0].url.startsWith("https://shop-api.cohentra.digital/shop-media/"));
  assert.equal((await shopApi("GET", "/api/public/shop/products/bestaat-niet")).status, 404);
});

test("registratie maakt pas na e-mailbevestiging één klantrecord aan; dubbele registratie maakt geen tweede account", async () => {
  const before = row("SELECT COUNT(*) AS n FROM customers").n;
  const r = await portal("POST", "/api/customer/auth/register", { body: { customer_type: "individual", name: "Ilse de Vries", email: "ilse@example.com", password: "een-sterk-wachtwoord" } });
  assert.equal(r.status, 202);
  assert.equal(row("SELECT COUNT(*) AS n FROM customers").n, before, "nog geen klantrecord vóór bevestiging");
  const token = /token=([a-f0-9]{64})/.exec(EMAIL.last("ilse@example.com").text)[1];
  const v = await portal("POST", "/api/customer/auth/verify-email", { body: { token } });
  assert.equal(v.status, 200);
  ctx.ilse = v.data.session_token;
  assert.equal((await portal("POST", "/api/customer/auth/verify-email", { body: { token } })).status, 400, "link werkt één keer");
  const again = await portal("POST", "/api/customer/auth/register", { body: { customer_type: "business", name: "X", company_name: "Ander BV", email: "ILSE@example.com", password: "nog-een-wachtwoord" } });
  assert.equal(again.status, 202);
  assert.match(EMAIL.last("ilse@example.com").subject, /wachtwoord|Wachtwoord|herstel/i, "bestaand account krijgt een herstellink, geen tweede account");
  assert.equal(row("SELECT COUNT(*) AS n FROM customer_portal_accounts WHERE email = 'ilse@example.com'").n, 1);
  const customer = row("SELECT c.* FROM customers c JOIN customer_portal_accounts a ON a.customer_id = c.id WHERE a.email = 'ilse@example.com'");
  assert.equal(customer.customer_type, "individual");
  assert.equal(customer.source, "shop");
  ctx.ilseCustomer = customer.id;
  // Klantrecord staat in het bestaande klantoverzicht van het staffportaal.
  const list = await staff("GET", "/api/admin/customers", { token: ctx.owner });
  assert.ok(list.data.customers.some((c) => c.id === customer.id && c.customer_type === "individual"));
});

test("bestaande klant wordt alleen gekoppeld op een bevestigd, exact contact-e-mailadres", async () => {
  const created = await staff("POST", "/api/admin/customers", { token: ctx.owner, body: { name: "Bestaand BV", contact_email: "inkoop@bestaand.nl" } });
  assert.equal(created.status, 201);
  // Zelfde bedrijfsnaam, ander e-mailadres: geen koppeling.
  await registerAndVerify({ type: "business", name: "Iemand", email: "iemand@elders.nl", company: "Bestaand BV" });
  assert.equal(row("SELECT COUNT(*) AS n FROM customer_portal_accounts WHERE customer_id = ?", created.data.customer.id).n, 0);
  await registerAndVerify({ type: "business", name: "Inkoper", email: "inkoop@bestaand.nl", company: "Wat dan ook" });
  assert.equal(row("SELECT COUNT(*) AS n FROM customer_portal_accounts WHERE customer_id = ?", created.data.customer.id).n, 1);
});

test("terugkeren op de succespagina geeft geen toegang; alleen een geverifieerde webhook", async () => {
  const { order, session, url } = await buy(ctx.ilse, ctx.basicPrice, { context: "business", billing: { billing_company: "Ilse Ontwerp", vat_number: "NL123456789B01", kvk_number: "12345678", street: "Straat 1", postal_code: "1234AB", city: "Utrecht", country: "Nederland" } });
  assert.ok(url.startsWith("https://checkout.stripe.test/"));
  assert.equal(order.status, "pending");
  assert.equal(order.purchase_context, "business");
  assert.equal(JSON.parse(order.billing_json).billing_company, "Ilse Ontwerp");
  assert.equal(row("SELECT customer_type FROM customers WHERE id = ?", ctx.ilseCustomer).customer_type, "individual", "zakelijke aankoop maakt geen organisatieaccount");
  assert.equal(stripe.state.customers[session.customer].metadata.customer_id, ctx.ilseCustomer);
  const o = await portal("GET", `/api/customer/orders/${order.id}`, { token: ctx.ilse });
  assert.equal(o.data.order.status, "pending");
  assert.equal((await summary(ctx.ilse)).entitlements.length, 0);
  // Dezelfde bestelling opnieuw starten hergebruikt de open sessie: geen dubbele betaling.
  const again = await portal("POST", "/api/customer/checkout", { token: ctx.ilse, body: { price_id: ctx.basicPrice, purchase_context: "private", billing: {} } });
  assert.equal(again.data.reused, true);
  // Vervalste of oude handtekening wordt geweigerd.
  stripe.completeCheckout(session.id);
  const event = stripeEvent("checkout.session.completed", { id: session.id });
  assert.equal((await webhook(event, { secret: "whsec_fout" })).status, 400);
  assert.equal((await webhook(event, { signature: signPayload(JSON.stringify(event), WEBHOOK_SECRET, Math.floor(Date.now() / 1000) - 3600) })).status, 400);
  assert.equal(row("SELECT status FROM shop_orders WHERE id = ?", order.id).status, "pending");
  assert.equal((await webhook(event)).status, 200);
  assert.equal(row("SELECT status FROM shop_orders WHERE id = ?", order.id).status, "paid");
  // Dubbele melding: geen tweede recht of abonnement.
  assert.equal((await webhook(event)).data.duplicate, true);
  const copy = stripeEvent("checkout.session.completed", { id: session.id });
  assert.equal((await webhook(copy)).status, 200);
  assert.equal(row("SELECT COUNT(*) AS n FROM entitlements WHERE customer_id = ?", ctx.ilseCustomer).n, 1);
  assert.equal(row("SELECT COUNT(*) AS n FROM shop_subscriptions WHERE customer_id = ?", ctx.ilseCustomer).n, 1);
  const s = await summary(ctx.ilse);
  assert.equal(s.entitlements[0].status, "active");
  assert.deepEqual(s.entitlements[0].features, { max_events: 10 });
  assert.equal(s.subscriptions[0].status, "active");
  assert.equal(s.invoices.length, 1);
  ctx.ilseSub = s.subscriptions[0].id;
  ctx.ilseEnt = s.entitlements[0].id;
  // Tweede abonnement op hetzelfde product wordt geweigerd.
  const double = await portal("POST", "/api/customer/checkout", { token: ctx.ilse, body: { price_id: ctx.proPrice, billing: {} } });
  assert.equal(double.status, 409);
  assert.equal(double.data.code, "subscription_exists");
});

test("staffportaal toont klant, Stripe-klant, bestelling, abonnement, recht en historie", async () => {
  const d = await staff("GET", `/api/admin/customers/${ctx.ilseCustomer}/commerce`, { token: ctx.owner });
  assert.equal(d.status, 200, JSON.stringify(d.data));
  assert.ok(d.data.customer.stripe_url.startsWith("https://dashboard.stripe.com/test/customers/"));
  assert.equal(d.data.orders[0].status, "paid");
  assert.equal(d.data.subscriptions[0].status_label, "Actief");
  assert.equal(d.data.entitlements[0].use_allowed, true);
  assert.ok(d.data.history.some((h) => h.action === "checkout.started") && d.data.history.some((h) => h.action === "subscription.created"));
  // Een supportmedewerker zonder shoprechten ziet dit niet en kan geen producten beheren.
  ctx.support = await staffSession({ role: "support", functions: ["support"] });
  assert.equal((await staff("GET", `/api/admin/customers/${ctx.ilseCustomer}/commerce`, { token: ctx.support })).status, 403);
  assert.equal((await staff("POST", "/api/admin/shop/products", { token: ctx.support, body: { id: "x", name: "X" } })).status, 403);
  // Klanten met betaalhistorie kunnen niet worden verwijderd.
  const name = row("SELECT name FROM customers WHERE id = ?", ctx.ilseCustomer).name;
  assert.equal((await staff("DELETE", `/api/admin/customers/${ctx.ilseCustomer}`, { token: ctx.owner, body: { confirm_name: name } })).status, 409);
});

test("licentie → juiste functies; activatielimiet; download via tijdelijke link", async () => {
  const k = await portal("POST", `/api/customer/entitlements/${ctx.ilseEnt}/licenses`, { token: ctx.ilse, body: { label: "Laptop" } });
  assert.equal(k.status, 201, JSON.stringify(k.data));
  ctx.ilseKey = k.data.license.license_key;
  ctx.ilseDevice = deviceId();
  const v = await validate(ctx.ilseKey, ctx.ilseDevice, "planner");
  assert.equal(v.data.valid, true, JSON.stringify(v.data));
  assert.equal(v.data.plan, "Basis");
  assert.deepEqual(v.data.features, { max_events: 10 });
  assert.match(v.data.valid_until, /^\d{4}-\d{2}-\d{2}$/, "datumformaat dat EventHub kan lezen");
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice, "eventhub")).data.valid, false, "sleutel van ander product");
  assert.equal((await validate(ctx.ilseKey, deviceId())).data.valid, false, "één apparaat per sleutel");
  assert.equal((await portal("POST", `/api/customer/entitlements/${ctx.ilseEnt}/licenses`, { token: ctx.ilse, body: {} })).status, 409, "max. 1 activatie in Basis");
  const dl = await portal("POST", `/api/customer/downloads/${ctx.release}`, { token: ctx.ilse });
  assert.equal(dl.status, 200, JSON.stringify(dl.data));
  const path = new URL(dl.data.url).pathname;
  const file = await shopApi("GET", path);
  assert.equal(file.status, 200);
  assert.equal(await file.res.text(), "installer-bytes");
  assert.match(file.res.headers.get("Content-Disposition"), /attachment; filename="Planner Setup.exe"/);
  DB.raw.prepare("UPDATE download_tokens SET expires_at = 0").run();
  assert.equal((await shopApi("GET", path)).status, 410, "verlopen link werkt niet meer");
  assert.equal((await shopApi("GET", "/download/" + "a".repeat(64))).status, 410);
});

test("klanten kunnen geen gegevens, licenties, downloads of portalsessies van anderen benaderen", async () => {
  ctx.other = await registerAndVerify({ type: "individual", name: "Ander", email: "ander@example.com" });
  const s = await summary(ctx.other);
  assert.equal(s.entitlements.length + s.orders.length + s.licenses.length, 0);
  assert.equal((await portal("POST", `/api/customer/downloads/${ctx.release}`, { token: ctx.other })).status, 403);
  const order = row("SELECT id FROM shop_orders WHERE customer_id = ?", ctx.ilseCustomer);
  assert.equal((await portal("GET", `/api/customer/orders/${order.id}`, { token: ctx.other })).status, 404);
  assert.equal((await portal("POST", `/api/customer/subscriptions/${ctx.ilseSub}/cancel`, { token: ctx.other })).status, 404);
  assert.equal((await portal("POST", `/api/customer/entitlements/${ctx.ilseEnt}/licenses`, { token: ctx.other, body: {} })).status, 404);
  const lic = row("SELECT id FROM licenses WHERE entitlement_id = ?", ctx.ilseEnt);
  assert.equal((await portal("POST", `/api/customer/shop-licenses/${lic.id}/revoke`, { token: ctx.other })).status, 404);
  const portalSession = await portal("POST", "/api/customer/billing-portal", { token: ctx.other });
  assert.equal(portalSession.status, 404, "geen Stripe-klant → geen portalsessie, en zeker niet die van een ander");
  const own = await portal("POST", "/api/customer/billing-portal", { token: ctx.ilse });
  assert.equal(own.status, 200);
  assert.ok(own.data.url.endsWith(row("SELECT stripe_customer_id FROM customers WHERE id = ?", ctx.ilseCustomer).stripe_customer_id));
  assert.equal((await portal("GET", "/api/customer/shop/summary")).status, 401);
});

test("upgrade gaat direct in met verrekening; mislukte bijbetaling laat het oude plan staan", async () => {
  const preview = await portal("POST", `/api/customer/subscriptions/${ctx.ilseSub}/change-preview`, { token: ctx.ilse, body: { price_id: ctx.proPrice } });
  assert.equal(preview.data.timing, "immediate");
  assert.equal(preview.data.amount_due, 1500);
  stripe.state.failNextUpgradePayment = true;
  const failed = await portal("POST", `/api/customer/subscriptions/${ctx.ilseSub}/change`, { token: ctx.ilse, body: { price_id: ctx.proPrice } });
  assert.equal(failed.status, 200);
  assert.equal(failed.data.applied, false);
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.plan, "Basis");
  const ok = await portal("POST", `/api/customer/subscriptions/${ctx.ilseSub}/change`, { token: ctx.ilse, body: { price_id: ctx.proPrice } });
  assert.equal(ok.data.applied, true);
  const v = await validate(ctx.ilseKey, ctx.ilseDevice);
  assert.equal(v.data.plan, "Pro");
  assert.deepEqual(v.data.features, { export: true, live: true, max_events: "unlimited" });
  assert.equal(v.data.limits.max_activations, 3);
});

test("downgrade wordt gepland per einde periode en gaat pas bij verlenging in", async () => {
  stripe.state.rejectIterations = true; // nieuwere Stripe-API: terugval op 'duration'
  const r = await portal("POST", `/api/customer/subscriptions/${ctx.ilseSub}/change`, { token: ctx.ilse, body: { price_id: ctx.basicPrice } });
  assert.equal(r.status, 200, JSON.stringify(r.data));
  assert.equal(r.data.timing, "period_end");
  const sub = row("SELECT * FROM shop_subscriptions WHERE id = ?", ctx.ilseSub);
  assert.equal(sub.pending_price_id, ctx.basicPrice);
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.plan, "Pro", "tot periode-einde blijft Pro");
  const s = await summary(ctx.ilse);
  assert.equal(s.subscriptions[0].pending.plan_name, "Basis");
  // Opzeggen terwijl een wijziging gepland staat: de planning vervalt, opzegging lukt.
  const stripeSub = stripe.state.subs[sub.stripe_subscription_id];
  const inv = stripe.renew(stripeSub.id);
  await webhook(stripeEvent("invoice.paid", { id: inv.id }));
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.plan, "Basis");
  assert.equal(row("SELECT pending_price_id FROM shop_subscriptions WHERE id = ?", ctx.ilseSub).pending_price_id, null);
  assert.equal(row("SELECT COUNT(*) AS n FROM billing_invoices WHERE customer_id = ?", ctx.ilseCustomer).n, 2);
});

test("mislukte betaling: hersteltermijn (gebruik ja, download nee), herstel, en verkeerd geordende meldingen", async () => {
  const stripeSubId = row("SELECT stripe_subscription_id FROM shop_subscriptions WHERE id = ?", ctx.ilseSub).stripe_subscription_id;
  const failedInvoice = stripe.renew(stripeSubId, { paid: false });
  await webhook(stripeEvent("invoice.payment_failed", { id: failedInvoice.id }));
  let s = await summary(ctx.ilse);
  assert.equal(s.subscriptions[0].status, "past_due");
  assert.equal(s.entitlements[0].status, "grace");
  assert.ok(s.notices.some((n) => n.level === "error" && /mislukt/.test(n.text)));
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.valid, true);
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.recheck_after_seconds, 3600);
  assert.equal((await portal("POST", `/api/customer/downloads/${ctx.release}`, { token: ctx.ilse })).status, 403);
  // Optionele maximale hersteltermijn.
  shopEnv.SHOP_GRACE_DAYS = "0";
  DB.raw.prepare("UPDATE shop_subscriptions SET past_due_since = '2020-01-01T00:00:00.000Z' WHERE id = ?").run(ctx.ilseSub);
  await webhook(stripeEvent("customer.subscription.updated", { id: stripeSubId }));
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.valid, false);
  delete shopEnv.SHOP_GRACE_DAYS;
  // Betaling lukt alsnog; daarna komt de oude 'payment_failed' nog een keer (verkeerde volgorde) → blijft actief.
  const sub = stripe.state.subs[stripeSubId];
  sub.status = "active"; stripe.state.invoices[failedInvoice.id].status = "paid";
  await webhook(stripeEvent("invoice.paid", { id: failedInvoice.id }));
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.valid, true);
  const stale = stripeEvent("invoice.payment_failed", { id: failedInvoice.id, status: "open" }, { created: Math.floor(Date.now() / 1000) - 600 });
  await webhook(stale);
  s = await summary(ctx.ilse);
  assert.equal(s.subscriptions[0].status, "active");
  assert.equal(s.entitlements[0].status, "active");
});

test("handmatige uitzonderingen: met reden, los van Stripe, niet overschreven door webhooks", async () => {
  const noReason = await staff("POST", `/api/admin/entitlements/${ctx.ilseEnt}/overrides`, { token: ctx.owner, body: { kind: "suspend" } });
  assert.equal(noReason.status, 400);
  const sus = await staff("POST", `/api/admin/entitlements/${ctx.ilseEnt}/overrides`, { token: ctx.owner, body: { kind: "suspend", reason: "Misbruik onderzocht" } });
  assert.equal(sus.status, 201);
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.valid, false);
  const stripeSubId = row("SELECT stripe_subscription_id FROM shop_subscriptions WHERE id = ?", ctx.ilseSub).stripe_subscription_id;
  await webhook(stripeEvent("customer.subscription.updated", { id: stripeSubId }));
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.valid, false, "Stripe-update heft opschorting niet op");
  const feat = await staff("POST", `/api/admin/entitlements/${ctx.ilseEnt}/overrides`, { token: ctx.owner, body: { kind: "features", value: { set: { live: true } }, reason: "Pilot live sessies" } });
  assert.equal(feat.status, 201);
  assert.equal((await staff("POST", `/api/admin/overrides/${sus.data.id}/revoke`, { token: ctx.owner, body: { reason: "Onderzoek afgerond" } })).status, 200);
  const v = await validate(ctx.ilseKey, ctx.ilseDevice);
  assert.equal(v.data.valid, true);
  assert.deepEqual(v.data.features, { max_events: 10, live: true });
  const hist = (await staff("GET", `/api/admin/customers/${ctx.ilseCustomer}/commerce`, { token: ctx.owner })).data.history;
  assert.ok(hist.some((h) => h.action === "override.suspend" && h.reason === "Misbruik onderzocht" && h.actor_type === "staff"));
  assert.ok(hist.some((h) => h.action === "override.revoked"));
});

test("opzeggen: toegang tot einde periode, daarna verlopen; verlengen door staff geeft tijdelijk weer toegang", async () => {
  const c = await portal("POST", `/api/customer/subscriptions/${ctx.ilseSub}/cancel`, { token: ctx.ilse });
  assert.equal(c.status, 200, JSON.stringify(c.data));
  assert.equal(c.data.cancel_at_period_end, true);
  assert.ok(c.data.access_until);
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.valid, true);
  assert.ok((await summary(ctx.ilse)).notices.some((n) => /opgezegd/.test(n.text)));
  const resume = await portal("POST", `/api/customer/subscriptions/${ctx.ilseSub}/resume`, { token: ctx.ilse });
  assert.equal(resume.data.cancel_at_period_end, false);
  await portal("POST", `/api/customer/subscriptions/${ctx.ilseSub}/cancel`, { token: ctx.ilse });
  const stripeSubId = row("SELECT stripe_subscription_id FROM shop_subscriptions WHERE id = ?", ctx.ilseSub).stripe_subscription_id;
  Object.assign(stripe.state.subs[stripeSubId], { status: "canceled", ended_at: Math.floor(Date.now() / 1000) });
  // Een oude 'updated'-melding met verouderde inhoud na de 'deleted': de actuele stand blijft 'beëindigd'.
  await webhook(stripeEvent("customer.subscription.deleted", { id: stripeSubId }));
  await webhook(stripeEvent("customer.subscription.updated", { id: stripeSubId, status: "active" }, { created: 1 }));
  const v = await validate(ctx.ilseKey, ctx.ilseDevice);
  assert.equal(v.data.valid, false);
  assert.equal(v.data.entitlement_status, "expired");
  assert.match(v.data.message, /verlopen/);
  assert.equal((await portal("POST", `/api/customer/downloads/${ctx.release}`, { token: ctx.ilse })).status, 403);
  const until = new Date(Date.now() + 7 * 864e5).toISOString().slice(0, 10);
  await staff("POST", `/api/admin/entitlements/${ctx.ilseEnt}/overrides`, { token: ctx.owner, body: { kind: "extend", value: { until }, reason: "Coulance overstapperiode" } });
  assert.equal((await validate(ctx.ilseKey, ctx.ilseDevice)).data.valid, true);
});

test("eenmalige aankoop: volledig terugbetaald trekt in, gedeeltelijk niet", async () => {
  const { order, session } = await buy(ctx.other, ctx.perpetualPrice);
  await confirmCheckout(session);
  assert.equal(row("SELECT status FROM shop_orders WHERE id = ?", order.id).status, "paid");
  const ent = row("SELECT * FROM entitlements WHERE source = 'order' AND source_id = ?", order.id);
  assert.equal(ent.status, "active");
  assert.equal(ent.valid_until, null);
  const key = (await portal("POST", `/api/customer/entitlements/${ent.id}/licenses`, { token: ctx.other, body: {} })).data.license.license_key;
  const dev = deviceId();
  assert.equal((await validate(key, dev)).data.valid, true);
  assert.equal(row("SELECT COUNT(*) AS n FROM billing_invoices WHERE order_id = ?", order.id).n, 1, "één factuur, door Stripe");
  const again = await portal("POST", "/api/customer/checkout", { token: ctx.other, body: { price_id: ctx.perpetualPrice, billing: {} } });
  assert.equal(again.data.code, "already_owned");
  stripe.refund(session.charge, 1000);
  await webhook(stripeEvent("charge.refunded", { id: session.charge }));
  assert.equal(row("SELECT status FROM shop_orders WHERE id = ?", order.id).status, "partially_refunded");
  assert.equal((await validate(key, dev)).data.valid, true);
  stripe.refund(session.charge, 8900);
  const refundEvent = stripeEvent("charge.refunded", { id: session.charge });
  await webhook(refundEvent);
  await webhook(refundEvent);
  assert.equal(row("SELECT status FROM shop_orders WHERE id = ?", order.id).status, "refunded");
  const v = await validate(key, dev);
  assert.equal(v.data.valid, false);
  assert.match(v.data.message, /ingetrokken/);
});

test("mislukte en verlopen Checkout-sessies geven geen toegang", async () => {
  const token = await registerAndVerify({ type: "individual", name: "Laat", email: "laat@example.com" });
  const { order, session } = await buy(token, ctx.basicPrice);
  session.status = "expired";
  await webhook(stripeEvent("checkout.session.expired", { id: session.id }));
  assert.equal(row("SELECT status FROM shop_orders WHERE id = ?", order.id).status, "expired");
  assert.equal((await summary(token)).entitlements.length, 0);
});

test("organisatie: beheerder nodigt gebruikers uit binnen de limiet; gewone gebruiker beheert geen facturatie", async () => {
  const admin = await registerAndVerify({ type: "business", name: "Bea Beheer", email: "bea@orgbv.nl", company: "Org BV" });
  const customerId = row("SELECT customer_id FROM customer_portal_accounts WHERE email = 'bea@orgbv.nl'").customer_id;
  assert.equal((await portal("POST", "/api/customer/team", { token: admin, body: { name: "Tom", email: "tom@orgbv.nl" } })).status, 409, "zonder recht alleen de beheerder");
  const { session } = await buy(admin, ctx.proPrice);
  assert.equal(session.params.tax_id_collection.enabled, "true", "zakelijk: btw-nummer in Checkout");
  await confirmCheckout(session);
  for (const [n, e] of [["Tom", "tom@orgbv.nl"], ["Uma", "uma@orgbv.nl"]]) assert.equal((await portal("POST", "/api/customer/team", { token: admin, body: { name: n, email: e } })).status, 201);
  assert.equal((await portal("POST", "/api/customer/team", { token: admin, body: { name: "Vic", email: "vic@orgbv.nl" } })).status, 409, "Pro: max. 3 gebruikers");
  const invite = /flow=invite&token=([a-f0-9]{64})/.exec(EMAIL.last("tom@orgbv.nl").text)[1];
  assert.equal((await portal("POST", "/api/customer/auth/complete-email-auth", { body: { token: invite, flow: "invite", password: "tom-zijn-wachtwoord" } })).status, 200);
  const tom = (await portal("POST", "/api/customer/auth/login", { body: { username: "tom@orgbv.nl", password: "tom-zijn-wachtwoord" } })).data.session_token;
  const s = await summary(tom);
  assert.equal(s.account.role, "member");
  assert.equal(s.entitlements[0].plan_name, "Pro");
  assert.equal(s.orders.length + s.invoices.length, 0, "gebruiker ziet geen facturen");
  assert.equal((await portal("POST", "/api/customer/billing-portal", { token: tom })).status, 403);
  assert.equal((await portal("POST", "/api/customer/checkout", { token: tom, body: { price_id: ctx.basicPrice } })).status, 403);
  assert.equal((await portal("POST", `/api/customer/downloads/${ctx.release}`, { token: tom })).status, 200, "gebruiker mag wel downloaden");
  const sub = row("SELECT id, stripe_subscription_id FROM shop_subscriptions WHERE customer_id = ?", customerId);
  assert.equal((await portal("POST", `/api/customer/subscriptions/${sub.id}/cancel`, { token: tom })).status, 403);
  assert.equal(stripe.state.subs[sub.stripe_subscription_id].customer, row("SELECT stripe_customer_id FROM customers WHERE id = ?", customerId).stripe_customer_id, "betaling hoort bij de organisatie");
  // Staff zet Tom op beheerder; de laatste beheerder kan niet worden gedegradeerd.
  const bea = row("SELECT id FROM customer_portal_accounts WHERE email = 'bea@orgbv.nl'").id;
  assert.equal((await staff("PUT", `/api/admin/portal-users/${bea}/role`, { token: ctx.owner, body: { role: "member" } })).status, 409);
});

test("bestaande klanten met EventHub-quotum blijven werken (regressie)", async () => {
  const c = await staff("POST", "/api/admin/customers", { token: ctx.owner, body: { name: "Legacy BV", contact_email: "legacy@example.com", max_licenses: 2, allowed_license_types: ["beta"] } });
  const accountId = crypto.randomUUID(), now = new Date().toISOString();
  const { hashPassword } = await import("./password-helper.mjs");
  const cred = await hashPassword("legacy-wachtwoord");
  DB.raw.prepare("INSERT INTO customer_portal_accounts (id, customer_id, username, name, email, password_salt, password_hash, active, created_at, updated_at) VALUES (?, ?, 'legacy@example.com', 'Leg', 'legacy@example.com', ?, ?, 1, ?, ?)").run(accountId, c.data.customer.id, cred.salt, cred.hash, now, now);
  const token = (await portal("POST", "/api/customer/auth/login", { body: { username: "legacy@example.com", password: "legacy-wachtwoord" } })).data.session_token;
  assert.ok(token);
  const me = await portal("GET", "/api/customer/me", { token });
  assert.equal(me.data.customer.legacy_licensing, true);
  assert.equal(me.data.customer.role, "admin");
  const today = new Date().toISOString().slice(0, 10);
  const lic = await portal("POST", "/api/customer/licenses", { token, body: { license_type: "beta", valid_from: today, valid_until: today } });
  assert.equal(lic.status, 201, JSON.stringify(lic.data));
  const v = await validate(lic.data.license.license_key, deviceId());
  assert.equal(v.data.valid, true);
  assert.equal(v.data.license_type, "Gesloten beta");
  assert.equal(v.data.valid_until, today);
  // Bestaande klant houdt ook ticket-, overzicht- en wachtwoordfuncties, en ziet geen shoprechten die hij niet heeft.
  assert.equal((await portal("GET", "/api/customer/tickets", { token })).status, 200);
  assert.equal((await portal("GET", "/api/customer/licenses", { token })).data.licenses.length, 1);
  const legacySummary = await summary(token);
  assert.equal(legacySummary.entitlements.length, 0);
  assert.equal(legacySummary.account.role, "admin");
  // Shopklant zonder quotum kan geen quotumlicentie maken.
  assert.equal((await portal("POST", "/api/customer/licenses", { token: ctx.other, body: { license_type: "beta", valid_from: today, valid_until: today } })).status, 403);
});

test("meldingen uit de verkeerde modus worden genegeerd; Checkout dicht zonder schakelaar", async () => {
  const live = stripeEvent("checkout.session.completed", { id: "cs_live_x" }, { livemode: true });
  const r = await webhook(live);
  assert.equal(r.data.ignored, true);
  shopEnv.SHOP_CHECKOUT_ENABLED = "false";
  const closed = await portal("POST", "/api/customer/checkout", { token: ctx.other, body: { price_id: ctx.basicPrice } });
  assert.equal(closed.status, 503);
  shopEnv.SHOP_CHECKOUT_ENABLED = "true";
  shopEnv.STRIPE_SECRET_KEY = "sk_live_abc";
  const status = await staff("GET", "/api/admin/shop/status", { token: ctx.owner });
  assert.equal(status.data.config.checkout_ready, false);
  assert.ok(status.data.config.problems.some((p) => /STRIPE_ALLOW_LIVE/.test(p)));
  shopEnv.STRIPE_SECRET_KEY = "sk_test_123";
});

test("pagina's: staffportaal bevat Shop, klantenportaal laadt, browserscripts parsen", async () => {
  const page = await licenseWorker.fetch(new Request("https://staff.cohentra.digital/"), licenseEnv);
  const html = await page.text();
  assert.ok(html.includes('id="shopNav"') && html.includes('id="view-shop"'));
  const customerPage = await (await licenseWorker.fetch(new Request("https://customer.cohentra.digital/"), licenseEnv)).text();
  assert.equal(customerPage, CUSTOMER_PORTAL_HTML);
  for (const source of [html, customerPage]) {
    for (const [, script] of source.matchAll(/<script>([\s\S]*?)<\/script>/g)) new vm.Script(script);
  }
});
