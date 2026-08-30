(() => {
  if (document.getElementById("eventhub-rudder-launcher")) return;

  const normalize = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");

  const launcher = document.createElement("button");
  launcher.id = "eventhub-rudder-launcher";
  launcher.type = "button";
  launcher.textContent = "EventHub aanwezigheid";
  document.body.appendChild(launcher);

  const picker = document.createElement("input");
  picker.type = "file"; picker.accept = ".json,application/json"; picker.hidden = true;
  document.body.appendChild(picker);
  launcher.addEventListener("click", () => { picker.value = ""; picker.click(); });

  function closeOverlay() { document.getElementById("eventhub-rudder-overlay")?.remove(); }
  function listBlock(title, rows) {
    if (!rows.length) return "";
    const items = rows.slice(0, 30).map(value => `<li>${escapeHtml(value)}</li>`).join("");
    const more = rows.length > 30 ? `<li>… en nog ${rows.length - 30}</li>` : "";
    return `<details class="eventhub-rudder-details"><summary>${escapeHtml(title)} (${rows.length})</summary><ul>${items}${more}</ul></details>`;
  }
  function escapeHtml(value) {
    const node = document.createElement("span"); node.textContent = String(value || ""); return node.innerHTML;
  }
  function showError(message) {
    closeOverlay();
    const overlay = document.createElement("div"); overlay.id = "eventhub-rudder-overlay";
    overlay.innerHTML = `<section class="eventhub-rudder-panel"><h2>EventHub Browserassistent</h2><p class="eventhub-rudder-warning">${escapeHtml(message)}</p><div class="eventhub-rudder-actions"><button class="eventhub-rudder-action" data-close>Sluiten</button></div></section>`;
    document.body.appendChild(overlay); overlay.querySelector("[data-close]").addEventListener("click", closeOverlay);
  }

  function pageRows() {
    return [...document.querySelectorAll('form[action*="/attendance"] tbody tr')].map(row => {
      const radios = [...row.querySelectorAll('input[type="radio"][name^="registration["]')];
      if (!radios.length) return null;
      const match = radios[0].name.match(/^registration\[([^\]]+)\]$/);
      const name = row.querySelector("a.table__link")?.textContent?.trim() || "Onbekende deelnemer";
      return {row, radios, id:match ? match[1] : "", name, key:normalize(name), current:radios.find(input => input.checked)?.value || "unknown"};
    }).filter(Boolean);
  }

  function makeIndex(participants, field) {
    const index = new Map();
    participants.forEach(person => {
      const key = field === "name" ? normalize(person.full_name) : String(person.identifier || "").trim();
      if (!key) return;
      if (!index.has(key)) index.set(key, []);
      index.get(key).push(person);
    });
    return index;
  }

  function preparePlan(payload) {
    const participants = Array.isArray(payload.participants) ? payload.participants : [];
    const byId = makeIndex(participants, "identifier");
    const byName = makeIndex(participants, "name");
    const matchedPeople = new Set();
    const uncertain = [], defaulted = [], preservedCanceled = [], plans = [];
    pageRows().forEach(entry => {
      if (entry.current === "canceled") { preservedCanceled.push(entry.name); return; }
      let matches = byId.get(entry.id) || [];
      let method = matches.length === 1 ? "registratienummer" : "";
      if (matches.length !== 1) { matches = byName.get(entry.key) || []; method = matches.length === 1 ? "naam" : ""; }
      if (matches.length === 1) {
        const person = matches[0]; matchedPeople.add(person.source_id);
        plans.push({...entry, target:person.present ? "yes" : "no", method});
      } else if (matches.length > 1) {
        uncertain.push(`${entry.name} — meerdere EventHub-records; blijft ${entry.current}`);
      } else if (entry.current === "unknown") {
        plans.push({...entry, target:"no", method:"resterende Unknown"}); defaulted.push(entry.name);
      }
    });
    const notOnPage = participants.filter(person => !matchedPeople.has(person.source_id)).map(person => person.full_name || person.identifier || "Onbekend");
    return {plans, uncertain, defaulted, preservedCanceled, notOnPage, totalRows:pageRows().length};
  }

  function showPreview(payload, plan) {
    closeOverlay();
    const toYes = plan.plans.filter(item => item.target === "yes").length;
    const toNo = plan.plans.filter(item => item.target === "no").length;
    const changed = plan.plans.filter(item => item.current !== item.target).length;
    const overlay = document.createElement("div"); overlay.id = "eventhub-rudder-overlay";
    overlay.innerHTML = `<section class="eventhub-rudder-panel">
      <h2>Controle aanwezigheid</h2>
      <p><strong>${escapeHtml(payload.event?.name || "Evenement")}</strong> — er wordt nog niets opgeslagen.</p>
      <div class="eventhub-rudder-stats">
        <div class="eventhub-rudder-stat"><strong>${toYes}</strong>Yes</div>
        <div class="eventhub-rudder-stat"><strong>${toNo}</strong>No</div>
        <div class="eventhub-rudder-stat"><strong>${changed}</strong>Wijzigingen</div>
        <div class="eventhub-rudder-stat"><strong>${plan.preservedCanceled.length}</strong>Canceled behouden</div>
      </div>
      <p class="eventhub-rudder-warning"><strong>Let op:</strong> ${plan.defaulted.length} resterende Unknown-registratie(s) worden op No gezet. Na toepassen moet u zelf nog op ‘Aanwezigheid opslaan’ klikken.</p>
      ${listBlock("Unknown wordt No", plan.defaulted)}
      ${listBlock("Niet zeker gekoppeld", plan.uncertain)}
      ${listBlock("EventHub-deelnemer niet gevonden op deze pagina", plan.notOnPage)}
      <div class="eventhub-rudder-actions">
        <button class="eventhub-rudder-action" data-close>Annuleren</button>
        <button class="eventhub-rudder-action primary" data-apply>Wijzigingen toepassen</button>
      </div></section>`;
    document.body.appendChild(overlay);
    overlay.querySelector("[data-close]").addEventListener("click", closeOverlay);
    overlay.querySelector("[data-apply]").addEventListener("click", () => {
      plan.plans.forEach(item => {
        const radio = item.radios.find(input => input.value === item.target);
        if (!radio) return;
        if (!radio.checked) { radio.checked = true; radio.dispatchEvent(new Event("change", {bubbles:true})); item.row.classList.add("eventhub-rudder-changed"); }
      });
      closeOverlay();
      launcher.textContent = `${changed} wijziging(en) ingevuld — nu opslaan`;
      launcher.style.background = "#1fb77a";
      window.scrollTo({top:0, behavior:"smooth"});
    });
  }

  picker.addEventListener("change", async () => {
    const file = picker.files?.[0]; if (!file) return;
    try {
      const payload = JSON.parse(await file.text());
      if (payload.format !== "EventHub Rudder Attendance" || !Array.isArray(payload.participants)) throw new Error("Dit is geen geldig EventHub-aanwezigheidsbestand.");
      const rows = pageRows(); if (!rows.length) throw new Error("Op deze pagina is geen Rudder-aanwezigheidsformulier gevonden.");
      showPreview(payload, preparePlan(payload));
    } catch (error) { showError(error.message || String(error)); }
  });

  function loadDirectExport() {
    const match = location.hash.match(/^#eventhub=(\d+)\.([a-f0-9]{64})$/i);
    if (!match) return;
    const [, port, token] = match;
    history.replaceState(null, "", location.pathname + location.search);
    launcher.textContent = "EventHub-presentie ophalen…";
    chrome.runtime.sendMessage(
      {type:"eventhub-fetch-attendance", port:Number(port), token},
      response => {
        if (chrome.runtime.lastError) {
          showError(`De Browserassistent kon EventHub niet bereiken: ${chrome.runtime.lastError.message}`);
          launcher.textContent = "EventHub aanwezigheid";
          return;
        }
        if (!response?.ok) {
          showError(`De lokale EventHub-export kon niet worden opgehaald: ${response?.error || "onbekende fout"}`);
          launcher.textContent = "EventHub aanwezigheid";
          return;
        }
        const payload = response.payload;
        const pageEvent = location.pathname.match(/\/rudder\/event\/events\/(\d+)\/attendance\/?$/i)?.[1] || "";
        const payloadEvent = String(payload?.event?.rudder_event_id || "");
        if (!payload || payload.format !== "EventHub Rudder Attendance" || !Array.isArray(payload.participants)) {
          showError("EventHub stuurde geen geldig aanwezigheidsbestand.");
          return;
        }
        if (payloadEvent && pageEvent && payloadEvent !== pageEvent) {
          showError(`Deze export hoort bij Rudder-event ${payloadEvent}, maar de geopende pagina is event ${pageEvent}.`);
          return;
        }
        if (!pageRows().length) {
          showError("Op deze pagina is geen Rudder-aanwezigheidsformulier gevonden.");
          return;
        }
        launcher.textContent = "EventHub aanwezigheid";
        showPreview(payload, preparePlan(payload));
      }
    );
  }

  loadDirectExport();
})();
