// Meerdere Rudder-evenementen in een keer naar EventHub halen.
//
// Rudder filtert zelf op eigenaar, evenementsoort en krijgsmacht. Wie daar op
// de eigen naam filtert, ziet precies de evenementen die hij wil importeren.
// Dit script neemt die getoonde lijst over, haalt per evenement de
// bewerkpagina op en stuurt de gegevens door over dezelfde lokale brug als de
// enkelvoudige import.
//
// De pagina's worden opgehaald in plaats van geopend: alles wat uitgelezen
// wordt staat in de server-gerenderde HTML, dus tabbladen openen zou alleen
// trager en rommeliger zijn. Er wordt uitsluitend gelezen; in Rudder verandert
// niets.
(() => {
  if (!/^\/rudder\/event\/events\/?$/i.test(location.pathname)) return;

  const HINT_DISMISSED = "eventhub-bulk-hint-dismissed";
  const SESSION_KEY = "eventhub-bulk-import-session";
  const LIFETIME_MS = 30 * 60 * 1000;

  // De sessie moet het filteren overleven. EventHub opent de kale
  // overzichtspagina; zodra de gebruiker daar op eigen naam filtert herlaadt
  // Rudder de pagina en is de hash weg. Zonder deze opslag zou het paneel dan
  // de ongefilterde lijst tonen, of helemaal verdwijnen.
  const bewaar = reference => sessionStorage.setItem(SESSION_KEY, JSON.stringify(reference));
  const herstel = () => {
    try {
      const opgeslagen = JSON.parse(sessionStorage.getItem(SESSION_KEY) || "null");
      if (!opgeslagen || Date.now() > opgeslagen.expiresAt) return null;
      return opgeslagen;
    } catch (_error) {
      return null;
    }
  };

  const match = location.hash.match(/^#eventhub-import-all=(\d+)\.([a-f0-9]{64})$/i);
  if (match) {
    bewaar({ port: Number(match[1]), token: match[2], expiresAt: Date.now() + LIFETIME_MS });
    history.replaceState(null, "", location.pathname + location.search);
  }
  const sessie = herstel();
  if (!sessie) {
    // Zonder poort en token valt er niets te versturen. Wie hier zelf naartoe
    // navigeert en een importknop zoekt, krijgt daarom te zien waar hij wel
    // begint; anders lijkt de assistent niet te werken.
    if (sessionStorage.getItem(HINT_DISMISSED)) return;
    const hint = document.createElement("div");
    hint.id = "eventhub-bulk-hint";
    hint.className = "eventhub-rudder-toast";
    hint.innerHTML =
      "<b>Evenementen importeren?</b><br>" +
      "Begin in EventHub: Evenementen, knop Importeren uit Rudder. " +
      "Deze pagina opent dan opnieuw met de importknop erbij." +
      "<br><button type=\"button\" id=\"eventhub-bulk-hint-close\">Verbergen</button>";
    document.body.appendChild(hint);
    hint.addEventListener("click", event => {
      if (event.target.id === "eventhub-bulk-hint-close") {
        sessionStorage.setItem(HINT_DISMISSED, "1");
        hint.remove();
      }
    });
    return;
  }
  const reference = sessie;

  const scraper = window.EventHubRudderScrape;
  if (!scraper) return;

  const send = payload => new Promise(resolve => {
    chrome.runtime.sendMessage(
      { type: "eventhub-send-event", port: reference.port, token: reference.token, payload },
      response => resolve(response || { ok: false, error: "Geen antwoord van de assistent." }),
    );
  });

  const panel = document.createElement("div");
  panel.id = "eventhub-bulk-panel";
  panel.className = "eventhub-rudder-toast ready";
  document.body.appendChild(panel);

  const setStatus = text => { panel.innerHTML = text; };
  let bezig = false;

  // Rudder vernieuwt de lijst na het kiezen van een filter zonder de pagina te
  // herladen. Een momentopname bij het laden zou dus blijven hangen op de
  // ongefilterde lijst; daarom wordt er telkens opnieuw gelezen.
  const huidigeKaarten = () => scraper.scrapeEventList(document);

  const huidigePagina = () => Number(new URLSearchParams(location.search).get("page") || 1);

  // Andere pagina's opvragen met dezelfde filters: alleen page verandert.
  const paginaUrl = nummer => {
    const params = new URLSearchParams(location.search);
    params.set("page", String(nummer));
    return `${location.pathname}?${params.toString()}`;
  };

  // Welke pagina's zijn aangevinkt. De huidige staat standaard aan; de rest
  // kiest de gebruiker er zelf bij, zodat er niet ongevraagd tientallen
  // pagina's worden opgehaald.
  let gekozenPaginas = new Set([huidigePagina()]);

  function beschikbarePaginas() {
    const gevonden = scraper.scrapePageLinks(document);
    const hoogste = gevonden.length ? Math.max(...gevonden) : 1;
    return Array.from({ length: hoogste }, (_value, index) => index + 1);
  }

  function paginaKeuze(paginas) {
    if (paginas.length <= 1) return "";
    const vakjes = paginas.map(nummer => {
      const aan = gekozenPaginas.has(nummer) ? " checked" : "";
      const nu = nummer === huidigePagina() ? " title=\"Pagina die u nu ziet\"" : "";
      return `<label class="eventhub-bulk-page"><input type="checkbox" data-page="${nummer}"${aan}${nu}> ${nummer}</label>`;
    }).join("");
    return (
      `<br><span class="eventhub-bulk-label">Pagina's (${paginas.length}):</span>` +
      `<div class="eventhub-bulk-pages">${vakjes}</div>` +
      `<button type="button" id="eventhub-bulk-all-pages">Alles aanvinken</button>` +
      `<button type="button" id="eventhub-bulk-this-page">Alleen deze</button>`
    );
  }

  function toonKeuze() {
    if (bezig) return;
    const cards = huidigeKaarten();
    if (!cards.length) {
      setStatus(
        "<b>Geen evenementen in beeld.</b><br>Pas het filter in Rudder aan." +
        `<br><button type="button" id="eventhub-bulk-cancel">Annuleren</button>`,
      );
      return;
    }
    const paginas = beschikbarePaginas();
    const eigenaren = [...new Set(cards.map(card => card.owner).filter(Boolean))];
    const meerdere = gekozenPaginas.size > 1;
    setStatus(
      `<b>${cards.length} evenement(en) op deze pagina</b>` +
      (eigenaren.length === 1
        ? `<br>Eigenaar: ${scraper.clean(eigenaren[0])}`
        : `<br>${eigenaren.length} verschillende eigenaren. Filter hierboven op uw naam; dit paneel blijft staan.`) +
      paginaKeuze(paginas) +
      `<br><button type="button" id="eventhub-bulk-start">` +
      (meerdere ? `Importeren (${gekozenPaginas.size} pagina's)` : "Alles importeren naar EventHub") +
      `</button>` +
      `<button type="button" id="eventhub-bulk-cancel">Annuleren</button>`,
    );
  }

  // Meebewegen met het filter, gedempt zodat een reeks wijzigingen tot een
  // enkele verversing leidt.
  let wachtend = null;
  const observer = new MutationObserver(mutaties => {
    if (bezig) return;
    // Wijzigingen binnen het eigen paneel niet als filterwijziging lezen;
    // anders wist het opnieuw tekenen de zojuist gezette vinkjes.
    if (mutaties.every(mutatie => panel.contains(mutatie.target))) return;
    clearTimeout(wachtend);
    wachtend = setTimeout(toonKeuze, 250);
  });
  observer.observe(document.body, { childList: true, subtree: true });

  toonKeuze();

  async function haalPagina(nummer) {
    if (nummer === huidigePagina()) return huidigeKaarten();
    const response = await fetch(paginaUrl(nummer), {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Requested-With": "EventHub" },
    });
    if (!response.ok) throw new Error(`pagina ${nummer}: status ${response.status}`);
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    return scraper.scrapeEventList(doc);
  }

  async function haalEvenement(id) {
    const response = await fetch(`/rudder/event/events/${id}/edit`, {
      credentials: "same-origin",
      cache: "no-store",
      headers: { "X-Requested-With": "EventHub" },
    });
    if (!response.ok) throw new Error(`status ${response.status}`);
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    return scraper.scrapeEvent(doc, id);
  }

  async function importeerAlles() {
    bezig = true;
    const mislukt = [];
    const paginas = [...gekozenPaginas].sort((a, b) => a - b);

    // Eerst de lijsten verzamelen, zodat duidelijk is hoeveel er komen voordat
    // het echte werk begint. Dubbele ids kunnen ontstaan wanneer Rudder
    // tussentijds herschikt; die tellen een keer.
    const gezien = new Set();
    const cards = [];
    for (const [index, nummer] of paginas.entries()) {
      setStatus(`Lijst ophalen: pagina ${index + 1} van ${paginas.length}...`);
      try {
        for (const card of await haalPagina(nummer)) {
          if (gezien.has(card.id)) continue;
          gezien.add(card.id);
          cards.push(card);
        }
      } catch (error) {
        mislukt.push(error.message || String(error));
      }
    }

    let gelukt = 0;
    for (const [index, card] of cards.entries()) {
      setStatus(`Bezig: ${index + 1} van ${cards.length}<br>${scraper.clean(card.title)}`);
      try {
        const payload = await haalEvenement(card.id);
        const antwoord = await send(payload);
        if (!antwoord.ok) throw new Error(antwoord.error || "EventHub weigerde het evenement.");
        gelukt += 1;
      } catch (error) {
        mislukt.push(`${card.id}: ${error.message || error}`);
      }
    }

    // Sluitsignaal: hierop rondt EventHub de import af en toont het overzicht.
    await send({ format: scraper.EVENT_FORMAT, action: "done" });
    sessionStorage.removeItem(SESSION_KEY);
    observer.disconnect();
    setStatus(
      `<b>Klaar.</b><br>${gelukt} van ${cards.length} verstuurd naar EventHub` +
      (paginas.length > 1 ? ` (${paginas.length} pagina's).` : ".") +
      (mislukt.length ? `<br>Overgeslagen: ${mislukt.slice(0, 3).join("; ")}` : "") +
      "<br>Ga terug naar EventHub om de import te bevestigen.",
    );
  }

  panel.addEventListener("change", event => {
    const nummer = Number(event.target.dataset?.page || 0);
    if (!nummer) return;
    if (event.target.checked) gekozenPaginas.add(nummer);
    else gekozenPaginas.delete(nummer);
    // Nooit met een lege keuze eindigen; dan valt er niets te importeren.
    if (!gekozenPaginas.size) gekozenPaginas.add(huidigePagina());
    toonKeuze();
  });

  panel.addEventListener("click", event => {
    if (event.target.id === "eventhub-bulk-all-pages") {
      gekozenPaginas = new Set(beschikbarePaginas());
      toonKeuze();
    }
    if (event.target.id === "eventhub-bulk-this-page") {
      gekozenPaginas = new Set([huidigePagina()]);
      toonKeuze();
    }
    if (event.target.id === "eventhub-bulk-cancel") {
      send({ format: scraper.EVENT_FORMAT, action: "done" });
      sessionStorage.removeItem(SESSION_KEY);
      observer.disconnect();
      panel.remove();
    }
    if (event.target.id === "eventhub-bulk-start") {
      setStatus("Bezig met importeren...");
      importeerAlles();
    }
  });
})();
