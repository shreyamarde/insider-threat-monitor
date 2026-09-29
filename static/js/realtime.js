/*
 * Real-time client (Socket.IO).
 *  - every signed-in user: connection status + heartbeat (online/offline presence)
 *  - managers: instant alert notifications, live activity events, presence updates
 * Page scripts subscribe to DOM events: itm:activity, itm:alert, itm:alert-changed,
 * itm:presence, itm:reconnect.
 */
(function () {
    "use strict";
    const { esc, fmtTime, badge, toast } = window.ITM;
    const statusEl = document.getElementById("live-status");
    const isManager = document.body.dataset.role === "manager";
    const heartbeatMs = (Number(document.body.dataset.heartbeat) || 25) * 1000;
    const emit = (name, detail) => document.dispatchEvent(new CustomEvent(name, { detail }));

    function setStatus(state, text) {
        if (!statusEl) return;
        statusEl.className = `live-status ${state}`;
        statusEl.querySelector(".label").textContent = text;
        statusEl.title = state === "connected" ? "Real-time updates active" : "Real-time updates unavailable — retrying";
    }

    if (typeof io === "undefined") {
        setStatus("disconnected", "Offline");
        console.warn("Socket.IO client failed to load; live updates disabled.");
        return;
    }

    const socket = io({ reconnectionDelayMax: 5000 });
    let heartbeat = null;
    let everConnected = false;

    socket.on("connect", () => {
        setStatus("connected", "Live");
        if (everConnected) emit("itm:reconnect");  // catch up on anything missed
        everConnected = true;
        clearInterval(heartbeat);
        heartbeat = setInterval(() => socket.emit("heartbeat", {}), heartbeatMs);
    });
    socket.on("disconnect", () => { setStatus("disconnected", "Reconnecting…"); clearInterval(heartbeat); });
    socket.on("connect_error", () => setStatus("disconnected", "Reconnecting…"));

    socket.on("account:disabled", (data) => {
        alert((data && data.message) || "Your account has been disabled.");
        window.location.href = "/";
    });

    if (!isManager) return;

    // --------------------------------------------------- manager only
    const countEl = document.getElementById("notif-count");
    const navCount = document.getElementById("nav-alert-count");
    const panel = document.getElementById("notif-panel");
    const list = document.getElementById("notif-list");
    const baseTitle = document.title;
    let newAlerts = [];

    function renderCount(n) {
        [countEl, navCount].forEach((el) => { if (el) { el.textContent = n > 99 ? "99+" : n; el.hidden = n === 0; } });
        document.title = n ? `(${n}) ${baseTitle}` : baseTitle;
    }

    function renderList() {
        if (!list) return;
        if (!newAlerts.length) { list.innerHTML = `<div class="empty">No new alerts</div>`; return; }
        list.innerHTML = newAlerts.slice(0, 10).map((a) => `
            <div class="notif-item" data-view-alert="${a.id}">
                <div>${badge.sev(a.severity)}</div>
                <div><strong>${esc(a.employee_id)}</strong> · ${esc(a.title)}
                <p>${esc(a.message)}</p><small>${esc(fmtTime(a.timestamp))}</small></div>
            </div>`).join("");
    }

    async function loadNewAlerts() {
        try {
            const res = await window.ITM.api("GET", "/api/manager/alerts?status=NEW&per_page=10");
            newAlerts = res.items;
            renderCount(res.total);
            renderList();
        } catch (e) { /* shown elsewhere */ }
    }

    const ICON = { LOW: "🔵", MEDIUM: "🟠", HIGH: "🔴", CRITICAL: "🚨" };
    const RANK = { LOW: 0, MEDIUM: 1, HIGH: 2, CRITICAL: 3 };

    // One suspicious action can raise several alerts at once (e.g. unauthorized
    // access + privilege escalation + level escalation). Group alerts that arrive
    // together for the same employee into a single notification.
    const pending = new Map();
    function queueToast(a) {
        const key = a.employee_id;
        if (!pending.has(key)) {
            pending.set(key, []);
            setTimeout(() => { alertToast(pending.get(key)); pending.delete(key); }, 700);
        }
        pending.get(key).push(a);
    }

    function alertToast(group) {
        const box = document.getElementById("toasts");
        if (!box || !group.length) return;
        const top = group.reduce((m, a) => (RANK[a.severity] > RANK[m.severity] ? a : m), group[0]);
        const latest = group[group.length - 1];
        const sev = top.severity;
        const el = document.createElement("div");
        el.className = `toast alert-toast sev-${sev}`;
        el.setAttribute("role", "alert");
        const reasons = group.length === 1
            ? `<dt>Alert</dt><dd>${esc(top.title)}</dd><dt>Reason</dt><dd>${esc(top.message)}</dd>`
            : `<dt>Alerts</dt><dd>${group.map((a) => `${badge.sev(a.severity)} ${esc(a.title)}`).join("<br>")}</dd>
               <dt>Reason</dt><dd>${esc(top.message)}</dd>`;
        el.innerHTML = `
            <div class="headline"><span>${ICON[sev] || "⚠"} NEW ${esc(sev)}${RANK[sev] >= 2 ? "-RISK" : ""} ALERT${group.length > 1 ? ` (${group.length})` : ""}</span>
                <button class="close-btn" aria-label="Dismiss">×</button></div>
            <dl>
                <dt>Employee</dt><dd><strong>${esc(top.employee_id)}</strong>${top.name ? " · " + esc(top.name) : ""}</dd>
                ${reasons}
                <dt>Risk score</dt><dd>${esc(latest.risk_score)} ${latest.risk_level ? badge.level(latest.risk_level) : ""}</dd>
                <dt>Time</dt><dd>${esc(fmtTime(latest.timestamp))}</dd>
            </dl>
            <div class="btn-row">
                ${latest.activity_id ? `<button class="btn sm" data-view-activity="${latest.activity_id}">View activity</button>` : ""}
                <button class="btn sm primary" data-ack-group>Acknowledge${group.length > 1 ? " all" : ""}</button>
            </div>`;
        el.querySelector(".close-btn").addEventListener("click", () => el.remove());
        el.querySelector("[data-ack-group]").addEventListener("click", async (e) => {
            e.target.disabled = true;
            for (const a of group) await window.ITM.acknowledgeAlert(a.id);
            el.remove();
        });
        box.prepend(el);
        setTimeout(() => el.remove(), RANK[sev] >= 2 ? 60000 : 15000);
        while (box.children.length > 4) box.lastElementChild.remove();
    }

    socket.on("alert:new", (a) => {
        newAlerts.unshift(a);
        renderCount((Number(countEl?.textContent) || 0) + 1);
        renderList();
        queueToast(a);
        emit("itm:alert", a);
    });
    socket.on("alert:updated", (a) => { loadNewAlerts(); emit("itm:alert-changed", a); });
    socket.on("activity:new", (a) => emit("itm:activity", a));
    socket.on("presence", (p) => emit("itm:presence", p));

    document.addEventListener("itm:alert-changed", () => loadNewAlerts());
    document.addEventListener("itm:reconnect", () => loadNewAlerts());

    document.getElementById("notif-button")?.addEventListener("click", (e) => {
        e.stopPropagation();
        panel.hidden = !panel.hidden;
    });
    document.addEventListener("click", (e) => {
        if (panel && !panel.hidden && !panel.contains(e.target)) panel.hidden = true;
    });

    loadNewAlerts();
    window.ITM.socket = socket;
    window.ITM.toastInfo = toast;
})();
