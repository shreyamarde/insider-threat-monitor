/* Manager dashboard: initial load from /api/manager/dashboard + live Socket.IO updates. */
(function () {
    "use strict";
    const { api, esc, fmtTime, fmtDateTime, timeAgo, badge, alertButtons, debounce, cssVar } = window.ITM;
    const C = window.ITMCharts;
    const $ = (id) => document.getElementById(id);
    let last = null;

    // ---------------------------------------------------------- render
    function renderStats(stats, flash) {
        Object.entries(stats).forEach(([key, value]) => {
            document.querySelectorAll(`[data-kpi="${key}"]`).forEach((el) => {
                if (flash && el.textContent !== String(value) && el.classList.contains("kpi-value")) {
                    el.closest(".kpi").classList.remove("flash");
                    void el.offsetWidth;
                    el.closest(".kpi").classList.add("flash");
                }
                el.textContent = value;
            });
        });
    }

    function feedItem(a, isNew) {
        const li = document.createElement("li");
        li.className = (a.risk_score > 0 ? "risky " : "") + (isNew ? "new-row" : "");
        li.dataset.viewActivity = a.id;
        li.title = "Click for full activity details";
        li.innerHTML = `<span class="time">${esc(fmtTime(a.timestamp))}</span>
            <span class="who"><b>${esc(a.employee_id)}</b> — ${badge.action(a.action, a.risk_score)}
            <span class="muted small">${esc(a.resource || "")}</span></span>
            <span>${a.risk_score > 0 ? badge.risk(a.risk_score) : badge.actStatus(a.status)}</span>`;
        return li;
    }

    function renderFeed(items) {
        const ul = $("feed");
        ul.innerHTML = "";
        if (!items.length) { ul.innerHTML = `<li class="empty">No activity yet</li>`; return; }
        items.forEach((a) => ul.appendChild(feedItem(a, false)));
    }

    function alertRow(a, isNew) {
        return `<tr class="clickable ${isNew ? "new-row" : ""}" data-view-alert="${a.id}">
            <td>${window.ITM.person(a.employee_id, a.name, a.employee_id)}</td>
            <td><strong>${esc(a.title)}</strong><span class="sub truncate">${esc(a.message)}</span></td>
            <td>${badge.sev(a.severity)}</td><td class="num">${esc(a.risk_score)}</td>
            <td class="nowrap">${esc(fmtDateTime(a.timestamp))}</td><td>${badge.alertStatus(a.status)}</td>
            <td>${alertButtons(a)}</td></tr>`;
    }

    function renderAlerts(items) {
        $("alerts-body").innerHTML = items.length ? items.map((a) => alertRow(a, false)).join("")
            : `<tr><td colspan="7" class="empty">No alerts — all quiet.</td></tr>`;
    }

    function renderRisk(risk) {
        const levels = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
        $("risk-counts").innerHTML = levels.map((l) => `<a href="/manager/risk#${l}"><strong>${risk.counts[l]}</strong>${badge.level(l)}</a>`).join("");
        const top = levels.slice().reverse().flatMap((l) => risk.groups[l]).filter((e) => e.score > 0).slice(0, 5);
        $("risk-top").innerHTML = top.length ? top.map((e) => `
            <a class="risk-person" href="/manager/employees/${e.id}">
                <div class="top"><span>${esc(e.employee_id)} · ${esc(e.name)}</span>${badge.score(e.score)}</div>
                <p>${esc(e.last_reason || "")}</p></a>`).join("")
            : `<div class="empty">Every employee is at LOW risk with a score of 0.</div>`;
    }

    function renderPresence(rows) {
        $("presence-list").innerHTML = rows.length ? rows.slice(0, 8).map((p) => `
            <li><a href="/manager/employees/${p.id}"><strong>${esc(p.employee_id)}</strong> <span class="muted">${esc(p.name)}</span></a>
            <span>${p.status === "disabled" ? badge.account("disabled") : badge.presence(p.online)}
            <span class="muted small">${p.online ? "" : esc(timeAgo(p.last_seen))}</span></span></li>`).join("")
            : `<li class="empty">No employees</li>`;
    }

    function renderLogins(ok, failed) {
        $("logins-list").innerHTML = ok.length ? ok.map((l) => `<li><span><strong>${esc(l.employee_id)}</strong>
            <span class="muted small"> ${esc(l.ip_address || "")}</span></span><span class="muted small">${esc(fmtDateTime(l.timestamp))}</span></li>`).join("")
            : `<li class="empty">No sign-ins yet</li>`;
        $("failed-list").innerHTML = failed.length ? failed.map((l) => `<li><span><strong>${esc(l.employee_id)}</strong>
            <span class="badge plain st-FAILED">${esc((l.reason || "").replace(/_/g, " "))}</span></span>
            <span class="muted small">${esc(fmtDateTime(l.timestamp))}</span></li>`).join("")
            : `<li class="empty">No failed attempts</li>`;
    }

    function renderCharts(ch) {
        const s1 = cssVar("--series-1"), s2 = cssVar("--series-2");
        C.line("chart-timeline", ch.timeline.labels, [
            { label: "All activity", data: ch.timeline.activities, color: s1 },
            { label: "Risk-scored activity", data: ch.timeline.suspicious, color: s2 },
        ]);
        C.table($("table-timeline"), ["Hour", "All activity", "Risk-scored", "Alerts"],
            ch.timeline.labels.map((l, i) => [l, ch.timeline.activities[i], ch.timeline.suspicious[i], ch.timeline.alerts[i]]));

        const sevColors = { LOW: cssVar("--low"), MEDIUM: cssVar("--medium-fill"), HIGH: cssVar("--high-fill"), CRITICAL: cssVar("--critical") };
        const sevSeries = Object.keys(sevColors).map((s) => ({ label: s, data: ch.alerts_by_day.series[s], color: sevColors[s] }));
        C.legend($("legend-severity"), sevSeries);
        C.bars("chart-severity", ch.alerts_by_day.labels, sevSeries, { stacked: true });
        C.table($("table-severity"), ["Day", "LOW", "MEDIUM", "HIGH", "CRITICAL"],
            ch.alerts_by_day.labels.map((d, i) => [d, ...Object.keys(sevColors).map((s) => ch.alerts_by_day.series[s][i])]));

        C.bars("chart-actions", ch.action_types.labels, [{ label: "Actions", data: ch.action_types.values, color: s1 }], { horizontal: true });
        C.table($("table-actions"), ["Action", "Count"], ch.action_types.labels.map((l, i) => [l, ch.action_types.values[i]]));

        C.bars("chart-employees", ch.top_employees.labels, [{ label: "Actions", data: ch.top_employees.values, color: s1 }], { horizontal: true });
        C.table($("table-employees"), ["Employee", "Actions"], ch.top_employees.labels.map((l, i) => [l, ch.top_employees.values[i]]));
    }

    // ------------------------------------------------------------ data
    async function load(flash = false) {
        try {
            last = await api("GET", "/api/manager/dashboard");
            renderStats(last.stats, flash);
            renderFeed(last.feed);
            renderAlerts(last.alerts);
            renderRisk(last.risk);
            renderPresence(last.presence);
            renderLogins(last.recent_logins, last.failed_logins);
            renderCharts(last.charts);
        } catch (e) {
            window.ITM.toast(`Could not load dashboard: ${e.message}`, "error");
        }
    }
    const refresh = debounce(() => load(true), 1500);

    // ------------------------------------------------------ live events
    document.addEventListener("itm:activity", (e) => {
        const ul = $("feed");
        ul.querySelector(".empty")?.remove();
        ul.prepend(feedItem(e.detail, true));
        while (ul.children.length > 30) ul.lastElementChild.remove();
        refresh();
    });
    document.addEventListener("itm:alert", (e) => {
        const body = $("alerts-body");
        body.querySelector(".empty")?.closest("tr")?.remove();
        body.insertAdjacentHTML("afterbegin", alertRow(e.detail, true));
        while (body.children.length > 8) body.lastElementChild.remove();
        refresh();
    });
    ["itm:alert-changed", "itm:presence", "itm:reconnect"].forEach((ev) => document.addEventListener(ev, refresh));
    document.addEventListener("itm:theme", () => last && renderCharts(last.charts));
    setInterval(() => load(false), 30000); // presence timeouts & relative times

    load();
})();
