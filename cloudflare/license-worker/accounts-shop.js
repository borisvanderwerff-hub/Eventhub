// Accountuitbreidingen voor de shop in de licentie-worker (het accountsysteem):
// zelfregistratie met e-mailbevestiging, organisatiegebruikers en licentiesleutels bij een recht (entitlement).
// Betalen en abonnementen staan in de aparte worker cohentra-shop; deze worker bereikt die via een service binding.

import { loadEffectiveEntitlements, loadEffectiveEntitlement, userLimit, audit } from "../shared/entitlements.js";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const parse = (value, fallback) => { try { return JSON.parse(value) ?? fallback; } catch { return fallback; } };
const portalUrl = (env) => String(env.PUBLIC_CUSTOMER_URL || "https://customer.cohentra.digital").replace(/\/+$/, "");

async function nextCustomerNumber(env) {
  const last = await env.DB.prepare("SELECT MAX(CAST(substr(customer_number, 5) AS INTEGER)) AS n FROM customers WHERE customer_number LIKE 'CUS-%'").first();
  return "CUS-" + String(Number(last?.n || 0) + 1).padStart(4, "0");
}

async function sendRegistrationEmail(env, h, email, rawToken) {
  if (!env.EMAIL) throw new Error("De e-mailservice is niet beschikbaar.");
  const brand = await h.loadEmailTemplateSettings(env, "branding");
  const link = portalUrl(env) + "/?flow=verify&token=" + rawToken;
  const subject = "Bevestig je e-mailadres voor Cohentra";
  const intro = "Je hebt een account aangemaakt bij Cohentra Digital. Bevestig je e-mailadres om je account te activeren.";
  const html = h.renderAuthEmailHtml({ subject, intro, link, button: "E-mailadres bevestigen", expiryNote: "Deze link is 24 uur geldig en werkt één keer.", brand });
  await env.EMAIL.send({ to: email, from: { email: "noreply@noreply.cohentra.digital", name: "Cohentra Digital" }, replyTo: "info@cohentra.digital", subject, html,
    text: subject + "\n\n" + intro + "\n\nOpen deze link (24 uur geldig, eenmalig): " + link + "\n\nHeb je dit niet aangevraagd? Negeer deze e-mail.\n\nCohentra Digital · info@cohentra.digital" });
}

