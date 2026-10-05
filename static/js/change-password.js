/* Change password: live strong-password checklist + confirm match (the server re-checks everything). */
(function () {
    "use strict";
    const { passwordChecklist } = window.ITM;
    const form = document.getElementById("change-password-form");
    const input = document.getElementById("new_password");
    const confirmInput = document.getElementById("confirm_password");
    const confirmHint = document.getElementById("confirm-hint");
    const checklist = passwordChecklist(input, () => ({ employeeId: input.dataset.employeeId, name: input.dataset.name }));

    function checkMatch() {
        const mismatch = confirmInput.value.length > 0 && confirmInput.value !== input.value;
        confirmHint.hidden = !mismatch;
        confirmHint.textContent = mismatch ? "The passwords do not match yet." : "";
        confirmInput.classList.toggle("invalid", mismatch);
        return !mismatch;
    }
    input.addEventListener("input", checkMatch);
    confirmInput.addEventListener("input", checkMatch);

    form.addEventListener("submit", (e) => {
        if (!checklist.isStrong()) {
            e.preventDefault();
            input.classList.add("invalid");
            input.focus();
        } else if (!checkMatch() || !confirmInput.value) {
            e.preventDefault();
            confirmInput.focus();
        }
    });
})();
