/*
 * Thin Chart.js wrappers following the data-viz rules used in this project:
 * one y-axis, 2px lines, 4px rounded bar ends, recessive grid, crosshair-style
 * index tooltips, HTML legends, and a data-table fallback for every chart.
 * Colours are read from CSS variables so light/dark themes stay in sync.
 */
(function () {
    "use strict";
    const { cssVar, esc } = window.ITM;
    const charts = {};

    function base(stacked = false, horizontal = false) {
        const grid = cssVar("--chart-grid"), text = cssVar("--chart-text");
        const valueAxis = { beginAtZero: true, stacked, grid: { color: grid }, border: { display: false },
            ticks: { color: text, precision: 0, font: { size: 11 } } };
        const catAxis = { stacked, grid: { display: false }, border: { color: grid },
            ticks: { color: text, font: { size: 11 }, maxRotation: 0, autoSkip: !horizontal, autoSkipPadding: 12 } };
        return {
            responsive: true, maintainAspectRatio: false, animation: { duration: 250 },
            indexAxis: horizontal ? "y" : "x",
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: cssVar("--surface"), titleColor: cssVar("--text"), bodyColor: cssVar("--text-2"),
                    borderColor: cssVar("--border"), borderWidth: 1, padding: 10, boxPadding: 4, usePointStyle: true,
                },
            },
            scales: horizontal ? { x: valueAxis, y: catAxis } : { x: catAxis, y: valueAxis },
        };
    }

    function upsert(id, config) {
        const canvas = document.getElementById(id);
        if (!canvas || typeof Chart === "undefined") return null;
        if (charts[id]) {
            charts[id].data = config.data;
            charts[id].options = config.options;
            charts[id].update("none");
            return charts[id];
        }
        charts[id] = new Chart(canvas, config);
        return charts[id];
    }

    function line(id, labels, series) {
        return upsert(id, {
            type: "line",
            data: { labels, datasets: series.map((s) => ({
                label: s.label, data: s.data, borderColor: s.color, backgroundColor: s.color,
                borderWidth: 2, cubicInterpolationMode: "monotone", pointRadius: 0, pointHoverRadius: 5,
                pointHoverBorderColor: cssVar("--surface"), pointHoverBorderWidth: 2, fill: false,
            })) },
            options: base(),
        });
    }

    function bars(id, labels, series, { stacked = false, horizontal = false } = {}) {
        return upsert(id, {
            type: "bar",
            data: { labels, datasets: series.map((s) => ({
                label: s.label, data: s.data, backgroundColor: s.color, borderColor: cssVar("--surface"),
                borderWidth: stacked ? { top: 2 } : 0, borderRadius: 4, borderSkipped: stacked ? false : "start",
                maxBarThickness: horizontal ? 16 : 22, categoryPercentage: 0.7, barPercentage: 0.9,
            })) },
            options: base(stacked, horizontal),
        });
    }

    function legend(el, items) {
        if (!el) return;
        el.innerHTML = items.map((i) => `<span><i class="sq" style="background:${i.color}"></i>${esc(i.label)}</span>`).join("");
    }

    function table(detailsEl, headers, rows) {
        if (!detailsEl) return;
        const open = detailsEl.open;
        detailsEl.innerHTML = `<summary>View data table</summary><div class="table-wrap"><table>
            <thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>
            <tbody>${rows.length ? rows.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")
                : `<tr><td colspan="${headers.length}" class="empty">No data</td></tr>`}</tbody></table></div>`;
        detailsEl.open = open;
    }

    window.ITMCharts = { line, bars, legend, table };
})();
