// Stripe-koppeling: klanten, Checkout, abonnementen, facturen, terugbetalingen en webhooks.
// Toegang hangt alleen af van wat Stripe aan de serverzijde bevestigt. Elke melding haalt het actuele object
// opnieuw bij Stripe op, zodat dubbele, vertraagde of verkeerd geordende meldingen altijd op de juiste eindstand uitkomen.

import { stripeRequest, verifyStripeSignature, stripeConfig } from "./stripe.js";
import { mapStripeSubscriptionStatus, entitlementStatusForSubscription, entitlementStatusForOrder, upsertSourceEntitlement, audit, planSnapshot } from "../shared/entitlements.js";

const iso = (seconds) => (Number.isFinite(Number(seconds)) && seconds ? new Date(Number(seconds) * 1000).toISOString() : null);
const nowIso = () => new Date().toISOString();

export function graceDays(env) {
  const value = Number(env.SHOP_GRACE_DAYS);
  return env.SHOP_GRACE_DAYS !== undefined && env.SHOP_GRACE_DAYS !== "" && Number.isInteger(value) && value >= 0 ? value : null;
}

export function shopApiUrl(env) {
  return String(env.PUBLIC_SHOP_API_URL || "https://shop-api.cohentra.digital").replace(/\/+$/, "");
}

export function customerPortalUrl(env) {
  return String(env.PUBLIC_CUSTOMER_URL || "https://customer.cohentra.digital").replace(/\/+$/, "");
}

// Koppelt de interne klant (organisatie of particulier) aan precies één Stripe-klant.
export async function ensureStripeCustomer(env, customer, account) {
  const details = {
    name: customer.billing_company || customer.name,
    email: customer.invoice_email || customer.contact_email || account?.email || undefined,
    address: customer.street || customer.city ? { line1: customer.street || undefined, postal_code: customer.postal_code || undefined, city: customer.city || undefined, country: countryCode(customer.country) } : undefined,
    preferred_locales: ["nl"],
    metadata: { customer_id: customer.id, customer_number: customer.customer_number || "", customer_type: customer.customer_type }
  };
  if (customer.stripe_customer_id) {
    await stripeRequest(env, "POST", `/v1/customers/${encodeURIComponent(customer.stripe_customer_id)}`, details);
    return customer.stripe_customer_id;
  }
  const created = await stripeRequest(env, "POST", "/v1/customers", details, { idempotencyKey: `customer-${customer.id}` });
  await env.DB.prepare("UPDATE customers SET stripe_customer_id = ?, updated_at = ? WHERE id = ? AND stripe_customer_id IS NULL").bind(created.id, nowIso(), customer.id).run();
  const row = await env.DB.prepare("SELECT stripe_customer_id FROM customers WHERE id = ?").bind(customer.id).first();
  return row.stripe_customer_id;
}

// Alleen landen die in de bestaande klantadministratie voorkomen; onbekende waarden laat Stripe zelf uitvragen.
function countryCode(country) {
  return ({ nederland: "NL", "belgië": "BE", belgie: "BE", duitsland: "DE", frankrijk: "FR", luxemburg: "LU", "verenigd koninkrijk": "GB" })[String(country || "").trim().toLowerCase()] || undefined;
}

