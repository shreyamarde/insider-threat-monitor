// Applied synchronously in <head> to avoid a flash of the wrong theme.
(function () {
    var theme = "dark";
    try {
        var saved = localStorage.getItem("itm-theme");
        if (saved === "light" || saved === "dark") theme = saved;
    } catch (e) { /* storage unavailable: keep default */ }
    document.documentElement.setAttribute("data-theme", theme);
})();