export async function handleCustomerAuthExtra(request, env, url, h) {
  if (request.method === "POST" && url.pathname === "/api/customer/auth/register") {
    let body; try { body = await h.readJson(request); } catch { return h.json({ error: "Ongeldige aanvraag." }, 400); }
    const type = body.customer_type === "business" ? "business" : body.customer_type === "individual" ? "individual" : "";
    const email = String(body.email || "").trim().toLowerCase(), name = String(body.name || "").trim().slice(0, 120);
    const company = String(body.company_name || "").trim().slice(0, 120), password = String(body.password || "");
    if (!type) return h.json({ error: "Kies of je als organisatie of als particulier/zelfstandige een account aanmaakt." }, 400);
    if (!name) return h.json({ error: "Vul je naam in." }, 400);
    if (type === "business" && !company) return h.json({ error: "Vul de naam van je organisatie in." }, 400);
    if (!EMAIL_PATTERN.test(email) || email.length > 254) return h.json({ error: "Vul een geldig e-mailadres in." }, 400);
    if (password.length < 10 || password.length > 512) return h.json({ error: "Gebruik een wachtwoord van minimaal 10 tekens." }, 400);
    const now = Date.now(), ipKey = await h.digest(request.headers.get("CF-Connecting-IP") || "unknown");
    const [emailAttempts, ipAttempts] = await Promise.all([h.recordCustomerAuthRequest(env, "register-email:" + await h.digest(email), now), h.recordCustomerAuthRequest(env, "register-ip:" + ipKey, now)]);
    if (emailAttempts > 5 || ipAttempts > 20) return h.json({ error: "Te veel verzoeken. Probeer het later opnieuw." }, 429);
    const generic = { message: "Controleer je inbox. We hebben een e-mail gestuurd om je e-mailadres te bevestigen." };
    const existing = await env.DB.prepare("SELECT id, active, disabled_at FROM customer_portal_accounts WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE LIMIT 1").bind(email, email).first();
    try {
      if (existing) {
        // Niet verklappen dat het account bestaat; de eigenaar krijgt een herstellink in plaats van een tweede account.
        if (!existing.disabled_at) await h.sendCustomerAuthEmail(env, existing.id, email, existing.active === 1 ? "password_reset" : "invite");
        return h.json(generic, 202);
      }
      const credentials = await h.hashPassword(password), rawToken = h.randomHex(32);
      await env.DB.batch([
        env.DB.prepare("UPDATE customer_registrations SET consumed_at = ? WHERE email = ? AND consumed_at IS NULL").bind(now, email),
        env.DB.prepare("INSERT INTO customer_registrations (token_hash, email, payload_json, created_at, expires_at) VALUES (?, ?, ?, ?, ?)").bind(await h.digest(rawToken), email, JSON.stringify({ type, name, company, salt: credentials.salt, hash: credentials.hash }), now, now + 24 * 3600 * 1000)
      ]);
      await sendRegistrationEmail(env, h, email, rawToken);
    } catch (error) {
      console.error("Registration email could not be sent", String(error?.message || error));
      return h.json({ error: "De bevestigingsmail kon niet worden verstuurd. Probeer het later opnieuw." }, 502);
    }
    return h.json(generic, 202);
  }
  if (request.method === "POST" && url.pathname === "/api/customer/auth/verify-email") {
    let body; try { body = await h.readJson(request); } catch { return h.json({ error: "Ongeldige aanvraag." }, 400); }
    const rawToken = String(body.token || "");
    if (!/^[a-f0-9]{64}$/.test(rawToken)) return h.json({ error: "Deze link is ongeldig." }, 400);
    const tokenHash = await h.digest(rawToken), now = Date.now();
    const claimed = await env.DB.prepare("UPDATE customer_registrations SET consumed_at = ? WHERE token_hash = ? AND consumed_at IS NULL AND expires_at > ?").bind(now, tokenHash, now).run();
    if (claimed.meta?.changes !== 1) return h.json({ error: "Deze link is verlopen of al gebruikt. Meld je aan of maak opnieuw een account aan." }, 400);
    const reg = await env.DB.prepare("SELECT email, payload_json FROM customer_registrations WHERE token_hash = ?").bind(tokenHash).first();
    const data = parse(reg.payload_json, {}), email = reg.email.toLowerCase(), timestamp = new Date(now).toISOString();
    const taken = await env.DB.prepare("SELECT id FROM customer_portal_accounts WHERE username = ? COLLATE NOCASE OR email = ? COLLATE NOCASE LIMIT 1").bind(email, email).first();
    if (taken) return h.json({ error: "Bij dit e-mailadres hoort al een account. Meld je aan of herstel je wachtwoord." }, 409);
    // Koppel alleen aan een bestaand klantrecord als het bevestigde e-mailadres precies het vastgelegde contactadres is
    // en die klant nog geen portaalgebruikers heeft. Een zelf ingevulde bedrijfsnaam is nooit genoeg.
    const { results: matches } = await env.DB.prepare("SELECT c.id FROM customers c WHERE c.contact_email = ? COLLATE NOCASE AND c.status = 'active' AND c.id <> 'cohentra-website-intake' AND NOT EXISTS (SELECT 1 FROM customer_portal_accounts a WHERE a.customer_id = c.id)").bind(email).all();
    let customerId, linked = false;
    if (matches.length === 1) { customerId = matches[0].id; linked = true; }
    else {
      customerId = crypto.randomUUID();
      const displayName = data.type === "business" ? data.company : data.name;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          await env.DB.prepare("INSERT INTO customers (id, customer_number, name, contact_name, contact_email, customer_type, source, notes, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'shop', '', 'active', ?, ?)").bind(customerId, await nextCustomerNumber(env), displayName, data.name, email, data.type, timestamp, timestamp).run();
          break;
        } catch (error) { if (attempt === 2 || !String(error?.message || error).toLowerCase().includes("unique")) throw error; }
      }
    }
    const accountId = crypto.randomUUID();
    await env.DB.prepare("INSERT INTO customer_portal_accounts (id, customer_id, username, name, email, password_salt, password_hash, active, role, email_verified_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'admin', ?, ?, ?)").bind(accountId, customerId, email, data.name, email, data.salt, data.hash, timestamp, timestamp, timestamp).run();
    await audit(env, { customer_id: customerId, entity_type: "account", entity_id: accountId, action: linked ? "account.linked_existing_customer" : "account.registered", actor_type: "customer", actor_name: email, details: { customer_type: data.type } });
    return h.json({ session_token: await h.issueCustomerSession(env, accountId), expires_in: 43200 });
  }
  return null;
}