export async function createCheckoutSession(env, { order, customer, stripeCustomerId, price, plan, trialDays }) {
  const base = customerPortalUrl(env);
  const config = stripeConfig(env);
  const params = {
    mode: plan.billing_type === "recurring" ? "subscription" : "payment",
    customer: stripeCustomerId,
    client_reference_id: order.id,
    line_items: [{ price: price.stripe_price_id, quantity: 1 }],
    success_url: `${base}/?checkout=success&order=${encodeURIComponent(order.id)}`,
    cancel_url: `${base}/?checkout=cancel&order=${encodeURIComponent(order.id)}`,
    locale: "nl",
    expires_at: Math.floor(Date.now() / 1000) + 60 * 60,
    metadata: { order_id: order.id, customer_id: customer.id, plan_id: plan.id }
  };
  if (plan.billing_type === "recurring") {
    params.subscription_data = { metadata: { order_id: order.id, customer_id: customer.id, plan_id: plan.id } };
    if (trialDays > 0) params.subscription_data.trial_period_days = trialDays;
  } else {
    // Stripe maakt de factuur; er wordt dus nooit een tweede factuur buiten Stripe aangemaakt.
    params.invoice_creation = { enabled: true, invoice_data: { metadata: { order_id: order.id, customer_id: customer.id } } };
    params.payment_intent_data = { metadata: { order_id: order.id, customer_id: customer.id } };
  }
  if (order.purchase_context === "business") params.tax_id_collection = { enabled: true };
  if (config.automatic_tax) { params.automatic_tax = { enabled: true }; params.customer_update = { address: "auto", name: "auto" }; }
  if (config.require_terms) params.consent_collection = { terms_of_service: "required" };
  return await stripeRequest(env, "POST", "/v1/checkout/sessions", params, { idempotencyKey: `checkout-${order.id}` });
}

async function planAndPriceForStripePrice(env, stripePriceId) {
  return await env.DB.prepare("SELECT pp.*, pl.id AS plan_id, pl.product_id, pl.name AS plan_name FROM plan_prices pp JOIN product_plans pl ON pl.id = pp.plan_id WHERE pp.stripe_price_id = ?").bind(stripePriceId).first();
}

async function customerForStripe(env, stripeCustomerId, metadataCustomerId) {
  // Een klant wordt alleen gekoppeld als het Stripe-klantnummer overeenkomt met wat de server zelf heeft vastgelegd.
  const row = await env.DB.prepare("SELECT * FROM customers WHERE stripe_customer_id = ?").bind(String(stripeCustomerId || "")).first();
  if (row && metadataCustomerId && row.id !== metadataCustomerId) return null;
  return row;
}

function subscriptionPeriod(sub) {
  const item = sub.items?.data?.[0] || {};
  return { start: iso(sub.current_period_start ?? item.current_period_start), end: iso(sub.current_period_end ?? item.current_period_end) };
}

