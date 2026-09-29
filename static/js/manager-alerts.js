/* Alert queue: filter, view, acknowledge, resolve — updates live. */
(function () {
    "use strict";
    const { api, query, esc, badge, person, fmtDateTime, toast, renderPager, formValues, debounce, alertButtons } = window.ITM;
    const $ = (id) => document.getElementById(id);
    const form = $("filters");
    let page = 1;
    let maxSeen = null;

    const params = new URLSearchParams(location.search);
    params.forEach((v, k) => { if (form.elements[k]) form.elements[k].value = v; });

    const handledBy = (a) => a.resolved_by ? `Resolved by ${esc(a.resolved_by)}<span class="sub">${esc(fmtDateTime(a.resolved_at))}</span>`
        : a.acknowledged_by ? `Ack. by ${esc(a.acknowledged_by)}<span class="sub">${esc(fmtDateTime(a.acknowledged_at))}</span>` : `<span class="muted">—</span>`;

    const row = (a, isNew) => `<tr class="clickable ${isNew ? "new-row" : ""}" data-view-alert="${a.id}">
        <td class="nowrap">${esc(fmtDateTime(a.timestamp))}</td>
        <td>${person(a.employee_id, a.name, a.department ? `${a.employee_id} · ${a.department}` : a.employee_id)}</td>
        <td><strong>${esc(a.title)}</strong><span class="sub">${esc(a.message)}</span></td>
        <td>${badge.sev(a.severity)}</td>
        <td class="num">${badge.score(a.risk_score)}</td>
        <td>${badge.alertStatus(a.status)}</td>
        <td class="small">${handledBy(a)}</td>
        <td>${alertButtons(a, { view: true })}</td></tr>`;

    async function load() {
        try {
            const data = await api("GET", "/api/manager/alerts" + query({ ...formValues(form), page }));
            $("alert-body").innerHTML = data.items.length
                ? data.items.map((a) => row(a, maxSeen !== null && a.id > maxSeen)).join("")
                : `<tr><td colspan="8" class="empty">No alerts match these filters.</td></tr>`;
            maxSeen = Math.max(maxSeen || 0, data.items.reduce((m, a) => Math.max(m, a.id), 0));
            renderPager($("alert-pager"), data, (p) => { page = p; load(); });
        } catch (e) { toast(e.message, "error"); }
    }
    const reload = debounce(load, 300);

    form.addEventListener("input", debounce(() => { page = 1; load(); }, 300));
    form.addEventListener("submit", (e) => e.preventDefault());
    ["itm:alert", "itm:alert-changed", "itm:reconnect"].forEach((ev) => document.addEventListener(ev, reload));
    load();
})();