function isAdmin(customer) { return customer.account_role === "admin"; }
function adminOnly(h) { return h.json({ error: "Alleen een beheerder van jullie account kan dit doen." }, 403); }

export async function handleCustomerAccountShop(request, env, url, customer, h) {
  const path = url.pathname;
  const entLicenseRoute = /^\/api\/customer\/entitlements\/([0-9a-f-]{36})\/licenses$/i.exec(path);
  if (entLicenseRoute && request.method === "POST") {
    if (!isAdmin(customer)) return adminOnly(h);
    let body; try { body = await h.readJson(request); } catch { return h.json({ error: "Ongeldige aanvraag." }, 400); }
    const ent = await loadEffectiveEntitlement(env, entLicenseRoute[1]);
    if (!ent || ent.customer_id !== customer.customer_id) return h.json({ error: "Product niet gevonden." }, 404);
    if (!ent.use_allowed) return h.json({ error: "Er is geen actief recht om een licentie voor dit product te maken." }, 403);
    const limit = ent.max_activations === null || ent.max_activations === undefined ? 1000000 : Number(ent.max_activations);
    const label = String(body.label || "").trim().slice(0, 80), key = h.createLicenseKey(), id = crypto.randomUUID(), createdAt = new Date().toISOString();
    const inserted = await env.DB.prepare("INSERT INTO licenses (id, key_hash, label, created_at, valid_from, valid_until, license_type, customer_id, product_id, entitlement_id) SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ? WHERE (SELECT COUNT(*) FROM licenses WHERE entitlement_id = ? AND revoked_at IS NULL) < ?")
      .bind(id, await h.digest(h.normalizedKey(key)), label, createdAt, createdAt.slice(0, 10), h.UNLIMITED_UNTIL, ent.plan_name || "Abonnement", customer.customer_id, ent.product_id, ent.id, ent.id, limit).run();
    if (inserted.meta?.changes !== 1) return h.json({ error: `Het maximale aantal activaties (${limit}) voor dit abonnement is bereikt. Trek eerst een licentie in.` }, 409);
    await audit(env, { customer_id: customer.customer_id, entity_type: "license", entity_id: id, action: "license.created", actor_type: "customer", actor_name: customer.username, details: { entitlement_id: ent.id, label } });
    return h.json({ license: { id, license_key: key } }, 201);
  }

  const shopLicenseRoute = /^\/api\/customer\/shop-licenses\/([0-9a-f-]{36})\/(revoke|reset)$/i.exec(path);
  if (shopLicenseRoute && request.method === "POST") {
    if (!isAdmin(customer)) return adminOnly(h);
    const now = new Date().toISOString();
    const result = shopLicenseRoute[2] === "revoke"
      ? await env.DB.prepare("UPDATE licenses SET revoked_at = ? WHERE id = ? AND customer_id = ? AND entitlement_id IS NOT NULL AND revoked_at IS NULL").bind(now, shopLicenseRoute[1], customer.customer_id).run()
      : await env.DB.prepare("UPDATE licenses SET activated_device_hash = NULL, activated_at = NULL WHERE id = ? AND customer_id = ? AND entitlement_id IS NOT NULL AND revoked_at IS NULL").bind(shopLicenseRoute[1], customer.customer_id).run();
    if (!result.meta?.changes) return h.json({ error: "Licentie niet gevonden." }, 404);
    await audit(env, { customer_id: customer.customer_id, entity_type: "license", entity_id: shopLicenseRoute[1], action: `license.${shopLicenseRoute[2]}`, actor_type: "customer", actor_name: customer.username });
    return h.json({ ok: true });
  }

  if (path === "/api/customer/team" && request.method === "GET") {
    if (!isAdmin(customer)) return adminOnly(h);
    const { results } = await env.DB.prepare("SELECT id, name, email, role, active, disabled_at, last_seen_at FROM customer_portal_accounts WHERE customer_id = ? ORDER BY disabled_at IS NOT NULL, name COLLATE NOCASE").bind(customer.customer_id).all();
    return h.json({ users: results, limit: customer.customer_type === "business" ? userLimit(await loadEffectiveEntitlements(env, customer.customer_id)) : 1 });
  }
  if (path === "/api/customer/team" && request.method === "POST") {
    if (!isAdmin(customer)) return adminOnly(h);
    if (customer.customer_type !== "business") return h.json({ error: "Gebruikers uitnodigen kan alleen met een organisatieaccount." }, 403);
    let body; try { body = await h.readJson(request); } catch { return h.json({ error: "Ongeldige aanvraag." }, 400); }
    const name = String(body.name || "").trim().slice(0, 120), email = String(body.email || "").trim().toLowerCase().slice(0, 254);
    if (!name || !EMAIL_PATTERN.test(email)) return h.json({ error: "Vul een naam en een geldig e-mailadres in." }, 400);
    const limit = userLimit(await loadEffectiveEntitlements(env, customer.customer_id));
    const count = await env.DB.prepare("SELECT COUNT(*) AS n FROM customer_portal_accounts WHERE customer_id = ? AND disabled_at IS NULL").bind(customer.customer_id).first();
    if (limit !== null && Number(count.n) >= limit) return h.json({ error: `Jullie abonnement staat maximaal ${limit} ${limit === 1 ? "gebruiker" : "gebruikers"} toe.` }, 409);
    const id = crypto.randomUUID(), now = new Date().toISOString(), placeholder = await h.hashPassword(h.randomHex(32));
    try {
      await env.DB.prepare("INSERT INTO customer_portal_accounts (id, customer_id, username, name, email, password_salt, password_hash, active, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'member', ?, ?)").bind(id, customer.customer_id, email, name, email, placeholder.salt, placeholder.hash, now, now).run();
    } catch (error) {
      if (String(error?.message || error).toLowerCase().includes("unique")) return h.json({ error: "Dit e-mailadres heeft al een account." }, 409);
      throw error;
    }
    try { await h.sendCustomerAuthEmail(env, id, email, "invite"); }
    catch (error) { console.error("Team invitation could not be sent", String(error?.message || error)); return h.json({ error: "De gebruiker is toegevoegd, maar de uitnodiging kon niet worden verstuurd.", id }, 502); }
    await audit(env, { customer_id: customer.customer_id, entity_type: "account", entity_id: id, action: "team.invited", actor_type: "customer", actor_name: customer.username, details: { email } });
    return h.json({ ok: true, id }, 201);
  }
  const teamRoute = /^\/api\/customer\/team\/([0-9a-f-]{36})\/(disable|enable|role)$/i.exec(path);
  if (teamRoute && request.method === "POST") {
    if (!isAdmin(customer)) return adminOnly(h);
    if (teamRoute[1] === customer.account_id) return h.json({ error: "Je kunt je eigen account hier niet wijzigen." }, 400);
    const target = await env.DB.prepare("SELECT id, role FROM customer_portal_accounts WHERE id = ? AND customer_id = ?").bind(teamRoute[1], customer.customer_id).first();
    if (!target) return h.json({ error: "Gebruiker niet gevonden." }, 404);
    const now = new Date().toISOString();
    if (teamRoute[2] === "role") {
      let body; try { body = await h.readJson(request); } catch { return h.json({ error: "Ongeldige aanvraag." }, 400); }
      const role = body.role === "admin" ? "admin" : "member";
      await env.DB.prepare("UPDATE customer_portal_accounts SET role = ?, updated_at = ? WHERE id = ?").bind(role, now, target.id).run();
    } else if (teamRoute[2] === "disable") {
      await env.DB.batch([
        env.DB.prepare("UPDATE customer_portal_accounts SET disabled_at = COALESCE(disabled_at, ?), updated_at = ? WHERE id = ?").bind(now, now, target.id),
        env.DB.prepare("UPDATE customer_sessions SET revoked_at = ? WHERE customer_account_id = ? AND revoked_at IS NULL").bind(now, target.id)
      ]);
    } else {
      const limit = userLimit(await loadEffectiveEntitlements(env, customer.customer_id));
      const count = await env.DB.prepare("SELECT COUNT(*) AS n FROM customer_portal_accounts WHERE customer_id = ? AND disabled_at IS NULL").bind(customer.customer_id).first();
      if (limit !== null && Number(count.n) >= limit) return h.json({ error: `Jullie abonnement staat maximaal ${limit} gebruikers toe.` }, 409);
      await env.DB.prepare("UPDATE customer_portal_accounts SET disabled_at = NULL, updated_at = ? WHERE id = ?").bind(now, target.id).run();
    }
    await audit(env, { customer_id: customer.customer_id, entity_type: "account", entity_id: target.id, action: `team.${teamRoute[2]}`, actor_type: "customer", actor_name: customer.username });
    return h.json({ ok: true });
  }
  return null;
}
