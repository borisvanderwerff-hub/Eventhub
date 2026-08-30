// Shared helpers for the EventHub Server browser frontend.
// No external/CDN dependencies: everything here runs fully offline on the
// local network, matching the "internet mag niet noodzakelijk zijn" requirement.

const EventHubClient = (() => {
    const STORAGE_KEY = "eventhub_client";

    function getStoredClient() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (err) {
            return null;
        }
    }

    function storeClient(client) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(client));
    }

    function clearStoredClient() {
        localStorage.removeItem(STORAGE_KEY);
    }

    async function apiFetch(path, options = {}) {
        const timeoutMs = Number(options.timeoutMs || 8000);
        delete options.timeoutMs;
        const client = getStoredClient();
        const headers = Object.assign({}, options.headers || {});
        if (client && client.id) {
            headers["X-Client-Id"] = client.id;
        }
        if (options.json !== undefined) {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(options.json);
        }
        if (options.operationId) headers["X-Operation-Id"] = options.operationId;
        if (options.operationCreatedAt) headers["X-Operation-Created-At"] = options.operationCreatedAt;
        let response;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);
        const externalSignal = options.signal;
        if (externalSignal) externalSignal.addEventListener("abort", () => controller.abort(), {once:true});
        try {
            response = await fetch(path, Object.assign({}, options, { headers, signal: controller.signal }));
        } catch (cause) {
            const error = new Error("De server is niet bereikbaar.");
            error.isNetworkError = true;
            error.cause = cause;
            throw error;
        } finally {
            clearTimeout(timeout);
        }
        if (!response.ok) {
            let message = `Fout ${response.status}`;
            try {
                const data = await response.json();
                if (data && data.error) message = data.error;
            } catch (err) { /* ignore */ }
            const error = new Error(message);
            error.status = response.status;
            throw error;
        }
        if (response.status === 204) return null;
        return response.json();
    }

    async function registerClient(clientName, role, eventCode) {
        const client = await apiFetch("/api/clients/register", {
            method: "POST",
            json: { client_name: clientName, client_type: "Browser", role, event_code: eventCode },
        });
        storeClient(client);
        startHeartbeat();
        return client;
    }

    async function downloadFile(path, fileName) {
        const client = getStoredClient();
        const headers = client && client.id ? {"X-Client-Id": client.id} : {};
        const response = await fetch(path, {headers});
        if (!response.ok) {
            let message = `Fout ${response.status}`;
            try { message = (await response.json()).error || message; } catch (err) { /* ignore */ }
            throw new Error(message);
        }
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement("a");
        link.href = url; link.download = fileName; document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    async function logout() {
        stopHeartbeat();
        const client = getStoredClient();
        if (client && client.id) {
            try {
                await apiFetch(`/api/clients/${client.id}`, { method: "DELETE" });
            } catch (err) { /* best effort — clear locally regardless */ }
        }
        clearStoredClient();
    }

    let heartbeatTimer = null;
    function startHeartbeat() {
        if (heartbeatTimer) return;
        heartbeatTimer = setInterval(() => {
            const client = getStoredClient();
            if (client && client.id) {
                apiFetch(`/api/clients/${client.id}/heartbeat`, { method: "POST" }).catch(() => {});
            }
        }, 15000);
    }

    function stopHeartbeat() {
        if (heartbeatTimer) {
            clearInterval(heartbeatTimer);
            heartbeatTimer = null;
        }
    }

    function subscribeToLiveUpdates(onEvent, onConnectionChange = null) {
        const source = new EventSource("/api/events/stream");
        source.onopen = () => { if (onConnectionChange) onConnectionChange(true); };
        source.onerror = () => { if (onConnectionChange) onConnectionChange(false); };
        source.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data);
                onEvent(payload);
            } catch (err) { /* ignore malformed keep-alive */ }
        };
        return source;
    }

    function openOfflineDb() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open("eventhub_offline", 1);
            req.onupgradeneeded = () => {
                const db = req.result;
                if (!db.objectStoreNames.contains("queue")) db.createObjectStore("queue", { keyPath: "id" });
                if (!db.objectStoreNames.contains("cache")) db.createObjectStore("cache");
            };
            req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
        });
    }
    async function dbAction(store, mode, action) {
        const db = await openOfflineDb();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(store, mode); const req = action(tx.objectStore(store));
            req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
        });
    }
    const queueAction = item => dbAction("queue", "readwrite", s => s.put(item));
    const queuedActions = () => dbAction("queue", "readonly", s => s.getAll());
    const removeQueuedAction = id => dbAction("queue", "readwrite", s => s.delete(id));
    const clearQueuedActions = () => dbAction("queue", "readwrite", s => s.clear());
    const cacheParticipants = rows => dbAction("cache", "readwrite", s => s.put(rows, "participants"));
    const cachedParticipants = () => dbAction("cache", "readonly", s => s.get("participants"));

    return {
        getStoredClient, storeClient, clearStoredClient, apiFetch, registerClient, downloadFile,
        logout, startHeartbeat, stopHeartbeat, subscribeToLiveUpdates,
        queueAction, queuedActions, removeQueuedAction, clearQueuedActions, cacheParticipants, cachedParticipants,
    };
})();

