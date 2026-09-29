/* Risk monitoring: employees grouped by level + explained score changes. */
(function () {
    "use strict";
    const { api, esc, badge, fmtDateTime, toast, debounce } = window.ITM;
    const LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

    async function load() {
        try {
            const data = await api("GET", "/api/manager/risk");
            document.getElementById("risk-columns").innerHTML = LEVELS.map((level) => `
                <div class="risk-col" id="${level}">
                    <h4>${badge.level(level)}<span class="count-pill">${data.counts[level]} employee${data.counts[level] === 1 ? "" : "s"}</span></h4>
                    ${data.groups[level].length ? data.groups[level].map((e) => `
                        <a class="risk-person" href="/manager/employees/${e.id}">
                            <div class="top"><span>${esc(e.employee_id)} · ${esc(e.name)}</span>${badge.score(e.score, level)}</div>
                            <p>${esc(e.department)}${e.status === "disabled" ? " · disabled" : ""}${e.online ? " · online" : ""}</p>
                            ${e.last_reason ? `<p>Latest: ${esc(e.last_reason)}</p>` : ""}
                        </a>`).join("") : `<div class="empty small">None</div>`}
                </div>`).join("");
            document.getElementById("events-body").innerHTML = data.recent_events.length ? data.recent_events.map((e) => `
                <tr><td class="nowrap">${esc(fmtDateTime(e.created_at))}</td>
                    <td><strong>${esc(e.employee_id)}</strong><span class="sub">${esc(e.name)}</span></td>
                    <td><span class="action-tag">${esc(e.rule_key)}</span></td>
                    <td>Risk increased by ${e.points} because: ${esc(e.reason)}</td>
                    <td class="num"><span class="pts" style="color:var(--critical);font-weight:700">+${e.points}</span></td>
                    <td class="num nowrap">${e.score_before} → <strong>${e.score_after}</strong></td>
                    <td>${e.activity_id ? `<button class="btn sm" data-view-activity="${e.activity_id}">Activity</button>` : ""}</td></tr>`).join("")
                : `<tr><td colspan="7" class="empty">No risk events yet.</td></tr>`;
            if (location.hash) document.querySelector(location.hash)?.scrollIntoView({ block: "center" });
        } catch (e) { toast(e.message, "error"); }
    }
    const reload = debounce(load, 800);
    document.addEventListener("itm:activity", (e) => { if (e.detail.risk_score > 0) reload(); });
    document.addEventListener("itm:reconnect", load);
    load();
})();
