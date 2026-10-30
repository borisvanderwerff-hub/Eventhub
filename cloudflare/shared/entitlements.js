// Centraal rechtensysteem: bepaalt per klant en product wat gebruikt en gedownload mag worden.
// Bronnen (Stripe-abonnement, eenmalige bestelling, handmatige toekenning) leveren een basisrecht;
// handmatige uitzonderingen van medewerkers liggen daar los bovenop en worden nooit door webhooks overschreven.

// Verlengingen komen via een webhook binnen; zonder deze marge zou een vertraagde melding een klant kort buitensluiten.
export const RENEWAL_TOLERANCE_MS = 48 * 60 * 60 * 1000;

export const SUBSCRIPTION_STATUS_LABELS = {
  pending: "Wacht op eerste betaling", trialing: "Proefperiode", active: "Actief", past_due: "Betaling mislukt",
  suspended: "Opgeschort (onbetaald)", paused: "Gepauzeerd", canceled: "Beëindigd", expired: "Verlopen"
};
export const ENTITLEMENT_STATUS_LABELS = {
  pending: "Wacht op betaling", active: "Actief", grace: "Hersteltermijn", suspended: "Opgeschort", expired: "Verlopen", revoked: "Ingetrokken"
};

// Vertaalt de Stripe-abonnementsstatus naar de interne status.
export function mapStripeSubscriptionStatus(stripeStatus) {
  return ({
    trialing: "trialing", active: "active", past_due: "past_due", unpaid: "suspended", paused: "paused",
    incomplete: "pending", incomplete_expired: "expired", canceled: "canceled"
  })[stripeStatus] || "pending";
}

// Basisstatus van het recht op grond van een abonnement.
// graceDays: optionele maximale hersteltermijn na een mislukte betaling; zonder waarde volgt de toegang Stripe's eigen herhaalpogingen.
export function entitlementStatusForSubscription(sub, now = Date.now(), graceDays = null) {
  switch (sub.status) {
    case "trialing": case "active": return { status: "active", reason: sub.cancel_at_period_end ? "Opgezegd; loopt tot het einde van de periode" : "" };
    case "past_due": {
      const since = Date.parse(sub.past_due_since || "");
      if (graceDays !== null && Number.isFinite(since) && now > since + graceDays * 864e5) return { status: "suspended", reason: "Hersteltermijn na mislukte betaling verstreken" };
      return { status: "grace", reason: "Betaling mislukt; hersteltermijn loopt" };
    }
    case "suspended": return { status: "suspended", reason: "Factuur onbetaald" };
    case "paused": return { status: "suspended", reason: "Abonnement gepauzeerd" };
    case "pending": return { status: "pending", reason: "Eerste betaling nog niet bevestigd" };
    case "canceled": return { status: "expired", reason: "Abonnement beëindigd" };
    default: return { status: "expired", reason: "Abonnement verlopen" };
  }
}

export function entitlementStatusForOrder(order) {
  if (order.status === "paid" || order.status === "partially_refunded") return { status: "active", reason: order.status === "partially_refunded" ? "Gedeeltelijk terugbetaald" : "" };
  if (order.status === "refunded") return { status: "revoked", reason: "Terugbetaald" };
  return { status: "pending", reason: "Betaling nog niet bevestigd" };
}

function parseJson(value, fallback) {
  try { const parsed = JSON.parse(value); return parsed ?? fallback; } catch { return fallback; }
}

export function overrideIsActive(override, now = Date.now()) {
  if (override.revoked_at) return false;
  if (override.expires_at && Date.parse(override.expires_at) <= now) return false;
  return true;
}

// Berekent het effectieve recht. Volgorde: basisrecht → tijdscontrole → uitzonderingen (opschorten gaat altijd voor).
// Downloaden en gebruiken zijn aparte rechten: tijdens een hersteltermijn blijft gebruik toegestaan, nieuwe downloads niet.
export function effectiveEntitlement(row, overrides = [], now = Date.now()) {
  let status = row.status, reason = row.status_reason || "";
  let validUntil = row.valid_until || null;
  let features = parseJson(row.features_json, {});
  let maxUsers = row.max_users ?? null, maxActivations = row.max_activations ?? null;
  const applied = [];
  if (Date.parse(row.valid_from) > now) { status = "pending"; reason = "Nog niet ingegaan"; }
  if ((status === "active" || status === "grace") && validUntil) {
    const tolerance = row.source === "subscription" ? RENEWAL_TOLERANCE_MS : 0;
    if (Date.parse(validUntil) + tolerance < now) { status = "expired"; reason = "Geldigheid verlopen"; }
  }
  const active = overrides.filter((o) => overrideIsActive(o, now)).sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
  for (const o of active) {
    const value = parseJson(o.value_json, {});
    if (o.kind === "features") {
      features = { ...features, ...(value.set && typeof value.set === "object" ? value.set : {}) };
      for (const key of Array.isArray(value.remove) ? value.remove : []) delete features[key];
      applied.push(o.id);
    } else if (o.kind === "limits") {
      if (value.max_users !== undefined) maxUsers = value.max_users;
      if (value.max_activations !== undefined) maxActivations = value.max_activations;
      applied.push(o.id);
    } else if (o.kind === "extend" && value.until) {
      const until = Date.parse(value.until);
      if (Number.isFinite(until) && until > now) {
        if (status !== "active" && status !== "grace") { status = "active"; reason = "Handmatig verlengd door Cohentra"; }
        if (!validUntil || Date.parse(validUntil) < until) validUntil = new Date(until).toISOString();
        applied.push(o.id);
      }
    }
  }
  const suspension = active.find((o) => o.kind === "suspend");
  if (suspension) { status = "suspended"; reason = "Toegang door Cohentra opgeschort"; applied.push(suspension.id); }
  return {
    id: row.id, customer_id: row.customer_id, product_id: row.product_id, plan_id: row.plan_id, plan_name: row.plan_name,
    source: row.source, source_id: row.source_id, base_status: row.status, status, reason,
    use_allowed: status === "active" || status === "grace",
    download_allowed: status === "active",
    features, max_users: maxUsers, max_activations: maxActivations,
    valid_from: row.valid_from, valid_until: validUntil, overrides_applied: applied
  };
}

