// Testomgeving: echte migraties in SQLite (D1-shim), R2- en e-mailmock en een nagebootste Stripe-API.
import { DatabaseSync } from "node:sqlite";
import { readFileSync, readdirSync } from "node:fs";
import { createHmac } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.dirname(fileURLToPath(import.meta.url));

export function createD1() {
  const db = new DatabaseSync(":memory:");
  db.exec("PRAGMA foreign_keys = ON");
  const dir = path.join(ROOT, "..", "license-worker", "migrations");
  for (const file of readdirSync(dir).filter((f) => f.endsWith(".sql")).sort()) db.exec(readFileSync(path.join(dir, file), "utf8").replace(/^﻿/, ""));
  const clean = (args) => args.map((v) => (v === undefined ? null : typeof v === "boolean" ? (v ? 1 : 0) : v));
  class Stmt {
    constructor(sql, args = []) { this.sql = sql; this.args = args; }
    bind(...args) { return new Stmt(this.sql, args); }
    async first(column) { const row = db.prepare(this.sql).get(...clean(this.args)); if (!row) return null; const o = { ...row }; return column ? o[column] : o; }
    async all() { return { results: db.prepare(this.sql).all(...clean(this.args)).map((r) => ({ ...r })) }; }
    runSync() { const info = db.prepare(this.sql).run(...clean(this.args)); return { meta: { changes: Number(info.changes) } }; }
    async run() { return this.runSync(); }
  }
  return {
    raw: db,
    prepare: (sql) => new Stmt(sql),
    async batch(statements) {
      db.exec("BEGIN");
      try { const out = statements.map((s) => s.runSync()); db.exec("COMMIT"); return out; }
      catch (error) { db.exec("ROLLBACK"); throw error; }
    }
  };
}

export function createR2() {
  const store = new Map();
  return {
    store,
    async put(key, value) {
      let bytes;
      if (value instanceof Uint8Array) bytes = value;
      else if (value instanceof ReadableStream) bytes = new Uint8Array(await new Response(value).arrayBuffer());
      else bytes = new Uint8Array(await new Response(value).arrayBuffer());
      store.set(key, bytes);
    },
    async get(key) { const bytes = store.get(key); return bytes ? { body: new Blob([bytes]).stream(), size: bytes.length } : null; },
    async delete(key) { store.delete(key); }
  };
}

export function createEmail() {
  const sent = [];
  return { sent, async send(message) { sent.push(message); }, last(to) { return [...sent].reverse().find((m) => m.to === to); } };
}

function parseForm(body) {
  const out = {};
  for (const [key, value] of new URLSearchParams(body || "")) {
    const parts = key.replace(/\]/g, "").split("[");
    let o = out;
    parts.forEach((part, i) => {
      if (i === parts.length - 1) o[part] = value;
      else { o[part] = o[part] ?? (/^\d+$/.test(parts[i + 1]) ? [] : {}); o = o[part]; }
    });
  }
  return out;
}

