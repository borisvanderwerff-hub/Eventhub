// Stripe via de REST-API met fetch: geen SDK of extra afhankelijkheid nodig in de Worker.
// Geheime sleutels komen uitsluitend uit Worker Secrets (env) en verlaten de server nooit.

const STRIPE_API = "https://api.stripe.com";

// Leest de configuratie en weigert live-sleutels zolang live betalen niet expliciet is aangezet.
export function stripeConfig(env) {
  const key = String(env.STRIPE_SECRET_KEY || "");
  const liveAllowed = String(env.STRIPE_ALLOW_LIVE || "") === "true";
  const problems = [];
  let mode = null;
  if (!key) problems.push("STRIPE_SECRET_KEY ontbreekt.");
  else if (/^(sk|rk)_test_/.test(key)) mode = "test";
  else if (/^(sk|rk)_live_/.test(key)) {
    mode = "live";
    if (!liveAllowed) problems.push("Er is een live-sleutel ingesteld, maar STRIPE_ALLOW_LIVE staat niet op true. Live betalingen blijven uit.");
  } else problems.push("STRIPE_SECRET_KEY heeft geen herkenbaar formaat (sk_test_… of sk_live_…).");
  if (!env.STRIPE_WEBHOOK_SECRET) problems.push("STRIPE_WEBHOOK_SECRET ontbreekt; betalingen kunnen dan niet worden bevestigd.");
  const checkoutReady = !!mode && !(mode === "live" && !liveAllowed) && !!env.STRIPE_WEBHOOK_SECRET;
  return {
    mode,
    live_allowed: liveAllowed,
    checkout_ready: checkoutReady && String(env.SHOP_CHECKOUT_ENABLED || "") === "true",
    checkout_switch: String(env.SHOP_CHECKOUT_ENABLED || "") === "true",
    webhook_secret_set: !!env.STRIPE_WEBHOOK_SECRET,
    portal_configuration: env.STRIPE_PORTAL_CONFIGURATION_ID ? "ingesteld" : "Stripe-standaard",
    automatic_tax: String(env.STRIPE_AUTOMATIC_TAX || "") === "true",
    require_terms: String(env.STRIPE_REQUIRE_TERMS || "") === "true",
    problems
  };
}

export class StripeError extends Error {
  constructor(message, status, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

// Zet geneste objecten om naar Stripe-formaat: a[b][0][c]=waarde.
export function formEncode(params, prefix = "", out = []) {
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null) continue;
    const name = prefix ? `${prefix}[${key}]` : key;
    if (Array.isArray(value)) value.forEach((item, index) => {
      if (item !== null && typeof item === "object") formEncode(item, `${name}[${index}]`, out);
      else out.push(`${encodeURIComponent(`${name}[${index}]`)}=${encodeURIComponent(String(item))}`);
    });
    else if (typeof value === "object") formEncode(value, name, out);
    else out.push(`${encodeURIComponent(name)}=${encodeURIComponent(String(value))}`);
  }
  return out.join("&");
}

export async function stripeRequest(env, method, path, params = null, options = {}) {
  const config = stripeConfig(env);
  if (!config.mode || (config.mode === "live" && !config.live_allowed)) throw new StripeError("Stripe is niet (veilig) geconfigureerd.", 503, null);
  const headers = { "Authorization": `Bearer ${env.STRIPE_SECRET_KEY}` };
  if (env.STRIPE_API_VERSION) headers["Stripe-Version"] = env.STRIPE_API_VERSION;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
  let url = STRIPE_API + path, body;
  const encoded = params ? formEncode(params) : "";
  if (method === "GET") { if (encoded) url += "?" + encoded; }
  else { body = encoded; headers["Content-Type"] = "application/x-www-form-urlencoded"; }
  const response = await fetch(url, { method, headers, body });
  let data = null;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) {
    const message = data?.error?.message || `Stripe gaf status ${response.status}.`;
    throw new StripeError(message, response.status, data);
  }
  return data;
}

function hexToBytes(hex) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  return bytes;
}

// Controleert de Stripe-Signature-header (HMAC-SHA256 over "t.payload") met een maximale leeftijd tegen replay.
// Meerdere geheimen (komma-gescheiden) maken rotatie van het webhookgeheim mogelijk.
export async function verifyStripeSignature(payload, header, secrets, toleranceSeconds = 300, nowSeconds = Math.floor(Date.now() / 1000)) {
  const parts = String(header || "").split(",").map((part) => part.trim().split("="));
  const timestamp = Number(parts.find(([k]) => k === "t")?.[1]);
  const signatures = parts.filter(([k, v]) => k === "v1" && /^[0-9a-f]{64}$/i.test(v || "")).map(([, v]) => v.toLowerCase());
  if (!Number.isInteger(timestamp) || !signatures.length) return { ok: false, reason: "header" };
  if (Math.abs(nowSeconds - timestamp) > toleranceSeconds) return { ok: false, reason: "timestamp" };
  const data = new TextEncoder().encode(`${timestamp}.${payload}`);
  for (const secret of String(secrets || "").split(",").map((s) => s.trim()).filter(Boolean)) {
    const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["verify"]);
    for (const signature of signatures) {
      // crypto.subtle.verify vergelijkt in constante tijd.
      if (await crypto.subtle.verify("HMAC", key, hexToBytes(signature), data)) return { ok: true, timestamp };
    }
  }
  return { ok: false, reason: "signature" };
}

export function stripeDashboardUrl(mode, kind, id) {
  if (!id) return "";
  return `https://dashboard.stripe.com/${mode === "live" ? "" : "test/"}${kind}/${encodeURIComponent(id)}`;
}
