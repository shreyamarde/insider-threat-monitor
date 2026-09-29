// Show / hide password (kept out of the HTML so the page works with a strict CSP)
(function () {
    const toggle = document.getElementById("password-toggle");
    const input = document.getElementById("password");
    if (!toggle || !input) return;
    toggle.addEventListener("click", function () {
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        toggle.setAttribute("aria-label", show ? "Hide password" : "Show password");
        toggle.style.color = show ? "#60a5fa" : "";
    });
})();
