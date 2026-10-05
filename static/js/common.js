/* Shared front-end helpers: API client, formatting, badges, modal, toasts. */
(function () {
    "use strict";
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content || "";

    // ------------------------------------------------------------- API
    async function api(method, url, body) {
        const options = {
            method,
            headers: { "Accept": "application/json", "X-CSRFToken": csrf },
            credentials: "same-origin",
        };
        if (body !== undefined) {
            options.headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        let response;
        try {
            response = await fetch(url, options);
        } catch (e) {
            throw new Error("Network error — is the server running?");
        }
        let data = null;
        try { data = await response.json(); } catch (e) { /* non-JSON */ }
        if (response.status === 401) {
            window.location.href = "/?expired=1";
            throw new Error("Session expired");
        }
        if (!response.ok) {
            const err = new Error((data && data.message) || `Request failed (${response.status})`);
            err.field = data && data.field;
            err.status = response.status;
            throw err;
        }
        return data;
    }

    function query(params) {
        const q = new URLSearchParams();
        Object.entries(params || {}).forEach(([k, v]) => {
            if (v !== undefined && v !== null && v !== "" && v !== false) q.set(k, v === true ? "1" : v);
        });
        const s = q.toString();
        return s ? "?" + s : "";
    }

    // ------------------------------------------------------ formatting
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const parse = (iso) => (iso ? new Date(iso) : null);
    const pad = (n) => String(n).padStart(2, "0");
    const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    function fmtTime(iso) {
        const d = parse(iso);
        return d ? `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}` : "—";
    }
    function fmtDateTime(iso) {
        const d = parse(iso);
        if (!d) return "—";
        const today = new Date();
        const sameDay = d.toDateString() === today.toDateString();
        return (sameDay ? "Today" : `${pad(d.getDate())} ${MONTHS[d.getMonth()]}`) + " " + fmtTime(iso);
    }
    function timeAgo(iso) {
        const d = parse(iso);
        if (!d) return "never";
        const s = Math.max(0, Math.round((Date.now() - d.getTime()) / 1000));
        if (s < 60) return "just now";
        if (s < 3600) return `${Math.floor(s / 60)} min ago`;
        if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
        return `${Math.floor(s / 86400)} d ago`;
    }

    const RISKY = new Set(["FAILED_LOGIN", "UNAUTHORIZED_ACCESS"]);
    const LEVEL_FOR = (score) => (score >= 80 ? "CRITICAL" : score >= 60 ? "HIGH" : score >= 30 ? "MEDIUM" : "LOW");

    const badge = {
        sev: (s) => `<span class="badge sev-${esc(s)}">${esc(s)}</span>`,
        level: (l) => `<span class="badge lvl-${esc(l)}">${esc(l)}</span>`,
        alertStatus: (s) => `<span class="badge plain st-${esc(s)}">${esc(s)}</span>`,
        actStatus: (s) => `<span class="badge plain st-${esc(s)}">${esc(s)}</span>`,
        account: (s) => `<span class="badge plain acct-${esc(s)}">${esc(s === "active" ? "Active" : "Disabled")}</span>`,
        role: (r) => `<span class="badge plain role-${esc(r)}">${esc(r === "manager" ? "Manager" : "Employee")}</span>`,
        action: (a, risk) => `<span class="action-tag ${risk > 0 || RISKY.has(a) ? "risky" : ""}">${esc(a)}</span>`,
        presence: (online) => `<span class="presence ${online ? "online" : "offline"}">${online ? "Online" : "Offline"}</span>`,
        score: (score, level) => {
            const lvl = level || LEVEL_FOR(score || 0);
            return `<span class="score"><span class="score-bar"><span class="fill-${lvl}" style="width:${Math.min(100, score || 0)}%"></span></span>${score ?? 0}</span>`;
        },
        risk: (score) => (score > 0 ? `<span class="badge plain sev-${LEVEL_FOR(score)}">+${score}</span>` : `<span class="muted">0</span>`),
    };

    const initials = (name) => (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase();
    const person = (emp, name, sub) => `<div class="person"><div class="avatar">${esc(initials(name || emp))}</div><div><strong>${esc(name || emp)}</strong><small>${esc(sub || emp)}</small></div></div>`;

    // ---------------------------------------------------------- toasts
    function toast(message, type = "info", timeout = 4500) {
        const box = document.getElementById("toasts");
        if (!box) return;
        const el = document.createElement("div");
        el.className = `toast ${type}`;
        el.setAttribute("role", type === "error" ? "alert" : "status");
        el.textContent = message;
        box.prepend(el);
        setTimeout(() => el.remove(), timeout);
    }

    // ----------------------------------------------------------- modal
    let lastFocus = null;
    function openModal(title, bodyHtml, { wide = false, footer = "" } = {}) {
        closeModal();
        lastFocus = document.activeElement;
        const wrap = document.createElement("div");
        wrap.className = "modal-backdrop";
        wrap.id = "modal";
        wrap.innerHTML = `<div class="modal ${wide ? "wide" : ""}" role="dialog" aria-modal="true" aria-labelledby="modal-title">
            <div class="modal-header"><h3 id="modal-title">${title}</h3><button class="close-btn" data-close aria-label="Close">×</button></div>
            <div class="modal-body">${bodyHtml}</div>${footer ? `<div class="modal-footer">${footer}</div>` : ""}</div>`;
        wrap.addEventListener("click", (e) => { if (e.target === wrap || e.target.closest("[data-close]")) closeModal(); });
        document.body.appendChild(wrap);
        wrap.querySelector(".close-btn").focus();
        return wrap;
    }
    function closeModal() {
        document.getElementById("modal")?.remove();
        if (lastFocus && lastFocus.focus) lastFocus.focus();
    }
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

    // ---------------------------------------------- manager: detail views
    function detailRows(rows) {
        return `<dl class="detail-grid">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>`;
    }

    function reasonList(events, fallbackReason) {
        if (events && events.length) {
            return `<ul class="reason-list">${events.map((e) => `<li><span class="pts">+${e.points}</span>
                <span>${esc(e.reason)}<br><span class="muted small">Score ${e.score_before} → ${e.score_after}${e.score_after - e.score_before < e.points ? " (capped at 100)" : ""} · rule ${esc(e.rule_key)}</span></span></li>`).join("")}</ul>`;
        }
        if (fallbackReason) {
            return `<ul class="reason-list">${fallbackReason.split("; ").map((r) => {
                const m = r.match(/^\+(\d+)\s(.*)$/);
                return `<li><span class="pts">${m ? "+" + m[1] : ""}</span><span>${esc(m ? m[2] : r)}</span></li>`;
            }).join("")}</ul>`;
        }
        return `<p class="muted small">No risk points: this activity matched no detection rule.</p>`;
    }

    async function showActivity(id) {
        const modal = openModal("Activity details", `<div class="empty">Loading…</div>`, { wide: true });
        try {
            const a = await api("GET", `/api/manager/activities/${id}`);
            const emp = a.employee;
            let html = detailRows([
                ["Employee ID", emp ? `<a href="/manager/employees/${emp.id}">${esc(a.employee_id)}</a>` : esc(a.employee_id)],
                ["Employee name", esc(a.name || "Unknown account")],
                ["Department", esc(a.department || "—")],
                ["Action", badge.action(a.action, a.risk_score)],
                ["Resource", `<code>${esc(a.resource || "—")}</code>`],
                ["Description", esc(a.description || "—")],
                ["Timestamp", esc(fmtDateTime(a.timestamp))],
                ["IP address", `<code>${esc(a.ip_address || "—")}</code>`],
                ["User agent", `<span class="small">${esc(a.user_agent || "—")}</span>`],
                ["Status", badge.actStatus(a.status)],
                ["Risk score", `${badge.risk(a.risk_score)} <span class="muted small">points added by this activity</span>`],
                ["Employee risk now", emp ? `${badge.score(emp.current_risk_score, emp.current_risk_level)} ${badge.level(emp.current_risk_level)}` : "—"],
            ]);
            html += `<div class="section-title">Risk reason</div>${reasonList(a.risk_events, a.risk_reason)}`;
            if (a.alerts && a.alerts.length) {
                html += `<div class="section-title">Alerts raised</div><div class="table-wrap"><table><tbody>${a.alerts.map((al) => `
                    <tr><td>${badge.sev(al.severity)}</td><td><strong>${esc(al.title)}</strong><span class="sub">${esc(al.message)}</span></td>
                    <td>${badge.alertStatus(al.status)}</td><td>${alertButtons(al)}</td></tr>`).join("")}</tbody></table></div>`;
            }
            modal.querySelector(".modal-body").innerHTML = html;
        } catch (e) {
            modal.querySelector(".modal-body").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
        }
    }

    function alertButtons(al, { view = false } = {}) {
        let html = "";
        if (view && al.activity_id) html += `<button class="btn sm" data-view-activity="${al.activity_id}">View activity</button> `;
        if (al.status === "NEW") html += `<button class="btn sm" data-ack="${al.id}">Acknowledge</button> `;
        if (al.status !== "RESOLVED") html += `<button class="btn sm success" data-resolve="${al.id}">Resolve</button>`;
        return `<div class="btn-row">${html || '<span class="muted small">Closed</span>'}</div>`;
    }

    async function showAlert(id) {
        const modal = openModal("Alert details", `<div class="empty">Loading…</div>`, { wide: true });
        try {
            const al = await api("GET", `/api/manager/alerts/${id}`);
            let html = detailRows([
                ["Alert", `<strong>${esc(al.title)}</strong> <span class="muted small">#${al.id}</span>`],
                ["Severity", badge.sev(al.severity)],
                ["Status", badge.alertStatus(al.status)],
                ["Employee", `${esc(al.employee_id)} ${al.name ? "· " + esc(al.name) : ""}`],
                ["Reason", esc(al.message)],
                ["Risk score", `${badge.score(al.risk_score)} <span class="muted small">at the time of the alert</span>`],
                ["Time", esc(fmtDateTime(al.timestamp))],
                ["Acknowledged", al.acknowledged_at ? `${esc(al.acknowledged_by)} · ${esc(fmtDateTime(al.acknowledged_at))}` : "—"],
                ["Resolved", al.resolved_at ? `${esc(al.resolved_by)} · ${esc(fmtDateTime(al.resolved_at))}` : "—"],
                ["Resolution note", esc(al.resolution_note || "—")],
            ]);
            if (al.activity) {
                const a = al.activity;
                html += `<div class="section-title">Triggering activity</div>` + detailRows([
                    ["Action", badge.action(a.action, a.risk_score)],
                    ["Resource", `<code>${esc(a.resource || "—")}</code>`],
                    ["Description", esc(a.description || "—")],
                    ["IP / agent", `<code>${esc(a.ip_address || "—")}</code> <span class="small muted">${esc(a.user_agent || "")}</span>`],
                    ["Risk reason", esc(a.risk_reason || "—")],
                ]);
            }
            html += `<div style="margin-top:16px">${alertButtons(al, { view: true })}</div>`;
            modal.querySelector(".modal-body").innerHTML = html;
        } catch (e) {
            modal.querySelector(".modal-body").innerHTML = `<div class="empty">${esc(e.message)}</div>`;
        }
    }

    async function acknowledgeAlert(id) {
        try {
            const res = await api("PUT", `/api/manager/alerts/${id}/acknowledge`);
            toast(res.message, "success");
            document.dispatchEvent(new CustomEvent("itm:alert-changed", { detail: res.alert }));
            return res.alert;
        } catch (e) { toast(e.message, "error"); return null; }
    }

    function resolveAlert(id) {
        const modal = openModal("Resolve alert", `
            <div class="field"><label for="resolve-note">Resolution note</label>
            <textarea class="input" id="resolve-note" maxlength="500" placeholder="What was found and what action was taken? (kept in the audit trail)"></textarea></div>`,
            { footer: `<button class="btn" data-close>Cancel</button><button class="btn primary" id="resolve-confirm">Resolve alert</button>` });
        modal.querySelector("#resolve-note").focus();
        modal.querySelector("#resolve-confirm").addEventListener("click", async () => {
            try {
                const res = await api("PUT", `/api/manager/alerts/${id}/resolve`, { note: modal.querySelector("#resolve-note").value });
                closeModal();
                toast(res.message, "success");
                document.dispatchEvent(new CustomEvent("itm:alert-changed", { detail: res.alert }));
            } catch (e) { toast(e.message, "error"); }
        });
    }

    // Delegated handlers so any page can render these buttons.
    document.addEventListener("click", (e) => {
        const t = e.target.closest("[data-view-activity],[data-view-alert],[data-ack],[data-resolve]");
        if (!t) return;
        e.preventDefault();
        e.stopPropagation();
        if (t.dataset.viewActivity) showActivity(t.dataset.viewActivity);
        else if (t.dataset.viewAlert) showAlert(t.dataset.viewAlert);
        else if (t.dataset.ack) { t.disabled = true; acknowledgeAlert(t.dataset.ack).then(() => { t.disabled = false; }); }
        else if (t.dataset.resolve) resolveAlert(t.dataset.resolve);
    });
    // Refresh any open alert modal after a state change.
    document.addEventListener("itm:alert-changed", (e) => {
        const title = document.getElementById("modal-title");
        if (title && title.textContent === "Alert details" && e.detail) showAlert(e.detail.id);
        else if (title && title.textContent === "Activity details" && e.detail && e.detail.activity_id) showActivity(e.detail.activity_id);
    });

    // ------------------------------------------------------------ pager
    function renderPager(el, data, onPage) {
        if (!el) return;
        const { page, pages, total } = data;
        el.innerHTML = `<span>${total} result${total === 1 ? "" : "s"} · page ${page} of ${pages}</span>
            <span class="btn-row"><button class="btn sm" data-p="${page - 1}" ${page <= 1 ? "disabled" : ""}>← Prev</button>
            <button class="btn sm" data-p="${page + 1}" ${page >= pages ? "disabled" : ""}>Next →</button></span>`;
        el.querySelectorAll("[data-p]").forEach((b) => b.addEventListener("click", () => onPage(Number(b.dataset.p))));
    }

    function formValues(form) {
        const out = {};
        new FormData(form).forEach((v, k) => { out[k] = typeof v === "string" ? v.trim() : v; });
        form.querySelectorAll('input[type="checkbox"]').forEach((c) => { out[c.name] = c.checked; });
        return out;
    }

    function debounce(fn, ms) {
        let t;
        return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
    }

    // ------------------------------------------------- strong passwords
    // Mirrors utils/validators.py password_problems(); the server is still the real check.
    const WEAK_WORDS = ["password", "passw0rd", "qwerty", "123456", "abcdef", "letmein", "welcome", "shrutu"];

    function passwordRules(pw, minLength, ctx) {
        const lower = pw.toLowerCase();
        const rules = [
            [`At least ${minLength} characters`, pw.length >= minLength],
            ["An uppercase letter (A-Z)", /[A-Z]/.test(pw)],
            ["A lowercase letter (a-z)", /[a-z]/.test(pw)],
            ["A number (0-9)", /\d/.test(pw)],
            ["A special character (@ # $ ! % …)", /[^A-Za-z0-9\s]/.test(pw)],
            ["No spaces", pw.length > 0 && !/\s/.test(pw)],
            ["No character repeated 3+ times in a row", pw.length > 0 && !/(.)\1\1/.test(pw)],
            ["No common words like 'password' or '123456'", pw.length > 0 && !WEAK_WORDS.some((w) => lower.includes(w))],
        ];
        const empId = (ctx.employeeId || "").toLowerCase();
        if (empId) rules.push(["Does not contain the employee ID", pw.length > 0 && !lower.includes(empId)]);
        const nameParts = (ctx.name || "").toLowerCase().split(/[\s.'-]+/).filter((p) => p.length >= 3);
        if (nameParts.length) rules.push(["Does not contain the person's name", pw.length > 0 && !nameParts.some((p) => lower.includes(p))]);
        return rules;
    }

    /* Live checklist under a password input. getContext() returns {employeeId, name} for the account
       the password is for (optional). Returns {update, isStrong}. */
    function passwordChecklist(input, getContext = () => ({})) {
        const minLength = Number(input.dataset.minLength) || 8;
        const list = document.createElement("ul");
        list.className = "pw-rules";
        list.setAttribute("aria-live", "polite");
        (input.closest(".field") || input.parentElement).appendChild(list);
        let strong = false;
        const update = () => {
            const rules = passwordRules(input.value, minLength, getContext() || {});
            strong = rules.every(([, ok]) => ok);
            list.innerHTML = rules.map(([label, ok]) =>
                `<li class="${ok ? "ok" : ""}"><span aria-hidden="true">${ok ? "✓" : "○"}</span> ${esc(label)}</li>`).join("");
            input.classList.toggle("invalid", input.value.length > 0 && !strong);
        };
        input.addEventListener("input", update);
        update();
        return { update, isStrong: () => strong };
    }

    // Random temporary password that always passes every rule above.
    function generatePassword() {
        const sets = ["ABCDEFGHJKLMNPQRSTUVWXYZ", "abcdefghijkmnpqrstuvwxyz", "23456789", "@#$%&*!?"];
        const all = sets.join("");
        const rand = (n) => { const b = new Uint32Array(1); crypto.getRandomValues(b); return b[0] % n; };
        const chars = sets.map((s) => s[rand(s.length)]);               // one from each class
        while (chars.length < 12) chars.push(all[rand(all.length)]);
        for (let i = chars.length - 1; i > 0; i--) {                      // shuffle
            const j = rand(i + 1);
            [chars[i], chars[j]] = [chars[j], chars[i]];
        }
        const pw = chars.join("");
        return /(.)\1\1/.test(pw) ? generatePassword() : pw;
    }

    function cssVar(name) {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    // ------------------------------------------------------ page chrome
    document.getElementById("theme-toggle")?.addEventListener("click", () => {
        const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        try { localStorage.setItem("itm-theme", next); } catch (e) { /* ignore */ }
        document.dispatchEvent(new CustomEvent("itm:theme", { detail: next }));
    });
    document.getElementById("menu-toggle")?.addEventListener("click", (e) => {
        e.stopPropagation();
        document.getElementById("sidebar")?.classList.toggle("open");
    });
    document.addEventListener("click", (e) => {
        const sb = document.getElementById("sidebar");
        if (sb && sb.classList.contains("open") && !sb.contains(e.target)) sb.classList.remove("open");
    });

    window.ITM = {
        api, query, esc, fmtTime, fmtDateTime, timeAgo, badge, person, toast, openModal, closeModal,
        showActivity, showAlert, acknowledgeAlert, resolveAlert, alertButtons, renderPager, formValues,
        debounce, cssVar, detailRows, reasonList, LEVEL_FOR, passwordChecklist, generatePassword,
        role: document.body.dataset.role,
    };
})();
