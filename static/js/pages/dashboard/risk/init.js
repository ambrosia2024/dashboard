// static/js/pages/dashboard/risk/init.js

function mean(arr) {
    if (!arr.length) return 0;
    return arr.reduce((a,b)=>a+b,0) / arr.length;
}

function linearSlopeYPerStep(arr) {
    // simple least-squares slope with x = 0..n-1
    const n = arr.length;

    if (n < 2) return 0;

    const xbar = (n - 1) / 2;
    const ybar = mean(arr);

    let num = 0, den = 0;

    for (let i = 0; i < n; i++) {
        num += (i - xbar) * (arr[i] - ybar);
        den += (i - xbar) * (i - xbar);
    }

    return den === 0 ? 0 : num / den;
}

function pct(a, b) {
    if (!b) return 0;

    return (a / b) * 100;
}

function monthLabel(iso) {
    const d = new Date(iso);

    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
}

// Build HTML for toxins explanation
function explainToxins(rows) {
    if (!rows?.length) return "<em>No data in the selected period.</em>";

    const limit = rows[0]?.toxin_limit_ug_per_kg ?? window.RISK_CONFIG?.defaultToxinLimit ?? 0;

    const y = rows.map(r => r.toxin_level_ug_per_kg);
    const over = rows.filter(r => r.toxin_level_ug_per_kg > limit).length;
    const max = Math.max(...y), min = Math.min(...y);
    const avg = mean(y);
    const last = rows[rows.length - 1].toxin_level_ug_per_kg;
    const first = rows[0].toxin_level_ug_per_kg;

    const slope = linearSlopeYPerStep(y);              // μg/kg per step (step ≈ month)
    const trend = slope > 0.05 ? "rising" : slope < -0.05 ? "falling" : "flat";
    const arrow = slope > 0.05 ? "↑" : slope < -0.05 ? "↓" : "→";

    const period = `${monthLabel(rows[0].date)} → ${monthLabel(rows[rows.length-1].date)}`;
    const overPct = Math.round(pct(over, rows.length));

    return `
        <strong>What this shows</strong>
        <ul class="mb-2">
          <li><em>${period}</em> toxin levels for <strong>${rows[0].crop}</strong> — <strong>${rows[0].pathogen}</strong> (μg/kg), with the action limit at <strong>${limit}</strong>.</li>
        </ul>
        <strong>Key numbers</strong>
        <ul class="mb-2">
          <li>Average: <strong>${avg.toFixed(1)}</strong> μg/kg (min <strong>${min.toFixed(1)}</strong>, max <strong>${max.toFixed(1)}</strong>).</li>
          <li>Above limit: <strong>${over}</strong> of ${rows.length} points (<strong>${overPct}%</strong>).</li>
          <li>Trend: <strong>${trend}</strong> ${arrow} (≈ ${slope.toFixed(2)} μg/kg per month).</li>
          <li>Latest value: <strong>${last.toFixed(1)}</strong> μg/kg; change vs first point: <strong>${(last-first>=0?'+':'')}${(last-first).toFixed(1)}</strong>.</li>
        </ul>
        <strong>Interpretation</strong>
        <p class="mb-2">
          The series is ${trend}. ${over ? `There are occasional exceedances over the ${limit} μg/kg limit; consider investigating those months for heatwaves, rainfall, or handling issues.` : `No exceedances detected in the selected period.`}
        </p>
        <strong>Note</strong>
        <p class="mb-2">
          Values are illustrative dummy outputs - illustrative only.
        </p>
      `;
}

