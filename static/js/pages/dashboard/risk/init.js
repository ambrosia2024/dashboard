// static/js/pages/dashboard/risk/init.js

document.addEventListener("DOMContentLoaded", function () {
    const pair = { crop: "Lettuce", pathogen: "Salmonella" }; // current dummy default
    const pairLabel = `${pair.crop} — ${pair.pathogen}`;

    // Example events: short spikes around specified months
    const events = [
        { iso: "2022-07-01", type: "heatwave",   boost: 3.0 },
        { iso: "2023-09-01", type: "heavy_rain", boost: 2.2 }
    ];

    // Build a single crop–pathogen pair series (dummy)
    const rows = window.buildDummyRiskSeries({
         ...pair,
        startISO: "2021-01-01",
        endISO:   "2023-12-01",
        baseProb: 1.2,
        seasonAmp: 1.1,
        noise: 0.25,
        events
    });

    // Render the four charts
    window.renderToxinChart("toxinsChart", rows, pairLabel);
    window.renderPathogenConcChart("pathogenConcChart", rows, pairLabel);
    window.renderProbChart("probChart", rows, pairLabel);
    window.renderCasesChart("casesChart", rows, pairLabel);
    window.renderSeasonalHeatmap("seasonalHeatmap", rows, "risk_multiplier", pairLabel);

    const inRange = filterByPeriod(rows);
    window.renderToxinChart("toxinsChart", inRange, pairLabel);
    window.renderProbChart("probChart", inRange, pairLabel);
    window.renderCasesChart("casesChart", inRange, pairLabel);
    window.renderSeasonalHeatmap("seasonalHeatmap", inRange, "risk_multiplier", pairLabel);
    window.renderPathogenConcChart("pathogenConcChart", inRange, pairLabel);

    ['rm-start','rm-end','rm-scale'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', () => {
            const rerows = filterByPeriod(rows);
            window.renderToxinChart("toxinsChart", rerows, pairLabel);
            window.renderProbChart("probChart", rerows, pairLabel);
            window.renderCasesChart("casesChart", rerows, pairLabel);
            window.renderSeasonalHeatmap("seasonalHeatmap", rerows, "risk_multiplier", pairLabel);
            window.renderPathogenConcChart("pathogenConcChart", rerows, pairLabel);
        });
    });

    // OPTIONAL: expose a hook to re-render when switching to crop/pathogen later
    window.renderRiskFor = function (opts) {
        const next = { ...opts };
        const newRows = window.buildDummyRiskSeries({ ...next, events });
        const label = `${next.crop || "Crop"} — ${next.pathogen || "Pathogen"}`;

        window.renderToxinChart("toxinsChart", newRows, label);
        window.renderProbChart("probChart", newRows, label);
        window.renderCasesChart("casesChart", newRows, label);
        window.renderSeasonalHeatmap("seasonalHeatmap", newRows, "risk_multiplier", label);
    };
});

function filterByPeriod(rows) {
  const s = new Date(document.getElementById('rm-start')?.value || '2023-01-01');
  const e = new Date(document.getElementById('rm-end')?.value   || '2023-12-31');
  return rows.filter(r => {
    const d = new Date(r.date);
    return d >= s && d <= e;
  });
}



