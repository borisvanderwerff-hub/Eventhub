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

  const match = location.hash.match(/^#eventhub-import-all=(\d+)\.([a-f0-9]{64})$/i);
  if (!match) {
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
  const reference = { port: Number(match[1]), token: match[2] };
  history.replaceState(null, "", location.pathname + location.search);

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

  const cards = scraper.scrapeEventList(document);
  const pages = scraper.scrapePageLinks(document);
  const laatste = pages.length ? Math.max(...pages) : 1;

  if (!cards.length) {
    panel.textContent = "Geen evenementen op deze pagina. Pas het filter in Rudder aan.";
    return;
  }

  const eigenaren = [...new Set(cards.map(card => card.owner).filter(Boolean))];
  panel.innerHTML =
    `<b>${cards.length} evenement(en) op deze pagina</b>` +
    (eigenaren.length === 1 ? `<br>Eigenaar: ${scraper.clean(eigenaren[0])}` : "") +
    (laatste > 1 ? `<br>Er zijn ${laatste} pagina's. Filter in Rudder om het aantal te beperken.` : "") +
    `<br><button type="button" id="eventhub-bulk-start">Alles importeren naar EventHub</button>` +
    `<button type="button" id="eventhub-bulk-cancel">Annuleren</button>`;

  const setStatus = text => { panel.innerHTML = text; };

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
    let gelukt = 0;
    const mislukt = [];
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
    setStatus(
      `<b>Klaar.</b><br>${gelukt} van ${cards.length} verstuurd naar EventHub.` +
      (mislukt.length ? `<br>Overgeslagen: ${mislukt.slice(0, 3).join("; ")}` : "") +
      "<br>Ga terug naar EventHub om de import te bevestigen.",
    );
  }

  panel.addEventListener("click", event => {
    if (event.target.id === "eventhub-bulk-cancel") {
      send({ format: scraper.EVENT_FORMAT, action: "done" });
      panel.remove();
    }
    if (event.target.id === "eventhub-bulk-start") {
      setStatus("Bezig met importeren...");
      importeerAlles();
    }
  });
})();
