// Lokale ontwikkelserver met demodata, alleen voor visuele controle (geen echte Stripe, geen echte e-mail).
//   node --import ./cloudflare/tests/cf-register.mjs cloudflare/tests/dev-server.mjs
// Eén poort (PORT, standaard 8790): website localhost, klantenportaal customer.localhost, staffportaal staff.localhost, shop-API shop-api.localhost
import http from "node:http";
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createD1, createR2, createEmail, createFakeStripe, stripeEvent, signPayload } from "./harness.mjs";
import licenseWorker from "../license-worker/worker.js";
import { handlePublic, handleCustomer, handleAdmin, safely } from "../shop-worker/app.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SITE = path.join(ROOT, "cohentra-pages-upload");
const PORT = Number(process.env.PORT || 8790);
const at = (sub) => `http://${sub ? sub + "." : ""}localhost:${PORT}`;
const DB = createD1(), EMAIL = createEmail(), FILES = createR2(), stripe = createFakeStripe();
const shopEnv = { DB, PRODUCT_FILES: FILES, STRIPE_SECRET_KEY: "sk_test_dev", STRIPE_WEBHOOK_SECRET: "whsec_dev", SHOP_CHECKOUT_ENABLED: "true", PUBLIC_SHOP_API_URL: at("shop-api"), PUBLIC_CUSTOMER_URL: at("customer") };
const licenseEnv = { DB, EMAIL, PUBLIC_CUSTOMER_URL: at("customer"), SHOP: { customer: (r, i) => safely(() => handleCustomer(r, shopEnv, i)), admin: (r, a) => safely(() => handleAdmin(r, shopEnv, a)) } };
const realFetch = globalThis.fetch;
globalThis.fetch = (url, init) => (String(url).startsWith("https://api.stripe.com") ? stripe.fetch(String(url), init) : realFetch(url, init));

const call = async (host, method, p, { token, body, headers = {} } = {}) => {
  const init = { method, headers: { ...headers } };
  if (token) init.headers.Authorization = "Bearer " + token;
  if (body !== undefined) { if (body instanceof Uint8Array) init.body = body; else { init.body = JSON.stringify(body); init.headers["Content-Type"] = "application/json"; } }
  const res = await licenseWorker.fetch(new Request(`https://${host}${p}`, init), licenseEnv);
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(`${method} ${p}: ${res.status} ${JSON.stringify(data)}`);
  return data;
};
const webhook = async (event) => { const payload = JSON.stringify(event); await handlePublic(new Request("https://x/api/stripe/webhook", { method: "POST", body: payload, headers: { "Stripe-Signature": signPayload(payload, "whsec_dev") } }), shopEnv); };