export async function syncSubscription(env, stripeSubscriptionId, actor = "stripe") {
  const sub = await stripeRequest(env, "GET", `/v1/subscriptions/${encodeURIComponent(stripeSubscriptionId)}`);
  const customer = await customerForStripe(env, typeof sub.customer === "string" ? sub.customer : sub.customer?.id, sub.metadata?.customer_id);
  if (!customer) return { ignored: "onbekende klant" };
  const stripePrice = sub.items?.data?.[0]?.price?.id;
  const price = stripePrice ? await planAndPriceForStripePrice(env, stripePrice) : null;
  if (!price) return { ignored: "onbekende prijs" };
  const plan = await env.DB.prepare("SELECT * FROM product_plans WHERE id = ?").bind(price.plan_id).first();
  const existing = await env.DB.prepare("SELECT * FROM shop_subscriptions WHERE stripe_subscription_id = ?").bind(sub.id).first();
  const status = mapStripeSubscriptionStatus(sub.status);
  const period = subscriptionPeriod(sub);
  const now = nowIso();
  const pastDueSince = status === "past_due" ? (existing?.past_due_since || now) : null;
  let pending = { plan: null, price: null, at: null, schedule: null };
  const scheduleId = typeof sub.schedule === "string" ? sub.schedule : sub.schedule?.id;
  if (scheduleId) {
    const schedule = await stripeRequest(env, "GET", `/v1/subscription_schedules/${encodeURIComponent(scheduleId)}`);
    const next = (schedule.phases || []).find((phase) => phase.start_date > Math.floor(Date.now() / 1000));
    const nextPrice = next?.items?.[0]?.price;
    const nextRow = nextPrice ? await planAndPriceForStripePrice(env, typeof nextPrice === "string" ? nextPrice : nextPrice.id) : null;
    if (nextRow && nextRow.id !== price.id && ["active", "not_started"].includes(schedule.status)) pending = { plan: nextRow.plan_id, price: nextRow.id, at: iso(next.start_date), schedule: schedule.id };
  }
  const orderId = sub.metadata?.order_id || existing?.order_id || null;
  const order = orderId ? await env.DB.prepare("SELECT id FROM shop_orders WHERE id = ? AND customer_id = ?").bind(orderId, customer.id).first() : null;
  const planChanged = existing && existing.plan_id !== plan.id;
  const snapshot = JSON.stringify(planSnapshot(plan, price));
  const id = existing?.id || crypto.randomUUID();
  await env.DB.prepare(`INSERT INTO shop_subscriptions (id, customer_id, product_id, plan_id, price_id, order_id, stripe_subscription_id, stripe_status, status, current_period_start, current_period_end, cancel_at_period_end, cancel_at, canceled_at, ended_at, trial_end, past_due_since, pending_plan_id, pending_price_id, pending_change_at, stripe_schedule_id, plan_snapshot_json, livemode, synced_at, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(stripe_subscription_id) DO UPDATE SET plan_id = excluded.plan_id, price_id = excluded.price_id, order_id = COALESCE(shop_subscriptions.order_id, excluded.order_id), stripe_status = excluded.stripe_status, status = excluded.status,
      current_period_start = excluded.current_period_start, current_period_end = excluded.current_period_end, cancel_at_period_end = excluded.cancel_at_period_end, cancel_at = excluded.cancel_at, canceled_at = excluded.canceled_at,
      ended_at = excluded.ended_at, trial_end = excluded.trial_end, past_due_since = excluded.past_due_since, pending_plan_id = excluded.pending_plan_id, pending_price_id = excluded.pending_price_id,
      pending_change_at = excluded.pending_change_at, stripe_schedule_id = excluded.stripe_schedule_id,
      plan_snapshot_json = CASE WHEN shop_subscriptions.plan_id <> excluded.plan_id THEN excluded.plan_snapshot_json ELSE shop_subscriptions.plan_snapshot_json END,
      synced_at = excluded.synced_at, updated_at = excluded.updated_at`)
    .bind(id, customer.id, plan.product_id, plan.id, price.id, order?.id || null, sub.id, sub.status, status, period.start, period.end, sub.cancel_at_period_end ? 1 : 0, iso(sub.cancel_at), iso(sub.canceled_at), iso(sub.ended_at), iso(sub.trial_end), pastDueSince, pending.plan, pending.price, pending.at, pending.schedule, snapshot, sub.livemode ? 1 : 0, now, now, now).run();
  const saved = await env.DB.prepare("SELECT * FROM shop_subscriptions WHERE stripe_subscription_id = ?").bind(sub.id).first();
  const base = entitlementStatusForSubscription(saved, Date.now(), graceDays(env));
  const validUntil = ["canceled", "expired"].includes(saved.status) ? (saved.ended_at || saved.current_period_end || now) : saved.current_period_end;
  const { row, previous } = await upsertSourceEntitlement(env, { customerId: customer.id, productId: plan.product_id, plan, source: "subscription", sourceId: saved.id, status: base.status, reason: base.reason, validFrom: saved.created_at, validUntil, snapshotChanged: false });
  if (order && ["active", "trialing", "past_due"].includes(saved.status)) {
    await env.DB.prepare("UPDATE shop_orders SET stripe_subscription_id = ?, status = CASE WHEN status IN ('pending', 'processing') THEN 'paid' ELSE status END, paid_at = COALESCE(paid_at, ?), updated_at = ? WHERE id = ?").bind(sub.id, now, now, order.id).run();
  }
  if (!existing || existing.status !== saved.status || planChanged || existing.cancel_at_period_end !== saved.cancel_at_period_end || existing.pending_price_id !== saved.pending_price_id) {
    await audit(env, { customer_id: customer.id, entity_type: "subscription", entity_id: saved.id, action: !existing ? "subscription.created" : "subscription.changed", actor_type: actor === "stripe" ? "stripe" : "staff", actor_name: actor, details: { from: existing ? { status: existing.status, plan_id: existing.plan_id, cancel_at_period_end: existing.cancel_at_period_end } : null, to: { status: saved.status, stripe_status: saved.stripe_status, plan_id: saved.plan_id, cancel_at_period_end: saved.cancel_at_period_end, pending_price_id: saved.pending_price_id, period_end: saved.current_period_end } } });
  }
  if (previous && previous.status !== row.status) await audit(env, { customer_id: customer.id, entity_type: "entitlement", entity_id: row.id, action: "entitlement.status", actor_type: "stripe", actor_name: "Stripe", reason: row.status_reason, details: { from: previous.status, to: row.status } });
  return { subscription: saved, entitlement: row };
}

