(() => {
  if (!/^\/rudder\/event\/events\/?$/i.test(location.pathname)) return;

  const PENDING_KEY = "eventhub-rudder-import-pending";
  const LIFETIME_MS = 5 * 60 * 1000;
  const match = location.hash.match(/^#eventhub-import=(\d+)\.([a-f0-9]{64})$/i);
  if (!match) return;

  const reference = {
    port: Number(match[1]),
    token: match[2],
    expiresAt: Date.now() + LIFETIME_MS,
  };
  sessionStorage.setItem(PENDING_KEY, JSON.stringify(reference));
  history.replaceState(null, "", location.pathname + location.search);

  const toast = document.createElement("div");
  toast.id = "eventhub-rudder-toast";
  toast.className = "eventhub-rudder-toast ready";
  toast.textContent = "Kies het evenement dat u naar EventHub wilt importeren.";
  document.body.appendChild(toast);

  document.addEventListener("click", event => {
    const anchor = event.target.closest?.("a[href]");
    if (!anchor || Date.now() >= reference.expiresAt) return;
    let target;
    try { target = new URL(anchor.href, location.href); }
    catch (_error) { return; }
    if (target.origin !== location.origin || !/^\/rudder\/event\/events\/\d+\/edit\/?$/i.test(target.pathname)) return;
    target.hash = `eventhub-import=${reference.port}.${reference.token}`;
    anchor.href = target.toString();
  }, true);
})();
