const WEBSITE_ORIGIN = "https://cohentra.digital";
const CUSTOMER_ID = "cohentra-website-intake";
const REQUEST_TYPES = {
  maatwerksoftware: "Software op maat",
  procesautomatisering: "Procesautomatisering",
  website: "Website op maat",
  overig: "Verkennend gesprek",
};
const MAX_BODY_BYTES = 8192;

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": WEBSITE_ORIGIN,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "600",
    "Vary": "Origin",
  };
}

function json(data, status = 200, withCors = true) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      ...(withCors ? corsHeaders() : {}),
    },
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function htmlMessage(message, status = 200) {
  const safeMessage = escapeHtml(message);
  return new Response(`<!doctype html><html lang="nl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#080914"><title>Contact · Cohentra Digital</title><body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#080914;color:#f5f6ff;font:16px/1.7 system-ui,sans-serif"><main style="max-width:560px;padding:40px 28px;text-align:center"><p style="color:#62d9ef;font-size:12px;letter-spacing:.15em;text-transform:uppercase">Cohentra Digital</p><h1 style="font-size:clamp(32px,7vw,54px);line-height:1.08">${safeMessage}</h1><a style="display:inline-block;margin-top:18px;padding:12px 19px;border-radius:99px;background:linear-gradient(112deg,#9236ef,#455fff 65%,#22bfdf);color:white;text-decoration:none;font-weight:700" href="https://cohentra.digital/#contact">Terug naar Cohentra</a></main></body></html>`, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
    },
  });
}