async function grantOrderEntitlement(env, orderId) {
  const order = await env.DB.prepare("SELECT * FROM shop_orders WHERE id = ?").bind(orderId).first();
  const plan = await env.DB.prepare("SELECT * FROM product_plans WHERE id = ?").bind(order.plan_id).first();
  // Het vastgelegde plan uit de bestelling bepaalt de rechten, niet de huidige planinstelling.
  const snap = JSON.parse(order.plan_snapshot_json || "{}");
  const frozen = { ...plan, name: snap.name || plan.name, features_json: JSON.stringify(snap.features || {}), max_users: snap.max_users ?? null, max_activations: snap.max_activations ?? null };
  const base = entitlementStatusForOrder(order);
  const { row, previous } = await upsertSourceEntitlement(env, { customerId: order.customer_id, productId: order.product_id, plan: frozen, source: "order", sourceId: order.id, status: base.status, reason: base.reason, validFrom: order.paid_at || order.created_at, validUntil: null, snapshotChanged: false });
  if (!previous || previous.status !== row.status) await audit(env, { customer_id: order.customer_id, entity_type: "entitlement", entity_id: row.id, action: previous ? "entitlement.status" : "entitlement.granted", actor_type: "stripe", actor_name: "Stripe", reason: row.status_reason, details: { order: order.order_number, from: previous?.status || null, to: row.status } });
  return row;
}

export async function syncCheckoutSession(env, sessionId) {
  const session = await stripeRequest(env, "GET", `/v1/checkout/sessions/${encodeURIComponent(sessionId)}`);
  const orderId = session.metadata?.order_id || session.client_reference_id;
  const order = orderId ? await env.DB.prepare("SELECT * FROM shop_orders WHERE id = ?").bind(orderId).first() : null;
  if (!order || (order.stripe_checkout_session_id && order.stripe_checkout_session_id !== session.id)) return { ignored: "onbekende bestelling" };
  const customer = await customerForStripe(env, typeof session.customer === "string" ? session.customer : session.customer?.id, order.customer_id);
  if (!customer || customer.id !== order.customer_id) return { ignored: "klant komt niet overeen" };
  const now = nowIso();
  if (session.status === "expired") {
    await env.DB.prepare("UPDATE shop_orders SET status = 'expired', updated_at = ? WHERE id = ? AND status IN ('pending', 'processing')").bind(now, order.id).run();
    return { order: order.id, status: "expired" };
  }
  if (session.status !== "complete") return { order: order.id, status: order.status };
  const paymentIntent = typeof session.payment_intent === "string" ? session.payment_intent : session.payment_intent?.id || null;
  const invoice = typeof session.invoice === "string" ? session.invoice : session.invoice?.id || null;
  const subscription = typeof session.subscription === "string" ? session.subscription : session.subscription?.id || null;
  const paid = session.payment_status === "paid" || session.payment_status === "no_payment_required";
  const next = paid ? "paid" : "processing";
  await env.DB.prepare("UPDATE shop_orders SET status = CASE WHEN status IN ('pending', 'processing', 'failed') THEN ? ELSE status END, amount_total = COALESCE(?, amount_total), stripe_payment_intent_id = COALESCE(?, stripe_payment_intent_id), stripe_invoice_id = COALESCE(?, stripe_invoice_id), stripe_subscription_id = COALESCE(?, stripe_subscription_id), livemode = ?, paid_at = CASE WHEN ? = 'paid' THEN COALESCE(paid_at, ?) ELSE paid_at END, updated_at = ? WHERE id = ?")
    .bind(next, session.amount_total ?? null, paymentIntent, invoice, subscription, session.livemode ? 1 : 0, next, now, now, order.id).run();
  if (order.status !== next && ["pending", "processing", "failed"].includes(order.status)) await audit(env, { customer_id: order.customer_id, entity_type: "order", entity_id: order.id, action: `order.${next}`, actor_type: "stripe", actor_name: "Stripe", details: { order: order.order_number, payment_status: session.payment_status } });
  if (session.mode === "subscription" && subscription) await syncSubscription(env, subscription);
  else if (paid) await grantOrderEntitlement(env, order.id);
  if (invoice) await syncInvoice(env, invoice);
  return { order: order.id, status: next };
}