// Build HTML for pathogen explanation
function explainPathogens(rows) {
    if (!rows?.length) return "<em>No data in the selected period.</em>";

    const y = rows.map(r => r.pathogen_conc_units_per_g ?? 0);
    const max = Math.max(...y), min = Math.min(...y);
    const avg = mean(y);
    const last = y[y.length - 1];
    const first = y[0];

    const slope = linearSlopeYPerStep(y);
    const trend = slope > 0.05 ? "rising" : slope < -0.05 ? "falling" : "flat";
    const arrow = slope > 0.05 ? "↑" : slope < -0.05 ? "↓" : "→";

    const period = `${monthLabel(rows[0].date)} → ${monthLabel(rows[rows.length-1].date)}`;

    // crude “elevated month” marker: above avg + 1 sd
    const sd = Math.sqrt(mean(y.map(v => (v-avg)*(v-avg))));
    const elevatedCount = y.filter(v => v >= (avg + sd)).length;

    return `
    <strong>What this shows</strong>
    <ul class="mb-2">
      <li><em>${period}</em> pathogen concentration for <strong>${rows[0].crop}</strong> — <strong>${rows[0].pathogen}</strong> (units/g).</li>
    </ul>
    <strong>Key numbers</strong>
    <ul class="mb-2">
      <li>Average: <strong>${avg.toFixed(1)}</strong> units/g (min <strong>${min.toFixed(1)}</strong>, max <strong>${max.toFixed(1)}</strong>).</li>
      <li>Trend: <strong>${trend}</strong> ${arrow} (≈ ${slope.toFixed(2)} units/g per month).</li>
      <li>Elevated months (≥ mean + 1σ): <strong>${elevatedCount}</strong>.</li>
      <li>Latest value: <strong>${last.toFixed(1)}</strong> units/g; change vs first point: <strong>${(last-first>=0?'+':'')}${(last-first).toFixed(1)}</strong>.</li>
    </ul>
    <strong>Interpretation</strong>
    <p class="mb-2">
      Concentrations are ${trend}. Peaks often align with rainfall events in the dummy model.
    </p>
    <strong>Note</strong>
    <p class="mb-2">
      Values are illustrative dummy outputs - illustrative only.
    </p>
  `;
}

function explainProbability(rows) {
    if (!rows?.length) return "<em>No data in the selected period.</em>";

    const y = rows.map(r => r.prob_illness_pct);
    const baseline = y[0];
    const avg = mean(y), min = Math.min(...y), max = Math.max(...y);
    const slope = linearSlopeYPerStep(y);
    const trend = slope > 0.02 ? "rising" : slope < -0.02 ? "falling" : "flat";
    const arrow = slope > 0.02 ? "↑" : slope < -0.02 ? "↓" : "→";
    const last = y[y.length - 1];
    const incPct = baseline > 0 ? ((last - baseline) / baseline) * 100 : 0;
    const period = `${monthLabel(rows[0].date)} → ${monthLabel(rows[rows.length-1].date)}`;

    return `
        <strong>What this shows</strong>
        <ul class="mb-2">
          <li><em>${period}</em> probability that you become ill upon consuming <strong>${rows[0].crop}</strong> contaminated by <strong>${rows[0].pathogen}</strong> (%).</li>
          <li>Baseline = first value in the selected period.</li>
        </ul>
        <strong>Key numbers</strong>
        <ul class="mb-2">
          <li>Average: <strong>${avg.toFixed(2)}%</strong> (min <strong>${min.toFixed(2)}%</strong>, max <strong>${max.toFixed(2)}%</strong>).</li>
          <li>Trend: <strong>${trend}</strong> ${arrow} (≈ ${slope.toFixed(2)} %/month).</li>
          <li>Latest vs baseline: <strong>${last.toFixed(2)}%</strong> (${incPct>=0?'+':''}${incPct.toFixed(1)}%).</li>
        </ul>
        <strong>Interpretation</strong>
        <p class="mb-2">
          Line colour denotes increase vs baseline: Small &lt;10%, Moderate 10–25%, Large 25–50%, Significant &gt;50%.
          Use sustained increases to trigger targeted controls (e.g., hygiene or cold-chain checks).
        </p>
        <strong>Note</strong>
        <p class="mb-2">
          Values are illustrative dummy outputs - illustrative only.
        </p>
    `;
}