// Een vereenvoudigde, maar gedragsgetrouwe Stripe: objecten blijven bewaard en worden bij GET actueel teruggegeven.
export function createFakeStripe() {
  const s = { customers: {}, products: {}, prices: {}, sessions: {}, subs: {}, schedules: {}, invoices: {}, charges: {}, idem: {}, calls: [], seq: 0, failNextUpgradePayment: false };
  const now = () => Math.floor(Date.now() / 1000);
  const newId = (prefix) => `${prefix}_${(++s.seq).toString(36)}${Math.random().toString(36).slice(2, 7)}`;
  const ok = (data) => new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
  const fail = (status, message) => new Response(JSON.stringify({ error: { message } }), { status, headers: { "Content-Type": "application/json" } });
  const invoiceFor = (customer, amount, extra = {}) => {
    const inv = { id: newId("in"), object: "invoice", customer, status: "paid", amount_due: amount, amount_paid: amount, currency: "eur", number: "TEST-" + s.seq, created: now(), hosted_invoice_url: "https://invoice.stripe.test/" + s.seq, invoice_pdf: null, lines: { data: [{ period: { start: now(), end: now() + 30 * 86400 } }] }, metadata: {}, livemode: false, ...extra };
    s.invoices[inv.id] = inv; return inv;
  };

  async function handle(method, route, params) {
    let m;
    if (method === "POST" && route === "/v1/customers") { const c = { id: newId("cus"), object: "customer", ...params }; s.customers[c.id] = c; return ok(c); }
    if ((m = /^\/v1\/customers\/([^/]+)$/.exec(route)) && method === "POST") { if (!s.customers[m[1]]) return fail(404, "No such customer"); Object.assign(s.customers[m[1]], params); return ok(s.customers[m[1]]); }
    if ((m = /^\/v1\/customers\/([^/]+)\/tax_ids$/.exec(route))) { const c = s.customers[m[1]]; c.tax_ids = c.tax_ids || []; if (method === "POST") { c.tax_ids.push({ type: params.type, value: params.value }); return ok({ id: newId("txi"), ...params }); } return ok({ data: c.tax_ids }); }
    if (method === "POST" && route === "/v1/products") { const p = { id: newId("prod"), ...params }; s.products[p.id] = p; return ok(p); }
    if (method === "POST" && route === "/v1/prices") { const p = { id: newId("price"), object: "price", active: true, currency: params.currency, unit_amount: Number(params.unit_amount), product: params.product, tax_behavior: params.tax_behavior, recurring: params.recurring ? { interval: params.recurring.interval, interval_count: Number(params.recurring.interval_count) } : null }; s.prices[p.id] = p; return ok(p); }
    if ((m = /^\/v1\/prices\/([^/]+)$/.exec(route))) { const p = s.prices[m[1]]; if (!p) return fail(404, "No such price"); if (method === "POST") p.active = params.active !== "false"; return ok(p); }
    if (method === "POST" && route === "/v1/checkout/sessions") {
      const price = s.prices[params.line_items[0].price];
      const cs = { id: newId("cs_test"), object: "checkout.session", mode: params.mode, customer: params.customer, client_reference_id: params.client_reference_id, metadata: params.metadata || {}, status: "open", payment_status: "unpaid", url: "https://checkout.stripe.test/pay/" + s.seq, livemode: false, amount_total: price.unit_amount, price: price.id, params };
      s.sessions[cs.id] = cs; return ok(cs);
    }
    if ((m = /^\/v1\/checkout\/sessions\/([^/]+)$/.exec(route))) { const cs = s.sessions[m[1]]; return cs ? ok(cs) : fail(404, "No such session"); }
    if ((m = /^\/v1\/subscriptions\/([^/]+)$/.exec(route))) {
      const sub = s.subs[m[1]]; if (!sub) return fail(404, "No such subscription");
      if (method === "DELETE") { sub.status = "canceled"; sub.ended_at = now(); sub.canceled_at = now(); return ok(sub); }
      if (method === "POST") {
        if (params.cancel_at_period_end !== undefined) { if (sub.schedule) return fail(400, "Subscription is managed by a schedule"); sub.cancel_at_period_end = params.cancel_at_period_end === "true"; }
        if (params.items) {
          if (s.failNextUpgradePayment && params.payment_behavior === "pending_if_incomplete") { s.failNextUpgradePayment = false; sub.pending_update = { price: params.items[0].price }; return ok(sub); }
          sub.items.data[0].price = { id: params.items[0].price };
        }
      }
      return ok(sub);
    }
    if (method === "POST" && route === "/v1/subscription_schedules") {
      const sub = s.subs[params.from_subscription];
      const sch = { id: newId("sub_sched"), subscription: sub.id, status: "active", end_behavior: "release", phases: [{ start_date: sub.current_period_start, end_date: sub.current_period_end, items: [{ price: sub.items.data[0].price.id }] }] };
      s.schedules[sch.id] = sch; sub.schedule = sch.id; return ok(sch);
    }
    if ((m = /^\/v1\/subscription_schedules\/([^/]+)\/release$/.exec(route))) { const sch = s.schedules[m[1]]; sch.status = "released"; s.subs[sch.subscription].schedule = null; return ok(sch); }
    if ((m = /^\/v1\/subscription_schedules\/([^/]+)$/.exec(route))) {
      const sch = s.schedules[m[1]]; if (!sch) return fail(404, "No such schedule");
      if (method === "POST" && params.phases) {
        if (s.rejectIterations && params.phases[1].iterations) return fail(400, "Received unknown parameter: phases[1][iterations]");
        const first = params.phases[0];
        sch.phases = [{ start_date: Number(first.start_date), end_date: Number(first.end_date), items: [{ price: first.items[0].price }] }, { start_date: Number(first.end_date), end_date: null, items: [{ price: params.phases[1].items[0].price }] }];
      }
      return ok(sch);
    }
    if (method === "POST" && route === "/v1/invoices/create_preview") return ok({ amount_due: 1500, currency: "eur" });
    if ((m = /^\/v1\/invoices\/([^/]+)$/.exec(route))) { const inv = s.invoices[m[1]]; return inv ? ok(inv) : fail(404, "No such invoice"); }
    if ((m = /^\/v1\/charges\/([^/]+)$/.exec(route))) { const ch = s.charges[m[1]]; return ch ? ok(ch) : fail(404, "No such charge"); }
    if (method === "POST" && route === "/v1/billing_portal/sessions") return ok({ id: newId("bps"), url: "https://billing.stripe.test/session/" + params.customer });
    return fail(404, `Fake Stripe kent ${method} ${route} niet`);
  }

  const api = {
    state: s,
    async fetch(url, init = {}) {
      const u = new URL(url), method = init.method || "GET";
      const params = method === "GET" ? parseForm(u.search.slice(1)) : parseForm(init.body);
      const auth = (init.headers || {}).Authorization || "";
      if (!/^Bearer sk_test_/.test(auth)) return fail(401, "Invalid API key");
      const key = (init.headers || {})["Idempotency-Key"];
      s.calls.push({ method, route: u.pathname, params, key });
      if (key && s.idem[key]) return new Response(s.idem[key], { status: 200, headers: { "Content-Type": "application/json" } });
      const response = await handle(method, u.pathname, params);
      if (key && response.ok) s.idem[key] = await response.clone().text();
      return response;
    },
    // Simuleert een klant die in Stripe Checkout betaalt.
    completeCheckout(sessionId, { paid = true, trialDays = 0 } = {}) {
      const cs = s.sessions[sessionId];
      cs.status = "complete"; cs.payment_status = paid ? "paid" : "unpaid";
      if (cs.mode === "subscription") {
        const start = now(), trial = Number(cs.params.subscription_data?.trial_period_days || trialDays || 0);
        const sub = { id: newId("sub"), object: "subscription", customer: cs.customer, status: trial ? "trialing" : "active", items: { data: [{ id: newId("si"), price: { id: cs.price }, current_period_start: start, current_period_end: start + 30 * 86400 }] }, metadata: cs.params.subscription_data?.metadata || {}, cancel_at_period_end: false, current_period_start: start, current_period_end: start + 30 * 86400, trial_end: trial ? start + trial * 86400 : null, livemode: false, schedule: null };
        s.subs[sub.id] = sub; cs.subscription = sub.id;
        if (trial) cs.payment_status = "no_payment_required";
        cs.invoice = invoiceFor(cs.customer, trial ? 0 : cs.amount_total, { subscription: sub.id }).id;
      } else if (paid) {
        const pi = newId("pi"), ch = { id: newId("ch"), object: "charge", payment_intent: pi, customer: cs.customer, amount: cs.amount_total, amount_refunded: 0, refunded: false, currency: "eur" };
        s.charges[ch.id] = ch; cs.payment_intent = pi;
        cs.invoice = invoiceFor(cs.customer, cs.amount_total, { metadata: cs.params.invoice_creation?.invoice_data?.metadata || {} }).id;
        cs.charge = ch.id;
      }
      return cs;
    },
    // Verlengt een abonnement met één periode, zoals Stripe aan het einde van de periode doet.
    renew(subId, { paid = true } = {}) {
      const sub = s.subs[subId], start = sub.current_period_end, end = start + 30 * 86400;
      if (paid) { Object.assign(sub, { current_period_start: start, current_period_end: end, status: "active" }); Object.assign(sub.items.data[0], { current_period_start: start, current_period_end: end }); }
      else sub.status = "past_due";
      const inv = invoiceFor(sub.customer, 1000, { subscription: sub.id, status: paid ? "paid" : "open", amount_paid: paid ? 1000 : 0 });
      // Een geplande wijziging (schedule) gaat in bij de nieuwe periode.
      if (paid && sub.schedule) { const sch = s.schedules[sub.schedule]; const next = sch.phases[1]; if (next && next.start_date <= end) { sub.items.data[0].price = { id: next.items[0].price }; sch.status = "released"; sub.schedule = null; } }
      return inv;
    },
    refund(chargeId, amount) { const ch = s.charges[chargeId]; ch.amount_refunded += amount; ch.refunded = ch.amount_refunded >= ch.amount; return ch; }
  };
  return api;
}

let eventSeq = 0;
export function stripeEvent(type, object, { livemode = false, created = Math.floor(Date.now() / 1000) } = {}) {
  return { id: `evt_test_${++eventSeq}_${Math.random().toString(36).slice(2, 8)}`, object: "event", type, created, livemode, data: { object } };
}

export function signPayload(payload, secret, timestamp = Math.floor(Date.now() / 1000)) {
  const signature = createHmac("sha256", secret).update(`${timestamp}.${payload}`).digest("hex");
  return `t=${timestamp},v1=${signature}`;
}