const EventHubAppearance = (() => {
    const THEME_KEY = "eventhub_theme";
    const WAKE_KEY = "eventhub_wake_lock";
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    let wakeLock = null;

    function themePreference() {
        const value = localStorage.getItem(THEME_KEY) || "auto";
        return ["auto", "light", "dark"].includes(value) ? value : "auto";
    }

    function applyTheme(value = themePreference()) {
        const preference = ["auto", "light", "dark"].includes(value) ? value : "auto";
        const dark = preference === "dark" || (preference === "auto" && media.matches);
        localStorage.setItem(THEME_KEY, preference);
        document.documentElement.dataset.themePreference = preference;
        document.documentElement.dataset.theme = dark ? "dark" : "light";
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.content = dark ? "#0d1117" : "#f3f6fb";
        return preference;
    }

    function wakeEnabled() {
        return localStorage.getItem(WAKE_KEY) !== "false";
    }

    function setWakeEnabled(enabled) {
        localStorage.setItem(WAKE_KEY, enabled ? "true" : "false");
        if (!enabled) releaseWakeLock();
    }

    function wakeSupported() {
        return "wakeLock" in navigator && typeof navigator.wakeLock.request === "function";
    }

    async function requestWakeLock() {
        if (!wakeEnabled() || !wakeSupported() || document.visibilityState !== "visible") return false;
        if (wakeLock && !wakeLock.released) return true;
        try {
            wakeLock = await navigator.wakeLock.request("screen");
            wakeLock.addEventListener("release", () => { wakeLock = null; });
            return true;
        } catch (err) {
            wakeLock = null;
            return false;
        }
    }

    async function releaseWakeLock() {
        const current = wakeLock;
        wakeLock = null;
        if (current && !current.released) {
            try { await current.release(); } catch (err) { /* already released */ }
        }
    }

    const onSystemThemeChange = () => {
        if (themePreference() === "auto") applyTheme("auto");
    };
    if (typeof media.addEventListener === "function") media.addEventListener("change", onSystemThemeChange);
    else if (typeof media.addListener === "function") media.addListener(onSystemThemeChange);
    document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible" && EventHubClient.getStoredClient()) requestWakeLock();
    });
    document.addEventListener("pointerdown", () => {
        if (EventHubClient.getStoredClient()) requestWakeLock();
    }, {passive:true});
    applyTheme();

    return {
        themePreference, applyTheme, wakeEnabled, setWakeEnabled,
        wakeSupported, requestWakeLock, releaseWakeLock,
    };
})();

if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {});
    navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (sessionStorage.getItem("eventhub_sw_reloaded") === "1") return;
        sessionStorage.setItem("eventhub_sw_reloaded", "1");
        location.reload();
    });
}