function explainCases(rows) {
    if (!rows?.length) return "<em>No data in the selected period.</em>";

    const y = rows.map(r => r.cases_per_100k);
    const avg = Math.round(mean(y));
    const min = Math.min(...y), max = Math.max(...y);
    const last = y[y.length - 1];
    const first = y[0];
    const slope = linearSlopeYPerStep(y);
    const trend = slope > 5 ? "rising" : slope < -5 ? "falling" : "flat";
    const arrow = slope > 5 ? "↑" : slope < -5 ? "↓" : "→";
    const period = `${monthLabel(rows[0].date)} → ${monthLabel(rows[rows.length-1].date)}`;

    return `
        <strong>What this shows</strong>
        <ul class="mb-2">
          <li><em>${period}</em> expected cases per 100,000 people (derived from probability × exposure).</li>
          <li>Green line in the chart is a ${window.RISK_CONFIG?.rollingWindow || 3}-period moving average.</li>
        </ul>
        <strong>Key numbers</strong>
        <ul class="mb-2">
          <li>Average: <strong>${avg}</strong> per 100k (min <strong>${min}</strong>, max <strong>${max}</strong>).</li>
          <li>Trend: <strong>${trend}</strong> ${arrow} (latest: <strong>${last}</strong>; change vs first: <strong>${(last-first>=0?'+':'')}${last-first}</strong>).</li>
        </ul>
        <strong>Interpretation</strong>
        <p class="mb-2">
          Use peaks and moving-average direction to plan interventions and communications; cases reflect both risk and exposure.
        </p>
        <strong>Note</strong>
        <p class="mb-2">
          Values are illustrative dummy outputs - illustrative only.
        </p>
    `;
}

function explainHeatmap(rows) {
    if (!rows?.length) return "<em>No data in the selected period.</em>";

    // We passed risk_multiplier = local multiplier vs start-of-period
    const period = `${rows[0].year}–${rows[rows.length-1].year}`;
    // derive multipliers if missing to avoid NaN when callers pass plain rows
    const base = rows[0]?.prob_illness_pct ?? 0;
    const vals = rows.map(r => {
        if (Number.isFinite(r.risk_multiplier)) return r.risk_multiplier;
        return base > 0 ? (r.prob_illness_pct / base) : 0;
    });
    const max = Math.max(...vals), min = Math.min(...vals), avg = mean(vals);

    return `
        <strong>What this shows</strong>
        <ul class="mb-2">
          <li>Month × Year heatmap of <em>× baseline</em>, where baseline is the first value in the selected period.</li>
          <li>Darker orange/red ⇒ higher multiple of baseline.</li>
        </ul>
        <strong>Key numbers</strong>
        <ul class="mb-2">
          <li>Average multiplier: <strong>${avg.toFixed(2)}×</strong> (min <strong>${min.toFixed(2)}×</strong>, max <strong>${max.toFixed(2)}×</strong>).</li>
        </ul>
        <strong>Interpretation</strong>
        <p class="mb-2">
          Highlights seasonal pockets with risk markedly above the period’s starting level; focus sampling and controls in those months.
        </p>
        <strong>Note</strong>
        <p class="mb-2">
          Values are illustrative dummy outputs - illustrative only.
        </p>
    `;
}

// Safely write summary HTML into the page
function renderExplanations(toxinRows, pathogenRows, heatRows = toxinRows) {
    const toxEl = document.getElementById("toxinsExplain");
    const patEl = document.getElementById("pathogenExplain");
    const probEl = document.getElementById("probExplain");
    const casesEl = document.getElementById("casesExplain");
    const heatEl = document.getElementById("heatmapExplain");

    if (toxEl) toxEl.innerHTML = explainToxins(toxinRows);
    if (patEl) patEl.innerHTML = explainPathogens(pathogenRows);
    if (probEl) probEl.innerHTML = explainProbability(toxinRows);
    if (casesEl) casesEl.innerHTML = explainCases(toxinRows);
    if (heatEl) heatEl.innerHTML = explainHeatmap(heatRows);
}