export async function markCheckoutFailed(env, sessionId) {
  const session = await stripeRequest(env, "GET", `/v1/checkout/sessions/${encodeURIComponent(sessionId)}`);
  const orderId = session.metadata?.order_id || session.client_reference_id;
  if (!orderId || session.payment_status === "paid") return;
  const result = await env.DB.prepare("UPDATE shop_orders SET status = 'failed', updated_at = ? WHERE id = ? AND stripe_checkout_session_id = ? AND status IN ('pending', 'processing')").bind(nowIso(), orderId, session.id).run();
  if (result.meta?.changes) {
    const order = await env.DB.prepare("SELECT customer_id, order_number FROM shop_orders WHERE id = ?").bind(orderId).first();
    await audit(env, { customer_id: order.customer_id, entity_type: "order", entity_id: orderId, action: "order.failed", actor_type: "stripe", actor_name: "Stripe", details: { order: order.order_number } });
  }
}

export async function syncInvoice(env, invoiceId) {
  const inv = await stripeRequest(env, "GET", `/v1/invoices/${encodeURIComponent(invoiceId)}`);
  const customer = await customerForStripe(env, typeof inv.customer === "string" ? inv.customer : inv.customer?.id, inv.metadata?.customer_id);
  if (!customer) return { ignored: "onbekende klant" };
  const subscription = (typeof inv.subscription === "string" ? inv.subscription : inv.subscription?.id) || inv.parent?.subscription_details?.subscription || null;
  const orderId = inv.metadata?.order_id || null;
  const order = orderId ? await env.DB.prepare("SELECT id FROM shop_orders WHERE id = ? AND customer_id = ?").bind(orderId, customer.id).first()
    : await env.DB.prepare("SELECT id FROM shop_orders WHERE stripe_invoice_id = ? AND customer_id = ?").bind(inv.id, customer.id).first();
  const line = inv.lines?.data?.[0]?.period || {};
  await env.DB.prepare(`INSERT INTO billing_invoices (id, customer_id, stripe_invoice_id, stripe_subscription_id, order_id, number, status, currency, amount_due, amount_paid, hosted_invoice_url, invoice_pdf, period_start, period_end, stripe_created, livemode, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(stripe_invoice_id) DO UPDATE SET status = excluded.status, number = COALESCE(excluded.number, billing_invoices.number), amount_due = excluded.amount_due, amount_paid = excluded.amount_paid,
      hosted_invoice_url = COALESCE(excluded.hosted_invoice_url, billing_invoices.hosted_invoice_url), invoice_pdf = COALESCE(excluded.invoice_pdf, billing_invoices.invoice_pdf), order_id = COALESCE(billing_invoices.order_id, excluded.order_id), updated_at = excluded.updated_at`)
    .bind(crypto.randomUUID(), customer.id, inv.id, subscription, order?.id || null, inv.number || null, inv.status || "draft", inv.currency || "", inv.amount_due || 0, inv.amount_paid || 0, inv.hosted_invoice_url || null, inv.invoice_pdf || null, iso(line.start), iso(line.end), inv.created || Math.floor(Date.now() / 1000), inv.livemode ? 1 : 0, nowIso()).run();
  if (subscription) await syncSubscription(env, subscription);
  return { invoice: inv.id };
}

