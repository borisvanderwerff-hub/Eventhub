// Routering van de shop-worker, los van de Cloudflare-runtime zodat het ook lokaal te testen is.
// Publiek (shop-api.cohentra.digital): catalogus, productafbeeldingen, Stripe-webhook en tijdelijke downloadlinks.
// Geauthenticeerd: alleen via de service binding vanuit de licentie-worker, met een al gecontroleerde klant of medewerker.

import { handlePublicShop, handleShopMedia, handleDownload, handleCustomerShop } from "./customer-api.js";
import { handleAdminShop } from "./admin-api.js";
import { handleStripeWebhook } from "./billing.js";

const JSON_HEADERS = { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" };

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}

export async function digest(value) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function randomHex(bytes = 32) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function readJson(request, maxLength = 8192) {
  const length = Number(request.headers.get("Content-Length") || 0);
  if (length > maxLength) throw new Error("Aanvraag is te groot.");
  return await request.json();
}

async function readBoundedRequestBytes(request, maxBytes) {
  const reader = request.body?.getReader();
  if (!reader) return new Uint8Array();
  const chunks = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > maxBytes) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return bytes;
}

const helpers = { json, digest, randomHex, readJson, readBoundedRequestBytes };

export async function handlePublic(request, env) {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") return json({ status: "ok" });
  if (url.pathname === "/api/stripe/webhook" && request.method === "POST") return await handleStripeWebhook(request, env);
  if (url.pathname.startsWith("/api/public/shop/")) return await handlePublicShop(request, env, url);
  if (url.pathname.startsWith("/shop-media/") && request.method === "GET") return (await handleShopMedia(env, url)) || json({ error: "Niet gevonden." }, 404);
  if (url.pathname.startsWith("/download/")) return (await handleDownload(request, env, url, helpers)) || json({ error: "Niet gevonden." }, 404);
  return json({ error: "Niet gevonden." }, 404);
}

// identity: { account_id, customer_id, account_role, customer_type, username, account_name, account_email }
export async function handleCustomer(request, env, identity) {
  if (!identity?.customer_id || !identity?.account_id) return json({ error: "Niet aangemeld." }, 401);
  return (await handleCustomerShop(request, env, new URL(request.url), identity, helpers)) || json({ error: "Niet gevonden." }, 404);
}

// actor: { id, name, role, permissions }
export async function handleAdmin(request, env, actor) {
  if (!actor?.role) return json({ error: "Niet aangemeld." }, 401);
  return (await handleAdminShop(request, env, new URL(request.url), actor, helpers)) || json({ error: "Niet gevonden." }, 404);
}

export async function safely(fn) {
  try { return await fn(); }
  catch (error) {
    console.error(JSON.stringify({ event: "shop_request_failed", message: String(error?.message || error).slice(0, 300) }));
    return json({ error: "Er is iets misgegaan. Probeer het later opnieuw." }, 500);
  }
}