async function seed() {
  const ownerToken = "dev".padEnd(64, "0");
  const hash = Buffer.from(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(ownerToken))).toString("hex"), now = new Date().toISOString();
  DB.raw.prepare("INSERT INTO owner_mfa (id, name, first_name, totp_secret_enc, mfa_enabled, username) VALUES (1, 'Demo Beheerder', 'Demo', 'x', 1, 'demo')").run();
  DB.raw.prepare("INSERT INTO staff_sessions (id, token_hash, staff_id, actor_role, created_at, expires_at, last_seen_at, mfa_verified) VALUES (?, ?, NULL, 'owner', ?, ?, ?, 1)").run(crypto.randomUUID(), hash, now, Date.now() + 864e5, now);
  // Houd de demosessie actief (de echte portal meldt na 30 minuten inactiviteit af).
  setInterval(() => DB.raw.prepare("UPDATE staff_sessions SET last_seen_at = ?").run(new Date().toISOString()), 60000);
  const s = (m, p, o) => call("staff.cohentra.digital", m, p, { token: ownerToken, ...o });
  // Fictief demoproduct; EventHub is maatwerk en staat niet in de shop.
  await s("POST", "/api/admin/shop/products", { body: { id: "planner", name: "Planner" } });
  await s("PUT", "/api/admin/shop/products/planner/features", { body: { features: [
    { key: "events", name: "Evenementen beheren", kind: "flag" }, { key: "checkin", name: "Live check-in", kind: "flag" }, { key: "dashboard", name: "Live dashboard", kind: "flag" },
    { key: "devices", name: "Gekoppelde check-inapparaten", kind: "limit", description: "Per livesessie" }, { key: "export", name: "Rapportages exporteren", kind: "flag" } ] } });
  const plan = async (b) => (await s("POST", "/api/admin/shop/products/planner/plans", { body: b })).id;
  const start = await plan({ code: "start", name: "Start", billing_type: "recurring", rank: 1, max_users: 1, max_activations: 1, features: { events: true, checkin: true, devices: 2 } });
  const team = await plan({ code: "team", name: "Team", billing_type: "recurring", rank: 2, max_users: 5, max_activations: 5, features: { events: true, checkin: true, dashboard: true, devices: 10, export: true } });
  const org = await plan({ code: "organisatie", name: "Organisatie", billing_type: "recurring", rank: 3, max_users: 25, features: { events: true, checkin: true, dashboard: true, devices: "unlimited", export: true } });
  const prices = {};
  for (const [id, m, y] of [[start, 1900, 19000], [team, 4900, 49000], [org, 12900, 129000]]) {
    prices[id] = (await s("POST", `/api/admin/shop/plans/${id}/prices`, { body: { currency: "eur", unit_amount: m, interval: "month", tax_behavior: "exclusive" } })).id;
    await s("POST", `/api/admin/shop/plans/${id}/prices`, { body: { currency: "eur", unit_amount: y, interval: "year", tax_behavior: "exclusive" } });
  }
  for (const [id, n, d, r, u, a, f] of [[start, "Start", "Voor wie zelf evenementen organiseert.", 1, 1, 1, { events: true, checkin: true, devices: 2 }], [team, "Team", "Voor teams die samen evenementen draaien.", 2, 5, 5, { events: true, checkin: true, dashboard: true, devices: 10, export: true }], [org, "Organisatie", "Voor organisaties met veel evenementen.", 3, 25, "", { events: true, checkin: true, dashboard: true, devices: "unlimited", export: true }]])
    await s("PATCH", `/api/admin/shop/plans/${id}`, { body: { name: n, description: d, rank: r, max_users: u, max_activations: a, trial_days: id === team ? 14 : 0, features: f, published: true } });
  await s("PATCH", "/api/admin/shop/products/planner", { body: { name: "Planner", slug: "planner", tagline: "Fictief demoproduct om de shop te testen.", description: "Dit is een fictief product, alleen bedoeld om de shop lokaal te bekijken.\n\nProductnaam, functies en prijzen zijn voorbeelden.", published: true } });
  for (const img of ["cohentra-beeldmerk.png"]) {
    const bytes = new Uint8Array(readFileSync(path.join(SITE, "images", img)));
    await s("POST", "/api/admin/shop/products/planner/images?alt=Planner", { body: bytes, headers: { "Content-Type": "image/png" } });
  }
  const rel = (await s("POST", "/api/admin/shop/products/planner/releases", { body: { version: "0.4.0", platform: "Windows", notes: "Shopversie met licentiecontrole per abonnement.\nVerbeterde live check-in." } })).id;
  await s("PUT", `/api/admin/shop/releases/${rel}/file?name=Planner-0.4.0-Setup.exe`, { body: new TextEncoder().encode("demo"), headers: { "Content-Type": "application/octet-stream", "Content-Length": "4" } });
  await s("PATCH", `/api/admin/shop/releases/${rel}`, { body: { published: true, notes: "Shopversie met licentiecontrole per abonnement.\nVerbeterde live check-in." } });
  // Demoklant (organisatie) met een actief Team-abonnement, een licentie en een mislukte betaling als melding.
  await call("customer.cohentra.digital", "POST", "/api/customer/auth/register", { body: { customer_type: "business", name: "Sanne Vos", company_name: "Vos Events BV", email: "sanne@vosevents.nl", password: "demo-wachtwoord-1" } });
  const token = /token=([a-f0-9]{64})/.exec(EMAIL.last("sanne@vosevents.nl").text)[1];
  const session = (await call("customer.cohentra.digital", "POST", "/api/customer/auth/verify-email", { body: { token } })).session_token;
  const c = (m, p, o) => call("customer.cohentra.digital", m, p, { token: session, ...o });
  const checkout = await c("POST", "/api/customer/checkout", { body: { price_id: prices[team], billing: { street: "Havenweg 12", postal_code: "3511 AB", city: "Utrecht", country: "Nederland", vat_number: "NL123456789B01", kvk_number: "12345678" } } });
  const order = DB.raw.prepare("SELECT stripe_checkout_session_id FROM shop_orders WHERE id = ?").get(checkout.order_id);
  const cs = stripe.completeCheckout(order.stripe_checkout_session_id);
  await webhook(stripeEvent("checkout.session.completed", { id: cs.id }));
  const sum = await c("GET", "/api/customer/shop/summary");
  await c("POST", `/api/customer/entitlements/${sum.entitlements[0].id}/licenses`, { body: { label: "Laptop Sanne" } });
  await c("POST", "/api/customer/team", { body: { name: "Tom de Wit", email: "tom@vosevents.nl" } });
  // Bestaande EventHub-klant (maatwerk) met quotum, zoals Cohentra die nu al aanmaakt.
  const legacy = await s("POST", "/api/admin/customers", { body: { name: "Gemeente Voorbeeld", contact_email: "eventhub@voorbeeld.nl", max_licenses: 5, allowed_license_types: ["beta"] } });
  const { hashPassword } = await import("./password-helper.mjs");
  const cred = await hashPassword("demo-wachtwoord-2"), stamp = new Date().toISOString();
  DB.raw.prepare("INSERT INTO customer_portal_accounts (id, customer_id, username, name, email, password_salt, password_hash, active, created_at, updated_at) VALUES (?, ?, 'eventhub@voorbeeld.nl', 'Eva', 'eventhub@voorbeeld.nl', ?, ?, 1, ?, ?)").run(crypto.randomUUID(), legacy.customer.id, cred.salt, cred.hash, stamp, stamp);
  console.log("Bestaande EventHub-klant: eventhub@voorbeeld.nl / demo-wachtwoord-2");
  console.log(`Staff-token (zet in sessionStorage 'eventhub-admin-token'): ${ownerToken}`);
  console.log(`Klant: sanne@vosevents.nl / demo-wachtwoord-1`);
  console.log(`Prijs voor ?buy=: ${prices[start]}`);
}