async function readBody(request) {
  const declaredLength = Number(request.headers.get("Content-Length") || 0);
  if (declaredLength > MAX_BODY_BYTES) throw new Error("large");
  const reader = request.body?.getReader();
  if (!reader) return {};
  const chunks = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > MAX_BODY_BYTES) {
        try { await reader.cancel(); } catch {}
        throw new Error("large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  const raw = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  const contentType = (request.headers.get("Content-Type") || "").split(";", 1)[0].trim().toLowerCase();
  if (contentType === "application/json") return JSON.parse(raw);
  if (contentType === "application/x-www-form-urlencoded") return Object.fromEntries(new URLSearchParams(raw));
  throw new Error("format");
}

function normalize(value, maxLength) {
  return String(value || "").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

function randomHex(byteCount = 6) {
  return [...crypto.getRandomValues(new Uint8Array(byteCount))]
    .map((byte) => byte.toString(16).padStart(2, "0")).join("").toUpperCase();
}

async function hashIp(value) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function handleContact(request, env) {
  const origin = request.headers.get("Origin") || "";
  const contentType = (request.headers.get("Content-Type") || "").split(";", 1)[0].trim().toLowerCase();
  const isJson = contentType === "application/json";
  const respond = (data, status = 200) => {
    if (isJson) return json(data, status);
    const message = data.error || `Bedankt. Je aanvraag ${data.reference} staat als Websiteformulier-ticket bij Cohentra Support.`;
    return htmlMessage(message, status);
  };

  if (request.method === "OPTIONS") {
    const requestedHeaders = (request.headers.get("Access-Control-Request-Headers") || "")
      .split(",").map((value) => value.trim().toLowerCase()).filter(Boolean);
    if (origin !== WEBSITE_ORIGIN
      || request.headers.get("Access-Control-Request-Method") !== "POST"
      || requestedHeaders.some((header) => header !== "content-type")) {
      return new Response(null, { status: 403, headers: { "Cache-Control": "no-store" } });
    }
    return new Response(null, { status: 204, headers: corsHeaders() });
  }
  if (request.method !== "POST") return json({ error: "Niet gevonden." }, 404, false);
  if (origin !== WEBSITE_ORIGIN) return respond({ error: "Deze aanvraag is niet toegestaan." }, 403);

  let body;
  try {
    body = await readBody(request);
  } catch (error) {
    const tooLarge = error?.message === "large";
    return respond({ error: tooLarge ? "Je bericht is te groot." : "Vul het formulier opnieuw in en probeer het nog eens." }, tooLarge ? 413 : 400);
  }
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return respond({ error: "Vul het formulier opnieuw in en probeer het nog eens." }, 400);
  }

  // Silently accept filled honeypots so automated spam does not reach the ticket queue.
  if (normalize(body.company_site, 200)) {
    return respond({ ok: true, reference: `CH-${new Date().getUTCFullYear()}-${randomHex(6)}` }, 201);
  }

  const name = normalize(body.name, 120);
  const email = normalize(body.email, 254).toLowerCase();
  const organization = normalize(body.organization, 160);
  const requestType = normalize(body.request_type, 40);
  const subject = normalize(body.subject, 120);
  const message = String(body.message || "").replace(/\r\n?/g, "\n").trim();
  if (!name || !/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/.test(email)
    || !REQUEST_TYPES[requestType] || !subject || !message || message.length > 5000) {
    return respond({ error: "Controleer je naam, e-mailadres, onderwerp en bericht." }, 400);
  }

  const currentHour = Math.floor(Date.now() / 3_600_000);
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";
  const ipHash = await hashIp(`${currentHour}:${ip}`);
  await env.DB.batch([
    env.DB.prepare("DELETE FROM website_contact_rate_limits WHERE window_started_at < ?").bind(currentHour - 24),
    env.DB.prepare("INSERT INTO website_contact_rate_limits (ip_hash, window_started_at, request_count) VALUES (?, ?, 1) ON CONFLICT(ip_hash, window_started_at) DO UPDATE SET request_count = request_count + 1").bind(ipHash, currentHour),
  ]);
  const limit = await env.DB.prepare("SELECT request_count FROM website_contact_rate_limits WHERE ip_hash = ? AND window_started_at = ?")
    .bind(ipHash, currentHour).first();
  if (Number(limit?.request_count || 0) > 5) {
    return respond({ error: "Je hebt veel aanvragen kort na elkaar verstuurd. Probeer het later opnieuw." }, 429);
  }

  const now = new Date().toISOString();
  const id = crypto.randomUUID();
  const reference = `CH-${new Date(now).getUTCFullYear()}-${randomHex(6)}`;
  const displayType = REQUEST_TYPES[requestType];
  const ticketSubject = `Websiteformulier · ${displayType} — ${subject}`;
  const ticketMessage = [
    "Bron: Websiteformulier",
    `Type aanvraag: ${displayType}`,
    `Naam: ${name}`,
    `E-mailadres: ${email}`,
    `Bedrijf of organisatie: ${organization || "Niet opgegeven"}`,
    "",
    "Bericht:",
    message,
  ].join("\n");

  await env.DB.batch([
    env.DB.prepare("INSERT OR IGNORE INTO customers (id, name, contact_name, contact_email, notes, status, created_at, updated_at) VALUES (?, 'Websiteformulier', '', '', 'Gegroepeerde inbox voor aanvragen van cohentra.digital.', 'paused', ?, ?)")
      .bind(CUSTOMER_ID, now, now),
    env.DB.prepare("INSERT INTO support_tickets (id, reference, customer_id, created_by_account_id, category, subject, message, status, assigned_to, created_at, updated_at, source, contact_name, contact_email, organization, request_type) VALUES (?, ?, ?, NULL, 'other', ?, ?, 'new', NULL, ?, ?, 'website', ?, ?, ?, ?)")
      .bind(id, reference, CUSTOMER_ID, ticketSubject, ticketMessage, now, now, name, email, organization, requestType),
  ]);

  return respond({ ok: true, reference, source: "website" }, 201);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      try {
        await env.DB.prepare("SELECT 1 AS ok").first();
        return json({ status: "ok" }, 200, false);
      } catch {
        return json({ status: "unavailable" }, 503, false);
      }
    }
    if (url.pathname === "/api/public/contact") return handleContact(request, env);
    return json({ error: "Niet gevonden." }, 404, false);
  },
};
