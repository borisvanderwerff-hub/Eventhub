(() => {
  if (document.getElementById("eventhub-rudder-event-launcher")) return;

  const EVENT_FORMAT = "EventHub Rudder Event";
  const IMPORT_REFERENCE_PREFIX = "eventhub-rudder-import:";
  const PENDING_IMPORT_KEY = "eventhub-rudder-import-pending";
  const IMPORT_REFERENCE_LIFETIME_MS = 5 * 60 * 1000;
  const launcher = document.createElement("button");
  launcher.id = "eventhub-rudder-event-launcher";
  launcher.type = "button";
  launcher.textContent = "Importeren naar EventHub";
  launcher.title = "Importeer de gegevens van dit Rudder-evenement naar EventHub";
  document.body.appendChild(launcher);

  const escapeHtml = value => {
    const node = document.createElement("span"); node.textContent = String(value || ""); return node.innerHTML;
  };
  const clean = value => String(value || "").replace(/\s+/g, " ").trim();
  const field = name => document.querySelector(`[name="${CSS.escape(name)}"]`);
  const value = name => field(name)?.value || "";
  const checked = name => Boolean(document.querySelector(`[name="${CSS.escape(name)}"][type="checkbox"]`)?.checked);
  const radio = name => document.querySelector(`[name="${CSS.escape(name)}"]:checked`)?.value || "";
  const selected = name => clean(field(name)?.selectedOptions?.[0]?.textContent || "");
  const info = name => {
    const node = document.querySelector(`.js-event-template-info[data-field="${CSS.escape(name)}"]`);
    if (!node) return "";
    const copy = node.cloneNode(true); copy.querySelectorAll("button,svg").forEach(item => item.remove());
    return clean(copy.textContent);
  };
  const pageEventId = () => location.pathname.match(/\/rudder\/event\/events\/(\d+)\/edit\/?$/i)?.[1] || "";

  function closeOverlay() { document.getElementById("eventhub-rudder-overlay")?.remove(); }
  function showError(message) {
    closeOverlay();
    const overlay = document.createElement("div"); overlay.id = "eventhub-rudder-overlay";
    overlay.innerHTML = `<section class="eventhub-rudder-panel"><h2>EventHub Browserassistent</h2><p class="eventhub-rudder-warning">${escapeHtml(message)}</p><div class="eventhub-rudder-actions"><button class="eventhub-rudder-action" data-close>Sluiten</button></div></section>`;
    document.body.appendChild(overlay); overlay.querySelector("[data-close]").addEventListener("click", closeOverlay);
  }
  function showSuccess(title, message) {
    closeOverlay();
    const overlay = document.createElement("div"); overlay.id = "eventhub-rudder-overlay";
    overlay.innerHTML = `<section class="eventhub-rudder-panel"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(message)}</p><div class="eventhub-rudder-actions"><button class="eventhub-rudder-action primary" data-close>Gereed</button></div></section>`;
    document.body.appendChild(overlay); overlay.querySelector("[data-close]").addEventListener("click", closeOverlay);
  }
  function showToast(message, state = "success") {
    document.getElementById("eventhub-rudder-toast")?.remove();
    const toast = document.createElement("div");
    toast.id = "eventhub-rudder-toast";
    toast.className = `eventhub-rudder-toast ${state}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    window.setTimeout(() => toast.remove(), state === "error" ? 8000 : 5000);
  }

  function scrapeDates() {
    const dates = [];
    document.querySelectorAll('input[name^="event_dates["][name$="[date]"]').forEach(dateInput => {
      const match = dateInput.name.match(/^event_dates\[([^\]]+)\]\[date\]$/);
      if (!match || match[1] === "__INDEX__" || !dateInput.value) return;
      const prefix = `event_dates[${match[1]}]`;
      dates.push({
        id: match[1], date: dateInput.value,
        start_time: value(`${prefix}[start_time]`), end_time: value(`${prefix}[end_time]`),
      });
    });
    return dates;
  }

  function scrapeEvent() {
    const locationPlate = document.querySelector(".js-event-template-location-license-plate");
    const plateText = clean(locationPlate?.textContent || "").toLowerCase();
    return {
      format: EVENT_FORMAT, version: 1, direction: "import", event_id: pageEventId(),
      data: {
        active: checked("item[nl_NL][active]"),
        event_template_id: value("item[event_template_id]"), event_template: selected("item[event_template_id]"),
        reference: info("reference"), event_type: info("event_type.title"), form_type: info("form_type.title"),
        owner_id: value("item[user_id]"), owner: selected("item[user_id]"), dates: scrapeDates(),
        publication_date: value("item[publication_date]"), expiration_date: value("item[expiration_date]"),
        internal_registration: radio("item[internal_registration]") === "1",
        registrant_limit: checked("item[registrant_limit]"), maximum_registrants: value("item[maximum_registrants]"),
        allows_invitees: checked("item[allows_invitees]"), invitees_per_registrant: value("item[invitees_per_registrant]"),
        registration_url: value("item[registration_url]"), prior_closing_days: value("item[prior_closing_days]"),
        event_location_id: value("item[event_location_id]"), event_location: selected("item[event_location_id]"),
        location_address: clean(document.querySelector(".js-event-template-location-address")?.textContent || ""),
        license_plate_registration: plateText ? plateText === clean(locationPlate?.dataset?.yes || "ja").toLowerCase() : null,
        location_instructions: value("item[nl_NL][location_instructions]"),
        minimal_education: info("minimal_required_education.translations.[LOCALE].title"),
        minimal_age: info("minimal_age"), maximal_age: info("maximal_age"),
      },
    };
  }

  function setValue(name, next, changes) {
    const input = field(name); if (!input || next === undefined || next === null) return;
    const old = String(input.value || ""); const wanted = String(next || "");
    if (old === wanted) return;
    input.value = wanted; input.dispatchEvent(new Event("input", {bubbles:true})); input.dispatchEvent(new Event("change", {bubbles:true}));
    changes.push(`${name}: ${old || "—"} → ${wanted || "—"}`);
  }
  function setChecked(name, next, changes) {
    const input = document.querySelector(`[name="${CSS.escape(name)}"][type="checkbox"]`);
    if (!input || typeof next !== "boolean" || input.checked === next) return;
    input.checked = next; input.dispatchEvent(new Event("change", {bubbles:true})); changes.push(`${name}: ${next ? "Ja" : "Nee"}`);
  }
  function setRadio(name, next, changes) {
    if (typeof next !== "boolean") return;
    const input = document.querySelector(`[name="${CSS.escape(name)}"][value="${next ? "1" : "0"}"]`);
    if (!input || input.checked) return;
    input.checked = true; input.dispatchEvent(new Event("change", {bubbles:true})); changes.push(`${name}: ${next ? "Intern" : "Extern"}`);
  }
  function setRichText(name, next, changes) {
    const input = field(name); if (!input || next === undefined || next === null) return;
    const old = String(input.value || ""); const wanted = String(next || "");
    if (old === wanted) return;
    input.value = wanted; input.dispatchEvent(new Event("input", {bubbles:true})); input.dispatchEvent(new Event("change", {bubbles:true}));
    const editorFrame = input.parentElement?.querySelector(".cke_contents iframe");
    try {
      if (editorFrame?.contentDocument?.body) {
        editorFrame.contentDocument.body.innerHTML = wanted;
        editorFrame.contentDocument.body.dispatchEvent(new Event("input", {bubbles:true}));
      }
    } catch (_error) { /* Rudder still receives the underlying textarea value. */ }
    changes.push(`${name}: aanvullende instructies bijgewerkt`);
  }
  function applyExport(payload) {
    const data = payload.data || {}; const changes = []; const warnings = [];
    const known = new Set(Array.isArray(payload.known_fields) ? payload.known_fields : Object.keys(data));
    if (known.has("active")) setChecked("item[nl_NL][active]", data.active, changes);
    if (known.has("publication_date")) setValue("item[publication_date]", data.publication_date, changes);
    if (known.has("expiration_date")) setValue("item[expiration_date]", data.expiration_date, changes);
    if (known.has("internal_registration")) setRadio("item[internal_registration]", data.internal_registration, changes);
    if (known.has("registrant_limit")) setChecked("item[registrant_limit]", data.registrant_limit, changes);
    if (known.has("maximum_registrants")) setValue("item[maximum_registrants]", data.maximum_registrants, changes);
    if (known.has("allows_invitees")) setChecked("item[allows_invitees]", data.allows_invitees, changes);
    if (known.has("invitees_per_registrant")) setValue("item[invitees_per_registrant]", data.invitees_per_registrant, changes);
    if (known.has("registration_url")) setValue("item[registration_url]", data.registration_url, changes);
    if (known.has("prior_closing_days")) setValue("item[prior_closing_days]", data.prior_closing_days, changes);
    if (known.has("location_instructions")) setRichText("item[nl_NL][location_instructions]", data.location_instructions, changes);
    const currentDates = scrapeDates(); const wantedDates = Array.isArray(data.dates) ? data.dates : [];
    if (known.has("dates")) {
      if (wantedDates.length !== currentDates.length) warnings.push("Het aantal eventdagen verschilt. EventHub wijzigt daarom alleen bestaande datumregels en voegt geen regels toe of verwijdert ze.");
      currentDates.forEach((current, index) => {
        const wanted = wantedDates[index]; if (!wanted) return;
        const prefix = `event_dates[${current.id}]`;
        setValue(`${prefix}[date]`, wanted.date, changes); setValue(`${prefix}[start_time]`, wanted.start_time, changes); setValue(`${prefix}[end_time]`, wanted.end_time, changes);
      });
    }
    if (known.has("event_template_id") || known.has("owner_id") || known.has("event_location_id")) warnings.push("Template, beheerder en locatie zijn dynamische Rudder-keuzelijsten en worden in deze versie bewust niet gewijzigd.");
    return {changes, warnings};
  }

  function showExportPreview(payload) {
    const current = scrapeEvent();
    const proposed = [];
    const known = new Set(Array.isArray(payload.known_fields) ? payload.known_fields : Object.keys(payload.data || {}));
    const pairs = [
      ["active", "Actief", current.data.active, payload.data.active], ["publication_date", "Publicatie", current.data.publication_date, payload.data.publication_date],
      ["expiration_date", "Vervaldatum", current.data.expiration_date, payload.data.expiration_date], ["maximum_registrants", "Maximum registraties", current.data.maximum_registrants, payload.data.maximum_registrants],
      ["allows_invitees", "Introducees", current.data.allows_invitees, payload.data.allows_invitees], ["prior_closing_days", "Sluitingsdagen", current.data.prior_closing_days, payload.data.prior_closing_days],
    ];
    pairs.forEach(([key, label, before, after]) => { if (known.has(key) && String(before) !== String(after)) proposed.push(`<li><strong>${escapeHtml(label)}:</strong> ${escapeHtml(before)} → ${escapeHtml(after)}</li>`); });
    closeOverlay();
    const overlay = document.createElement("div"); overlay.id = "eventhub-rudder-overlay";
    overlay.innerHTML = `<section class="eventhub-rudder-panel"><h2>Exporteren naar Rudder</h2>
      <p>Controleer de voorgenomen wijzigingen. EventHub slaat nooit automatisch op.</p>
      ${proposed.length ? `<ul>${proposed.join("")}</ul>` : "<p>De belangrijkste velden zijn al gelijk. EventHub controleert ook datums en aanvullende instructies.</p>"}
      <p class="eventhub-rudder-warning"><strong>Na invullen:</strong> controleer de pagina en klik zelf op de Rudder-opslagknop.</p>
      <div class="eventhub-rudder-actions"><button class="eventhub-rudder-action" data-close>Annuleren</button><button class="eventhub-rudder-action primary" data-apply>Velden invullen</button></div></section>`;
    document.body.appendChild(overlay);
    overlay.querySelector("[data-close]").addEventListener("click", closeOverlay);
    overlay.querySelector("[data-apply]").addEventListener("click", () => {
      const result = applyExport(payload); closeOverlay();
      launcher.textContent = `${result.changes.length} veld(en) ingevuld — controleer en sla op`;
      launcher.style.background = "#1fb77a";
      if (result.warnings.length) showSuccess("Velden ingevuld", `${result.changes.length} wijziging(en) zijn voorbereid. ${result.warnings.join(" ")} Controleer alles en klik daarna zelf op opslaan.`);
      window.scrollTo({top:0, behavior:"smooth"});
    });
  }

  function bridgeReference(kind) {
    const match = location.hash.match(new RegExp(`^#eventhub-${kind}=(\\d+)\\.([a-f0-9]{64})$`, "i"));
    return match ? {port:Number(match[1]), token:match[2]} : null;
  }
  function importStorageKey() { return `${IMPORT_REFERENCE_PREFIX}${pageEventId()}`; }
  function storeImportReference(reference) {
    if (!reference || !pageEventId()) return;
    sessionStorage.setItem(importStorageKey(), JSON.stringify({
      port: reference.port,
      token: reference.token,
      eventId: pageEventId(),
      expiresAt: Date.now() + IMPORT_REFERENCE_LIFETIME_MS,
    }));
  }
  function readImportReference() {
    let reference = null;
    try { reference = JSON.parse(sessionStorage.getItem(importStorageKey()) || "null"); }
    catch (_error) { reference = null; }
    if (!reference || reference.eventId !== pageEventId() || !Number.isInteger(reference.port) ||
        reference.port < 1024 || reference.port > 65535 || !/^[a-f0-9]{64}$/i.test(String(reference.token || "")) ||
        Number(reference.expiresAt || 0) <= Date.now()) {
      sessionStorage.removeItem(importStorageKey());
      return null;
    }
    return {port: reference.port, token: reference.token};
  }
  function readPendingImportReference() {
    let reference = null;
    try { reference = JSON.parse(sessionStorage.getItem(PENDING_IMPORT_KEY) || "null"); }
    catch (_error) { reference = null; }
    if (!reference || !Number.isInteger(reference.port) || reference.port < 1024 || reference.port > 65535 ||
        !/^[a-f0-9]{64}$/i.test(String(reference.token || "")) || Number(reference.expiresAt || 0) <= Date.now()) {
      sessionStorage.removeItem(PENDING_IMPORT_KEY);
      return null;
    }
    sessionStorage.removeItem(PENDING_IMPORT_KEY);
    return {port: reference.port, token: reference.token};
  }
  function setImportReady() {
    launcher.disabled = false;
    launcher.textContent = "Importeren naar EventHub";
    launcher.classList.add("eventhub-rudder-ready");
    launcher.classList.remove("eventhub-rudder-success", "eventhub-rudder-busy");
    launcher.title = "EventHub wacht op deze gegevens — klik om nu te importeren";
    showToast("EventHub is gekoppeld. Klik op ‘Importeren naar EventHub’.", "ready");
  }
  function sendImportToEventHub() {
    const importing = readImportReference();
    if (!importing) {
      showError("Er is geen actieve importkoppeling. Start in EventHub ‘Importeren uit Rudder’; deze pagina wordt dan opnieuw geopend en de knop is direct klaar voor één klik.");
      return;
    }
    launcher.disabled = true;
    launcher.textContent = "Importeren…";
    launcher.classList.remove("eventhub-rudder-ready", "eventhub-rudder-success");
    launcher.classList.add("eventhub-rudder-busy");
    chrome.runtime.sendMessage({type:"eventhub-send-event", ...importing, payload:scrapeEvent()}, response => {
      launcher.disabled = false;
      if (chrome.runtime.lastError || !response?.ok) {
        launcher.textContent = "Opnieuw importeren naar EventHub";
        launcher.classList.remove("eventhub-rudder-busy");
        launcher.classList.add("eventhub-rudder-ready");
        showError(`EventHub kon de gegevens niet ontvangen: ${chrome.runtime.lastError?.message || response?.error || "onbekende fout"}. Laat EventHub openstaan en probeer deze knop opnieuw.`);
        return;
      }
      sessionStorage.removeItem(importStorageKey());
      launcher.textContent = "Geïmporteerd in EventHub";
      launcher.classList.remove("eventhub-rudder-ready", "eventhub-rudder-busy");
      launcher.classList.add("eventhub-rudder-success");
      launcher.title = "De gegevens zijn naar EventHub verstuurd";
      showToast("Rudder-gegevens zijn naar EventHub verstuurd.");
    });
  }
  function handleBridge() {
    const importing = bridgeReference("import"); const exporting = bridgeReference("export");
    if (!importing && !exporting) {
      const pendingImport = readPendingImportReference();
      if (pendingImport) {
        storeImportReference(pendingImport);
        setImportReady();
      }
      return;
    }
    history.replaceState(null, "", location.pathname + location.search);
    if (importing) {
      sessionStorage.removeItem(PENDING_IMPORT_KEY);
      storeImportReference(importing);
      setImportReady();
      return;
    }
    launcher.textContent = "EventHub-evenement ophalen…";
    chrome.runtime.sendMessage({type:"eventhub-fetch-event", ...exporting}, response => {
      if (chrome.runtime.lastError || !response?.ok) { showError(`EventHub kon niet worden bereikt: ${chrome.runtime.lastError?.message || response?.error || "onbekende fout"}`); return; }
      const payload = response.payload;
      if (!payload || payload.format !== EVENT_FORMAT || String(payload.event_id || "") !== pageEventId()) { showError("Deze EventHub-export hoort niet bij het geopende Rudder-evenement."); return; }
      launcher.textContent = "Importeren naar EventHub"; showExportPreview(payload);
    });
  }

  launcher.addEventListener("click", sendImportToEventHub);
  window.addEventListener("hashchange", handleBridge);
  window.addEventListener("pageshow", handleBridge);
  handleBridge();
})();