const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".png": "image/png", ".svg": "image/svg+xml" };
function serveSite(req, res) {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p === "/") p = "/index.html";
  if (!path.extname(p)) p += ".html";
  const file = path.join(SITE, path.normalize(p));
  if (!file.startsWith(SITE) || !existsSync(file)) { res.writeHead(404); return res.end("Niet gevonden"); }
  let body = readFileSync(file);
  if (file.endsWith(".html")) body = body.toString().replace("https://shop-api.cohentra.digital", at("shop-api")).replace(/content="https:\/\/customer\.cohentra\.digital"/, `content="${at("customer")}"`);
  res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream" });
  res.end(body);
}

async function toRequest(req) {
  const chunks = []; for await (const chunk of req) chunks.push(chunk);
  const headers = new Headers(); for (const [k, v] of Object.entries(req.headers)) if (typeof v === "string") headers.set(k, v);
  return { chunks, headers };
}

await seed();
// Eén poort; de hostnaam bepaalt welke worker antwoordt, zodat origins (en CSP 'self') gescheiden blijven zoals live.
const HOSTS = { customer: "customer.cohentra.digital", staff: "staff.cohentra.digital" };
http.createServer(async (req, res) => {
  const sub = String(req.headers.host || "").split(".")[0].split(":")[0];
  if (!["customer", "staff", "shop-api"].includes(sub)) return serveSite(req, res);
  const { chunks, headers } = await toRequest(req);
  const target = sub === "shop-api" ? `http://shop-api.localhost${req.url}` : `https://${HOSTS[sub]}${req.url}`;
  const request = new Request(target, { method: req.method, headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : Buffer.concat(chunks) });
  try {
    const response = sub === "shop-api" ? await handlePublic(request, shopEnv) : await licenseWorker.fetch(request, licenseEnv);
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch (error) { console.error(error); res.writeHead(500); res.end(String(error)); }
}).listen(PORT);
console.log(`Dev-server klaar: ${at("")}/shop · ${at("customer")} · ${at("staff")} · ${at("shop-api")}`);
