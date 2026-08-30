(() => {
    const includeToggle = document.getElementById("includeIntroduceesToggle");
    const insideOnlyToggle = document.getElementById("insideOnlyToggle");
    let serverStartedAt = null;

    function renderElapsedTime() {
        const element = document.getElementById("sessionElapsedTime");
        if (!element) return;
        if (!serverStartedAt) {
            element.textContent = "00:00:00";
            return;
        }
        const started = new Date(serverStartedAt);
        const elapsed = Math.max(0, Math.floor((Date.now() - started.getTime()) / 1000));
        const hours = Math.floor(elapsed / 3600);
        const minutes = Math.floor((elapsed % 3600) / 60);
        const seconds = elapsed % 60;
        element.textContent = `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }

    function includeIntroducees() {
        return includeToggle ? includeToggle.checked : true;
    }

    function insideOnly() {
        return insideOnlyToggle ? insideOnlyToggle.checked : false;
    }

    async function refreshSessionActivity() {
        const payload = await EventHubClient.apiFetch("/api/session/activity?limit=12");
        const state = payload.state || {};
        const emergency = payload.emergency || {active:false};
        serverStartedAt = payload.server_started_at || null;
        renderElapsedTime();
        const windowElement = document.getElementById("sessionStatusWindow");
        const textElement = document.getElementById("sessionStatusText");
        if (!windowElement || !textElement) return;
        if (emergency.active) {
            textElement.textContent = `Calamiteitenmodus · ${emergency.unaccounted || 0} nog te controleren`;
            windowElement.className = "session-status-window state-danger";
        } else if (state.checkin_stopped) {
            textElement.textContent = "Inchecken gestopt";
            windowElement.className = "session-status-window state-danger";
        } else if (state.frozen) {
            textElement.textContent = "Inchecken gepauzeerd";
            windowElement.className = "session-status-window state-warning";
        } else {
            textElement.textContent = "Inchecken actief";
            windowElement.className = "session-status-window state-success";
        }
    }

    async function refreshOverview() {
        const overview = await EventHubClient.apiFetch(`/api/statistics/overview?include_introducees=${includeIntroducees()}`);
        document.getElementById("kpiRegistered").textContent = overview.registered;
        document.getElementById("kpiPresent").textContent = overview.present;
        document.getElementById("kpiExpected").textContent = overview.expected;
        document.getElementById("kpiInside").textContent = overview.inside;
        document.getElementById("kpiTurnout").textContent = `${overview.turnout_percentage}%`;

        EventHubCharts.donutChart(document.getElementById("chartAttendance"), [
            { label: "Aanwezig geweest", value: overview.present, color: "#1fb77a" },
            { label: "Afwezig", value: overview.absent, color: "#c9385a" },
            { label: "Nog verwacht", value: overview.expected, color: "#6c2cff" },
        ]);
    }

    async function refreshBreakdown(dimension, elementId) {
        const data = await EventHubClient.apiFetch(`/api/statistics/${dimension}?include_introducees=${includeIntroducees()}&inside_only=${insideOnly()}`);
        EventHubCharts.barChart(document.getElementById(elementId), data, { valueKey: "registered", labelKey: "label" });
    }

    async function refreshTimeline() {
        const timeline = await EventHubClient.apiFetch("/api/statistics/attendance");
        EventHubCharts.lineChart(document.getElementById("chartTimeline"), timeline);
        if (timeline.length) {
            document.getElementById("lastCheckin").textContent = `Laatste check-in: ${timeline[timeline.length - 1].time}`;
        }
    }

    async function refreshClients() {
        const clientsElement = document.getElementById("chartClients");
        if (clientsElement) {
            const clients = await EventHubClient.apiFetch("/api/statistics/clients");
            EventHubCharts.barChart(clientsElement, clients, { valueKey: "checkin_count", labelKey: "client_name" });
        }
        const allClients = await EventHubClient.apiFetch("/api/clients");
        const online = allClients.filter((c) => c.online).length;
        document.getElementById("onlineClients").textContent = `${online} client${online === 1 ? "" : "s"} online`;
    }

    async function refreshAll() {
        try {
            await Promise.all([refreshOverview(), refreshSessionActivity(), refreshBreakdown("education", "chartEducation"),
                refreshBreakdown("profile", "chartProfile"), refreshBreakdown("gender", "chartGender"),
                refreshBreakdown("age", "chartAge"), refreshTimeline(), refreshClients()]);
        } catch (err) {
            console.error("Kon dashboard niet verversen:", err);
        }
    }

    if (includeToggle) {
        includeToggle.addEventListener("change", refreshAll);
    }
    if (insideOnlyToggle) {
        insideOnlyToggle.addEventListener("change", refreshAll);
    }

    refreshAll();
    renderElapsedTime();
    setInterval(renderElapsedTime, 1000);
    setInterval(refreshAll, 20000); // safety-net poll in case an SSE event is missed
    EventHubClient.subscribeToLiveUpdates((event) => {
        if (["participant_checked_in", "participant_checked_out", "participant_checkin_undone",
             "checkin_stopped", "checkin_resumed", "statistics_updated", "client_connected",
             "client_disconnected", "client_kicked", "client_role_changed", "client_profile_changed",
             "session_freeze_changed", "emergency_started", "emergency_instruction_updated",
             "emergency_participant_updated", "emergency_ended"].includes(event.type)) {
            refreshAll();
        }
    });
})();
