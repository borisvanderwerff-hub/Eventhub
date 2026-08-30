chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
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
