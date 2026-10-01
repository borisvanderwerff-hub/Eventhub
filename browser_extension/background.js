// EventHub luistert op deze vaste poort zolang de app open staat. Er komt
// niets uit zonder dat de gebruiker het daar bevestigt.
const EVENTHUB_PORT = 47615;

function eventhubUnreachable(error) {
  const text = error?.message || String(error || "");
  return /failed to fetch|networkerror|load failed/i.test(text)
    ? "EventHub is niet bereikbaar. Staat de app open, met het juiste dossier?"
    : text;
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "eventhub-request-attendance") {
    const eventId = String(message.event || "");
    if (!/^\d+$/.test(eventId)) {
      sendResponse({ok:false, error:"Geen geldig Rudder-evenementnummer op deze pagina."});
      return false;
    }
    fetch(`http://127.0.0.1:${EVENTHUB_PORT}/attendance?event=${encodeURIComponent(eventId)}`, {cache:"no-store"})
      .then(async response => {
        const data = await response.json().catch(() => null);
        if (!response.ok) throw new Error(data?.error || `EventHub antwoordde met status ${response.status}.`);
        return data;
      })
      .then(payload => sendResponse({ok:true, payload}))
      .catch(error => sendResponse({ok:false, error:eventhubUnreachable(error)}));
    return true;
  }
  if (!message || !["eventhub-fetch-attendance", "eventhub-fetch-event", "eventhub-send-event"].includes(message.type)) return false;
  const port = Number(message.port);
  const token = String(message.token || "");
  if (!Number.isInteger(port) || port < 1024 || port > 65535 || !/^[a-f0-9]{64}$/i.test(token)) {
    sendResponse({ok:false, error:"Ongeldige lokale EventHub-koppeling."});
    return false;
  }
  const isAttendance = message.type === "eventhub-fetch-attendance";
  const isSend = message.type === "eventhub-send-event";
  const path = isAttendance ? "attendance" : "event";
  const options = {cache:"no-store"};
  if (isSend) {
    options.method = "POST";
    options.headers = {"Content-Type":"application/json"};
    options.body = JSON.stringify(message.payload || {});
  }
  fetch(`http://127.0.0.1:${port}/${path}?token=${encodeURIComponent(token)}`, options)
    .then(async response => {
      if (!response.ok) throw new Error(`EventHub antwoordde met status ${response.status}.`);
      return response.json();
    })
    .then(payload => sendResponse({ok:true, payload}))
    .catch(error => sendResponse({ok:false, error:error.message || String(error)}));
  return true;
});