// ---- Probability interpretation helpers ----
function fmtPct(v, digits = 2) {
    return `${(v ?? 0).toFixed(digits)}%`;
}

function buildProbInterpretationHTML(rows, idx) {
    if (!rows?.length) return "<em>No data.</em>";

    const i = Math.max(0, Math.min(idx ?? rows.length - 1, rows.length - 1));
    const r = rows[i];

    const baseline = rows[0]?.prob_illness_pct ?? 0;
    const current  = r.prob_illness_pct ?? 0;
    const xbase    = baseline > 0 ? current / baseline : 0;
    const deltaPct = baseline > 0 ? ((current - baseline) / baseline) * 100 : 0;

    const dateLabel = r.date;
    const band =
        deltaPct < 0  ? "Lower than baseline"
        : deltaPct < 10 ? "Small increase (<10%)"
        : deltaPct < 25 ? "Moderate increase (10–25%)"
        : deltaPct < 50 ? "Large increase (25–50%)"
        : "Significant increase (>50%)";

    // Render the nice 3-column table
    return `
        <table class="table table-sm align-middle">
          <tbody>
            <tr><th style="width: 240px">Date</th>
                <td style="width: 420px">The time point (month end).</td>
                <td><strong>${dateLabel}</strong> — this observation.</td></tr>
    
            <tr><th>P(illness)</th>
                <td>The model’s predicted probability that you become ill after consuming the crop.</td>
                <td><strong>${fmtPct(current)}</strong> — roughly ${(current/100).toFixed(3)} of the population per serving.</td></tr>
    
            <tr><th>Baseline</th>
                <td>The reference risk at the <em>start of the selected period</em>.</td>
                <td><strong>${fmtPct(baseline)}</strong> — your period’s “normal”.</td></tr>
    
            <tr><th>× baseline</th>
                <td>Ratio = current ÷ baseline.</td>
                <td><strong>${xbase.toFixed(2)}×</strong> — current is ${Math.round(xbase*100)}% of baseline.</td></tr>
    
            <tr><th>Δ vs baseline</th>
                <td>Percentage change from baseline.</td>
                <td><strong>${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(1)}%</strong> (${band}).</td></tr>
          </tbody>
        </table>
    
        <p class="mb-0">
          <strong>Summary:</strong> On <strong>${dateLabel}</strong>, risk was
          <strong>${deltaPct >= 0 ? `${deltaPct.toFixed(1)}% higher` : `${Math.abs(deltaPct).toFixed(1)}% lower`}</strong>
          than at the period start (baseline ${fmtPct(baseline)}), with a current probability of <strong>${fmtPct(current)}</strong>.
        </p>
    `;
}

// Open the modal with interpretation for index idx (or last / latest if absent)
window.showProbPointInterpretation = function(rows, idx) {
    const body = document.getElementById('probExplainModalBody');

    if (!body) return;

    const useIdx = (typeof idx === 'number' ? idx
                : (typeof window.__probLastIndex === 'number' ? window.__probLastIndex
                : rows.length - 1));

    body.innerHTML = buildProbInterpretationHTML(rows, useIdx);

    // Bootstrap 5 modal show
    const modalEl = document.getElementById('probExplainModal');

    if (!modalEl) return;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);

    modal.show();
};

window.__probLastIndex = null;     // last hover index
window.__probPinnedIndex = null;   // pinned by click

function _probSelectIndex() {
    if (typeof window.__probPinnedIndex === 'number') return window.__probPinnedIndex;

    if (typeof window.__probLastIndex === 'number')   return window.__probLastIndex;

    return null;
}

