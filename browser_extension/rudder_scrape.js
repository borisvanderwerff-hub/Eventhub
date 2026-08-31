// Gedeelde uitleeslogica voor Rudder-evenementpagina's.
//
// Zowel de knop op een enkele bewerkpagina als de bulkimport vanaf het
// overzicht leest dezelfde velden. Door dat hier te doen kan de bulkimport de
// pagina's ophalen en uitlezen zonder ze te openen, en blijven beide routes
// gegarandeerd dezelfde gegevens opleveren.
(() => {
  if (window.EventHubRudderScrape) return;

  const EVENT_FORMAT = "EventHub Rudder Event";
  const clean = value => String(value || "").replace(/\s+/g, " ").trim();

  function readers(root) {
    const field = name => root.querySelector(`[name="${CSS.escape(name)}"]`);
    return {
      value: name => field(name)?.value || "",
      checked: name => Boolean(root.querySelector(`[name="${CSS.escape(name)}"][type="checkbox"]`)?.checked),
      radio: name => root.querySelector(`[name="${CSS.escape(name)}"]:checked`)?.value || "",
      selected: name => clean(field(name)?.selectedOptions?.[0]?.textContent || ""),
      info: name => {
        const node = root.querySelector(`.js-event-template-info[data-field="${CSS.escape(name)}"]`);
        if (!node) return "";
        const copy = node.cloneNode(true);
        copy.querySelectorAll("button,svg").forEach(item => item.remove());
        return clean(copy.textContent);
      },
    };
  }

  function scrapeDates(root, value) {
    const dates = [];
    root.querySelectorAll('input[name^="event_dates["][name$="[date]"]').forEach(dateInput => {
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

  // Leest een bewerkpagina uit, of dat nu de geopende pagina is of een
  // opgehaald document.
  function scrapeEvent(root, eventId) {
    const { value, checked, radio, selected, info } = readers(root);
    const locationPlate = root.querySelector(".js-event-template-location-license-plate");
    const plateText = clean(locationPlate?.textContent || "").toLowerCase();
    return {
      format: EVENT_FORMAT, version: 1, direction: "import", event_id: String(eventId || ""),
      data: {
        active: checked("item[nl_NL][active]"),
        event_template_id: value("item[event_template_id]"), event_template: selected("item[event_template_id]"),
        reference: info("reference"), event_type: info("event_type.title"), form_type: info("form_type.title"),
        owner_id: value("item[user_id]"), owner: selected("item[user_id]"),
        dates: scrapeDates(root, value),
        publication_date: value("item[publication_date]"), expiration_date: value("item[expiration_date]"),
        internal_registration: radio("item[internal_registration]") === "1",
        registrant_limit: checked("item[registrant_limit]"), maximum_registrants: value("item[maximum_registrants]"),
        allows_invitees: checked("item[allows_invitees]"), invitees_per_registrant: value("item[invitees_per_registrant]"),
        registration_url: value("item[registration_url]"), prior_closing_days: value("item[prior_closing_days]"),
        event_location_id: value("item[event_location_id]"), event_location: selected("item[event_location_id]"),
        location_address: clean(root.querySelector(".js-event-template-location-address")?.textContent || ""),
        license_plate_registration: plateText ? plateText === clean(locationPlate?.dataset?.yes || "ja").toLowerCase() : null,
        location_instructions: value("item[nl_NL][location_instructions]"),
        minimal_education: info("minimal_required_education.translations.[LOCALE].title"),
        minimal_age: info("minimal_age"), maximal_age: info("maximal_age"),
      },
    };
  }

  // Leest de evenementkaarten van een overzichtspagina. Rudder filtert zelf op
  // eigenaar, soort en krijgsmacht; wij nemen over wat er in beeld staat.
  function scrapeEventList(root) {
    const cards = [];
    root.querySelectorAll(".event-card.js-event").forEach(card => {
      const editLink = card.querySelector('a[href*="/edit"]');
      const id = editLink?.getAttribute("href")?.match(/\/events\/(\d+)\/edit/)?.[1];
      if (!id) return;
      const text = selector => clean(card.querySelector(selector)?.textContent || "");
      cards.push({
        id,
        title: text(".event-card__title"),
        meta: text(".event-card__meta"),
        owner: text(".event-card__byline"),
        status: text(".event-card__status"),
      });
    });
    return cards;
  }

  // De paginering van het gefilterde resultaat, zodat een selectie over
  // meerdere pagina's kan lopen.
  function scrapePageLinks(root) {
    const pages = new Set();
    root.querySelectorAll('a[href*="page="]').forEach(anchor => {
      const number = anchor.getAttribute("href")?.match(/[?&]page=(\d+)/)?.[1];
      if (number) pages.add(Number(number));
    });
    return [...pages].sort((a, b) => a - b);
  }

  window.EventHubRudderScrape = { EVENT_FORMAT, clean, scrapeEvent, scrapeEventList, scrapePageLinks };
})();
