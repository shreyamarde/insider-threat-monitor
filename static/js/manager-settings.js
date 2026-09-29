/* Settings: edit detection rules. */
(function () {
    "use strict";
    const { api, esc, toast } = window.ITM;
    const SEVERITIES = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"];
    const body = document.getElementById("rules-body");

    const row = (r) => `<tr data-id="${r.id}">
        <td><strong>${esc(r.name)}</strong> <span class="action-tag">${esc(r.rule_key)}</span><span class="sub">${esc(r.description || "")}</span></td>
        <td class="num"><input class="input" style="width:74px" type="number" min="0" max="100" name="points" value="${r.points}"></td>
        <td class="num"><input class="input" style="width:80px" type="number" min="1" max="1000" name="threshold" value="${r.threshold}"></td>
        <td class="num"><input class="input" style="width:80px" type="number" min="0" max="1440" name="window_minutes" value="${r.window_minutes}"></td>
        <td><select class="input" name="severity">${SEVERITIES.map((s) => `<option ${s === r.severity ? "selected" : ""}>${s}</option>`).join("")}</select></td>
        <td><label class="checkbox"><input type="checkbox" name="enabled" ${r.enabled ? "checked" : ""}> On</label></td>
        <td><button class="btn sm primary" data-save>Save</button></td></tr>`;

    async function load() {
        try {
            const rules = await api("GET", "/api/manager/rules");
            body.innerHTML = rules.map(row).join("");
        } catch (e) { toast(e.message, "error"); }
    }

    body.addEventListener("click", async (e) => {
        const btn = e.target.closest("[data-save]");
        if (!btn) return;
        const tr = btn.closest("tr");
        const val = (n) => tr.querySelector(`[name="${n}"]`);
        const payload = {
            points: Number(val("points").value), threshold: Number(val("threshold").value),
            window_minutes: Number(val("window_minutes").value), severity: val("severity").value, enabled: val("enabled").checked,
        };
        btn.disabled = true;
        try {
            const res = await api("PUT", `/api/manager/rules/${tr.dataset.id}`, payload);
            toast(res.message, "success");
        } catch (err) { toast(err.message, "error"); }
        btn.disabled = false;
    });
    document.getElementById("theme-toggle-2")?.addEventListener("click", () => document.getElementById("theme-toggle").click());
    load();
})();
