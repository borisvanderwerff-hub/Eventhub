// Publieke shop-API, zelfregistratie en de klantomgeving (aankopen, abonnementen, licenties, downloads, organisatiegebruikers).
// Prijzen en rechten worden altijd aan de serverzijde bepaald uit de productconfiguratie; de browser stuurt alleen keuzes (id's).

import { stripeRequest, stripeConfig, StripeError } from "./stripe.js";
import { loadEffectiveEntitlements, userLimit, audit, planSnapshot, SUBSCRIPTION_STATUS_LABELS, ENTITLEMENT_STATUS_LABELS } from "../shared/entitlements.js";
import { ensureStripeCustomer, createCheckoutSession, syncSubscription, syncCheckoutSession, customerPortalUrl, shopApiUrl } from "./billing.js";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const DOWNLOAD_TTL_MS = 10 * 60 * 1000;
const DOWNLOAD_MAX_USES = 5;

function publicJson(data, status = 200, maxAge = 60) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": status === 200 ? `public, max-age=${maxAge}` : "no-store", "Access-Control-Allow-Origin": "*", "X-Content-Type-Options": "nosniff" } });
}

const parse = (value, fallback) => { try { return JSON.parse(value) ?? fallback; } catch { return fallback; } };

function priceOut(p) {
  return { id: p.id, currency: p.currency, unit_amount: p.unit_amount, interval: p.billing_interval, interval_count: p.interval_count, tax_behavior: p.tax_behavior };
}

async function publishedCatalog(env, slug) {
  const products = slug
    ? (await env.DB.prepare("SELECT * FROM products WHERE slug = ? AND published = 1 AND active = 1 AND shop_allowed = 1").bind(slug).all()).results
    : (await env.DB.prepare("SELECT * FROM products WHERE published = 1 AND active = 1 AND shop_allowed = 1 ORDER BY sort_order, name COLLATE NOCASE").all()).results;
  if (!products.length) return [];
  const ids = products.map((p) => p.id), marks = ids.map(() => "?").join(",");
  const [plans, prices, images, features, releases] = await Promise.all([
    env.DB.prepare(`SELECT * FROM product_plans WHERE product_id IN (${marks}) AND published = 1 AND archived_at IS NULL ORDER BY rank, name COLLATE NOCASE`).bind(...ids).all(),
    env.DB.prepare(`SELECT pp.* FROM plan_prices pp JOIN product_plans pl ON pl.id = pp.plan_id WHERE pl.product_id IN (${marks}) AND pp.active = 1 AND pp.stripe_price_id IS NOT NULL ORDER BY pp.unit_amount`).bind(...ids).all(),
    env.DB.prepare(`SELECT id, product_id, alt FROM product_images WHERE product_id IN (${marks}) ORDER BY sort_order, created_at`).bind(...ids).all(),
    env.DB.prepare(`SELECT * FROM product_features WHERE product_id IN (${marks}) ORDER BY sort_order, name COLLATE NOCASE`).bind(...ids).all(),
    env.DB.prepare(`SELECT product_id, version, platform, notes, published_at FROM product_releases WHERE product_id IN (${marks}) AND published = 1 ORDER BY published_at DESC`).bind(...ids).all()
  ]);
  return products.map((p) => {
    const productPlans = plans.results.filter((pl) => pl.product_id === p.id).map((pl) => ({
      id: pl.id, code: pl.code, name: pl.name, description: pl.description, billing_type: pl.billing_type, features: parse(pl.features_json, {}),
      max_users: pl.max_users, max_activations: pl.max_activations, trial_days: pl.trial_days,
      prices: prices.results.filter((pr) => pr.plan_id === pl.id).map(priceOut)
    })).filter((pl) => pl.prices.length);
    const all = productPlans.flatMap((pl) => pl.prices);
    return {
      id: p.id, slug: p.slug, name: p.name, tagline: p.tagline, description: p.description,
      images: images.results.filter((i) => i.product_id === p.id).map((i) => ({ url: `${shopApiUrl(env)}/shop-media/${i.id}`, alt: i.alt })),
      features: features.results.filter((f) => f.product_id === p.id).map((f) => ({ key: f.feature_key, name: f.name, description: f.description, kind: f.kind })),
      plans: productPlans,
      from_price: all.length ? all.reduce((a, b) => (a.unit_amount <= b.unit_amount ? a : b)) : null,
      latest_release: releases.results.find((r) => r.product_id === p.id) || null
    };
  });
}

