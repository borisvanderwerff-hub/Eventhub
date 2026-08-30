const CACHE = "eventhub-live-v21";
const ASSETS = ["/", "/static/css/style.css", "/static/js/app.js", "/static/js/connect.js",
  "/static/manifest.webmanifest", "/static/icons/eventhub-180.png", "/static/icons/eventhub-192.png",
  "/static/icons/eventhub-512.png", "/static/icons/eventhub-logo-transparent.png"];
self.addEventListener("install", e => e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting())));
self.addEventListener("activate", e => e.waitUntil(Promise.all([
  caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("eventhub-live-") && key !== CACHE).map(key => caches.delete(key)))),
  self.clients.claim()
])));
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET" || e.request.url.includes("/api/")) return;
  e.respondWith(fetch(e.request).then(r => { const copy=r.clone(); caches.open(CACHE).then(c=>c.put(e.request,copy)); return r; })
    .catch(() => caches.match(e.request).then(r => r || caches.match("/"))));
});
