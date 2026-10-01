(() => {
    const registerCard = document.getElementById("registerCard");
    const checkinCard = document.getElementById("checkinCard");
    const viewerWaitingCard = document.getElementById("viewerWaitingCard");
    const addWalkinButton = document.getElementById("addWalkinButton");
    const walkinModal = document.getElementById("walkinModal");
    const walkinName = document.getElementById("walkinName");
    const walkinPhone = document.getElementById("walkinPhone");
    const walkinMessage = document.getElementById("walkinMessage");
    const statusBar = document.getElementById("statusBar");
    const clientLabel = document.getElementById("clientLabel");
    const searchInput = document.getElementById("searchInput");
    const resultsList = document.getElementById("resultsList");
    const searchHint = document.getElementById("searchHint");
    const rosterShell = document.getElementById("rosterShell");
    const alphabetIndex = document.getElementById("alphabetIndex");
    const alphabetBubble = document.getElementById("alphabetBubble");
    const registerError = document.getElementById("registerError");
    const connectionStatus = document.getElementById("connectionStatus");
    const freezeBanner = document.getElementById("freezeBanner");
    const stopBanner = document.getElementById("stopBanner");
    const stopModal = document.getElementById("stopModal");
    const stopModalMessage = document.getElementById("stopModalMessage");
    const clearQueueButton = document.getElementById("clearQueueButton");
    const queueReviewModal = document.getElementById("queueReviewModal");
    const queueReviewList = document.getElementById("queueReviewList");
    const queueReviewMessage = document.getElementById("queueReviewMessage");
    const queueReviewClose = document.getElementById("queueReviewClose");
    const queueReviewAvailable = !!(queueReviewModal && queueReviewList && queueReviewMessage && queueReviewClose);
    const settingsButton = document.getElementById("settingsButton");
    const settingsMenu = document.getElementById("settingsMenu");
    const settingsClientName = document.getElementById("settingsClientName");
    const settingsRole = document.getElementById("settingsRole");
    const settingsTheme = document.getElementById("settingsTheme");
    const settingsHandedness = document.getElementById("settingsHandedness");
    const settingsHandednessGroup = document.getElementById("settingsHandednessGroup");
    const registerHandednessGroup = document.getElementById("registerHandednessGroup");
    const settingsWakeLock = document.getElementById("settingsWakeLock");
    const wakeLockStatus = document.getElementById("wakeLockStatus");
    const settingsMessage = document.getElementById("settingsMessage");
    const clientManagementCard = document.getElementById("clientManagementCard");
    const managedClientsBody = document.getElementById("managedClientsBody");
    const managementMessage = document.getElementById("managementMessage");
    const freezeSessionButton = document.getElementById("freezeSessionButton");
    const stopCheckinButton = document.getElementById("stopCheckinButton");
    const emergencySessionButton = document.getElementById("emergencySessionButton");
    const emergencyExportButton = document.getElementById("emergencyExportButton");
    const emergencyCard = document.getElementById("emergencyCard");
    const emergencyInstruction = document.getElementById("emergencyInstruction");
    const emergencyTotal = document.getElementById("emergencyTotal");
    const emergencySafe = document.getElementById("emergencySafe");
    const emergencyUnaccounted = document.getElementById("emergencyUnaccounted");
    const emergencySearch = document.getElementById("emergencySearch");
    const emergencyList = document.getElementById("emergencyList");
    const editEmergencyInstructionButton = document.getElementById("editEmergencyInstructionButton");
    const emergencyEndButton = document.getElementById("emergencyEndButton");
    const emergencyCardExportButton = document.getElementById("emergencyCardExportButton");
    const emergencyAssemblyPoint = document.getElementById("emergencyAssemblyPoint");
    const emergencyTeam = document.getElementById("emergencyTeam");
    const emergencyModal = document.getElementById("emergencyModal");
    const emergencyModalInstruction = document.getElementById("emergencyModalInstruction");
    const emergencyEndedModal = document.getElementById("emergencyEndedModal");
    const refreshClientsButton = document.getElementById("refreshClientsButton");
    const managerTabs = document.getElementById("managerTabs");
    const managementTabButton = document.getElementById("managementTabButton");
    const participantsTabButton = document.getElementById("participantsTabButton");
    const managementAvailable = !!(clientManagementCard && managedClientsBody && managementMessage &&
        freezeSessionButton && stopCheckinButton && refreshClientsButton);
    if (managementAvailable && checkinCard && checkinCard.parentNode) {
        checkinCard.parentNode.insertBefore(clientManagementCard, checkinCard);
    }
    let frozen = false;
    let checkoutRequired = false;
    let checkinStopped = false;
    let emergencyActive = false;
    let emergencyIncidentId = "";
    let emergencyPeople = [];
    let stopNoticeShown = false;
    let searchSequence = 0;
    let serverReachable = true;
    let syncInProgress = false;
    let currentRole = "viewer";
    let managementRefreshInProgress = false;
    let managerActiveTab = "management";
    const HANDEDNESS_KEY = "eventhub_handedness";
    const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
    let alphabetBubbleTimer = null;

    function handednessPreference() {
        return localStorage.getItem(HANDEDNESS_KEY) === "left" ? "left" : "right";
    }

    function usesTouchLayout() {
        const coarsePointer = window.matchMedia?.("(pointer: coarse)")?.matches === true;
        const noHover = window.matchMedia?.("(hover: none)")?.matches === true;
        const hasTouch = Number(navigator.maxTouchPoints || 0) > 0;
        return hasTouch && (coarsePointer || noHover);
    }

    const touchLayout = usesTouchLayout();

    function updateHandednessVisibility() {
        if (registerHandednessGroup) registerHandednessGroup.classList.toggle("hidden", !touchLayout);
        if (settingsHandednessGroup) settingsHandednessGroup.classList.toggle("hidden", !touchLayout);
    }

    function applyHandedness(value, persist = true) {
        const handedness = value === "left" ? "left" : "right";
        if (persist) localStorage.setItem(HANDEDNESS_KEY, handedness);
        if (rosterShell) {
            rosterShell.classList.toggle("hand-left", handedness === "left");
            rosterShell.classList.toggle("hand-right", handedness !== "left");
        }
        if (settingsHandedness) settingsHandedness.value = handedness;
        document.querySelectorAll('input[name="handedness"]').forEach(input => {
            input.checked = input.value === handedness;
        });
    }

    function actionLabel(action) {
        return ({checkin:"Inchecken", checkout:"Uitchecken", undo:"Aanwezigheid ongedaan maken"})[action] || action || "Onbekende actie";
    }

    function formatQueueTime(value) {
        if (!value) return "Tijdstip onbekend";
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? value : date.toLocaleString("nl-NL", {dateStyle:"short", timeStyle:"short"});
    }

    async function renderQueueReview() {
        if (!queueReviewAvailable) return;
        const queue = await EventHubClient.queuedActions();
        const conflicts = queue.filter(item => item.conflict);
        const participants = (await EventHubClient.cachedParticipants()) || [];
        queueReviewList.innerHTML = "";
        if (!conflicts.length) {
            queueReviewList.innerHTML = '<p class="hint">Er zijn geen acties meer die controle vereisen.</p>';
            return;
        }
        conflicts.forEach(item => {
            const participant = participants.find(row => String(row.id) === String(item.participantId));
            const card = document.createElement("article");
            card.className = "queue-review-item";
            const name = document.createElement("div");
            name.className = "queue-review-name";
            name.textContent = participant ? personLabel(participant) : `Deelnemer ${item.participantId}`;
            const meta = document.createElement("div");
            meta.className = "queue-review-meta";
            meta.textContent = `Actie: ${actionLabel(item.action)} · ${formatQueueTime(item.createdAt)}`;
            const actions = document.createElement("div");
            actions.className = "queue-review-actions";
            const retry = document.createElement("button");
            retry.type = "button"; retry.className = "btn btn-primary"; retry.textContent = "Opnieuw proberen";
            retry.addEventListener("click", () => retryQueuedAction(item, retry));
            const remove = document.createElement("button");
            remove.type = "button"; remove.className = "btn btn-secondary"; remove.textContent = "Actie verwijderen";
            remove.addEventListener("click", () => removeQueuedConflict(item));
            actions.append(retry, remove); card.append(name, meta, actions); queueReviewList.appendChild(card);
        });
    }

    async function openQueueReview() {
        const conflicts = (await EventHubClient.queuedActions()).filter(item => item.conflict);
        if (!conflicts.length) return;
        if (!queueReviewAvailable) {
            // An older cached HTML document can briefly run newer JavaScript while
            // Safari activates the new service worker. Never let that mixed state
            // break registration; one reload obtains the matching document.
            window.location.reload();
            return;
        }
        queueReviewMessage.textContent = "";
        await renderQueueReview();
        queueReviewModal.classList.remove("hidden");
    }

    async function retryQueuedAction(item, button) {
        button.disabled = true;
        queueReviewMessage.textContent = `${actionLabel(item.action)} opnieuw uitvoeren…`;
        try {
            await EventHubClient.apiFetch(`/api/participants/${item.participantId}/${item.action}`,
                {method:"POST", operationId:item.id, operationCreatedAt:item.createdAt});
            serverReachable = true;
            await EventHubClient.removeQueuedAction(item.id);
            queueReviewMessage.textContent = `${actionLabel(item.action)} is verwerkt.`;
            await runSearch(searchInput.value);
        } catch (err) {
            if (err.isNetworkError) serverReachable = false;
            item.conflict = true;
            await EventHubClient.queueAction(item);
            queueReviewMessage.textContent = `Niet verwerkt: ${err.message}`;
        }
        await renderQueueReview();
        await updateQueueStatus();
    }

    async function removeQueuedConflict(item) {
        if (!confirm(`${actionLabel(item.action)} uit de lokale wachtrij verwijderen?`)) return;
        await EventHubClient.removeQueuedAction(item.id);
        queueReviewMessage.textContent = "De actie is verwijderd.";
        await renderQueueReview();
        await updateQueueStatus();
    }

    function requireNewLogin(message = "De server is gestopt. Meld opnieuw aan zodra een nieuwe sessie beschikbaar is.", showPopup = false) {
        const hadClient = !!EventHubClient.getStoredClient();
        EventHubAppearance.releaseWakeLock();
        EventHubClient.stopHeartbeat();
        EventHubClient.clearStoredClient();
        checkinCard.classList.add("hidden");
        if (viewerWaitingCard) viewerWaitingCard.classList.add("hidden");
        statusBar.classList.add("hidden");
        settingsButton.classList.add("hidden");
        if (clientManagementCard) clientManagementCard.classList.add("hidden");
        if (emergencyCard) emergencyCard.classList.add("hidden");
        if (managerTabs) managerTabs.classList.add("hidden");
        setSettingsOpen(false);
        registerCard.classList.remove("hidden");
        document.getElementById("eventCodeInput").value = "";
        registerError.textContent = message;
        if (showPopup && hadClient) window.alert(message);
    }

    function roleLabel(role) {
        return ({checkin:"Check-in", viewer:"Viewer", event_manager:"Event Manager", admin:"Beheerder"})[role] || role;
    }

    function canManageSession() {
        return ["event_manager", "admin"].includes(currentRole);
    }

    function applyManagerTab() {
        const manager = canManageSession();
        if (emergencyActive) {
            if (managerTabs) managerTabs.classList.add("hidden");
            if (clientManagementCard) clientManagementCard.classList.add("hidden");
            checkinCard.classList.add("hidden");
            if (emergencyCard) emergencyCard.classList.remove("hidden");
            return;
        }
        if (emergencyCard) emergencyCard.classList.add("hidden");
        if (managerTabs) managerTabs.classList.toggle("hidden", !manager);
        if (!manager) {
            if (clientManagementCard) clientManagementCard.classList.add("hidden");
            const waiting = currentRole === "viewer";
            if (viewerWaitingCard) viewerWaitingCard.classList.toggle("hidden", !waiting);
            checkinCard.classList.toggle("hidden", waiting);
            if (addWalkinButton) addWalkinButton.classList.add("hidden");
            return;
        }
        if (viewerWaitingCard) viewerWaitingCard.classList.add("hidden");
        if (addWalkinButton) addWalkinButton.classList.remove("hidden");
        const showManagement = managerActiveTab === "management";
        if (clientManagementCard) clientManagementCard.classList.toggle("hidden", !showManagement);
        checkinCard.classList.toggle("hidden", showManagement);
        if (managementTabButton) {
            managementTabButton.classList.toggle("active", showManagement);
            managementTabButton.setAttribute("aria-selected", showManagement ? "true" : "false");
        }
        if (participantsTabButton) {
            participantsTabButton.classList.toggle("active", !showManagement);
            participantsTabButton.setAttribute("aria-selected", showManagement ? "false" : "true");
        }
        if (showManagement) refreshManagedClients();
    }

    function updateManagementVisibility() {
        if (!managementAvailable) return;
        applyManagerTab();
    }

    if (managementTabButton) managementTabButton.addEventListener("click", () => {
        managerActiveTab = "management";
        applyManagerTab();
    });
    if (participantsTabButton) participantsTabButton.addEventListener("click", () => {
        managerActiveTab = "participants";
        applyManagerTab();
        searchInput.focus();
    });

    function roleOptionsFor(client) {
        if (currentRole === "admin") return ["viewer", "checkin", "event_manager", "admin"];
        if (["admin", "event_manager"].includes(client.role)) return [client.role];
        return ["viewer", "checkin"];
    }

    function renderManagedClients(clients) {
        if (!managementAvailable) return;
        const ownClient = EventHubClient.getStoredClient();
        managedClientsBody.innerHTML = "";
        clients.forEach(client => {
            const row = document.createElement("tr");
            const nameCell = document.createElement("td");
            const name = document.createElement("strong");
            name.textContent = client.client_name || "Onbekend apparaat";
            const meta = document.createElement("small");
            meta.textContent = client.client_type || "Onbekend apparaat";
            nameCell.append(name, meta);

            const statusCell = document.createElement("td");
            const status = document.createElement("span");
            status.className = `client-status ${client.online ? "client-online" : "client-offline"}`;
            status.textContent = client.online ? "● Online" : "● Offline";
            statusCell.appendChild(status);

            const roleCell = document.createElement("td");
            const roleSelect = document.createElement("select");
            roleSelect.className = "client-role-select";
            roleOptionsFor(client).forEach(role => {
                const option = document.createElement("option");
                option.value = role; option.textContent = roleLabel(role);
                roleSelect.appendChild(option);
            });
            roleSelect.value = client.role;
            const ownRow = !!ownClient && ownClient.id === client.id;
            const protectedForManager = currentRole === "event_manager" && ["event_manager", "admin"].includes(client.role);
            roleSelect.disabled = ownRow || protectedForManager;
            roleSelect.addEventListener("change", async () => {
                try {
                    await EventHubClient.apiFetch(`/api/admin/clients/${client.id}/role`, {
                        method:"PATCH", json:{role:roleSelect.value},
                    });
                    managementMessage.textContent = `Rol van ${client.client_name} aangepast.`;
                    await refreshManagedClients();
                } catch (err) {
                    managementMessage.textContent = err.message;
                    await refreshManagedClients();
                }
            });
            roleCell.appendChild(roleSelect);

            const actionCell = document.createElement("td");
            const kickButton = document.createElement("button");
            kickButton.type = "button"; kickButton.className = "btn btn-danger btn-compact";
            kickButton.textContent = "Verwijderen";
            kickButton.disabled = ownRow || protectedForManager;
            kickButton.addEventListener("click", async () => {
                if (!confirm(`${client.client_name} afmelden?`)) return;
                try {
                    await EventHubClient.apiFetch(`/api/admin/clients/${client.id}`, {method:"DELETE"});
                    managementMessage.textContent = `${client.client_name} is afgemeld.`;
                    await refreshManagedClients();
                } catch (err) { managementMessage.textContent = err.message; }
            });
            actionCell.appendChild(kickButton);
            row.append(nameCell, statusCell, roleCell, actionCell);
            managedClientsBody.appendChild(row);
        });
        if (!clients.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 4; cell.textContent = "Geen clients verbonden.";
            row.appendChild(cell); managedClientsBody.appendChild(row);
        }
    }

    async function refreshManagedClients() {
        if (!managementAvailable || !canManageSession() || managementRefreshInProgress) return;
        managementRefreshInProgress = true;
        try {
            const clients = await EventHubClient.apiFetch("/api/admin/clients", {timeoutMs:5000});
            renderManagedClients(clients);
        } catch (err) {
            if (!err.isNetworkError) managementMessage.textContent = err.message;
        } finally {
            managementRefreshInProgress = false;
        }
    }

    if (refreshClientsButton) refreshClientsButton.addEventListener("click", refreshManagedClients);
    if (freezeSessionButton) freezeSessionButton.addEventListener("click", async () => {
        const nextFrozen = !frozen;
        const reason = nextFrozen ? (prompt("Reden voor pauzeren (optioneel):", "") || "") : "";
        try {
            await EventHubClient.apiFetch("/api/session/freeze", {method:"POST", json:{frozen:nextFrozen, reason}});
            await refreshState();
        } catch (err) { alert(err.message); }
    });
    if (stopCheckinButton) stopCheckinButton.addEventListener("click", async () => {
        try {
            if (checkinStopped) {
                if (!confirm(
                    "Inchecken opnieuw starten? Alle bezoekers die door het stoppen automatisch op Afwezig zijn gezet, " +
                    "worden teruggezet naar Nog niet ingecheckt."
                )) return;
                const result = await EventHubClient.apiFetch("/api/session/resume-checkin", {method:"POST"});
                managementMessage.textContent = `Inchecken hervat. ${result.restored || 0} bezoeker(s) teruggezet.`;
            } else {
                if (!confirm("Inchecken stoppen? Alle nog niet ingecheckte deelnemers worden op Afwezig gezet.")) return;
                const reason = prompt("Reden voor stoppen (optioneel):", "") || "";
                await EventHubClient.apiFetch("/api/session/stop-checkin", {method:"POST", json:{reason}});
            }
            await refreshState();
        } catch (err) { managementMessage.textContent = err.message; }
    });

    function canMarkEmergencySafe() {
        return ["checkin", "event_manager", "admin"].includes(currentRole);
    }

    function renderEmergencyPeople() {
        if (!emergencyList) return;
        const needle = (emergencySearch?.value || "").trim().toLocaleLowerCase("nl-NL");
        emergencyList.innerHTML = "";
        emergencyPeople.filter(person => !needle || [person.achternaam, person.tussenvoegsel, person.voornaam,
            person.geboortedatum, person.geboorteplaats].join(" ").toLocaleLowerCase("nl-NL").includes(needle))
            .forEach(person => {
                const item = document.createElement("li");
                item.className = `emergency-person ${person.safe ? "is-safe" : "needs-check"}`;
                const info = document.createElement("div");
                info.innerHTML = `<strong>${personLabel(person)}</strong><small>${person.geboortedatum || ""} ${person.geboorteplaats ? "· " + person.geboorteplaats : ""}</small>`;
                const action = document.createElement("button");
                action.type = "button";
                action.className = `btn ${person.safe ? "btn-secondary" : "btn-primary"}`;
                action.textContent = person.safe ? "Veilig gemeld ✓" : "Veilig melden";
                action.disabled = !canMarkEmergencySafe();
                action.addEventListener("click", async () => {
                    action.disabled = true;
                    try {
                        await EventHubClient.apiFetch(`/api/emergency/participants/${person.id}`, {
                            method:"PATCH", json:{
                                safe:!person.safe,
                                assembly_point:emergencyAssemblyPoint?.value || "",
                                team:emergencyTeam?.value || "",
                            },
                        });
                        await refreshEmergency();
                    } catch (err) { alert(err.message); action.disabled = false; }
                });
                item.append(info, action); emergencyList.appendChild(item);
            });
        if (!emergencyList.children.length) {
            emergencyList.innerHTML = '<li class="emergency-empty">Geen personen gevonden.</li>';
        }
    }

    async function refreshEmergency(showNotice = false) {
        if (!EventHubClient.getStoredClient()) return;
        const data = await EventHubClient.apiFetch("/api/emergency", {timeoutMs:5000});
        const wasActive = emergencyActive;
        emergencyActive = !!data.active;
        emergencyIncidentId = data.incident_id || "";
        emergencyPeople = data.participants || [];
        if (emergencyInstruction) emergencyInstruction.textContent = data.instruction || "Volg de instructies van de eventmanager of beheerder.";
        if (emergencyTotal) emergencyTotal.textContent = String(data.total || 0);
        if (emergencySafe) emergencySafe.textContent = String(data.safe || 0);
        if (emergencyUnaccounted) emergencyUnaccounted.textContent = String(data.unaccounted || 0);
        if (editEmergencyInstructionButton) editEmergencyInstructionButton.classList.toggle("hidden", !canManageSession() || !emergencyActive);
        if (emergencyEndButton) emergencyEndButton.classList.toggle("hidden", !canManageSession() || !emergencyActive);
        if (emergencyCardExportButton) emergencyCardExportButton.classList.toggle("hidden", !canManageSession() || !emergencyActive);
        if (emergencyExportButton) emergencyExportButton.classList.toggle("hidden", !canManageSession() || !data.incident_id);
        if (emergencySessionButton) {
            emergencySessionButton.textContent = emergencyActive ? "Calamiteitenmodus beëindigen" : "Calamiteitenmodus starten";
            emergencySessionButton.classList.toggle("btn-danger", !emergencyActive);
            emergencySessionButton.classList.toggle("btn-secondary", emergencyActive);
        }
        renderEmergencyPeople();
        applyManagerTab();
        const seenKey = emergencyIncidentId ? `eventhub_emergency_seen_${emergencyIncidentId}` : "";
        if (emergencyActive && (showNotice || (seenKey && !sessionStorage.getItem(seenKey)))) {
            emergencyModalInstruction.textContent = data.instruction || "Volg de instructies van de eventmanager of beheerder.";
            emergencyModal.classList.remove("hidden");
            if (seenKey) sessionStorage.setItem(seenKey, "1");
        }
        if (wasActive && !emergencyActive) emergencyEndedModal.classList.remove("hidden");
    }

    if (emergencySearch) emergencySearch.addEventListener("input", renderEmergencyPeople);
    document.getElementById("emergencyModalClose")?.addEventListener("click", () => emergencyModal.classList.add("hidden"));
    document.getElementById("emergencyEndedClose")?.addEventListener("click", () => emergencyEndedModal.classList.add("hidden"));
    async function toggleEmergencyMode() {
        try {
            if (emergencyActive) {
                const remaining = Number(emergencyUnaccounted?.textContent || 0);
                if (!confirm(`Calamiteitenmodus beëindigen? Nog te controleren: ${remaining} persoon/personen.`)) return;
                await EventHubClient.apiFetch("/api/emergency/end", {method:"POST"});
            } else {
                if (!confirm("Calamiteitenmodus starten? Alle verbonden apparaten ontvangen direct een melding.")) return;
                const instruction = prompt("Actuele instructie voor medewerkers:", "Volg de instructies van de eventmanager of beheerder.");
                if (instruction === null) return;
                await EventHubClient.apiFetch("/api/emergency/start", {method:"POST", json:{instruction}});
            }
            await refreshEmergency(true);
        } catch (err) { managementMessage.textContent = err.message; }
    }
    if (emergencySessionButton) emergencySessionButton.addEventListener("click", toggleEmergencyMode);
    if (emergencyEndButton) emergencyEndButton.addEventListener("click", toggleEmergencyMode);
    if (editEmergencyInstructionButton) editEmergencyInstructionButton.addEventListener("click", async () => {
        const instruction = prompt("Nieuwe actuele instructie:", emergencyInstruction.textContent || "");
        if (instruction === null) return;
        try {
            await EventHubClient.apiFetch("/api/emergency/instruction", {method:"PATCH", json:{instruction}});
            await refreshEmergency(true);
        } catch (err) { alert(err.message); }
    });
    async function downloadEmergencyExport(event) {
        event.preventDefault();
        try { await EventHubClient.downloadFile("/api/emergency/export", "EventHub-calamiteitenregistratie.xlsx"); }
        catch (err) { alert(err.message); }
    }
    if (emergencyExportButton) emergencyExportButton.addEventListener("click", downloadEmergencyExport);
    if (emergencyCardExportButton) emergencyCardExportButton.addEventListener("click", downloadEmergencyExport);

    function populateSettings(client) {
        if (!client) return;
        settingsClientName.value = client.client_name || "";
        settingsRole.value = roleLabel(client.role);
        settingsTheme.value = EventHubAppearance.themePreference();
        if (settingsHandedness) settingsHandedness.value = handednessPreference();
        settingsWakeLock.checked = EventHubAppearance.wakeEnabled();
        settingsWakeLock.disabled = !EventHubAppearance.wakeSupported();
        wakeLockStatus.textContent = EventHubAppearance.wakeSupported()
            ? "Actief zolang de livesessie zichtbaar is."
            : "Niet beschikbaar in deze browser of verbinding.";
        settingsMessage.textContent = "";
    }

    function setSettingsOpen(open) {
        settingsMenu.classList.toggle("hidden", !open);
        settingsButton.setAttribute("aria-expanded", open ? "true" : "false");
        if (open) populateSettings(EventHubClient.getStoredClient());
    }

    settingsButton.addEventListener("click", event => {
        event.stopPropagation();
        setSettingsOpen(settingsMenu.classList.contains("hidden"));
    });
    settingsMenu.addEventListener("click", event => event.stopPropagation());
    document.addEventListener("click", () => setSettingsOpen(false));
    document.addEventListener("keydown", event => { if (event.key === "Escape") setSettingsOpen(false); });

    function showStopNotice(reason = "") {
        stopNoticeShown = true;
        stopModalMessage.textContent = "De beheerder heeft het inchecken beëindigd." +
            (reason ? `\n\nReden: ${reason}` : "");
        stopModal.classList.remove("hidden");
    }

    document.getElementById("stopModalClose").addEventListener("click", () => stopModal.classList.add("hidden"));

    function personLabel(p) {
        const given = [p.voornaam, p.tussenvoegsel].filter(Boolean).join(" ");
        return p.achternaam && given ? `${p.achternaam}, ${given}` : (p.achternaam || given);
    }

    function surnameSort(a, b) {
        const key = p => [p.achternaam, p.tussenvoegsel, p.voornaam].map(v => (v || "").toLocaleLowerCase("nl-NL"));
        const ak=key(a), bk=key(b);
        for (let i=0;i<ak.length;i++) { const c=ak[i].localeCompare(bk[i], "nl-NL", {sensitivity:"base"}); if(c) return c; }
        return 0;
    }

    function surnameInitial(participant) {
        const surname = String(participant.achternaam || "").trim();
        if (!surname) return "#";
        const initial = surname.normalize("NFD").replace(/[\u0300-\u036f]/g, "").charAt(0).toUpperCase();
        return /^[A-Z]$/.test(initial) ? initial : "#";
    }

    function showAlphabetBubble(letter) {
        if (!alphabetBubble) return;
        alphabetBubble.textContent = letter;
        alphabetBubble.classList.remove("hidden");
        clearTimeout(alphabetBubbleTimer);
        alphabetBubbleTimer = setTimeout(() => alphabetBubble.classList.add("hidden"), 500);
    }

    function jumpToLetter(letter) {
        const target = resultsList.querySelector(`[data-surname-letter="${letter}"]`);
        if (!target) return;
        const top = resultsList.scrollTop + target.getBoundingClientRect().top - resultsList.getBoundingClientRect().top;
        resultsList.scrollTo({top: Math.max(0, top), behavior:"auto"});
        showAlphabetBubble(letter);
    }

    function renderAlphabetIndex(availableLetters) {
        if (!alphabetIndex) return;
        alphabetIndex.innerHTML = "";
        ALPHABET.forEach(letter => {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = letter;
            button.dataset.letter = letter;
            button.className = "alphabet-letter";
            button.disabled = !availableLetters.has(letter);
            button.setAttribute("aria-label", `Achternamen met ${letter}`);
            alphabetIndex.appendChild(button);
        });
        alphabetIndex.classList.toggle("hidden", availableLetters.size === 0);
    }

    let keyboardSelectedIndex = -1;
    let keyboardSelectionArmed = false;
    let keyboardActionLockedUntil = 0;

    function clearKeyboardSelection() {
        keyboardSelectedIndex = -1;
        keyboardSelectionArmed = false;
        resultsList.querySelectorAll(".result-row.keyboard-selected").forEach(row => {
            row.classList.remove("keyboard-selected");
            row.removeAttribute("aria-current");
        });
    }

    function selectKeyboardResult(direction) {
        const rows = [...resultsList.querySelectorAll(".result-row")];
        if (!rows.length) { clearKeyboardSelection(); return; }
        if (!keyboardSelectionArmed || keyboardSelectedIndex < 0 || keyboardSelectedIndex >= rows.length) {
            keyboardSelectedIndex = direction > 0 ? 0 : rows.length - 1;
        } else {
            keyboardSelectedIndex = Math.max(0, Math.min(rows.length - 1, keyboardSelectedIndex + direction));
        }
        rows.forEach((row, index) => {
            const selected = index === keyboardSelectedIndex;
            row.classList.toggle("keyboard-selected", selected);
            if (selected) row.setAttribute("aria-current", "true");
            else row.removeAttribute("aria-current");
        });
        keyboardSelectionArmed = true;
        rows[keyboardSelectedIndex].scrollIntoView({block:"nearest", behavior:"auto"});
    }

    async function activateKeyboardCheckin() {
        if (!keyboardSelectionArmed || Date.now() < keyboardActionLockedUntil) return;
        const rows = [...resultsList.querySelectorAll(".result-row")];
        const row = rows[keyboardSelectedIndex];
        const button = row?.querySelector('button[data-action="checkin"]:not(:disabled)');
        if (!button) return;
        // Disarm before dispatching the action: a second Space cannot immediately
        // undo/check out the same person after the result list refreshes.
        keyboardSelectionArmed = false;
        keyboardActionLockedUntil = Date.now() + 600;
        button.click();
    }

    function renderResults(participants) {
        clearKeyboardSelection();
        resultsList.innerHTML = "";
        const availableLetters = new Set();
        if (!participants.length) {
            renderAlphabetIndex(availableLetters);
            searchHint.textContent = "Geen deelnemers gevonden.";
            searchHint.classList.remove("hidden");
            return;
        }
        searchHint.classList.add("hidden");
        [...participants].sort(surnameSort).forEach((participant) => {
            const item = document.createElement("li");
            item.className = "result-row";
            const initial = surnameInitial(participant);
            item.dataset.surnameLetter = initial;
            if (initial !== "#") availableLetters.add(initial);
            const present = participant.attendance_status === "present";
            const checkedOut = participant.attendance_status === "checked_out";
            const absent = participant.attendance_status === "absent";
            let action = "checkin", actionLabel = "Inchecken", buttonClass = "btn-primary";
            if (present) {
                action = checkoutRequired ? "checkout" : "undo";
                actionLabel = checkoutRequired ? "Uitchecken" : "Ongedaan maken";
                buttonClass = "btn-danger";
            }
            const disabled = currentRole === "viewer" || frozen || checkedOut || absent || (checkinStopped && !present);
            const statusLabel = present ? "Binnen" : checkedOut ? "Uitgecheckt" : absent ? "Afwezig" : "Nog niet ingecheckt";
            item.innerHTML = `
                <div class="result-info">
                    <div class="result-name">${personLabel(participant)}</div>
                    <div class="result-meta">${participant.temporary_walkin ? (participant.telefoonnummer || "Geen telefoonnummer") + '<span class="walkin-badge">Niet vooraf aangemeld</span>' : (participant.geboortedatum || "")}</div>
                </div>
                <div class="result-actions">
                    <span class="status-pill status-${participant.attendance_status}">${statusLabel}</span>
                    <button class="btn ${buttonClass}" data-id="${participant.id}" data-action="${action}" ${disabled ? "disabled" : ""}>
                        ${actionLabel}
                    </button>
                </div>`;
            resultsList.appendChild(item);
        });
        renderAlphabetIndex(availableLetters);
    }

    if (alphabetIndex) {
        alphabetIndex.addEventListener("click", event => {
            const button = event.target.closest("button[data-letter]:not(:disabled)");
            if (button) jumpToLetter(button.dataset.letter);
        });
        const selectLetterAtPoint = (x, y) => {
            const button = document.elementFromPoint(x, y)?.closest("button[data-letter]:not(:disabled)");
            if (button && alphabetIndex.contains(button)) jumpToLetter(button.dataset.letter);
        };
        alphabetIndex.addEventListener("pointerdown", event => {
            alphabetIndex.setPointerCapture?.(event.pointerId);
            selectLetterAtPoint(event.clientX, event.clientY);
            event.preventDefault();
        });
        alphabetIndex.addEventListener("pointermove", event => {
            if (event.buttons || event.pointerType === "touch") selectLetterAtPoint(event.clientX, event.clientY);
        });
    }

    // Full A-Z roster (sorted by achternaam server-side) shown immediately;
    // typing narrows it down further. No minimum character count.
    async function runSearch(query) {
        if (currentRole === "viewer") return;
        const sequence = ++searchSequence;
        try {
            const results = await EventHubClient.apiFetch(`/api/participants/search?q=${encodeURIComponent(query.trim())}&limit=1000`);
            if (sequence !== searchSequence) return;
            await EventHubClient.cacheParticipants(results);
            renderResults(results);
            serverReachable = true;
            await updateQueueStatus();
        } catch (err) {
            if (sequence !== searchSequence) return;
            const cached = (await EventHubClient.cachedParticipants()) || [];
            const needle = query.trim().toLowerCase();
            const filtered = cached.filter(p => !needle || [p.voornaam,p.tussenvoegsel,p.achternaam,p.geboortedatum,p.geboorteplaats].join(" ").toLowerCase().includes(needle));
            renderResults(filtered);
            if (err.isNetworkError) {
                serverReachable = false;
                updateQueueStatus();
            } else {
                connectionStatus.textContent = `● Verbonden · ${err.message}`;
                connectionStatus.classList.remove("connection-offline");
            }
        }
    }

    async function updateQueueStatus() {
        const queue = await EventHubClient.queuedActions();
        const conflicts = queue.filter(item => item.conflict).length;
        clearQueueButton.classList.toggle("hidden", queue.length === 0);
        if (!serverReachable) {
            connectionStatus.textContent = `● Offline · ${queue.length} actie(s) wachten`;
            connectionStatus.classList.add("connection-offline");
        } else if (conflicts) {
            connectionStatus.textContent = `● Verbonden · ${conflicts} actie(s) vereisen controle`;
            connectionStatus.classList.remove("connection-offline");
            connectionStatus.classList.add("connection-review");
            connectionStatus.setAttribute("role", "button");
            connectionStatus.tabIndex = 0;
        } else if (queue.length) {
            connectionStatus.textContent = `● Verbonden · ${queue.length} actie(s) synchroniseren…`;
            connectionStatus.classList.remove("connection-offline");
        } else {
            connectionStatus.textContent = "● Verbonden · alles bijgewerkt";
            connectionStatus.classList.remove("connection-offline");
        }
        if (!conflicts || !serverReachable) {
            connectionStatus.classList.remove("connection-review");
            connectionStatus.removeAttribute("role");
            connectionStatus.removeAttribute("tabindex");
        }
    }

    connectionStatus.addEventListener("click", openQueueReview);
    connectionStatus.addEventListener("keydown", event => {
        if ((event.key === "Enter" || event.key === " ") && connectionStatus.classList.contains("connection-review")) {
            event.preventDefault(); openQueueReview();
        }
    });
    if (queueReviewAvailable) {
        queueReviewClose.addEventListener("click", () => queueReviewModal.classList.add("hidden"));
        queueReviewModal.addEventListener("click", event => {
            if (event.target === queueReviewModal) queueReviewModal.classList.add("hidden");
        });
    }

    clearQueueButton.addEventListener("click", async () => {
        const queue = await EventHubClient.queuedActions();
        if (!queue.length) return;
        if (!confirm(`Wilt u ${queue.length} lokale wachtrijactie(s) wissen? Handelingen die nog niet naar de server zijn gestuurd gaan dan verloren.`)) return;
        await EventHubClient.clearQueuedActions();
        await updateQueueStatus();
    });

    document.getElementById("saveSettingsButton").addEventListener("click", async () => {
        const client = EventHubClient.getStoredClient();
        if (!client) return;
        settingsMessage.textContent = "Opslaan…";
        EventHubAppearance.applyTheme(settingsTheme.value);
        if (touchLayout && settingsHandedness) applyHandedness(settingsHandedness.value);
        else applyHandedness("right", false);
        EventHubAppearance.setWakeEnabled(settingsWakeLock.checked);
        if (settingsWakeLock.checked) await EventHubAppearance.requestWakeLock();
        try {
            const updated = await EventHubClient.apiFetch(`/api/clients/${client.id}/preferences`, {
                method: "PATCH",
                json: {client_name: settingsClientName.value.trim()},
            });
            EventHubClient.storeClient(updated);
            currentRole = updated.role;
            clientLabel.textContent = `${updated.client_name} (${roleLabel(updated.role)})`;
            settingsMessage.textContent = "Instellingen opgeslagen.";
            renderResults(await EventHubClient.cachedParticipants() || []);
            updateManagementVisibility();
        } catch (err) {
            settingsMessage.textContent = err.message;
        }
    });

    document.getElementById("syncNowButton").addEventListener("click", async () => {
        settingsMessage.textContent = "Synchroniseren…";
        await refreshState();
        settingsMessage.textContent = serverReachable ? "Synchronisatie voltooid." : "Server niet bereikbaar.";
    });

    async function refreshState() {
        if (!EventHubClient.getStoredClient()) return;
        try {
            const state = await EventHubClient.apiFetch("/api/session/state", {timeoutMs: 5000});
            serverReachable = true;
            frozen = !!state.frozen;
            checkoutRequired = !!state.checkout_required;
            checkinStopped = !!state.checkin_stopped;
            if (freezeSessionButton) freezeSessionButton.textContent = frozen ? "Inchecken hervatten" : "Inchecken pauzeren";
            if (stopCheckinButton) {
                stopCheckinButton.textContent = checkinStopped ? "Inchecken hervatten" : "Inchecken stoppen";
                stopCheckinButton.classList.toggle("btn-danger", !checkinStopped);
                stopCheckinButton.classList.toggle("btn-secondary", checkinStopped);
            }
            freezeBanner.textContent = "⏸ Inchecken tijdelijk gepauzeerd" + (state.reason ? ` — ${state.reason}` : "");
            freezeBanner.classList.toggle("hidden", !frozen);
            stopBanner.textContent = "⛔ Inchecken is beëindigd door de beheerder" +
                (state.checkin_stopped_reason ? ` — ${state.checkin_stopped_reason}` : "");
            stopBanner.classList.toggle("hidden", !checkinStopped);
            if (checkinStopped && !stopNoticeShown) {
                showStopNotice(state.checkin_stopped_reason || "");
            }
            if (!checkinStopped) stopNoticeShown = false;
            if (!checkinCard.classList.contains("hidden")) await runSearch(searchInput.value);
            if (!frozen) await syncQueue();
            if (canManageSession()) await refreshManagedClients();
            await refreshEmergency();
        } catch (err) {
            if (err.isNetworkError) { serverReachable = false; await updateQueueStatus(); }
            else if (err.status === 401) { requireNewLogin("Deze sessie is afgesloten. Meld opnieuw aan om met een nieuwe sessie te verbinden.", true); }
        }
    }

    async function syncQueue() {
        if (syncInProgress) return;
        syncInProgress = true;
        try {
        const queue = (await EventHubClient.queuedActions()).sort((a,b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
        for (const item of queue) {
            if (item.conflict) continue;
            try {
                await EventHubClient.apiFetch(`/api/participants/${item.participantId}/${item.action}`,
                    { method:"POST", operationId:item.id, operationCreatedAt:item.createdAt });
                serverReachable = true;
                await EventHubClient.removeQueuedAction(item.id);
            } catch (err) {
                if (err.isNetworkError) { serverReachable = false; break; }
                serverReachable = true;
                if (err.message.toLowerCase().includes("gepauzeerd")) { frozen = true; break; }
                if (err.status || err.message.toLowerCase().includes("conflict") || err.message.toLowerCase().includes("beëindigd")) {
                    item.conflict = true; await EventHubClient.queueAction(item);
                }
            }
        }
        await updateQueueStatus();
        } finally {
            syncInProgress = false;
        }
    }

    let searchTimer = null;
    searchInput.addEventListener("input", () => {
        clearKeyboardSelection();
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => runSearch(searchInput.value), 200);
    });

    searchInput.addEventListener("keydown", event => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (event.repeat) return;
            selectKeyboardResult(event.key === "ArrowDown" ? 1 : -1);
            return;
        }
        if (event.code === "Space" && keyboardSelectionArmed) {
            event.preventDefault();
            if (event.repeat) return;
            activateKeyboardCheckin();
        }
        // Enter deliberately has no check-in shortcut.
    });

    resultsList.addEventListener("click", async (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        button.disabled = true;
        const { id, action } = button.dataset;
        if (frozen) { alert("Inchecken is tijdelijk gepauzeerd door de beheerder."); button.disabled=false; return; }
        const operationId = crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
        try {
            await EventHubClient.apiFetch(`/api/participants/${id}/${action}`, { method: "POST", operationId });
            serverReachable = true;
            await runSearch(searchInput.value);
        } catch (err) {
            if (err.message.toLowerCase().includes("gepauzeerd") || err.message.toLowerCase().includes("beëindigd")) { await refreshState(); alert(err.message); }
            else if (err.isNetworkError) {
                serverReachable = false;
                await EventHubClient.queueAction({id:operationId, participantId:id, action, createdAt:new Date().toISOString()});
                const cached = (await EventHubClient.cachedParticipants()) || [];
                const participant = cached.find(p => p.id === id);
                if (participant) participant.attendance_status = action === "checkin" ? "present" : action === "checkout" ? "checked_out" : "not_checked_in";
                await EventHubClient.cacheParticipants(cached); await runSearch(searchInput.value); await updateQueueStatus();
            } else {
                connectionStatus.textContent = `● Verbonden · ${err.message}`;
                connectionStatus.classList.remove("connection-offline");
                alert(err.message);
            }
        } finally {
            button.disabled = false;
        }
    });

    function setWalkinOpen(open) {
        if (!walkinModal) return;
        walkinModal.classList.toggle("hidden", !open);
        if (open) { walkinName.value=""; walkinPhone.value=""; walkinMessage.textContent=""; setTimeout(() => walkinName.focus(), 0); }
    }
    addWalkinButton?.addEventListener("click", () => { if (canManageSession()) setWalkinOpen(true); });
    document.getElementById("walkinCancel")?.addEventListener("click", () => setWalkinOpen(false));
    walkinModal?.addEventListener("click", event => { if (event.target === walkinModal) setWalkinOpen(false); });
    document.getElementById("walkinSave")?.addEventListener("click", async () => {
        if (!canManageSession()) return;
        const name = walkinName.value.trim();
        if (!name) { walkinMessage.textContent = "Vul een naam in."; return; }
        const button = document.getElementById("walkinSave");
        button.disabled = true; walkinMessage.textContent = "Toevoegen…";
        try {
            await EventHubClient.apiFetch("/api/participants/walkin", {method:"POST", json:{name, phone:walkinPhone.value.trim()}});
            setWalkinOpen(false);
            await runSearch(searchInput.value);
        } catch (err) { walkinMessage.textContent = err.message; }
        finally { button.disabled = false; }
    });

    function showCheckinScreen(client) {
        registerCard.classList.add("hidden");
        checkinCard.classList.add("hidden");
        if (viewerWaitingCard) viewerWaitingCard.classList.add("hidden");
        statusBar.classList.remove("hidden");
        currentRole = client.role || "viewer";
        clientLabel.textContent = `${client.client_name} (${roleLabel(currentRole)})`;
        settingsButton.classList.remove("hidden");
        populateSettings(client);
        updateManagementVisibility();
        searchInput.value = "";
        if (currentRole !== "viewer") { runSearch(""); searchInput.focus(); }
        EventHubAppearance.requestWakeLock();
    }

    document.getElementById("connectButton").addEventListener("click", async () => {
        registerError.textContent = "";
        const name = document.getElementById("clientNameInput").value.trim() || "Onbekend apparaat";
        const role = "viewer";
        const eventCode = document.getElementById("eventCodeInput").value.trim();
        if (!/^[0-9]{4}$/.test(eventCode)) {
            registerError.textContent = "Vul de 4-cijferige sessiecode in.";
            return;
        }
        try {
            const selectedHand = touchLayout
                ? (document.querySelector('input[name="handedness"]:checked')?.value || "right")
                : "right";
            applyHandedness(selectedHand, touchLayout);
            const client = await EventHubClient.registerClient(name, role, eventCode);
            showCheckinScreen(client);
        } catch (err) {
            registerError.textContent = err.message;
        }
    });

    document.getElementById("logoutButton").addEventListener("click", async () => {
        await EventHubAppearance.releaseWakeLock();
        await EventHubClient.logout();
        checkinCard.classList.add("hidden");
        if (viewerWaitingCard) viewerWaitingCard.classList.add("hidden");
        statusBar.classList.add("hidden");
        settingsButton.classList.add("hidden");
        if (clientManagementCard) clientManagementCard.classList.add("hidden");
        if (emergencyCard) emergencyCard.classList.add("hidden");
        if (managerTabs) managerTabs.classList.add("hidden");
        setSettingsOpen(false);
        registerCard.classList.remove("hidden");
        document.getElementById("eventCodeInput").value = "";
        registerError.textContent = "";
    });

    // Resume an already-registered client on this device without asking again.
    const existing = EventHubClient.getStoredClient();
    updateHandednessVisibility();
    applyHandedness(touchLayout ? handednessPreference() : "right", false);
    if (existing) {
        showCheckinScreen(existing);
        EventHubClient.startHeartbeat();
    }

    setInterval(refreshState, 4000);

    EventHubClient.subscribeToLiveUpdates((event) => {
        if (["participant_checked_in", "participant_checked_out", "participant_checkin_undone", "participant_walkin_added"].includes(event.type)) {
            if (!checkinCard.classList.contains("hidden")) {
                runSearch(searchInput.value);
            }
        }
        if (event.type === "session_freeze_changed") refreshState();
        if (event.type === "checkin_stopped") {
            checkinStopped = true;
            stopBanner.textContent = "⛔ Inchecken is beëindigd door de beheerder" + (event.reason ? ` — ${event.reason}` : "");
            stopBanner.classList.remove("hidden");
            showStopNotice(event.reason || "");
            if (!checkinCard.classList.contains("hidden")) runSearch(searchInput.value);
        }
        if (event.type === "checkin_resumed") {
            checkinStopped = false; stopNoticeShown = false;
            stopBanner.classList.add("hidden"); stopModal.classList.add("hidden");
            connectionStatus.textContent = "● Verbonden · inchecken hervat";
            serverReachable = true;
            connectionStatus.classList.remove("connection-offline");
            if (!checkinCard.classList.contains("hidden")) runSearch(searchInput.value);
        }
        if (["emergency_started", "emergency_instruction_updated", "emergency_participant_updated", "emergency_ended"].includes(event.type)) {
            refreshEmergency(event.type === "emergency_started" || event.type === "emergency_instruction_updated");
        }
        if (event.type === "client_kicked") {
            const client=EventHubClient.getStoredClient();
            if (client && event.client_id===client.id) {
                EventHubAppearance.releaseWakeLock();
                EventHubClient.stopHeartbeat(); EventHubClient.clearStoredClient();
                alert("Deze client is door de beheerder afgemeld."); location.reload();
            }
        }
        if (event.type === "server_stopped") {
            requireNewLogin("De server is gestopt. Meld opnieuw aan zodra de server weer beschikbaar is.", true);
        }
        if (event.type === "client_role_changed") {
            const client=EventHubClient.getStoredClient();
            if (client && event.client_id===client.id) {
                client.role=event.role; EventHubClient.storeClient(client); currentRole=event.role;
                clientLabel.textContent=`${client.client_name} (${roleLabel(client.role)})`;
                populateSettings(client); updateManagementVisibility(); if (currentRole !== "viewer") runSearch(searchInput.value);
            }
        }
        if (event.type === "client_profile_changed") {
            const client=EventHubClient.getStoredClient();
            if (client && event.client_id===client.id) {
                client.client_name=event.client_name; client.role=event.role;
                EventHubClient.storeClient(client); currentRole=event.role;
                clientLabel.textContent=`${client.client_name} (${roleLabel(client.role)})`;
                populateSettings(client); updateManagementVisibility(); if (currentRole !== "viewer") runSearch(searchInput.value);
            }
        }
        if (["client_connected", "client_disconnected", "client_kicked", "client_role_changed", "client_profile_changed"].includes(event.type)) {
            refreshManagedClients();
        }
    }, reachable => {
        if (!reachable) {
            serverReachable = false;
            updateQueueStatus();
        } else {
            refreshState();
        }
    });
    window.addEventListener("online", refreshState);
})();
