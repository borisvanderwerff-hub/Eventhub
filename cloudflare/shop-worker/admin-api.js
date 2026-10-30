// Beheer-API voor medewerkers: productbeheer en de commerciële kant van een klant.
// De licentie-worker controleert de medewerkerssessie en geeft de medewerker (actor) via de service binding door.
// Rechten: shop.view / shop.manage (productbeheer), billing.view / billing.manage (betalingen, abonnementen, uitzonderingen).

import { stripeRequest, stripeConfig, stripeDashboardUrl, StripeError } from "./stripe.js";
import { loadEffectiveEntitlements, loadOverrides, audit, SUBSCRIPTION_STATUS_LABELS, ENTITLEMENT_STATUS_LABELS } from "../shared/entitlements.js";
import { syncSubscription, syncCheckoutSession } from "./billing.js";

const IMAGE_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_RELEASE_BYTES = 100 * 1024 * 1024;
const parse = (value, fallback) => { try { return JSON.parse(value) ?? fallback; } catch { return fallback; } };

export function can(actor, permission) {
  return actor?.role === "owner" || actor?.permissions?.includes("*") || actor?.permissions?.includes(permission);
}

function cleanFeatures(input, known) {
  const out = {};
  for (const [key, value] of Object.entries(input && typeof input === "object" ? input : {})) {
    const feature = known.get(key);
    if (!feature) continue;
    if (feature.kind === "flag") { if (value === true) out[key] = true; }
    else if (value === null || value === "" || value === undefined) continue;
    else if (value === "unlimited") out[key] = "unlimited";
    else if (Number.isInteger(Number(value)) && Number(value) >= 0) out[key] = Number(value);
  }
  return out;
}

const optionalInt = (value, min, max) => {
  if (value === null || value === undefined || value === "") return { value: null };
  const n = Number(value);
  return Number.isInteger(n) && n >= min && n <= max ? { value: n } : { error: true };
};

async function productDetail(env, id) {
  const product = await env.DB.prepare("SELECT * FROM products WHERE id = ?").bind(id).first();
  if (!product) return null;
  const [images, features, plans, prices, releases] = await Promise.all([
    env.DB.prepare("SELECT id, alt, sort_order, content_type FROM product_images WHERE product_id = ? ORDER BY sort_order, created_at").bind(id).all(),
    env.DB.prepare("SELECT feature_key AS key, name, description, kind, sort_order FROM product_features WHERE product_id = ? ORDER BY sort_order, name COLLATE NOCASE").bind(id).all(),
    env.DB.prepare("SELECT p.*, (SELECT COUNT(*) FROM entitlements e WHERE e.plan_id = p.id AND e.status IN ('active', 'grace')) AS active_customers FROM product_plans p WHERE p.product_id = ? ORDER BY p.archived_at IS NOT NULL, p.rank, p.name COLLATE NOCASE").bind(id).all(),
    env.DB.prepare("SELECT pp.* FROM plan_prices pp JOIN product_plans pl ON pl.id = pp.plan_id WHERE pl.product_id = ? ORDER BY pp.active DESC, pp.created_at DESC").bind(id).all(),
    env.DB.prepare("SELECT id, version, platform, notes, file_name, file_size, sha256, published, published_at, created_at FROM product_releases WHERE product_id = ? ORDER BY created_at DESC").bind(id).all()
  ]);
  return {
    product, images: images.results, features: features.results, releases: releases.results,
    plans: plans.results.map((p) => ({ ...p, features: parse(p.features_json, {}), prices: prices.results.filter((pr) => pr.plan_id === p.id) }))
  };
}

async function knownFeatures(env, productId) {
  const { results } = await env.DB.prepare("SELECT feature_key, kind FROM product_features WHERE product_id = ?").bind(productId).all();
  return new Map(results.map((r) => [r.feature_key, r]));
}

// Maakt (indien nodig) het Stripe-product voor een plan en de Stripe-prijs aan. Prijzen in Stripe zijn onveranderlijk.
async function pushPriceToStripe(env, price) {
  const plan = await env.DB.prepare("SELECT pl.*, p.name AS product_name FROM product_plans pl JOIN products p ON p.id = pl.product_id WHERE pl.id = ?").bind(price.plan_id).first();
  let stripeProduct = plan.stripe_product_id;
  if (!stripeProduct) {
    stripeProduct = (await stripeRequest(env, "POST", "/v1/products", { name: `${plan.product_name} – ${plan.name}`, metadata: { product_id: plan.product_id, plan_id: plan.id } }, { idempotencyKey: `plan-product-${plan.id}` })).id;
    await env.DB.prepare("UPDATE product_plans SET stripe_product_id = ?, updated_at = ? WHERE id = ? AND stripe_product_id IS NULL").bind(stripeProduct, new Date().toISOString(), plan.id).run();
  }
  const params = { product: stripeProduct, currency: price.currency, unit_amount: price.unit_amount, tax_behavior: price.tax_behavior, metadata: { price_id: price.id, plan_id: plan.id } };
  if (plan.billing_type === "recurring") params.recurring = { interval: price.billing_interval, interval_count: price.interval_count };
  const created = await stripeRequest(env, "POST", "/v1/prices", params, { idempotencyKey: `price-${price.id}` });
  await env.DB.prepare("UPDATE plan_prices SET stripe_price_id = ? WHERE id = ? AND stripe_price_id IS NULL").bind(created.id, price.id).run();
  return created.id;
}