export async function handlePublicShop(request, env, url) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET", "Access-Control-Max-Age": "600" } });
  if (request.method !== "GET") return publicJson({ error: "Niet toegestaan." }, 405);
  const config = stripeConfig(env);
  if (url.pathname === "/api/public/shop/products") {
    const catalog = await publishedCatalog(env);
    return publicJson({ checkout_available: config.checkout_ready, products: catalog.map(({ description, features, plans, ...rest }) => ({ ...rest, plan_count: plans.length })) });
  }
  const productRoute = /^\/api\/public\/shop\/products\/([a-z0-9-]{1,60})$/.exec(url.pathname);
  if (productRoute) {
    const [product] = await publishedCatalog(env, productRoute[1]);
    if (!product) return publicJson({ error: "Product niet gevonden." }, 404);
    return publicJson({ checkout_available: config.checkout_ready, product });
  }
  const priceRoute = /^\/api\/public\/shop\/prices\/([0-9a-f-]{36})$/.exec(url.pathname);
  if (priceRoute) {
    const row = await env.DB.prepare("SELECT pp.id FROM plan_prices pp JOIN product_plans pl ON pl.id = pp.plan_id JOIN products p ON p.id = pl.product_id WHERE pp.id = ? AND pp.active = 1 AND pp.stripe_price_id IS NOT NULL AND pl.published = 1 AND pl.archived_at IS NULL AND p.published = 1 AND p.active = 1 AND p.shop_allowed = 1").bind(priceRoute[1]).first();
    if (!row) return publicJson({ error: "Deze prijs is niet (meer) beschikbaar." }, 404);
    const product = (await publishedCatalog(env)).find((p) => p.plans.some((pl) => pl.prices.some((pr) => pr.id === row.id)));
    const plan = product.plans.find((pl) => pl.prices.some((pr) => pr.id === row.id));
    return publicJson({ checkout_available: config.checkout_ready, product: { id: product.id, slug: product.slug, name: product.name, features: product.features }, plan, price: plan.prices.find((pr) => pr.id === row.id) }, 200, 0);
  }
  return publicJson({ error: "Niet gevonden." }, 404);
}

export async function handleShopMedia(env, url) {
  const match = /^\/shop-media\/([0-9a-f-]{36})$/.exec(url.pathname);
  if (!match || !env.PRODUCT_FILES) return null;
  const image = await env.DB.prepare("SELECT i.r2_key, i.content_type FROM product_images i JOIN products p ON p.id = i.product_id WHERE i.id = ?").bind(match[1]).first();
  if (!image) return new Response("Niet gevonden", { status: 404 });
  const object = await env.PRODUCT_FILES.get(image.r2_key);
  if (!object) return new Response("Niet gevonden", { status: 404 });
  return new Response(object.body, { headers: { "Content-Type": image.content_type, "Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*", "X-Content-Type-Options": "nosniff", "Cross-Origin-Resource-Policy": "cross-origin" } });
}

