/* Live activity log with filters; new events stream in on page 1. */
(function () {
    "use strict";
    const { api, query, esc, badge, fmtDateTime, toast, renderPager, formValues, debounce } = window.ITM;
    const $ = (id) => document.getElementById(id);
    const form = $("filters");
    let page = 1;
    let maxSeen = null; // highest activity id already shown -> newer rows get highlighted

    // Pre-fill filters from the URL (e.g. ?employee=EMP1003 from the employee page)
    const params = new URLSearchParams(location.search);
    params.forEach((v, k) => { const el = form.elements[k]; if (el) el.type === "checkbox" ? (el.checked = v === "1") : (el.value = v); });

    const row = (a, isNew) => `<tr class="clickable ${isNew ? "new-row" : ""}" data-view-activity="${a.id}">
        <td class="nowrap">${esc(fmtDateTime(a.timestamp))}</td>
        <td><strong>${esc(a.employee_id)}</strong><span class="sub">${esc(a.name || "unknown account")}${a.actor_role === "manager" ? " · manager" : ""}</span></td>
        <td>${badge.action(a.action, a.risk_score)}</td>
        <td><code>${esc(a.resource || "—")}</code></td>
        <td class="truncate" title="${esc(a.description || "")}">${esc(a.description || "")}</td>
        <td><code>${esc(a.ip_address || "—")}</code></td>
        <td>${badge.actStatus(a.status)}</td>
        <td class="num">${badge.risk(a.risk_score)}</td></tr>`;

    async function load() {
        try {
            const data = await api("GET", "/api/manager/activities" + query({ ...formValues(form), page }));
            $("act-body").innerHTML = data.items.length
                ? data.items.map((a) => row(a, maxSeen !== null && a.id > maxSeen)).join("")
                : `<tr><td colspan="8" class="empty">No activity matches these filters.</td></tr>`;
            const top = data.items.reduce((m, a) => Math.max(m, a.id), 0);
            maxSeen = Math.max(maxSeen || 0, top);
            renderPager($("act-pager"), data, (p) => { page = p; load(); });
        } catch (e) { toast(e.message, "error"); }
    }
    const reload = debounce(load, 300);

    form.addEventListener("input", debounce(() => { page = 1; load(); }, 300));
    form.addEventListener("reset", () => setTimeout(() => { page = 1; load(); }, 0));
    form.addEventListener("submit", (e) => e.preventDefault());

    // New activity arrives over Socket.IO; the server re-applies the current filters.
    document.addEventListener("itm:activity", () => {
        if ($("live-toggle").checked && page === 1) reload();
    });
    document.addEventListener("itm:reconnect", load);
    load();
})();