async function verifyExistingStripePrice(env, stripePriceId, price, plan) {
  const remote = await stripeRequest(env, "GET", `/v1/prices/${encodeURIComponent(stripePriceId)}`);
  const recurringOk = plan.billing_type === "recurring"
    ? remote.recurring && remote.recurring.interval === price.billing_interval && Number(remote.recurring.interval_count) === price.interval_count
    : !remote.recurring;
  if (remote.currency !== price.currency || Number(remote.unit_amount) !== price.unit_amount || !recurringOk || !remote.active) return "De Stripe-prijs komt niet overeen met bedrag, valuta of betaalperiode, of is niet actief.";
  return "";
}

function stripeProblem(h, error) {
  if (error instanceof StripeError) return h.json({ error: `Stripe: ${error.message}` }, error.status === 503 ? 503 : 502);
  throw error;
}

async function customerCommerce(env, customerId) {
  const customer = await env.DB.prepare("SELECT id, name, customer_type, billing_company, stripe_customer_id, source, vat_number, kvk_number, invoice_email FROM customers WHERE id = ?").bind(customerId).first();
  if (!customer) return null;
  const mode = stripeConfig(env).mode;
  const [accounts, orders, subs, invoices, log, rawEntitlements, licenseCounts] = await Promise.all([
    env.DB.prepare("SELECT id, name, email, role, active, disabled_at, email_verified_at, last_seen_at FROM customer_portal_accounts WHERE customer_id = ? ORDER BY role, name COLLATE NOCASE").bind(customerId).all(),
    env.DB.prepare("SELECT o.id, o.order_number, o.status, o.purchase_context, o.amount_total, o.amount_refunded, o.currency, o.created_at, o.paid_at, o.stripe_payment_intent_id, o.stripe_checkout_session_id, o.billing_json, p.name AS product_name, json_extract(o.plan_snapshot_json, '$.name') AS plan_name, a.email AS account_email FROM shop_orders o JOIN products p ON p.id = o.product_id LEFT JOIN customer_portal_accounts a ON a.id = o.account_id WHERE o.customer_id = ? ORDER BY o.created_at DESC LIMIT 100").bind(customerId).all(),
    env.DB.prepare("SELECT s.*, p.name AS product_name, pl.name AS plan_name, np.name AS pending_plan_name FROM shop_subscriptions s JOIN products p ON p.id = s.product_id JOIN product_plans pl ON pl.id = s.plan_id LEFT JOIN product_plans np ON np.id = s.pending_plan_id WHERE s.customer_id = ? ORDER BY s.created_at DESC").bind(customerId).all(),
    env.DB.prepare("SELECT number, status, currency, amount_due, amount_paid, hosted_invoice_url, stripe_invoice_id, stripe_created FROM billing_invoices WHERE customer_id = ? ORDER BY stripe_created DESC LIMIT 100").bind(customerId).all(),
    env.DB.prepare("SELECT action, actor_type, actor_name, reason, details_json, created_at, entity_type FROM commerce_audit_log WHERE customer_id = ? ORDER BY created_at DESC LIMIT 100").bind(customerId).all(),
    env.DB.prepare("SELECT * FROM entitlements WHERE customer_id = ? ORDER BY created_at DESC").bind(customerId).all(),
    env.DB.prepare("SELECT entitlement_id, COUNT(*) AS n FROM licenses WHERE customer_id = ? AND entitlement_id IS NOT NULL AND revoked_at IS NULL GROUP BY entitlement_id").bind(customerId).all()
  ]);
  const effective = await loadEffectiveEntitlements(env, customerId);
  const overrides = await loadOverrides(env, rawEntitlements.results.map((e) => e.id));
  const plans = await env.DB.prepare("SELECT pl.id, pl.name, p.name AS product_name, pl.product_id FROM product_plans pl JOIN products p ON p.id = pl.product_id WHERE pl.archived_at IS NULL ORDER BY p.name COLLATE NOCASE, pl.rank").all();
  const features = await env.DB.prepare("SELECT product_id, feature_key AS key, name, kind FROM product_features ORDER BY sort_order").all();
  return {
    plans: plans.results, features: features.results,
    customer: { ...customer, stripe_url: stripeDashboardUrl(mode, "customers", customer.stripe_customer_id) },
    stripe_mode: mode,
    accounts: accounts.results,
    orders: orders.results.map((o) => ({ ...o, billing: parse(o.billing_json, {}), billing_json: undefined, stripe_url: stripeDashboardUrl(mode, "payments", o.stripe_payment_intent_id) })),
    subscriptions: subs.results.map((s) => ({ ...s, plan_snapshot_json: undefined, status_label: SUBSCRIPTION_STATUS_LABELS[s.status] || s.status, stripe_url: stripeDashboardUrl(mode, "subscriptions", s.stripe_subscription_id) })),
    invoices: invoices.results.map((i) => ({ ...i, stripe_url: stripeDashboardUrl(mode, "invoices", i.stripe_invoice_id) })),
    entitlements: effective.map((e) => {
      const base = rawEntitlements.results.find((r) => r.id === e.id);
      return { ...e, status_label: ENTITLEMENT_STATUS_LABELS[e.status] || e.status, base_status_label: ENTITLEMENT_STATUS_LABELS[base.status] || base.status, base_reason: base.status_reason, base_valid_until: base.valid_until,
        licenses_in_use: Number(licenseCounts.results.find((r) => r.entitlement_id === e.id)?.n || 0),
        overrides: (overrides.get(e.id) || []).map((o) => ({ ...o, value: parse(o.value_json, {}), value_json: undefined })) };
    }),
    history: log.results.map((l) => ({ ...l, details: parse(l.details_json, {}), details_json: undefined }))
  };
}