// Volledige terugbetaling van een eenmalige aankoop trekt het recht in; een gedeeltelijke laat het recht staan.
// Een terugbetaling op een abonnementsfactuur verandert de toegang niet: die volgt de abonnementsstatus.
export async function syncCharge(env, chargeId) {
  const charge = await stripeRequest(env, "GET", `/v1/charges/${encodeURIComponent(chargeId)}`);
  const paymentIntent = typeof charge.payment_intent === "string" ? charge.payment_intent : charge.payment_intent?.id;
  const order = paymentIntent ? await env.DB.prepare("SELECT * FROM shop_orders WHERE stripe_payment_intent_id = ?").bind(paymentIntent).first() : null;
  const customer = await customerForStripe(env, typeof charge.customer === "string" ? charge.customer : charge.customer?.id, order?.customer_id);
  if (!order || !customer || customer.id !== order.customer_id) {
    if (customer) await audit(env, { customer_id: customer.id, entity_type: "charge", entity_id: charge.id, action: "refund.subscription_invoice", actor_type: "stripe", actor_name: "Stripe", details: { amount_refunded: charge.amount_refunded, currency: charge.currency } });
    return { ignored: "geen eenmalige bestelling" };
  }
  const status = charge.refunded ? "refunded" : charge.amount_refunded > 0 ? "partially_refunded" : order.status;
  await env.DB.prepare("UPDATE shop_orders SET status = ?, amount_refunded = ?, updated_at = ? WHERE id = ? AND status IN ('paid', 'partially_refunded', 'refunded')").bind(status, charge.amount_refunded || 0, nowIso(), order.id).run();
  if (status !== order.status) {
    await audit(env, { customer_id: order.customer_id, entity_type: "order", entity_id: order.id, action: `order.${status}`, actor_type: "stripe", actor_name: "Stripe", details: { order: order.order_number, amount_refunded: charge.amount_refunded } });
    await grantOrderEntitlement(env, order.id);
  }
  return { order: order.id, status };
}

const SUBSCRIPTION_EVENTS = new Set(["customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted", "customer.subscription.paused", "customer.subscription.resumed", "customer.subscription.pending_update_applied", "customer.subscription.pending_update_expired", "customer.subscription.trial_will_end"]);
const INVOICE_EVENTS = new Set(["invoice.paid", "invoice.payment_succeeded", "invoice.payment_failed", "invoice.finalized", "invoice.updated", "invoice.voided", "invoice.marked_uncollectible", "invoice.payment_action_required"]);

