// Importknop op de registratiepagina van een Rudder-evenement.
//
// Wie de inschrijvingen bekijkt en het evenement wil overnemen, moest eerst
// zelf naar het tabblad Aanpassen. Deze knop stuurt daar automatisch naartoe,
// met de lopende importsessie erbij, zodat de bestaande knop op de
// bewerkpagina het werk kan afmaken.
(() => {
  const match = location.pathname.match(/^\/rudder\/event\/events\/(\d+)\/registrations\/?$/i);
  if (!match) return;
  const eventId = match[1];

  // Dezelfde sleutels als de enkelvoudige en de bulkimport, zodat een sessie
  // die daar is gestart hier gewoon doorloopt.
  const readSession = () => {
    for (const key of ["eventhub-rudder-import-pending", "eventhub-bulk-import-session"]) {
      try {
        const stored = JSON.parse(sessionStorage.getItem(key) || "null");
        if (stored && stored.port && stored.token && (!stored.expiresAt || Date.now() <= stored.expiresAt)) {
          return stored;
        }
      } catch (_error) {
        // Een onleesbare sleutel is geen sessie; ga verder met de volgende.
      }
    }
    return null;
  };

  const button = document.createElement("button");
  button.id = "eventhub-rudder-launcher";
  button.type = "button";
  button.textContent = "Importeren naar EventHub";
  button.title = "Ga naar de bewerkpagina van dit evenement en importeer het";
  document.body.appendChild(button);

  button.addEventListener("click", () => {
    const session = readSession();
    const target = new URL(`/rudder/event/events/${eventId}/edit`, location.origin);
    if (session) target.hash = `eventhub-import=${session.port}.${session.token}`;
    location.href = target.toString();
  });
})();
