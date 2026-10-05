/* Employee detail page: edit account, reset password; reloads when this employee does something. */
(function () {
    "use strict";
    const { api, esc, toast, openModal, closeModal, formValues, debounce, passwordChecklist, generatePassword } = window.ITM;
    const root = document.getElementById("employee-detail");
    const userId = root.dataset.userId;
    const employeeId = root.dataset.employeeId;

    document.getElementById("edit-form").addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = e.target;
        const body = formValues(form);
        form.querySelectorAll("select[disabled]").forEach((s) => delete body[s.name]);
        if (body.status === "disabled" && !confirm("Disable this account? The employee will be signed out immediately.")) return;
        try {
            const res = await api("PUT", `/api/manager/employees/${userId}`, body);
            toast(res.message, "success");
            if (res.changes && res.changes.length) setTimeout(() => location.reload(), 700);
        } catch (err) {
            toast(err.message, "error");
            if (err.field) form.querySelector(`[name="${err.field}"]`)?.classList.add("invalid");
        }
    });

    document.getElementById("reset-btn").addEventListener("click", () => {
        const modal = openModal(`Reset password — ${esc(employeeId)}`, `
            <p class="muted small" style="margin-bottom:12px">The employee must choose a new password at their next login. Recorded in the audit log.</p>
            <div class="field"><label for="r-password">Temporary password</label>
            <div class="input-group"><input class="input" id="r-password" type="text" maxlength="128" autocomplete="new-password" value="${generatePassword()}">
            <button type="button" class="btn" id="r-gen">Generate</button></div></div>`,
            { footer: `<button class="btn" data-close>Cancel</button><button class="btn primary" id="r-submit">Reset password</button>` });
        const pwInput = modal.querySelector("#r-password");
        const checklist = passwordChecklist(pwInput, () => ({ employeeId, name: root.dataset.name }));
        modal.querySelector("#r-gen").addEventListener("click", () => { pwInput.value = generatePassword(); checklist.update(); });
        pwInput.focus();
        modal.querySelector("#r-submit").addEventListener("click", async () => {
            if (!checklist.isStrong()) {
                toast("The password does not meet all the strong-password rules.", "error");
                pwInput.focus();
                return;
            }
            try {
                const res = await api("POST", `/api/manager/employees/${userId}/reset-password`,
                    { password: modal.querySelector("#r-password").value });
                closeModal();
                toast(res.message, "success");
                setTimeout(() => location.reload(), 900);
            } catch (err) { toast(err.message, "error"); }
        });
    });

    // Keep the page current when this employee acts.
    const reload = debounce(() => { if (!document.getElementById("modal")) location.reload(); }, 2500);
    document.addEventListener("itm:activity", (e) => { if (e.detail.employee_id === employeeId && e.detail.risk_score > 0) reload(); });
})();