// Tijdelijke downloadlink: alleen de hash van het token staat in D1, de link verloopt na 10 minuten.
export async function handleDownload(request, env, url, h) {
  const match = /^\/download\/([a-f0-9]{64})$/.exec(url.pathname);
  if (!match || request.method !== "GET") return null;
  const tokenHash = await h.digest(match[1]), now = Date.now();
  const used = await env.DB.prepare("UPDATE download_tokens SET uses = uses + 1 WHERE token_hash = ? AND expires_at > ? AND uses < ?").bind(tokenHash, now, DOWNLOAD_MAX_USES).run();
  const fail = (text) => new Response(text, { status: 410, headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store" } });
  if (!used.meta?.changes) return fail("Deze downloadlink is verlopen. Vraag in het klantenportaal een nieuwe link aan.");
  const row = await env.DB.prepare("SELECT r.r2_key, r.file_name, r.file_size, r.published FROM download_tokens t JOIN product_releases r ON r.id = t.release_id WHERE t.token_hash = ?").bind(tokenHash).first();
  if (!row?.r2_key || row.published !== 1 || !env.PRODUCT_FILES) return fail("Dit bestand is niet meer beschikbaar.");
  const object = await env.PRODUCT_FILES.get(row.r2_key);
  if (!object) return fail("Dit bestand is niet meer beschikbaar.");
  const safeName = String(row.file_name || "download").replace(/[^A-Za-z0-9._ -]/g, "_");
  return new Response(object.body, { headers: { "Content-Type": "application/octet-stream", "Content-Disposition": `attachment; filename="${safeName}"`, "Content-Length": String(object.size), "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer" } });
}

function isAdmin(customer) { return customer.account_role === "admin"; }
function adminOnly(h) { return h.json({ error: "Alleen een beheerder van jullie account kan dit doen." }, 403); }

function noticeList(subs, entitlements, orders) {
  const notices = [];
  for (const s of subs) {
    const end = s.current_period_end ? new Date(s.current_period_end).toLocaleDateString("nl-NL") : "";
    if (s.status === "past_due") notices.push({ level: "error", text: `De laatste betaling voor ${s.product_name} (${s.plan_name}) is mislukt. Werk je betaalmethode bij via Betaalgegevens beheren; je toegang blijft tijdelijk actief.` });
    if (s.status === "suspended") notices.push({ level: "error", text: `${s.product_name} is opgeschort omdat een factuur onbetaald is. Betaal de openstaande factuur om weer toegang te krijgen.` });
    if (s.status === "pending") notices.push({ level: "info", text: `De eerste betaling voor ${s.product_name} wordt nog verwerkt.` });
    if (s.cancel_at_period_end && ["active", "trialing", "past_due"].includes(s.status)) notices.push({ level: "info", text: `Je abonnement op ${s.product_name} is opgezegd. Je houdt toegang tot en met ${end}.` });
  }
  for (const o of orders) if (o.status === "processing") notices.push({ level: "info", text: `Betaling voor bestelling ${o.order_number} wordt verwerkt. Zodra de betaling is bevestigd, krijg je toegang.` });
  for (const e of entitlements) if (e.status === "suspended" && e.overrides_applied.length && e.source !== "subscription") notices.push({ level: "error", text: `De toegang tot ${e.product_name} is opgeschort. Neem contact op met Cohentra.` });
  return notices;
}

function changeDirection(current, target) {
  if (current.billing_interval !== target.billing_interval || current.interval_count !== target.interval_count) return "interval";
  if (target.rank !== current.rank) return target.rank > current.rank ? "upgrade" : "downgrade";
  return target.unit_amount >= current.unit_amount ? "upgrade" : "downgrade";
}

function changeTiming(env, direction) {
  if (direction === "downgrade" && String(env.SHOP_DOWNGRADE_TIMING || "period_end") === "period_end") return "period_end";
  return "immediate";
}

async function changeOptions(env, sub) {
  const current = await env.DB.prepare("SELECT pp.*, pl.rank, pl.name AS plan_name FROM plan_prices pp JOIN product_plans pl ON pl.id = pp.plan_id WHERE pp.id = ?").bind(sub.price_id).first();
  if (!current) return [];
  const { results } = await env.DB.prepare("SELECT pp.*, pl.rank, pl.name AS plan_name FROM plan_prices pp JOIN product_plans pl ON pl.id = pp.plan_id WHERE pl.product_id = ? AND pl.billing_type = 'recurring' AND pl.published = 1 AND pl.archived_at IS NULL AND pp.active = 1 AND pp.stripe_price_id IS NOT NULL AND pp.id <> ? ORDER BY pl.rank, pp.unit_amount").bind(sub.product_id, sub.price_id).all();
  return results.map((target) => { const direction = changeDirection(current, target); return { price_id: target.id, plan_name: target.plan_name, ...priceOut(target), direction, timing: changeTiming(env, direction) }; });
}

async function summary(env, customer, h) {
  const admin = isAdmin(customer), now = Date.now();
  const [entitlements, subs, licenses, orders, invoices, accounts, row] = await Promise.all([
    loadEffectiveEntitlements(env, customer.customer_id, now),
    env.DB.prepare("SELECT s.*, p.name AS product_name, pl.name AS plan_name, pp.unit_amount, pp.currency, pp.billing_interval, pp.interval_count, np.name AS pending_plan_name FROM shop_subscriptions s JOIN products p ON p.id = s.product_id JOIN product_plans pl ON pl.id = s.plan_id LEFT JOIN plan_prices pp ON pp.id = s.price_id LEFT JOIN product_plans np ON np.id = s.pending_plan_id WHERE s.customer_id = ? ORDER BY s.created_at DESC").bind(customer.customer_id).all(),
    env.DB.prepare("SELECT l.id, l.label, l.product_id, l.entitlement_id, l.created_at, l.activated_at, l.last_seen_at, l.revoked_at, p.name AS product_name FROM licenses l JOIN products p ON p.id = l.product_id WHERE l.customer_id = ? AND l.entitlement_id IS NOT NULL ORDER BY l.revoked_at IS NOT NULL, l.created_at DESC LIMIT 500").bind(customer.customer_id).all(),
    admin ? env.DB.prepare("SELECT o.id, o.order_number, o.status, o.amount_total, o.amount_refunded, o.currency, o.purchase_context, o.created_at, o.paid_at, p.name AS product_name, json_extract(o.plan_snapshot_json, '$.name') AS plan_name FROM shop_orders o JOIN products p ON p.id = o.product_id WHERE o.customer_id = ? AND o.status <> 'pending' ORDER BY o.created_at DESC LIMIT 100").bind(customer.customer_id).all() : Promise.resolve({ results: [] }),
    admin ? env.DB.prepare("SELECT number, status, currency, amount_due, amount_paid, hosted_invoice_url, invoice_pdf, period_start, period_end, stripe_created FROM billing_invoices WHERE customer_id = ? AND status <> 'draft' ORDER BY stripe_created DESC LIMIT 100").bind(customer.customer_id).all() : Promise.resolve({ results: [] }),
    env.DB.prepare("SELECT COUNT(*) AS n FROM customer_portal_accounts WHERE customer_id = ? AND disabled_at IS NULL").bind(customer.customer_id).first(),
    env.DB.prepare("SELECT id, customer_number, customer_type, name, billing_company, contact_name, contact_email, invoice_email, street, postal_code, city, country, vat_number, kvk_number, stripe_customer_id FROM customers WHERE id = ?").bind(customer.customer_id).first()
  ]);
  const productIds = [...new Set(entitlements.filter((e) => e.download_allowed).map((e) => e.product_id))];
  const releases = productIds.length ? (await env.DB.prepare(`SELECT r.id, r.product_id, r.version, r.platform, r.notes, r.file_name, r.file_size, r.published_at, p.name AS product_name FROM product_releases r JOIN products p ON p.id = r.product_id WHERE r.published = 1 AND r.r2_key IS NOT NULL AND r.product_id IN (${productIds.map(() => "?").join(",")}) ORDER BY r.published_at DESC`).bind(...productIds).all()).results : [];
  const entitledProducts = [...new Set(entitlements.map((e) => e.product_id))];
  const featureRows = entitledProducts.length ? (await env.DB.prepare(`SELECT product_id, feature_key AS key, name, kind FROM product_features WHERE product_id IN (${entitledProducts.map(() => "?").join(",")}) ORDER BY sort_order`).bind(...entitledProducts).all()).results : [];
  const featureNames = {};
  for (const f of featureRows) (featureNames[f.product_id] = featureNames[f.product_id] || []).push({ key: f.key, name: f.name, kind: f.kind });
  const subscriptions = [];
  for (const s of subs.results) subscriptions.push({
    id: s.id, product_id: s.product_id, product_name: s.product_name, plan_name: s.plan_name, status: s.status, status_label: SUBSCRIPTION_STATUS_LABELS[s.status] || s.status,
    current_period_end: s.current_period_end, cancel_at_period_end: !!s.cancel_at_period_end, trial_end: s.trial_end, ended_at: s.ended_at,
    price: s.currency ? { unit_amount: s.unit_amount, currency: s.currency, interval: s.billing_interval, interval_count: s.interval_count } : null,
    pending: s.pending_price_id ? { plan_name: s.pending_plan_name, at: s.pending_change_at } : null,
    change_options: admin && ["active", "trialing"].includes(s.status) && !s.cancel_at_period_end ? await changeOptions(env, s) : []
  });
  const activeLicenses = (id) => licenses.results.filter((l) => l.entitlement_id === id && !l.revoked_at).length;
  const outEntitlements = entitlements.map((e) => ({ ...e, status_label: ENTITLEMENT_STATUS_LABELS[e.status] || e.status, licenses_in_use: activeLicenses(e.id), overrides_applied: undefined, has_override: e.overrides_applied.length > 0 }));
  return {
    account: { id: customer.account_id, name: customer.account_name, email: customer.account_email || customer.username, role: customer.account_role },
    customer: { ...row, stripe_customer_id: undefined, billing_portal_available: admin && !!row.stripe_customer_id },
    entitlements: outEntitlements, subscriptions,
    licenses: licenses.results.map((l) => ({ ...l, status: l.revoked_at ? "Ingetrokken" : l.activated_at ? "Geactiveerd" : "Nog niet geactiveerd" })),
    releases, feature_names: featureNames, orders: orders.results, invoices: invoices.results,
    team: { count: Number(accounts?.n || 0), limit: row.customer_type === "business" ? userLimit(entitlements) : 1 },
    notices: noticeList(subscriptions.map((s) => ({ ...s, current_period_end: s.current_period_end })), entitlements, orders.results),
    shop: { checkout_ready: stripeConfig(env).checkout_ready }
  };
}

function billingFromBody(body, customerType) {
  const text = (key, max) => String(body?.[key] ?? "").trim().slice(0, max);
  const billing = {
    billing_company: text("billing_company", 120), contact_name: text("contact_name", 120), invoice_email: text("invoice_email", 254).toLowerCase(),
    street: text("street", 160), postal_code: text("postal_code", 12).toUpperCase(), city: text("city", 80), country: text("country", 60) || "Nederland",
    vat_number: text("vat_number", 30).replace(/\s+/g, "").toUpperCase(), kvk_number: text("kvk_number", 20).replace(/\s+/g, "")
  };
  if (billing.invoice_email && !EMAIL_PATTERN.test(billing.invoice_email)) return { error: "Het factuur-e-mailadres is ongeldig." };
  if (billing.kvk_number && !/^\d{8}$/.test(billing.kvk_number)) return { error: "Een KvK-nummer bestaat uit 8 cijfers." };
  if (billing.vat_number && !/^[A-Z]{2}[A-Z0-9]{2,13}$/.test(billing.vat_number)) return { error: "Vul het btw-nummer in met landcode, bijvoorbeeld NL123456789B01." };
  if (customerType === "business") billing.billing_company = "";
  return { billing };
}

async function saveBilling(env, customerId, billing) {
  await env.DB.prepare("UPDATE customers SET billing_company = ?, contact_name = CASE WHEN ? <> '' THEN ? ELSE contact_name END, invoice_email = ?, street = ?, postal_code = ?, city = ?, country = ?, vat_number = ?, kvk_number = ?, updated_at = ? WHERE id = ?")
    .bind(billing.billing_company, billing.contact_name, billing.contact_name, billing.invoice_email, billing.street, billing.postal_code, billing.city, billing.country, billing.vat_number, billing.kvk_number, new Date().toISOString(), customerId).run();
}

function stripeFailure(h, error, fallback) {
  console.error(JSON.stringify({ event: "stripe_call_failed", message: String(error?.message || error).slice(0, 300) }));
  if (error instanceof StripeError && error.status === 503) return h.json({ error: "Online betalen is nog niet beschikbaar. Neem contact op met Cohentra." }, 503);
  return h.json({ error: fallback }, 502);
}

export async function handleCustomerShop(request, env, url, customer, h) {
  const path = url.pathname;
  if (request.method === "GET" && path === "/api/customer/shop/summary") return h.json(await summary(env, customer, h));
  // Dezelfde prijsinformatie als de publieke catalogus, maar via de portal-origin (CSP connect-src 'self').
  const priceLookup = /^\/api\/customer\/shop\/prices\/([0-9a-f-]{36})$/.exec(path);
  if (priceLookup && request.method === "GET") {
    const publicUrl = new URL(`/api/public/shop/prices/${priceLookup[1]}`, url.origin);
    return await handlePublicShop(new Request(publicUrl), env, publicUrl);
  }

  if (request.method === "PATCH" && path === "/api/customer/account/billing") {
    if (!isAdmin(customer)) return adminOnly(h);
    let body; try { body = await h.readJson(request); } catch { return h.json({ error: "Ongeldige aanvraag." }, 400); }
    const parsed = billingFromBody(body, customer.customer_type);
    if (parsed.error) return h.json({ error: parsed.error }, 400);
    await saveBilling(env, customer.customer_id, parsed.billing);
    await audit(env, { customer_id: customer.customer_id, entity_type: "customer", entity_id: customer.customer_id, action: "billing.updated", actor_type: "customer", actor_name: customer.username });
    return h.json({ ok: true });
  }

  if (request.method === "POST" && path === "/api/customer/checkout") {
    if (!isAdmin(customer)) return adminOnly(h);
    const config = stripeConfig(env);
    if (!config.checkout_ready) return h.json({ error: "Online bestellen is nog niet geopend. Neem contact op met Cohentra voor een offerte." }, 503);
    let body; try { body = await h.readJson(request); } catch { return h.json({ error: "Ongeldige aanvraag." }, 400); }
    const price = await env.DB.prepare("SELECT pp.* FROM plan_prices pp WHERE pp.id = ? AND pp.active = 1 AND pp.stripe_price_id IS NOT NULL").bind(String(body.price_id || "")).first();
    const plan = price ? await env.DB.prepare("SELECT * FROM product_plans WHERE id = ? AND published = 1 AND archived_at IS NULL").bind(price.plan_id).first() : null;
    const product = plan ? await env.DB.prepare("SELECT * FROM products WHERE id = ? AND published = 1 AND active = 1 AND shop_allowed = 1").bind(plan.product_id).first() : null;
    if (!product) return h.json({ error: "Dit abonnement is niet (meer) beschikbaar." }, 404);
    const context = customer.customer_type === "business" ? "business" : body.purchase_context === "business" ? "business" : "private";
    const parsed = billingFromBody(body.billing || {}, customer.customer_type);
    if (parsed.error) return h.json({ error: parsed.error }, 400);
    const billing = parsed.billing;
    if (customer.customer_type === "individual" && context === "business" && !billing.billing_company) return h.json({ error: "Vul de bedrijfsnaam in voor een zakelijke aankoop." }, 400);
    if (customer.customer_type === "individual" && context === "private") { billing.billing_company = ""; billing.vat_number = ""; billing.kvk_number = ""; }
    // Geen dubbele aankopen: een lopend abonnement wordt gewijzigd in plaats van opnieuw afgesloten.
    if (plan.billing_type === "recurring") {
      const running = await env.DB.prepare("SELECT id FROM shop_subscriptions WHERE customer_id = ? AND product_id = ? AND status IN ('pending', 'trialing', 'active', 'past_due', 'suspended')").bind(customer.customer_id, product.id).first();
      if (running) return h.json({ error: `Je hebt al een abonnement op ${product.name}. Wijzig dat abonnement onder Abonnementen.`, code: "subscription_exists" }, 409);
    } else {
      const owned = await env.DB.prepare("SELECT id FROM shop_orders WHERE customer_id = ? AND plan_id = ? AND status IN ('paid', 'partially_refunded', 'processing')").bind(customer.customer_id, plan.id).first();
      if (owned) return h.json({ error: "Je hebt dit product al gekocht. Je vindt het onder Mijn producten.", code: "already_owned" }, 409);
    }
    const open = await env.DB.prepare("SELECT id, stripe_checkout_session_id FROM shop_orders WHERE customer_id = ? AND price_id = ? AND status = 'pending' AND stripe_checkout_session_id IS NOT NULL AND created_at > ? ORDER BY created_at DESC LIMIT 1").bind(customer.customer_id, price.id, new Date(Date.now() - 55 * 60 * 1000).toISOString()).first();
    try {
      if (open) {
        const session = await stripeRequest(env, "GET", `/v1/checkout/sessions/${encodeURIComponent(open.stripe_checkout_session_id)}`);
        if (session.status === "open" && session.url) return h.json({ url: session.url, order_id: open.id, reused: true });
      }
      await saveBilling(env, customer.customer_id, billing);
      const fresh = await env.DB.prepare("SELECT * FROM customers WHERE id = ?").bind(customer.customer_id).first();
      const stripeCustomerId = await ensureStripeCustomer(env, fresh, { email: customer.account_email || customer.username });
      if (context === "business" && billing.vat_number) {
        const known = await stripeRequest(env, "GET", `/v1/customers/${encodeURIComponent(stripeCustomerId)}/tax_ids`, { limit: 10 }).catch(() => ({ data: [] }));
        if (!(known.data || []).some((t) => t.value === billing.vat_number)) await stripeRequest(env, "POST", `/v1/customers/${encodeURIComponent(stripeCustomerId)}/tax_ids`, { type: "eu_vat", value: billing.vat_number }).catch((error) => console.error("VAT id not accepted by Stripe", String(error?.message || error)));
      }
      const usedTrial = plan.trial_days > 0 ? await env.DB.prepare("SELECT 1 FROM shop_subscriptions WHERE customer_id = ? AND product_id = ? LIMIT 1").bind(customer.customer_id, product.id).first() : true;
      const orderId = crypto.randomUUID(), now = new Date().toISOString();
      const orderNumber = `ORD-${new Date().getUTCFullYear()}-${h.randomHex(4).toUpperCase()}`;
      const billingSnapshot = { ...billing, name: fresh.name, customer_type: fresh.customer_type, customer_number: fresh.customer_number, purchase_context: context };
      await env.DB.prepare("INSERT INTO shop_orders (id, order_number, customer_id, account_id, product_id, plan_id, price_id, purchase_context, billing_json, plan_snapshot_json, currency, amount_total, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)")
        .bind(orderId, orderNumber, customer.customer_id, customer.account_id, product.id, plan.id, price.id, context, JSON.stringify(billingSnapshot), JSON.stringify(planSnapshot(plan, price)), price.currency, price.unit_amount, now, now).run();
      const session = await createCheckoutSession(env, { order: { id: orderId, purchase_context: context }, customer: fresh, stripeCustomerId, price, plan, trialDays: usedTrial ? 0 : plan.trial_days });
      await env.DB.prepare("UPDATE shop_orders SET stripe_checkout_session_id = ?, livemode = ?, updated_at = ? WHERE id = ?").bind(session.id, session.livemode ? 1 : 0, now, orderId).run();
      await audit(env, { customer_id: customer.customer_id, entity_type: "order", entity_id: orderId, action: "checkout.started", actor_type: "customer", actor_name: customer.username, details: { order: orderNumber, plan: plan.name, price_id: price.id, context } });
      return h.json({ url: session.url, order_id: orderId }, 201);
    } catch (error) { return stripeFailure(h, error, "Het betaalscherm kon niet worden geopend. Probeer het later opnieuw."); }
  }

  const orderRoute = /^\/api\/customer\/orders\/([0-9a-f-]{36})$/i.exec(path);
  if (orderRoute && request.method === "GET") {
    const order = await env.DB.prepare("SELECT o.id, o.order_number, o.status, o.stripe_checkout_session_id, p.name AS product_name, json_extract(o.plan_snapshot_json, '$.name') AS plan_name FROM shop_orders o JOIN products p ON p.id = o.product_id WHERE o.id = ? AND o.customer_id = ?").bind(orderRoute[1], customer.customer_id).first();
    if (!order) return h.json({ error: "Bestelling niet gevonden." }, 404);
    // Valt de webhook langer dan verwacht weg, dan vraagt de server de status zelf bij Stripe op. De terugkeer naar de site geeft nooit zelf toegang.
    if ((order.status === "pending" || order.status === "processing") && order.stripe_checkout_session_id && url.searchParams.get("refresh") === "1") {
      try { await syncCheckoutSession(env, order.stripe_checkout_session_id); } catch (error) { console.error("Order refresh failed", String(error?.message || error)); }
      const updated = await env.DB.prepare("SELECT status FROM shop_orders WHERE id = ?").bind(order.id).first();
      order.status = updated.status;
    }
    return h.json({ order: { id: order.id, order_number: order.order_number, status: order.status, product_name: order.product_name, plan_name: order.plan_name } });
  }

  const subRoute = /^\/api\/customer\/subscriptions\/([0-9a-f-]{36})\/(cancel|resume|change|change-preview|cancel-change)$/i.exec(path);
  if (subRoute && request.method === "POST") {
    if (!isAdmin(customer)) return adminOnly(h);
    const sub = await env.DB.prepare("SELECT * FROM shop_subscriptions WHERE id = ? AND customer_id = ?").bind(subRoute[1], customer.customer_id).first();
    if (!sub) return h.json({ error: "Abonnement niet gevonden." }, 404);
    const action = subRoute[2];
    let body = {}; try { body = await h.readJson(request); } catch { body = {}; }
    try {
      if (action === "cancel" || action === "resume") {
        if (!["active", "trialing", "past_due"].includes(sub.status)) return h.json({ error: "Dit abonnement kan niet meer worden gewijzigd." }, 409);
        if (sub.stripe_schedule_id) await stripeRequest(env, "POST", `/v1/subscription_schedules/${encodeURIComponent(sub.stripe_schedule_id)}/release`, {});
        await stripeRequest(env, "POST", `/v1/subscriptions/${encodeURIComponent(sub.stripe_subscription_id)}`, { cancel_at_period_end: action === "cancel" ? "true" : "false" });
        const { subscription } = await syncSubscription(env, sub.stripe_subscription_id, customer.username);
        await audit(env, { customer_id: customer.customer_id, entity_type: "subscription", entity_id: sub.id, action: `subscription.${action}_requested`, actor_type: "customer", actor_name: customer.username });
        return h.json({ ok: true, access_until: subscription.current_period_end, cancel_at_period_end: !!subscription.cancel_at_period_end });
      }
      if (action === "cancel-change") {
        if (!sub.stripe_schedule_id) return h.json({ error: "Er staat geen wijziging gepland." }, 409);
        await stripeRequest(env, "POST", `/v1/subscription_schedules/${encodeURIComponent(sub.stripe_schedule_id)}/release`, {});
        await syncSubscription(env, sub.stripe_subscription_id, customer.username);
        return h.json({ ok: true });
      }
      if (!["active", "trialing"].includes(sub.status) || sub.cancel_at_period_end) return h.json({ error: "Wijzigen kan alleen bij een actief abonnement dat niet is opgezegd." }, 409);
      const option = (await changeOptions(env, sub)).find((o) => o.price_id === String(body.price_id || ""));
      if (!option) return h.json({ error: "Deze wijziging is niet beschikbaar." }, 400);
      const target = await env.DB.prepare("SELECT * FROM plan_prices WHERE id = ?").bind(option.price_id).first();
      const stripeSub = await stripeRequest(env, "GET", `/v1/subscriptions/${encodeURIComponent(sub.stripe_subscription_id)}`);
      const item = stripeSub.items?.data?.[0];
      const proration = String(env.SHOP_UPGRADE_PRORATION || "always_invoice");
      if (action === "change-preview") {
        if (option.timing === "period_end") return h.json({ timing: "period_end", effective_at: sub.current_period_end, amount_due: null, currency: target.currency });
        let preview = null;
        try {
          preview = await stripeRequest(env, "POST", "/v1/invoices/create_preview", { customer: stripeSub.customer, subscription: stripeSub.id, subscription_details: { items: [{ id: item.id, price: target.stripe_price_id }], proration_behavior: proration } });
        } catch (error) { console.error("Proration preview failed", String(error?.message || error)); }
        return h.json({ timing: "immediate", effective_at: new Date().toISOString(), amount_due: preview ? preview.amount_due : null, currency: target.currency, proration });
      }
      if (option.timing === "immediate") {
        if (sub.stripe_schedule_id) await stripeRequest(env, "POST", `/v1/subscription_schedules/${encodeURIComponent(sub.stripe_schedule_id)}/release`, {});
        // pending_if_incomplete: mislukt de bijbetaling, dan gaat de upgrade niet door en blijven de oude rechten gelden.
        await stripeRequest(env, "POST", `/v1/subscriptions/${encodeURIComponent(stripeSub.id)}`, { items: [{ id: item.id, price: target.stripe_price_id }], proration_behavior: proration, payment_behavior: "pending_if_incomplete" }, { idempotencyKey: `change-${sub.id}-${target.id}-${sub.updated_at}` });
      } else {
        let scheduleId = sub.stripe_schedule_id;
        if (!scheduleId) scheduleId = (await stripeRequest(env, "POST", "/v1/subscription_schedules", { from_subscription: stripeSub.id })).id;
        const schedule = await stripeRequest(env, "GET", `/v1/subscription_schedules/${encodeURIComponent(scheduleId)}`);
        const phase = schedule.phases[0];
        const currentPhase = { items: [{ price: item.price.id, quantity: 1 }], start_date: phase.start_date, end_date: phase.end_date };
        try {
          await stripeRequest(env, "POST", `/v1/subscription_schedules/${encodeURIComponent(scheduleId)}`, { end_behavior: "release", proration_behavior: "none", phases: [currentPhase, { items: [{ price: target.stripe_price_id, quantity: 1 }], iterations: 1 }] });
        } catch (error) {
          // Nieuwere Stripe-API-versies vervangen 'iterations' door 'duration'.
          if (!(error instanceof StripeError) || !/iterations/i.test(error.message)) throw error;
          await stripeRequest(env, "POST", `/v1/subscription_schedules/${encodeURIComponent(scheduleId)}`, { end_behavior: "release", proration_behavior: "none", phases: [currentPhase, { items: [{ price: target.stripe_price_id, quantity: 1 }], duration: { interval: target.billing_interval, interval_count: target.interval_count } }] });
        }
      }
      const { subscription } = await syncSubscription(env, sub.stripe_subscription_id, customer.username);
      await audit(env, { customer_id: customer.customer_id, entity_type: "subscription", entity_id: sub.id, action: "subscription.change_requested", actor_type: "customer", actor_name: customer.username, details: { to_price: target.id, timing: option.timing, direction: option.direction } });
      return h.json({ ok: true, timing: option.timing, effective_at: option.timing === "period_end" ? subscription.current_period_end : new Date().toISOString(), status: subscription.status, applied: subscription.price_id === target.id });
    } catch (error) { return stripeFailure(h, error, "De wijziging kon niet worden doorgevoerd. Er is niets veranderd; probeer het later opnieuw."); }
  }

  if (request.method === "POST" && path === "/api/customer/billing-portal") {
    if (!isAdmin(customer)) return adminOnly(h);
    const row = await env.DB.prepare("SELECT stripe_customer_id FROM customers WHERE id = ?").bind(customer.customer_id).first();
    if (!row?.stripe_customer_id) return h.json({ error: "Er zijn nog geen betaalgegevens om te beheren." }, 404);
    try {
      const params = { customer: row.stripe_customer_id, return_url: customerPortalUrl(env) + "/?tab=billing", locale: "nl" };
      if (env.STRIPE_PORTAL_CONFIGURATION_ID) params.configuration = env.STRIPE_PORTAL_CONFIGURATION_ID;
      const session = await stripeRequest(env, "POST", "/v1/billing_portal/sessions", params);
      await audit(env, { customer_id: customer.customer_id, entity_type: "customer", entity_id: customer.customer_id, action: "billing_portal.opened", actor_type: "customer", actor_name: customer.username });
      return h.json({ url: session.url });
    } catch (error) { return stripeFailure(h, error, "Betaalbeheer kon niet worden geopend. Probeer het later opnieuw."); }
  }

  const downloadRoute = /^\/api\/customer\/downloads\/([0-9a-f-]{36})$/i.exec(path);
  if (downloadRoute && request.method === "POST") {
    const release = await env.DB.prepare("SELECT id, product_id FROM product_releases WHERE id = ? AND published = 1 AND r2_key IS NOT NULL").bind(downloadRoute[1]).first();
    if (!release) return h.json({ error: "Download niet gevonden." }, 404);
    const allowed = (await loadEffectiveEntitlements(env, customer.customer_id)).some((e) => e.product_id === release.product_id && e.download_allowed);
    if (!allowed) return h.json({ error: "Je hebt op dit moment geen downloadrecht voor dit product. Controleer je abonnement of betaling." }, 403);
    const raw = h.randomHex(32), now = Date.now();
    await env.DB.batch([
      env.DB.prepare("DELETE FROM download_tokens WHERE expires_at < ?").bind(now - 24 * 3600 * 1000),
      env.DB.prepare("INSERT INTO download_tokens (token_hash, release_id, customer_id, account_id, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?)").bind(await h.digest(raw), release.id, customer.customer_id, customer.account_id, now, now + DOWNLOAD_TTL_MS)
    ]);
    return h.json({ url: `${shopApiUrl(env)}/download/${raw}`, expires_at: new Date(now + DOWNLOAD_TTL_MS).toISOString() });
  }

  return null;
}
