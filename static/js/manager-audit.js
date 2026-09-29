/* Audit trail (manager actions) and login attempts. */
(function () {
    "use strict";
    const { api, query, esc, badge, fmtDateTime, toast, renderPager, formValues, debounce } = window.ITM;
    const $ = (id) => document.getElementById(id);
    const pages = { manager: 1, logins: 1 };

    async function loadAudit() {
        try {
            const data = await api("GET", "/api/manager/audit" + query({ ...formValues($("audit-filters")), page: pages.manager }));
            $("audit-body").innerHTML = data.items.length ? data.items.map((a) => `
                <tr class="clickable" data-view-activity="${a.id}">
                    <td class="nowrap">${esc(fmtDateTime(a.timestamp))}</td>
                    <td><strong>${esc(a.employee_id)}</strong><span class="sub">${esc(a.name || "")}</span></td>
                    <td>${badge.action(a.action, 0)}</td>
                    <td><code>${esc(a.resource || "—")}</code></td>
                    <td class="truncate" title="${esc(a.description || "")}">${esc(a.description || "")}</td>
                    <td><code>${esc(a.ip_address || "—")}</code></td></tr>`).join("")
                : `<tr><td colspan="6" class="empty">No manager actions match.</td></tr>`;
            renderPager($("audit-pager"), data, (p) => { pages.manager = p; loadAudit(); });
        } catch (e) { toast(e.message, "error"); }
    }

    async function loadLogins() {
        try {
            const data = await api("GET", "/api/manager/login-attempts" + query({ ...formValues($("login-filters")), page: pages.logins }));
            $("login-body").innerHTML = data.items.length ? data.items.map((l) => `
                <tr><td class="nowrap">${esc(fmtDateTime(l.timestamp))}</td>
                    <td><strong>${esc(l.employee_id)}</strong></td>
                    <td>${badge.actStatus(l.success ? "SUCCESS" : "FAILED")}</td>
                    <td class="small">${esc((l.reason || "").replace(/_/g, " ").toLowerCase())}</td>
                    <td><code>${esc(l.ip_address || "—")}</code></td>
                    <td class="small truncate" title="${esc(l.user_agent || "")}">${esc(l.user_agent || "—")}</td></tr>`).join("")
                : `<tr><td colspan="6" class="empty">No login attempts match.</td></tr>`;
            renderPager($("login-pager"), data, (p) => { pages.logins = p; loadLogins(); });
        } catch (e) { toast(e.message, "error"); }
    }

    function show(tab) {
        document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
        document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = p.dataset.panel !== tab; });
        tab === "logins" ? loadLogins() : loadAudit();
    }

    document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
        history.replaceState(null, "", t.dataset.tab === "logins" ? "#logins" : "#");
        show(t.dataset.tab);
    }));
    $("audit-filters").addEventListener("input", debounce(() => { pages.manager = 1; loadAudit(); }, 300));
    $("login-filters").addEventListener("input", debounce(() => { pages.logins = 1; loadLogins(); }, 300));
    document.querySelectorAll("form.filters").forEach((f) => f.addEventListener("submit", (e) => e.preventDefault()));
    document.addEventListener("itm:activity", debounce((e) => {
        if (!$("audit-body").closest("[data-panel]").hidden) loadAudit(); else loadLogins();
    }, 800));

    show(location.hash === "#logins" ? "logins" : "manager");
})();