export async function handleAdminShop(request, env, url, actor, h) {
  const path = url.pathname, method = request.method;
  const deny = (permission) => h.json({ error: "Je account heeft geen toestemming voor deze actie.", required_permission: permission }, 403);
  const body = async (max = 65536) => { try { return await h.readJson(request, max); } catch { return null; } };
  const actorName = actor.name || "Medewerker";

  if (method === "GET" && path === "/api/admin/shop/status") {
    if (!can(actor, "shop.view") && !can(actor, "billing.view")) return deny("shop.view");
    const failed = await env.DB.prepare("SELECT id, type, error, received_at FROM stripe_events WHERE status = 'failed' ORDER BY received_at DESC LIMIT 10").all();
    const last = await env.DB.prepare("SELECT MAX(received_at) AS at FROM stripe_events").first();
    return h.json({ config: stripeConfig(env), files_storage: !!env.PRODUCT_FILES, failed_events: failed.results, last_event_at: last?.at || null, settings: { grace_days: env.SHOP_GRACE_DAYS ?? null, upgrade_proration: env.SHOP_UPGRADE_PRORATION || "always_invoice", downgrade_timing: env.SHOP_DOWNGRADE_TIMING || "period_end" } });
  }

  // ---- Productbeheer ----
  if (path.startsWith("/api/admin/shop/")) {
    const write = method !== "GET";
    if (!can(actor, write ? "shop.manage" : "shop.view")) return deny(write ? "shop.manage" : "shop.view");
  }
  if (method === "GET" && path === "/api/admin/shop/products") {
    const { results } = await env.DB.prepare("SELECT p.id, p.name, p.slug, p.tagline, p.published, p.active, p.sort_order, (SELECT COUNT(*) FROM product_plans pl WHERE pl.product_id = p.id AND pl.archived_at IS NULL) AS plan_count, (SELECT COUNT(*) FROM product_plans pl WHERE pl.product_id = p.id AND pl.published = 1 AND pl.archived_at IS NULL) AS published_plans FROM products p WHERE p.shop_allowed = 1 ORDER BY p.sort_order, p.name COLLATE NOCASE").all();
    return h.json({ products: results });
  }
  if (method === "POST" && path === "/api/admin/shop/products") {
    const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
    const id = String(b.id || "").trim().toLowerCase(), name = String(b.name || "").trim().slice(0, 80);
    if (!/^[a-z0-9][a-z0-9-]{1,39}$/.test(id) || !name) return h.json({ error: "Vul een naam en een korte code in (kleine letters, cijfers en streepjes)." }, 400);
    const now = new Date().toISOString();
    try { await env.DB.prepare("INSERT INTO products (id, name, active, slug, published, shop_allowed, created_at, updated_at) VALUES (?, ?, 1, ?, 0, 1, ?, ?)").bind(id, name, id, now, now).run(); }
    catch (error) { if (String(error?.message || error).toLowerCase().includes("unique")) return h.json({ error: "Deze code of naam bestaat al." }, 409); throw error; }
    return h.json({ id }, 201);
  }
  const productRoute = /^\/api\/admin\/shop\/products\/([a-z0-9-]{1,40})(?:\/(features|images|plans|releases))?$/.exec(path);
  if (productRoute) {
    const [, productId, sub] = productRoute;
    const exists = await env.DB.prepare("SELECT id, shop_allowed FROM products WHERE id = ?").bind(productId).first();
    if (!exists) return h.json({ error: "Product niet gevonden." }, 404);
    if (!exists.shop_allowed) return h.json({ error: "Dit is een maatwerkproduct en wordt niet via de shop aangeboden." }, 403);
    const now = new Date().toISOString();
    if (!sub && method === "GET") return h.json(await productDetail(env, productId));
    if (!sub && method === "PATCH") {
      const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
      const name = String(b.name || "").trim().slice(0, 80), slug = String(b.slug || productId).trim().toLowerCase();
      if (!name || !/^[a-z0-9][a-z0-9-]{1,59}$/.test(slug)) return h.json({ error: "Vul een naam en een geldige webadresnaam in." }, 400);
      const published = b.published ? 1 : 0;
      if (published) {
        const ready = await env.DB.prepare("SELECT COUNT(*) AS n FROM plan_prices pp JOIN product_plans pl ON pl.id = pp.plan_id WHERE pl.product_id = ? AND pl.published = 1 AND pl.archived_at IS NULL AND pp.active = 1 AND pp.stripe_price_id IS NOT NULL").bind(productId).first();
        if (!Number(ready.n)) return h.json({ error: "Publiceer eerst minimaal één abonnement met een prijs die aan Stripe is gekoppeld." }, 409);
      }
      try {
        await env.DB.prepare("UPDATE products SET name = ?, slug = ?, tagline = ?, description = ?, published = ?, sort_order = ?, updated_at = ? WHERE id = ?")
          .bind(name, slug, String(b.tagline || "").trim().slice(0, 160), String(b.description || "").trim().slice(0, 8000), published, Number.isInteger(Number(b.sort_order)) ? Number(b.sort_order) : 0, now, productId).run();
      } catch (error) { if (String(error?.message || error).toLowerCase().includes("unique")) return h.json({ error: "Deze naam of webadresnaam is al in gebruik." }, 409); throw error; }
      await audit(env, { entity_type: "product", entity_id: productId, action: published ? "product.saved_published" : "product.saved", actor_type: "staff", actor_name: actorName });
      return h.json({ ok: true });
    }
    if (sub === "features" && method === "PUT") {
      const b = await body(); if (!b || !Array.isArray(b.features)) return h.json({ error: "Ongeldige aanvraag." }, 400);
      const seen = new Set(), rows = [];
      for (const [index, f] of b.features.slice(0, 60).entries()) {
        const key = String(f.key || "").trim().toLowerCase(), name = String(f.name || "").trim().slice(0, 80);
        if (!/^[a-z][a-z0-9_]{1,39}$/.test(key) || !name || seen.has(key)) return h.json({ error: `Controleer functie ${index + 1}: een unieke sleutel (kleine letters, cijfers, _) en een naam zijn verplicht.` }, 400);
        seen.add(key); rows.push([key, name, String(f.description || "").trim().slice(0, 240), f.kind === "limit" ? "limit" : "flag", index]);
      }
      await env.DB.batch([env.DB.prepare("DELETE FROM product_features WHERE product_id = ?").bind(productId), ...rows.map((r) => env.DB.prepare("INSERT INTO product_features (product_id, feature_key, name, description, kind, sort_order) VALUES (?, ?, ?, ?, ?, ?)").bind(productId, ...r))]);
      return h.json({ ok: true });
    }
    if (sub === "images" && method === "POST") {
      if (!env.PRODUCT_FILES) return h.json({ error: "Bestandsopslag (R2-binding PRODUCT_FILES) is nog niet gekoppeld." }, 503);
      const type = String(request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
      if (!IMAGE_TYPES.has(type)) return h.json({ error: "Gebruik een PNG-, JPEG- of WebP-afbeelding." }, 415);
      const bytes = await h.readBoundedRequestBytes(request, MAX_IMAGE_BYTES);
      if (!bytes || !bytes.length) return h.json({ error: "De afbeelding is leeg of groter dan 5 MB." }, 413);
      const id = crypto.randomUUID(), key = `images/${productId}/${id}`;
      await env.PRODUCT_FILES.put(key, bytes, { httpMetadata: { contentType: type } });
      const order = await env.DB.prepare("SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM product_images WHERE product_id = ?").bind(productId).first();
      await env.DB.prepare("INSERT INTO product_images (id, product_id, r2_key, content_type, alt, sort_order, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)").bind(id, productId, key, type, String(url.searchParams.get("alt") || "").slice(0, 160), order.n, now).run();
      return h.json({ id }, 201);
    }
    if (sub === "plans" && method === "POST") {
      const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
      const code = String(b.code || "").trim().toLowerCase(), name = String(b.name || "").trim().slice(0, 80);
      const billingType = b.billing_type === "one_time" ? "one_time" : b.billing_type === "recurring" ? "recurring" : "";
      if (!/^[a-z0-9][a-z0-9-]{0,39}$/.test(code) || !name || !billingType) return h.json({ error: "Vul een code, naam en soort (eenmalig of abonnement) in." }, 400);
      const users = optionalInt(b.max_users, 1, 100000), activations = optionalInt(b.max_activations, 0, 100000), trial = optionalInt(b.trial_days, 0, 730), rank = optionalInt(b.rank, 0, 1000);
      if (users.error || activations.error || trial.error || rank.error) return h.json({ error: "Controleer de limieten, proefperiode en volgorde." }, 400);
      if (billingType === "one_time" && trial.value) return h.json({ error: "Een proefperiode kan alleen bij een abonnement." }, 400);
      const id = crypto.randomUUID(), features = cleanFeatures(b.features, await knownFeatures(env, productId));
      try {
        await env.DB.prepare("INSERT INTO product_plans (id, product_id, code, name, description, billing_type, features_json, max_users, max_activations, trial_days, rank, published, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)")
          .bind(id, productId, code, name, String(b.description || "").trim().slice(0, 600), billingType, JSON.stringify(features), users.value, activations.value, trial.value || 0, rank.value || 0, now, now).run();
      } catch (error) { if (String(error?.message || error).toLowerCase().includes("unique")) return h.json({ error: "Deze code bestaat al voor dit product." }, 409); throw error; }
      await audit(env, { entity_type: "plan", entity_id: id, action: "plan.created", actor_type: "staff", actor_name: actorName, details: { product_id: productId, name } });
      return h.json({ id }, 201);
    }
    if (sub === "releases" && method === "POST") {
      const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
      const version = String(b.version || "").trim().slice(0, 40), platform = String(b.platform || "").trim().slice(0, 40);
      if (!/^[0-9A-Za-z][0-9A-Za-z.+-]*$/.test(version)) return h.json({ error: "Vul een geldig versienummer in, bijvoorbeeld 0.4.0." }, 400);
      const id = crypto.randomUUID();
      try { await env.DB.prepare("INSERT INTO product_releases (id, product_id, version, platform, notes, published, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, ?, ?)").bind(id, productId, version, platform, String(b.notes || "").trim().slice(0, 8000), now, now).run(); }
      catch (error) { if (String(error?.message || error).toLowerCase().includes("unique")) return h.json({ error: "Deze versie bestaat al voor dit platform." }, 409); throw error; }
      return h.json({ id }, 201);
    }
    return h.json({ error: "Niet gevonden." }, 404);
  }
  const imageRoute = /^\/api\/admin\/shop\/images\/([0-9a-f-]{36})$/.exec(path);
  if (imageRoute && method === "GET") {
    // Het staffportaal mag alleen afbeeldingen van de eigen origin tonen (CSP); daarom via deze route.
    const image = await env.DB.prepare("SELECT r2_key, content_type FROM product_images WHERE id = ?").bind(imageRoute[1]).first();
    const object = image && env.PRODUCT_FILES ? await env.PRODUCT_FILES.get(image.r2_key) : null;
    if (!object) return h.json({ error: "Afbeelding niet gevonden." }, 404);
    return new Response(object.body, { headers: { "Content-Type": image.content_type, "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" } });
  }
  if (imageRoute && method === "DELETE") {
    const image = await env.DB.prepare("SELECT r2_key FROM product_images WHERE id = ?").bind(imageRoute[1]).first();
    if (!image) return h.json({ error: "Afbeelding niet gevonden." }, 404);
    await env.DB.prepare("DELETE FROM product_images WHERE id = ?").bind(imageRoute[1]).run();
    if (env.PRODUCT_FILES) await env.PRODUCT_FILES.delete(image.r2_key);
    return h.json({ ok: true });
  }
  const planRoute = /^\/api\/admin\/shop\/plans\/([0-9a-f-]{36})(?:\/(prices))?$/.exec(path);
  if (planRoute) {
    const plan = await env.DB.prepare("SELECT pl.* FROM product_plans pl JOIN products p ON p.id = pl.product_id WHERE pl.id = ? AND p.shop_allowed = 1").bind(planRoute[1]).first();
    if (!plan) return h.json({ error: "Abonnement niet gevonden." }, 404);
    const now = new Date().toISOString();
    if (!planRoute[2] && method === "PATCH") {
      const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
      const name = String(b.name || "").trim().slice(0, 80);
      const users = optionalInt(b.max_users, 1, 100000), activations = optionalInt(b.max_activations, 0, 100000), trial = optionalInt(b.trial_days, 0, 730), rank = optionalInt(b.rank, 0, 1000);
      if (!name || users.error || activations.error || trial.error || rank.error) return h.json({ error: "Controleer naam, limieten, proefperiode en volgorde." }, 400);
      if (plan.billing_type === "one_time" && trial.value) return h.json({ error: "Een proefperiode kan alleen bij een abonnement." }, 400);
      const published = b.published ? 1 : 0, archived = b.archived ? (plan.archived_at || now) : null;
      if (published && !archived) {
        const priced = await env.DB.prepare("SELECT 1 FROM plan_prices WHERE plan_id = ? AND active = 1 AND stripe_price_id IS NOT NULL").bind(plan.id).first();
        if (!priced) return h.json({ error: "Voeg eerst een prijs toe die aan Stripe is gekoppeld." }, 409);
      }
      const features = cleanFeatures(b.features, await knownFeatures(env, plan.product_id));
      // Bestaande klanten houden de functies uit hun aankoop; deze wijziging geldt voor nieuwe aankopen en planwissels.
      await env.DB.prepare("UPDATE product_plans SET name = ?, description = ?, features_json = ?, max_users = ?, max_activations = ?, trial_days = ?, rank = ?, published = ?, archived_at = ?, updated_at = ? WHERE id = ?")
        .bind(name, String(b.description || "").trim().slice(0, 600), JSON.stringify(features), users.value, activations.value, trial.value || 0, rank.value || 0, archived ? 0 : published, archived, now, plan.id).run();
      await audit(env, { entity_type: "plan", entity_id: plan.id, action: "plan.updated", actor_type: "staff", actor_name: actorName, details: { published, archived: !!archived } });
      return h.json({ ok: true });
    }
    if (planRoute[2] === "prices" && method === "POST") {
      const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
      const currency = String(b.currency || "").trim().toLowerCase(), amount = Number(b.unit_amount);
      const tax = ["inclusive", "exclusive", "unspecified"].includes(b.tax_behavior) ? b.tax_behavior : "";
      const interval = plan.billing_type === "recurring" ? (["day", "week", "month", "year"].includes(b.interval) ? b.interval : "") : null;
      const count = plan.billing_type === "recurring" ? Number(b.interval_count || 1) : 1;
      if (!/^[a-z]{3}$/.test(currency)) return h.json({ error: "Kies een valuta." }, 400);
      if (!Number.isInteger(amount) || amount < 0 || amount > 100000000) return h.json({ error: "Vul het bedrag in centen in, als heel getal." }, 400);
      if (!tax) return h.json({ error: "Kies of de prijs inclusief of exclusief btw is." }, 400);
      if (plan.billing_type === "recurring" && (!interval || !Number.isInteger(count) || count < 1 || count > 36)) return h.json({ error: "Kies een betaalperiode." }, 400);
      const id = crypto.randomUUID();
      const price = { id, plan_id: plan.id, currency, unit_amount: amount, billing_interval: interval, interval_count: count, tax_behavior: tax };
      const existingStripe = String(b.stripe_price_id || "").trim();
      if (existingStripe && !/^price_[A-Za-z0-9]+$/.test(existingStripe)) return h.json({ error: "Een Stripe-prijs-ID begint met price_." }, 400);
      if (existingStripe) {
        try { const problem = await verifyExistingStripePrice(env, existingStripe, price, plan); if (problem) return h.json({ error: problem }, 400); }
        catch (error) { return stripeProblem(h, error); }
      }
      await env.DB.prepare("INSERT INTO plan_prices (id, plan_id, currency, unit_amount, billing_interval, interval_count, tax_behavior, stripe_price_id, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)").bind(id, plan.id, currency, amount, interval, count, tax, existingStripe || null, now).run();
      let stripeError = "";
      if (!existingStripe && b.create_in_stripe !== false) {
        try { await pushPriceToStripe(env, price); } catch (error) { stripeError = error instanceof StripeError ? error.message : "Stripe niet bereikbaar"; }
      }
      await audit(env, { entity_type: "price", entity_id: id, action: "price.created", actor_type: "staff", actor_name: actorName, details: { plan: plan.name, currency, amount, interval, count, tax } });
      return h.json({ id, stripe_error: stripeError || undefined }, 201);
    }
    return h.json({ error: "Niet gevonden." }, 404);
  }
  const priceRoute = /^\/api\/admin\/shop\/prices\/([0-9a-f-]{36})\/(sync|archive)$/.exec(path);
  if (priceRoute && method === "POST") {
    const price = await env.DB.prepare("SELECT * FROM plan_prices WHERE id = ?").bind(priceRoute[1]).first();
    if (!price) return h.json({ error: "Prijs niet gevonden." }, 404);
    try {
      if (priceRoute[2] === "sync") {
        if (price.stripe_price_id) return h.json({ ok: true, stripe_price_id: price.stripe_price_id });
        return h.json({ ok: true, stripe_price_id: await pushPriceToStripe(env, price) });
      }
      // Archiveren stopt nieuwe aankopen; lopende abonnementen op deze prijs blijven ongewijzigd doorlopen.
      await env.DB.prepare("UPDATE plan_prices SET active = 0, archived_at = COALESCE(archived_at, ?) WHERE id = ?").bind(new Date().toISOString(), price.id).run();
      if (price.stripe_price_id && stripeConfig(env).mode) await stripeRequest(env, "POST", `/v1/prices/${encodeURIComponent(price.stripe_price_id)}`, { active: "false" });
      await audit(env, { entity_type: "price", entity_id: price.id, action: "price.archived", actor_type: "staff", actor_name: actorName });
      return h.json({ ok: true });
    } catch (error) { return stripeProblem(h, error); }
  }
  const releaseRoute = /^\/api\/admin\/shop\/releases\/([0-9a-f-]{36})(?:\/(file))?$/.exec(path);
  if (releaseRoute) {
    const release = await env.DB.prepare("SELECT * FROM product_releases WHERE id = ?").bind(releaseRoute[1]).first();
    if (!release) return h.json({ error: "Versie niet gevonden." }, 404);
    const now = new Date().toISOString();
    if (releaseRoute[2] === "file" && method === "PUT") {
      if (!env.PRODUCT_FILES) return h.json({ error: "Bestandsopslag (R2-binding PRODUCT_FILES) is nog niet gekoppeld." }, 503);
      if (release.published) return h.json({ error: "Depubliceer de versie voordat je het bestand vervangt." }, 409);
      const size = Number(request.headers.get("Content-Length") || 0);
      if (!size || size > MAX_RELEASE_BYTES) return h.json({ error: "Het bestand ontbreekt of is groter dan 100 MB." }, 413);
      const name = String(url.searchParams.get("name") || "download").replace(/[^A-Za-z0-9._ -]/g, "_").slice(0, 120);
      const sha = String(request.headers.get("X-File-SHA256") || "").toLowerCase();
      const key = `releases/${release.product_id}/${release.id}/${name}`;
      await env.PRODUCT_FILES.put(key, request.body, { httpMetadata: { contentType: "application/octet-stream" } });
      if (release.r2_key && release.r2_key !== key) await env.PRODUCT_FILES.delete(release.r2_key);
      await env.DB.prepare("UPDATE product_releases SET r2_key = ?, file_name = ?, file_size = ?, sha256 = ?, updated_at = ? WHERE id = ?").bind(key, name, size, /^[0-9a-f]{64}$/.test(sha) ? sha : null, now, release.id).run();
      return h.json({ ok: true });
    }
    if (!releaseRoute[2] && method === "PATCH") {
      const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
      const published = b.published ? 1 : 0;
      if (published && !release.r2_key) return h.json({ error: "Upload eerst het downloadbestand." }, 409);
      await env.DB.prepare("UPDATE product_releases SET notes = ?, published = ?, published_at = CASE WHEN ? = 1 THEN COALESCE(published_at, ?) ELSE published_at END, updated_at = ? WHERE id = ?").bind(String(b.notes ?? release.notes).trim().slice(0, 8000), published, published, now, now, release.id).run();
      await audit(env, { entity_type: "release", entity_id: release.id, action: published ? "release.published" : "release.unpublished", actor_type: "staff", actor_name: actorName, details: { version: release.version } });
      return h.json({ ok: true });
    }
    return h.json({ error: "Niet gevonden." }, 404);
  }

  // ---- Commerciële kant van een klant ----
  const commerceRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})\/commerce$/.exec(path);
  if (commerceRoute && method === "GET") {
    if (!can(actor, "billing.view")) return deny("billing.view");
    const data = await customerCommerce(env, commerceRoute[1]);
    return data ? h.json(data) : h.json({ error: "Klant niet gevonden." }, 404);
  }
  const grantRoute = /^\/api\/admin\/customers\/([0-9a-f-]{36})\/entitlements$/.exec(path);
  if (grantRoute && method === "POST") {
    if (!can(actor, "billing.manage")) return deny("billing.manage");
    const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
    const reason = String(b.reason || "").trim().slice(0, 500), until = String(b.valid_until || "");
    const plan = await env.DB.prepare("SELECT * FROM product_plans WHERE id = ?").bind(String(b.plan_id || "")).first();
    const customer = await env.DB.prepare("SELECT id FROM customers WHERE id = ?").bind(grantRoute[1]).first();
    if (!customer || !plan) return h.json({ error: "Klant of abonnement niet gevonden." }, 404);
    if (reason.length < 3) return h.json({ error: "Vul een reden in." }, 400);
    if (until && !/^\d{4}-\d{2}-\d{2}$/.test(until)) return h.json({ error: "Vul een geldige einddatum in." }, 400);
    const id = crypto.randomUUID(), now = new Date().toISOString();
    await env.DB.prepare("INSERT INTO entitlements (id, customer_id, product_id, plan_id, source, source_id, status, status_reason, plan_name, features_json, max_users, max_activations, valid_from, valid_until, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, 'manual', ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
      .bind(id, customer.id, plan.product_id, plan.id, id, reason, plan.name, plan.features_json, plan.max_users, plan.max_activations, now, until ? `${until}T23:59:59.999Z` : null, actorName, now, now).run();
    await audit(env, { customer_id: customer.id, entity_type: "entitlement", entity_id: id, action: "entitlement.manual_grant", actor_type: "staff", actor_name: actorName, reason, details: { plan: plan.name, valid_until: until || null } });
    return h.json({ id }, 201);
  }
  const overrideCreate = /^\/api\/admin\/entitlements\/([0-9a-f-]{36})\/overrides$/.exec(path);
  if (overrideCreate && method === "POST") {
    if (!can(actor, "billing.manage")) return deny("billing.manage");
    const b = await body(); if (!b) return h.json({ error: "Ongeldige aanvraag." }, 400);
    const ent = await env.DB.prepare("SELECT * FROM entitlements WHERE id = ?").bind(overrideCreate[1]).first();
    if (!ent) return h.json({ error: "Recht niet gevonden." }, 404);
    const kind = ["extend", "suspend", "features", "limits"].includes(b.kind) ? b.kind : "";
    const reason = String(b.reason || "").trim().slice(0, 500), expires = String(b.expires_at || "");
    if (!kind) return h.json({ error: "Kies een soort uitzondering." }, 400);
    if (reason.length < 3) return h.json({ error: "Vul een reden in; die wordt vastgelegd in de historie." }, 400);
    if (expires && !/^\d{4}-\d{2}-\d{2}$/.test(expires)) return h.json({ error: "Vul een geldige einddatum in." }, 400);
    let value = {};
    if (kind === "extend") { if (!/^\d{4}-\d{2}-\d{2}$/.test(String(b.value?.until || ""))) return h.json({ error: "Vul de datum in tot wanneer de toegang verlengd wordt." }, 400); value = { until: `${b.value.until}T23:59:59.999Z` }; }
    if (kind === "features") value = { set: cleanFeatures(b.value?.set, await knownFeatures(env, ent.product_id)), remove: (Array.isArray(b.value?.remove) ? b.value.remove : []).map(String).slice(0, 60) };
    if (kind === "limits") {
      const users = optionalInt(b.value?.max_users, 1, 100000), activations = optionalInt(b.value?.max_activations, 0, 100000);
      if (users.error || activations.error) return h.json({ error: "Controleer de limieten." }, 400);
      if (b.value?.max_users !== undefined && b.value?.max_users !== "") value.max_users = users.value;
      if (b.value?.max_activations !== undefined && b.value?.max_activations !== "") value.max_activations = activations.value;
    }
    const id = crypto.randomUUID(), now = new Date().toISOString();
    await env.DB.prepare("INSERT INTO entitlement_overrides (id, entitlement_id, kind, value_json, reason, created_by_staff_id, created_by_name, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)").bind(id, ent.id, kind, JSON.stringify(value), reason, actor.id || null, actorName, now, expires ? `${expires}T23:59:59.999Z` : null).run();
    await audit(env, { customer_id: ent.customer_id, entity_type: "override", entity_id: id, action: `override.${kind}`, actor_type: "staff", actor_name: actorName, reason, details: { entitlement_id: ent.id, value, expires_at: expires || null } });
    return h.json({ id }, 201);
  }
  const overrideRevoke = /^\/api\/admin\/overrides\/([0-9a-f-]{36})\/revoke$/.exec(path);
  if (overrideRevoke && method === "POST") {
    if (!can(actor, "billing.manage")) return deny("billing.manage");
    const b = await body() || {};
    const reason = String(b.reason || "").trim().slice(0, 500);
    if (reason.length < 3) return h.json({ error: "Vul een reden in." }, 400);
    const o = await env.DB.prepare("SELECT o.id, e.customer_id, o.kind FROM entitlement_overrides o JOIN entitlements e ON e.id = o.entitlement_id WHERE o.id = ? AND o.revoked_at IS NULL").bind(overrideRevoke[1]).first();
    if (!o) return h.json({ error: "Actieve uitzondering niet gevonden." }, 404);
    await env.DB.prepare("UPDATE entitlement_overrides SET revoked_at = ?, revoked_by_name = ?, revoke_reason = ? WHERE id = ? AND revoked_at IS NULL").bind(new Date().toISOString(), actorName, reason, o.id).run();
    await audit(env, { customer_id: o.customer_id, entity_type: "override", entity_id: o.id, action: "override.revoked", actor_type: "staff", actor_name: actorName, reason, details: { kind: o.kind } });
    return h.json({ ok: true });
  }
  const subAdmin = /^\/api\/admin\/subscriptions\/([0-9a-f-]{36})\/(resync|cancel)$/.exec(path);
  if (subAdmin && method === "POST") {
    if (!can(actor, subAdmin[2] === "resync" ? "billing.view" : "billing.manage")) return deny(subAdmin[2] === "resync" ? "billing.view" : "billing.manage");
    const sub = await env.DB.prepare("SELECT * FROM shop_subscriptions WHERE id = ?").bind(subAdmin[1]).first();
    if (!sub) return h.json({ error: "Abonnement niet gevonden." }, 404);
    try {
      if (subAdmin[2] === "cancel") {
        const b = await body() || {};
        const reason = String(b.reason || "").trim().slice(0, 500);
        if (reason.length < 3) return h.json({ error: "Vul een reden in." }, 400);
        if (b.mode === "now") await stripeRequest(env, "DELETE", `/v1/subscriptions/${encodeURIComponent(sub.stripe_subscription_id)}`);
        else await stripeRequest(env, "POST", `/v1/subscriptions/${encodeURIComponent(sub.stripe_subscription_id)}`, { cancel_at_period_end: "true" });
        await audit(env, { customer_id: sub.customer_id, entity_type: "subscription", entity_id: sub.id, action: b.mode === "now" ? "subscription.canceled_now_by_staff" : "subscription.cancel_requested_by_staff", actor_type: "staff", actor_name: actorName, reason });
      }
      await syncSubscription(env, sub.stripe_subscription_id, actorName);
      return h.json({ ok: true });
    } catch (error) { return stripeProblem(h, error); }
  }
  const orderAdmin = /^\/api\/admin\/orders\/([0-9a-f-]{36})\/resync$/.exec(path);
  if (orderAdmin && method === "POST") {
    if (!can(actor, "billing.view")) return deny("billing.view");
    const order = await env.DB.prepare("SELECT stripe_checkout_session_id FROM shop_orders WHERE id = ?").bind(orderAdmin[1]).first();
    if (!order?.stripe_checkout_session_id) return h.json({ error: "Bestelling niet gevonden." }, 404);
    try { await syncCheckoutSession(env, order.stripe_checkout_session_id); return h.json({ ok: true }); } catch (error) { return stripeProblem(h, error); }
  }
  return null;
}