async function processEvent(env, event) {
  const object = event.data?.object || {};
  if (event.type === "checkout.session.completed" || event.type === "checkout.session.async_payment_succeeded" || event.type === "checkout.session.expired") return await syncCheckoutSession(env, object.id);
  if (event.type === "checkout.session.async_payment_failed") return await markCheckoutFailed(env, object.id);
  if (SUBSCRIPTION_EVENTS.has(event.type)) return await syncSubscription(env, object.id);
  if (event.type.startsWith("subscription_schedule.")) { const sub = typeof object.subscription === "string" ? object.subscription : object.subscription?.id; return sub ? await syncSubscription(env, sub) : { ignored: "geen abonnement" }; }
  if (INVOICE_EVENTS.has(event.type)) return await syncInvoice(env, object.id);
  if (event.type === "charge.refunded") return await syncCharge(env, object.id);
  if (event.type === "refund.created" || event.type === "refund.updated") { const charge = typeof object.charge === "string" ? object.charge : object.charge?.id; return charge ? await syncCharge(env, charge) : { ignored: "geen betaling" }; }
  if (event.type === "charge.dispute.created") {
    // Een betwisting trekt niet automatisch toegang in; dat is een keuze voor een medewerker.
    const charge = await stripeRequest(env, "GET", `/v1/charges/${encodeURIComponent(typeof object.charge === "string" ? object.charge : object.charge?.id)}`);
    const customer = await customerForStripe(env, typeof charge.customer === "string" ? charge.customer : charge.customer?.id, null);
    if (!customer) return { ignored: "onbekende klant" };
    await audit(env, { customer_id: customer.id, entity_type: "charge", entity_id: charge.id, action: "dispute.created", actor_type: "stripe", actor_name: "Stripe", details: { amount: object.amount, reason: object.reason } });
    return { dispute: object.id };
  }
  return { ignored: "niet gebruikt" };
}

export async function handleStripeWebhook(request, env) {
  const respond = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  if (!env.STRIPE_WEBHOOK_SECRET) return respond({ error: "Webhook niet geconfigureerd." }, 503);
  const length = Number(request.headers.get("Content-Length") || 0);
  if (length > 1024 * 1024) return respond({ error: "Te groot." }, 413);
  const payload = await request.text();
  const verified = await verifyStripeSignature(payload, request.headers.get("Stripe-Signature"), env.STRIPE_WEBHOOK_SECRET);
  if (!verified.ok) return respond({ error: "Ongeldige handtekening." }, 400);
  let event;
  try { event = JSON.parse(payload); } catch { return respond({ error: "Ongeldige inhoud." }, 400); }
  if (!/^evt_[A-Za-z0-9_]+$/.test(String(event.id || ""))) return respond({ error: "Ongeldige melding." }, 400);
  const config = stripeConfig(env);
  // Meldingen uit een andere modus dan de ingestelde sleutel worden genegeerd: testbetalingen geven nooit live-toegang en omgekeerd.
  const modeMismatch = (event.livemode && config.mode !== "live") || (!event.livemode && config.mode !== "test");
  const now = nowIso();
  await env.DB.prepare("INSERT OR IGNORE INTO stripe_events (id, type, stripe_created, object_id, livemode, received_at, status) VALUES (?, ?, ?, ?, ?, ?, 'received')").bind(event.id, String(event.type || ""), Number(event.created || 0), event.data?.object?.id || null, event.livemode ? 1 : 0, now).run();
  const stored = await env.DB.prepare("SELECT status FROM stripe_events WHERE id = ?").bind(event.id).first();
  if (stored.status === "processed" || stored.status === "ignored") return respond({ received: true, duplicate: true });
  if (modeMismatch) {
    await env.DB.prepare("UPDATE stripe_events SET status = 'ignored', processed_at = ?, error = 'modus komt niet overeen' WHERE id = ?").bind(now, event.id).run();
    return respond({ received: true, ignored: true });
  }
  try {
    const result = await processEvent(env, event);
    const ignored = result && result.ignored;
    await env.DB.prepare("UPDATE stripe_events SET status = ?, processed_at = ?, error = ? WHERE id = ?").bind(ignored ? "ignored" : "processed", nowIso(), ignored || null, event.id).run();
    return respond({ received: true });
  } catch (error) {
    const message = String(error?.message || error).slice(0, 300);
    await env.DB.prepare("UPDATE stripe_events SET status = 'failed', error = ? WHERE id = ?").bind(message, event.id).run();
    console.error(JSON.stringify({ event: "stripe_webhook_failed", type: event.type, id: event.id, message }));
    // Een 5xx laat Stripe het later opnieuw proberen; de verwerking is idempotent.
    return respond({ error: "Verwerking mislukt; Stripe probeert het opnieuw." }, 500);
  }
}