export async function loadOverrides(env, entitlementIds) {
  if (!entitlementIds.length) return new Map();
  const { results } = await env.DB.prepare(`SELECT * FROM entitlement_overrides WHERE entitlement_id IN (${entitlementIds.map(() => "?").join(",")}) ORDER BY created_at`).bind(...entitlementIds).all();
  const map = new Map();
  for (const o of results) { if (!map.has(o.entitlement_id)) map.set(o.entitlement_id, []); map.get(o.entitlement_id).push(o); }
  return map;
}

export async function loadEffectiveEntitlements(env, customerId, now = Date.now()) {
  const { results } = await env.DB.prepare("SELECT e.*, p.name AS product_name FROM entitlements e JOIN products p ON p.id = e.product_id WHERE e.customer_id = ? ORDER BY e.created_at DESC").bind(customerId).all();
  const overrides = await loadOverrides(env, results.map((r) => r.id));
  return results.map((row) => ({ ...effectiveEntitlement(row, overrides.get(row.id) || [], now), product_name: row.product_name, created_at: row.created_at }));
}

export async function loadEffectiveEntitlement(env, entitlementId, now = Date.now()) {
  const row = await env.DB.prepare("SELECT * FROM entitlements WHERE id = ?").bind(entitlementId).first();
  if (!row) return null;
  const overrides = await loadOverrides(env, [row.id]);
  return effectiveEntitlement(row, overrides.get(row.id) || [], now);
}

// Maximaal aantal portaalgebruikers voor een organisatie: het ruimste actieve recht telt; null betekent geen limiet ingesteld.
export function userLimit(effectiveList) {
  const usable = effectiveList.filter((e) => e.use_allowed);
  if (!usable.length) return 1;
  if (usable.some((e) => e.max_users === null || e.max_users === undefined)) return null;
  return Math.max(1, ...usable.map((e) => Number(e.max_users)));
}

export async function audit(env, entry) {
  await env.DB.prepare("INSERT INTO commerce_audit_log (id, customer_id, entity_type, entity_id, action, actor_type, actor_name, reason, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
    .bind(crypto.randomUUID(), entry.customer_id || null, entry.entity_type, entry.entity_id || null, entry.action, entry.actor_type, entry.actor_name || "", entry.reason || "", JSON.stringify(entry.details || {}), new Date().toISOString()).run();
}

export function planSnapshot(plan, price) {
  return {
    plan_id: plan.id, code: plan.code, name: plan.name, billing_type: plan.billing_type,
    features: parseJson(plan.features_json, {}), max_users: plan.max_users ?? null, max_activations: plan.max_activations ?? null,
    price: price ? { id: price.id, currency: price.currency, unit_amount: price.unit_amount, interval: price.billing_interval, interval_count: price.interval_count, tax_behavior: price.tax_behavior } : null
  };
}

// Werkt het basisrecht van een bron bij. Functies en limieten worden vastgelegd bij (wijziging naar) een plan;
// latere aanpassingen aan het plan veranderen bestaande rechten dus niet ongemerkt.
export async function upsertSourceEntitlement(env, { customerId, productId, plan, source, sourceId, status, reason, validFrom, validUntil, snapshotChanged }) {
  const now = new Date().toISOString();
  const existing = await env.DB.prepare("SELECT * FROM entitlements WHERE source = ? AND source_id = ?").bind(source, sourceId).first();
  const features = JSON.stringify(parseJson(plan.features_json, {}));
  if (!existing) {
    const id = crypto.randomUUID();
    await env.DB.prepare("INSERT INTO entitlements (id, customer_id, product_id, plan_id, source, source_id, status, status_reason, plan_name, features_json, max_users, max_activations, valid_from, valid_until, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'stripe', ?, ?) ON CONFLICT(source, source_id) DO NOTHING")
      .bind(id, customerId, productId, plan.id, source, sourceId, status, reason || "", plan.name, features, plan.max_users ?? null, plan.max_activations ?? null, validFrom, validUntil, now, now).run();
    const row = await env.DB.prepare("SELECT * FROM entitlements WHERE source = ? AND source_id = ?").bind(source, sourceId).first();
    return { row, previous: null };
  }
  const planChanged = existing.plan_id !== plan.id || snapshotChanged;
  await env.DB.prepare("UPDATE entitlements SET status = ?, status_reason = ?, valid_until = ?, plan_id = ?, plan_name = CASE WHEN ? THEN ? ELSE plan_name END, features_json = CASE WHEN ? THEN ? ELSE features_json END, max_users = CASE WHEN ? THEN ? ELSE max_users END, max_activations = CASE WHEN ? THEN ? ELSE max_activations END, updated_at = ? WHERE id = ?")
    .bind(status, reason || "", validUntil, plan.id, planChanged ? 1 : 0, plan.name, planChanged ? 1 : 0, features, planChanged ? 1 : 0, plan.max_users ?? null, planChanged ? 1 : 0, plan.max_activations ?? null, now, existing.id).run();
  const row = await env.DB.prepare("SELECT * FROM entitlements WHERE id = ?").bind(existing.id).first();
  return { row, previous: existing };
}