document.addEventListener("DOMContentLoaded", function () {
    // 1) try to read what the homepage stored
    const storedCropLabel    = localStorage.getItem("lx_selected_crop_label");
    const storedPathogenLabel = localStorage.getItem("lx_selected_pathogen_label");

    // 2) fallback to old static values
    const pair = {
        crop: storedCropLabel    || "Lettuce",
        pathogen: storedPathogenLabel || "Salmonella"
    };
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

    const b0Full = rows.length ? rows[0].prob_illness_pct : 0;
    const hmRowsFull = rows.map(r => ({
        ...r,
        // local multiplier vs start-of-period (rows[0])
        risk_multiplier: b0Full > 0 ? +(r.prob_illness_pct / b0Full).toFixed(2) : 0
    }));
    window.renderSeasonalHeatmap("seasonalHeatmap", hmRowsFull, "risk_multiplier", pairLabel);

    renderExplanations(rows, rows, hmRowsFull);

    // Button: show interpretation for the last clicked point, else the latest point
    const btn = document.getElementById('probExplainBtn');
    if (btn) btn.addEventListener('click', () => {
        const windowRows = filterByPeriod(rows);
        const idx = _probSelectIndex();
        window.showProbPointInterpretation(windowRows, typeof idx === 'number' ? idx : windowRows.length - 1);
    });


    const inRange = filterByPeriod(rows);
    window.renderToxinChart("toxinsChart", inRange, pairLabel);
    window.renderProbChart("probChart", inRange, pairLabel);
    window.renderCasesChart("casesChart", inRange, pairLabel);
    window.renderPathogenConcChart("pathogenConcChart", inRange, pairLabel);

    const b0 = inRange.length ? inRange[0].prob_illness_pct : 0;
    const hmRows = inRange.map(r => ({
        ...r,
        risk_multiplier: b0 > 0 ? +(r.prob_illness_pct / b0).toFixed(2) : 0
    }));
    window.renderSeasonalHeatmap("seasonalHeatmap", hmRows, "risk_multiplier", pairLabel);

    // window.renderSeasonalHeatmap("seasonalHeatmap", inRange, "risk_multiplier", pairLabel);

    renderExplanations(inRange, inRange, hmRows);

    ['rm-start','rm-end','rm-scale'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('input', () => {
            const rerows = filterByPeriod(rows);
            window.renderToxinChart("toxinsChart", rerows, pairLabel);
            window.renderProbChart("probChart", rerows, pairLabel);
            window.renderCasesChart("casesChart", rerows, pairLabel);
            window.renderPathogenConcChart("pathogenConcChart", rerows, pairLabel);

            // heatmap with local baseline
            const b0R = rerows.length ? rerows[0].prob_illness_pct : 0;
            const hmR = rerows.map(r => ({
                ...r,
                risk_multiplier: b0R > 0 ? +(r.prob_illness_pct / b0R).toFixed(2) : 0
            }));
            window.renderSeasonalHeatmap("seasonalHeatmap", hmR, "risk_multiplier", pairLabel);

            // window.renderSeasonalHeatmap("seasonalHeatmap", rerows, "risk_multiplier", pairLabel);

            renderExplanations(rerows, rerows, hmR);
        });
    });

    // OPTIONAL: expose a hook to re-render when switching to crop/pathogen later
    window.renderRiskFor = function (opts) {
        const next = { ...opts };
        const newRows = window.buildDummyRiskSeries({ ...next, events });
        const label = `${next.crop || "Crop"} — ${next.pathogen || "Pathogen"}`;

        const b0 = newRows.length ? newRows[0].prob_illness_pct : 0;
        const hmRows = newRows.map(r => ({
            ...r,
            risk_multiplier: b0 > 0 ? +(r.prob_illness_pct / b0).toFixed(2) : 0
        }));

        window.renderToxinChart("toxinsChart", newRows, label);
        window.renderProbChart("probChart", newRows, label);
        window.renderCasesChart("casesChart", newRows, label);

        window.renderSeasonalHeatmap("seasonalHeatmap", hmRows, "risk_multiplier", label);
        renderExplanations(newRows, newRows, hmRows);
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

