/* Employee management: search/filter, create, enable/disable, reset password. */
(function () {
    "use strict";
    const { api, query, esc, badge, person, fmtDateTime, toast, openModal, closeModal, renderPager, formValues, debounce,
        passwordChecklist, generatePassword } = window.ITM;
    const $ = (id) => document.getElementById(id);
    let page = 1;

    function row(u) {
        const toggle = u.status === "active"
            ? `<button class="btn sm danger" data-status="disabled" data-id="${u.id}">Disable</button>`
            : `<button class="btn sm success" data-status="active" data-id="${u.id}">Enable</button>`;
        return `<tr>
            <td><a href="/manager/employees/${u.id}" style="color:inherit">${person(u.employee_id, u.name, `${u.employee_id} · ${u.email}`)}</a></td>
            <td>${esc(u.department)}<span class="sub">${esc(u.job_title || "")}</span></td>
            <td>${badge.role(u.role)}</td>
            <td>${badge.account(u.status)}${u.must_change_password ? '<span class="sub">temp password</span>' : ""}</td>
            <td>${badge.presence(u.online)}</td>
            <td class="nowrap">${u.role === "employee" ? badge.score(u.risk_score, u.risk_level) + " " + badge.level(u.risk_level) : '<span class="muted">—</span>'}</td>
            <td class="nowrap">${esc(fmtDateTime(u.last_login))}<span class="sub">${esc(u.last_login_ip || "")}</span></td>
            <td class="nowrap"><div class="btn-row" style="flex-wrap:nowrap"><a class="btn sm" href="/manager/employees/${u.id}">View</a>
                <button class="btn sm" data-reset="${u.id}" data-emp="${esc(u.employee_id)}" data-name="${esc(u.name)}">Reset</button>
                ${u.employee_id === document.body.dataset.employeeId ? "" : toggle}</div></td>
        </tr>`;
    }

    async function load() {
        const params = formValues($("filters"));
        try {
            const data = await api("GET", "/api/manager/employees" + query({ ...params, page }));
            $("emp-body").innerHTML = data.items.length ? data.items.map(row).join("")
                : `<tr><td colspan="8" class="empty">No employees match these filters.</td></tr>`;
            renderPager($("emp-pager"), data, (p) => { page = p; load(); });
        } catch (e) { toast(e.message, "error"); }
    }

    // --------------------------------------------------------- create
    async function openCreate() {
        const tpl = $("employee-form-template").innerHTML;
        const modal = openModal("Create employee account", tpl, {
            wide: true,
            footer: `<button class="btn" data-close>Cancel</button><button class="btn primary" id="create-submit">Create employee</button>`,
        });
        try { modal.querySelector("#e-id").value = (await api("GET", "/api/manager/employees/next-id")).employee_id; } catch (e) { /* keep server default */ }
        const pwInput = modal.querySelector("#e-password");
        pwInput.value = generatePassword();
        const checklist = passwordChecklist(pwInput, () => ({
            employeeId: modal.querySelector("#e-id").value.trim(), name: modal.querySelector("#e-name").value.trim(),
        }));
        modal.querySelector("#e-id").addEventListener("input", checklist.update);
        modal.querySelector("#e-name").addEventListener("input", checklist.update);
        modal.querySelector("#gen-password").addEventListener("click", () => { pwInput.value = generatePassword(); checklist.update(); });
        modal.querySelector("#e-name").focus();
        const form = modal.querySelector("#employee-form");
        const submit = modal.querySelector("#create-submit");
        const errEl = modal.querySelector("#form-error");
        const doSubmit = async () => {
            form.querySelectorAll(".invalid").forEach((el) => el.classList.remove("invalid"));
            errEl.hidden = true;
            if (!checklist.isStrong()) {
                errEl.textContent = "The temporary password does not meet all the strong-password rules.";
                errEl.hidden = false;
                pwInput.classList.add("invalid");
                pwInput.focus();
                return;
            }
            const body = formValues(form);
            body.employee_id = (body.employee_id || "").toUpperCase();
            submit.disabled = true;
            try {
                const res = await api("POST", "/api/manager/employees", body);
                closeModal();
                toast(`${res.message} Temporary password: ${body.password} — share it securely; it is not shown again.`, "success", 12000);
                page = 1;
                load();
            } catch (e) {
                errEl.textContent = e.message;
                errEl.hidden = false;
                if (e.field) form.querySelector(`[name="${e.field}"]`)?.classList.add("invalid");
            } finally { submit.disabled = false; }
        };
        submit.addEventListener("click", doSubmit);
        form.addEventListener("submit", (e) => { e.preventDefault(); doSubmit(); });
    }

    // -------------------------------------------------- reset password
    function openReset(id, empId, name) {
        const modal = openModal(`Reset password — ${esc(empId)}`, `
            <p class="muted small" style="margin-bottom:12px">Set a temporary password. The employee must choose a new one at their next login. This action is recorded in the audit log.</p>
            <div class="field"><label for="r-password">Temporary password</label>
            <div class="input-group"><input class="input" id="r-password" type="text" maxlength="128" value="${generatePassword()}" autocomplete="new-password">
            <button type="button" class="btn" id="r-gen">Generate</button></div></div>
            <p class="error-text" id="r-error" hidden></p>`,
            { footer: `<button class="btn" data-close>Cancel</button><button class="btn primary" id="r-submit">Reset password</button>` });
        const pwInput = modal.querySelector("#r-password");
        const checklist = passwordChecklist(pwInput, () => ({ employeeId: empId, name }));
        modal.querySelector("#r-gen").addEventListener("click", () => { pwInput.value = generatePassword(); checklist.update(); });
        modal.querySelector("#r-submit").addEventListener("click", async () => {
            if (!checklist.isStrong()) {
                const err = modal.querySelector("#r-error");
                err.textContent = "The password does not meet all the strong-password rules.";
                err.hidden = false;
                pwInput.focus();
                return;
            }
            try {
                const res = await api("POST", `/api/manager/employees/${id}/reset-password`, { password: modal.querySelector("#r-password").value });
                closeModal();
                toast(res.message, "success");
                load();
            } catch (e) {
                const err = modal.querySelector("#r-error");
                err.textContent = e.message;
                err.hidden = false;
            }
        });
    }

    async function setStatus(id, status, btn) {
        if (status === "disabled" && !confirm("Disable this account? The employee will be signed out and unable to log in.")) return;
        btn.disabled = true;
        try {
            const res = await api("PUT", `/api/manager/employees/${id}/status`, { status });
            toast(res.message, "success");
            load();
        } catch (e) { toast(e.message, "error"); btn.disabled = false; }
    }

    // --------------------------------------------------------- wiring
    $("new-employee").addEventListener("click", openCreate);
    $("filters").addEventListener("input", debounce(() => { page = 1; load(); }, 300));
    $("filters").addEventListener("submit", (e) => e.preventDefault());
    $("emp-body").addEventListener("click", (e) => {
        const reset = e.target.closest("[data-reset]");
        const status = e.target.closest("[data-status]");
        if (reset) openReset(reset.dataset.reset, reset.dataset.emp, reset.dataset.name);
        if (status) setStatus(status.dataset.id, status.dataset.status, status);
    });
    document.addEventListener("itm:presence", debounce(load, 800));
    document.addEventListener("itm:reconnect", load);
    if (new URLSearchParams(location.search).get("new") === "1") openCreate();
    load();
})();
