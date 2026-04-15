// static/js/pages/dashboard/risk/init.js
// Single entrypoint that renders ONLY charts that exist in the DOM.
// Supports per-chart config injected via window.__AMBROSIA_CHART_CONFIGS[domId].

/* -----------------------
   Small numeric helpers
------------------------ */

function mean(arr) {
  if (!arr || !arr.length) return 0;
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function linearSlopeYPerStep(arr) {
  // simple least-squares slope with x = 0..n-1
  const n = arr?.length ?? 0;
  if (n < 2) return 0;

  const xbar = (n - 1) / 2;
  const ybar = mean(arr);

  let num = 0;
  let den = 0;

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
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short" });
}

/* -----------------------
   Explanation builders
------------------------ */

function explainToxins(rows) {
  if (!rows?.length) return "<em>No data in the selected period.</em>";

  const limit =
    rows[0]?.toxin_limit_ug_per_kg ??
    window.RISK_CONFIG?.defaultToxinLimit ??
    0;

  const y = rows.map((r) => r.toxin_level_ug_per_kg);
  const over = rows.filter((r) => r.toxin_level_ug_per_kg > limit).length;

  const max = Math.max(...y);
  const min = Math.min(...y);
  const avg = mean(y);

  const last = rows[rows.length - 1].toxin_level_ug_per_kg;
  const first = rows[0].toxin_level_ug_per_kg;

  const slope = linearSlopeYPerStep(y); // μg/kg per step (step ≈ month)
  const trend = slope > 0.05 ? "rising" : slope < -0.05 ? "falling" : "flat";
  const arrow = slope > 0.05 ? "↑" : slope < -0.05 ? "↓" : "→";

  const period = `${monthLabel(rows[0].date)} → ${monthLabel(
    rows[rows.length - 1].date
  )}`;
  const overPct = Math.round(pct(over, rows.length));

  return `
    <strong>What this shows</strong>
    <ul class="mb-2">
      <li><em>${period}</em> toxin levels for <strong>${rows[0].crop}</strong> - <strong>${rows[0].pathogen}</strong> (μg/kg), with the action limit at <strong>${limit}</strong>.</li>
    </ul>
    <strong>Key numbers</strong>
    <ul class="mb-2">
      <li>Average: <strong>${avg.toFixed(1)}</strong> μg/kg (min <strong>${min.toFixed(
        1
      )}</strong>, max <strong>${max.toFixed(1)}</strong>).</li>
      <li>Above limit: <strong>${over}</strong> of ${rows.length} points (<strong>${overPct}%</strong>).</li>
      <li>Trend: <strong>${trend}</strong> ${arrow} (≈ ${slope.toFixed(
        2
      )} μg/kg per month).</li>
      <li>Latest value: <strong>${last.toFixed(
        1
      )}</strong> μg/kg; change vs first point: <strong>${(last - first >= 0
        ? "+"
        : "")}${(last - first).toFixed(1)}</strong>.</li>
    </ul>
    <strong>Interpretation</strong>
    <p class="mb-2">
      The series is ${trend}. ${
        over
          ? `There are occasional exceedances over the ${limit} μg/kg limit; consider investigating those months for heatwaves, rainfall, or handling issues.`
          : `No exceedances detected in the selected period.`
      }
    </p>
    <strong>Note</strong>
    <p class="mb-2">
      Values are illustrative dummy outputs - illustrative only.
    </p>
  `;
}

function explainPathogens(rows) {
  if (!rows?.length) return "<em>No data in the selected period.</em>";

  const y = rows.map((r) => r.pathogen_conc_units_per_g ?? 0);

  const max = Math.max(...y);
  const min = Math.min(...y);
  const avg = mean(y);

  const last = y[y.length - 1];
  const first = y[0];

  const slope = linearSlopeYPerStep(y);
  const trend = slope > 0.05 ? "rising" : slope < -0.05 ? "falling" : "flat";
  const arrow = slope > 0.05 ? "↑" : slope < -0.05 ? "↓" : "→";

  const period = `${monthLabel(rows[0].date)} → ${monthLabel(
    rows[rows.length - 1].date
  )}`;

  // crude “elevated month” marker: above avg + 1 sd
  const sd = Math.sqrt(mean(y.map((v) => (v - avg) * (v - avg))));
  const elevatedCount = y.filter((v) => v >= avg + sd).length;

  return `
    <strong>What this shows</strong>
    <ul class="mb-2">
      <li><em>${period}</em> pathogen concentration for <strong>${rows[0].crop}</strong> - <strong>${rows[0].pathogen}</strong> (units/g).</li>
    </ul>
    <strong>Key numbers</strong>
    <ul class="mb-2">
      <li>Average: <strong>${avg.toFixed(1)}</strong> units/g (min <strong>${min.toFixed(
        1
      )}</strong>, max <strong>${max.toFixed(1)}</strong>).</li>
      <li>Trend: <strong>${trend}</strong> ${arrow} (≈ ${slope.toFixed(
        2
      )} units/g per month).</li>
      <li>Elevated months (≥ mean + 1σ): <strong>${elevatedCount}</strong>.</li>
      <li>Latest value: <strong>${last.toFixed(
        1
      )}</strong> units/g; change vs first point: <strong>${(last - first >= 0
        ? "+"
        : "")}${(last - first).toFixed(1)}</strong>.</li>
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

  const y = rows.map((r) => r.prob_illness_pct);

  const baseline = y[0];
  const avg = mean(y);
  const min = Math.min(...y);
  const max = Math.max(...y);

  const slope = linearSlopeYPerStep(y);
  const trend = slope > 0.02 ? "rising" : slope < -0.02 ? "falling" : "flat";
  const arrow = slope > 0.02 ? "↑" : slope < -0.02 ? "↓" : "→";

  const last = y[y.length - 1];
  const incPct = baseline > 0 ? ((last - baseline) / baseline) * 100 : 0;

  const period = `${monthLabel(rows[0].date)} → ${monthLabel(
    rows[rows.length - 1].date
  )}`;

  return `
    <strong>What this shows</strong>
    <ul class="mb-2">
      <li><em>${period}</em> probability that you become ill upon consuming <strong>${rows[0].crop}</strong> contaminated by <strong>${rows[0].pathogen}</strong> (%).</li>
      <li>Baseline = first value in the selected period.</li>
    </ul>
    <strong>Key numbers</strong>
    <ul class="mb-2">
      <li>Average: <strong>${avg.toFixed(2)}%</strong> (min <strong>${min.toFixed(
        2
      )}%</strong>, max <strong>${max.toFixed(2)}%</strong>).</li>
      <li>Trend: <strong>${trend}</strong> ${arrow} (≈ ${slope.toFixed(
        2
      )} %/month).</li>
      <li>Latest vs baseline: <strong>${last.toFixed(2)}%</strong> (${incPct >= 0 ? "+" : ""}${incPct.toFixed(
        1
      )}%).</li>
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

  const y = rows.map((r) => r.cases_per_100k);

  const avg = Math.round(mean(y));
  const min = Math.min(...y);
  const max = Math.max(...y);

  const last = y[y.length - 1];
  const first = y[0];

  const slope = linearSlopeYPerStep(y);
  const trend = slope > 5 ? "rising" : slope < -5 ? "falling" : "flat";
  const arrow = slope > 5 ? "↑" : slope < -5 ? "↓" : "→";

  const period = `${monthLabel(rows[0].date)} → ${monthLabel(
    rows[rows.length - 1].date
  )}`;

  return `
    <strong>What this shows</strong>
    <ul class="mb-2">
      <li><em>${period}</em> expected cases per 100,000 people (derived from probability × exposure).</li>
      <li>Green line in the chart is a ${window.RISK_CONFIG?.rollingWindow || 3}-period moving average.</li>
    </ul>
    <strong>Key numbers</strong>
    <ul class="mb-2">
      <li>Average: <strong>${avg}</strong> per 100k (min <strong>${min}</strong>, max <strong>${max}</strong>).</li>
      <li>Trend: <strong>${trend}</strong> ${arrow} (latest: <strong>${last}</strong>; change vs first: <strong>${(last - first >= 0 ? "+" : "")}${last - first}</strong>).</li>
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
  const base = rows[0]?.prob_illness_pct ?? 0;
  const vals = rows.map((r) => {
    if (Number.isFinite(r.risk_multiplier)) return r.risk_multiplier;
    return base > 0 ? r.prob_illness_pct / base : 0;
  });

  const max = Math.max(...vals);
  const min = Math.min(...vals);
  const avg = mean(vals);

  return `
    <strong>What this shows</strong>
    <ul class="mb-2">
      <li>Month × Year heatmap of <em>× baseline</em>, where baseline is the first value in the selected period.</li>
      <li>Darker orange/red ⇒ higher multiple of baseline.</li>
    </ul>
    <strong>Key numbers</strong>
    <ul class="mb-2">
      <li>Average multiplier: <strong>${avg.toFixed(2)}×</strong> (min <strong>${min.toFixed(
    2
  )}×</strong>, max <strong>${max.toFixed(2)}×</strong>).</li>
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

/* -----------------------
   Probability modal bits
------------------------ */

function fmtPct(v, digits = 2) {
  return `${(v ?? 0).toFixed(digits)}%`;
}

function buildProbInterpretationHTML(rows, idx) {
  if (!rows?.length) return "<em>No data.</em>";

  const i = Math.max(0, Math.min(idx ?? rows.length - 1, rows.length - 1));
  const r = rows[i];

  const baseline = rows[0]?.prob_illness_pct ?? 0;
  const current = r.prob_illness_pct ?? 0;

  const xbase = baseline > 0 ? current / baseline : 0;
  const deltaPct = baseline > 0 ? ((current - baseline) / baseline) * 100 : 0;

  const dateLabel = r.date;
  const band =
    deltaPct < 0
      ? "Lower than baseline"
      : deltaPct < 10
      ? "Small increase (<10%)"
      : deltaPct < 25
      ? "Moderate increase (10–25%)"
      : deltaPct < 50
      ? "Large increase (25–50%)"
      : "Significant increase (>50%)";

  return `
    <table class="table table-sm align-middle">
      <tbody>
        <tr><th style="width: 240px">Date</th>
            <td style="width: 420px">The time point (month end).</td>
            <td><strong>${dateLabel}</strong> - this observation.</td></tr>

        <tr><th>P(illness)</th>
            <td>The model’s predicted probability that you become ill after consuming the crop.</td>
            <td><strong>${fmtPct(current)}</strong> - roughly ${(current / 100).toFixed(3)} of the population per serving.</td></tr>

        <tr><th>Baseline</th>
            <td>The reference risk at the <em>start of the selected period</em>.</td>
            <td><strong>${fmtPct(baseline)}</strong> - your period’s “normal”.</td></tr>

        <tr><th>× baseline</th>
            <td>Ratio = current ÷ baseline.</td>
            <td><strong>${xbase.toFixed(2)}×</strong> - current is ${Math.round(xbase * 100)}% of baseline.</td></tr>

        <tr><th>Δ vs baseline</th>
            <td>Percentage change from baseline.</td>
            <td><strong>${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(1)}%</strong> (${band}).</td></tr>
      </tbody>
    </table>

    <p class="mb-0">
      <strong>Summary:</strong> On <strong>${dateLabel}</strong>, risk was
      <strong>${
        deltaPct >= 0
          ? `${deltaPct.toFixed(1)}% higher`
          : `${Math.abs(deltaPct).toFixed(1)}% lower`
      }</strong>
      than at the period start (baseline ${fmtPct(baseline)}), with a current probability of <strong>${fmtPct(
    current
  )}</strong>.
    </p>
  `;
}

window.showProbPointInterpretation = function (rows, idx) {
  const body = document.getElementById("probExplainModalBody");
  if (!body) return;

  const useIdx =
    typeof idx === "number"
      ? idx
      : typeof window.__probLastIndex === "number"
      ? window.__probLastIndex
      : rows.length - 1;

  body.innerHTML = buildProbInterpretationHTML(rows, useIdx);

  const modalEl = document.getElementById("probExplainModal");
  if (!modalEl) return;

  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
};

window.__probLastIndex = null; // last hover index
window.__probPinnedIndex = null; // pinned by click

function probSelectIndex() {
  if (typeof window.__probPinnedIndex === "number") return window.__probPinnedIndex;
  if (typeof window.__probLastIndex === "number") return window.__probLastIndex;
  return null;
}

/* -----------------------
   Config + render pipeline
------------------------ */

function getCfg(domId) {
  return (window.__AMBROSIA_CHART_CONFIGS && window.__AMBROSIA_CHART_CONFIGS[domId]) || {};
}

function fileStamp() {
  return new Date()
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\.\d+Z$/, "")
    .replace("T", "_");
}

function safeName(s, fallback = "value") {
  return (s || fallback).toString().trim().replace(/\s+/g, "_").replace(/[^\w.-]/g, "");
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function loadScriptOnce(src, globalName) {
  if (globalName && window[globalName]) return Promise.resolve(window[globalName]);
  return new Promise((resolve, reject) => {
    const exists = Array.from(document.scripts).find((s) => s.src === src);
    if (exists) {
      exists.addEventListener("load", () => resolve(globalName ? window[globalName] : true), { once: true });
      exists.addEventListener("error", reject, { once: true });
      if (!globalName || window[globalName]) resolve(globalName ? window[globalName] : true);
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = () => resolve(globalName ? window[globalName] : true);
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

const CHART_EXPORT_META = {
  toxin: {
    title: "Toxin concentration vs time",
    instanceKey: "__toxinsChartInstance",
    rowsKey: "__toxinsRowsCurrent",
    sheetName: "toxin_data",
    buildRows(rows, ctx) {
      return rows.map((r) => ({
        date: r.date,
        crop: r.crop,
        hazard: r.pathogen,
        location: ctx.location,
        nuts2_id: ctx.nuts2,
        nuts2_name: ctx.nuts2Name,
        toxin_ug_per_kg: r.toxin_level_ug_per_kg,
        toxin_limit_ug_per_kg: r.toxin_limit_ug_per_kg,
        temperature_c: r.temperature_c,
        humidity_pct: r.humidity_pct,
        event: r.event,
      }));
    },
  },
  pathogen: {
    title: "Pathogen concentration vs time",
    instanceKey: "__pathogenChartInstance",
    rowsKey: "__pathogenRowsCurrent",
    sheetName: "pathogen_data",
    buildRows(rows, ctx) {
      return rows.map((r) => ({
        date: r.date,
        crop: r.crop,
        hazard: r.pathogen,
        location: ctx.location,
        nuts2_id: ctx.nuts2,
        nuts2_name: ctx.nuts2Name,
        pathogen_conc_units_per_g: r.pathogen_conc_units_per_g,
        toxin_ug_per_kg: r.toxin_level_ug_per_kg,
        temperature_c: r.temperature_c,
        humidity_pct: r.humidity_pct,
        event: r.event,
      }));
    },
  },
  probability: {
    title: "Probability of illness vs time",
    instanceKey: "__probChartInstance",
    rowsKey: "__probRowsCurrent",
    sheetName: "probability_data",
    buildRows(rows, ctx) {
      const baseline = rows.length ? rows[0].prob_illness_pct : null;
      return rows.map((r) => {
        const base =
          baseline ??
          r.baseline_prob_illness_pct ??
          r.prob_illness_pct ??
          0;
        const multiplier = base > 0 ? (r.prob_illness_pct ?? 0) / base : 0;
        return {
          date: r.date,
          crop: r.crop,
          hazard: r.pathogen,
          location: ctx.location,
          nuts2_id: ctx.nuts2,
          nuts2_name: ctx.nuts2Name,
          prob_illness_pct: r.prob_illness_pct,
          baseline_prob_illness_pct: base,
          risk_multiplier: +multiplier.toFixed(2),
          delta_vs_baseline_pct:
            base > 0
              ? +(((r.prob_illness_pct ?? 0) - base) / base * 100).toFixed(2)
              : 0,
          event: r.event,
        };
      });
    },
  },
  cases: {
    title: "Cases per 100k vs time",
    instanceKey: "__casesChartInstance",
    rowsKey: "__casesRowsCurrent",
    sheetName: "cases_data",
    buildRows(rows, ctx) {
      return rows.map((r) => ({
        date: r.date,
        crop: r.crop,
        hazard: r.pathogen,
        location: ctx.location,
        nuts2_id: ctx.nuts2,
        nuts2_name: ctx.nuts2Name,
        prob_illness_pct: r.prob_illness_pct,
        cases_per_100k: r.cases_per_100k,
        rolling_mean_cases_per_100k: r.rolling_mean_cases_per_100k,
        event: r.event,
      }));
    },
  },
  seasonal: {
    title: "Seasonal heatmap",
    instanceKey: "__seasonalHeatmapInstance",
    rowsKey: "__seasonalRowsCurrent",
    sheetName: "seasonal_heatmap_data",
    buildRows(rows, ctx) {
      return rows.map((r) => ({
        date: r.date,
        year: r.year,
        month: r.month,
        crop: r.crop,
        hazard: r.pathogen,
        location: ctx.location,
        nuts2_id: ctx.nuts2,
        nuts2_name: ctx.nuts2Name,
        prob_illness_pct: r.prob_illness_pct,
        risk_multiplier: r.risk_multiplier,
        mode: window.__seasonalModeCurrent || "risk_multiplier",
        event: r.event,
      }));
    },
  },
};

function exportBaseName(chartKey, rows) {
  const crop = safeName(rows?.[0]?.crop || localStorage.getItem("lx_selected_crop_label") || "crop");
  const hazard = safeName(rows?.[0]?.pathogen || localStorage.getItem("lx_selected_pathogen_label") || "hazard");
  return `${safeName(chartKey || "chart")}_${crop}_${hazard}_${fileStamp()}`;
}

function getExportContext() {
  return {
    nuts2: localStorage.getItem("lx_selected_nuts2_id") || "",
    nuts2Name: localStorage.getItem("lx_selected_nuts2_name") || "",
    location: localStorage.getItem("lx_selected_location") || "",
  };
}

function buildCsv(rows) {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]);
  return [
    headers.join(","),
    ...rows.map((row) =>
      headers
        .map((h) => `"${String(row[h] ?? "").replace(/"/g, '""')}"`)
        .join(",")
    ),
  ].join("\n");
}

async function exportChartByFormat(chartKey, fmt) {
  const meta = CHART_EXPORT_META[chartKey];
  if (!meta) return;

  const chart = window[meta.instanceKey];
  const rows = window[meta.rowsKey] || [];
  if (!chart || !rows.length) return;

  const base = exportBaseName(chartKey, rows);

  if (fmt === "png" || fmt === "jpg") {
    const dataURL = chart.getDataURL({
      type: fmt === "jpg" ? "jpeg" : "png",
      pixelRatio: 2,
      backgroundColor: "#ffffff",
    });
    const a = document.createElement("a");
    a.href = dataURL;
    a.download = `${base}.${fmt === "jpg" ? "jpg" : "png"}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    return;
  }

  if (fmt === "pdf") {
    const { jsPDF } = await loadScriptOnce(
      "https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js",
      "jspdf"
    );
    const dataURL = chart.getDataURL({
      type: "png",
      pixelRatio: 2,
      backgroundColor: "#ffffff",
    });
    const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
    const width = 277;
    const height = 150;
    pdf.text(meta.title, 10, 10);
    pdf.addImage(dataURL, "PNG", 10, 15, width, height, undefined, "FAST");
    pdf.save(`${base}.pdf`);
    return;
  }

  const exportRows = meta.buildRows(rows, getExportContext());
  if (!exportRows.length) return;

  if (fmt === "csv") {
    const csv = buildCsv(exportRows);
    downloadBlob(new Blob([csv], { type: "text/csv;charset=utf-8;" }), `${base}.csv`);
    return;
  }

  if (fmt === "xlsx") {
    const XLSX = await loadScriptOnce(
      "https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js",
      "XLSX"
    );
    const ws = XLSX.utils.json_to_sheet(exportRows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, meta.sheetName);
    XLSX.writeFile(wb, `${base}.xlsx`);
  }
}

function isISODate(value) {
  return /^\d{4}-\d{2}-\d{2}$/.test(value || "");
}

function normalizeRiskDateRange() {
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl) return;

  const start = startEl.value;
  const end = endEl.value;

  // Keep browser pickers constrained to a valid range.
  if (isISODate(start)) endEl.min = start;
  else endEl.removeAttribute("min");
  if (isISODate(end)) startEl.max = end;
  else startEl.removeAttribute("max");

  // Auto-fix invalid range if user typed dates manually.
  if (isISODate(start) && isISODate(end) && start > end) {
    endEl.value = start;
    endEl.min = start;
  }
}

function hydrateRiskDateFilters() {
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl) return;

  const params = new URLSearchParams(window.location.search);
  const qStart = params.get("start");
  const qEnd = params.get("end");
  const lsStart = localStorage.getItem("risk_filter_start");
  const lsEnd = localStorage.getItem("risk_filter_end");

  const start = isISODate(qStart) ? qStart : isISODate(lsStart) ? lsStart : startEl.value;
  const end = isISODate(qEnd) ? qEnd : isISODate(lsEnd) ? lsEnd : endEl.value;

  if (isISODate(start)) startEl.value = start;
  if (isISODate(end)) endEl.value = end;
  normalizeRiskDateRange();
}

function persistRiskDateFilters() {
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl) return;

  if (isISODate(startEl.value)) localStorage.setItem("risk_filter_start", startEl.value);
  if (isISODate(endEl.value)) localStorage.setItem("risk_filter_end", endEl.value);

  const url = new URL(window.location.href);
  if (isISODate(startEl.value)) url.searchParams.set("start", startEl.value);
  else url.searchParams.delete("start");
  if (isISODate(endEl.value)) url.searchParams.set("end", endEl.value);
  else url.searchParams.delete("end");
  window.history.replaceState({}, "", url.toString());
}

function filterByPeriod(rows) {
  const s = new Date(document.getElementById("rm-start")?.value || "2023-01-01");
  const e = new Date(document.getElementById("rm-end")?.value || "2023-12-31");

  return rows.filter((r) => {
    const d = new Date(r.date);
    return d >= s && d <= e;
  });
}

function getCookie(name) {
  const cookie = document.cookie
    .split(";")
    .map((v) => v.trim())
    .find((v) => v.startsWith(`${name}=`));
  return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
}

function getCsrfToken() {
  const fromForm = document.querySelector("#c1-chat-form input[name='csrfmiddlewaretoken']")?.value;
  if (fromForm) return fromForm;
  return getCookie("csrftoken");
}

function initC1ChartChat() {
  const toggleBtn = document.getElementById("c1-chat-toggle");
  const panel = document.getElementById("c1-chat-panel");
  const form = document.getElementById("c1-chat-form");
  const input = document.getElementById("c1-chat-input");
  const sendBtn = document.getElementById("c1-chat-send");
  const charCountEl = document.getElementById("c1-chat-char-count");
  const downloadBtn = document.getElementById("c1-chat-download");
  const thread = document.getElementById("c1-chat-thread");
  const quickPromptBtns = Array.from(document.querySelectorAll(".c1-chat-quick-prompt[data-c1-quick-prompt]"));
  if (!form || !input || !sendBtn || !thread || !downloadBtn || !toggleBtn || !panel) return;

  const chatHistory = [];
  const MAX_QUESTION_CHARS = Number(input.getAttribute("maxlength") || 1000);
  const CHAT_COOLDOWN_MS = 5000;
  const sendBtnDefaultLabel = sendBtn.textContent || "Send";
  let requestInFlight = false;
  let cooldownUntil = 0;
  let cooldownTimerId = null;

  function scrollThread() {
    thread.scrollTop = thread.scrollHeight;
  }

  function fmtTimestamp(ts) {
    const d = new Date(ts);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  function fmtDuration(ms) {
    const safe = Math.max(0, Number(ms || 0));
    if (safe < 1000) return `${safe} ms`;
    const s = safe / 1000;
    if (s < 60) return `${s.toFixed(2)} s`;
    const m = Math.floor(s / 60);
    const rs = s % 60;
    return `${m}m ${rs.toFixed(1)}s`;
  }

  function updateDownloadBtnState() {
    downloadBtn.disabled = chatHistory.length === 0;
  }

  function updateCharCounter() {
    if (!charCountEl) return;
    const len = (input.value || "").length;
    charCountEl.textContent = `${len}/${MAX_QUESTION_CHARS}`;
  }

  function updateSendBtnState() {
    const remainingMs = Math.max(0, cooldownUntil - Date.now());

    if (requestInFlight) {
      sendBtn.disabled = true;
      sendBtn.textContent = "Sending...";
      return;
    }

    if (remainingMs > 0) {
      sendBtn.disabled = true;
      sendBtn.textContent = `Wait ${Math.ceil(remainingMs / 1000)}s`;
      return;
    }

    sendBtn.disabled = false;
    sendBtn.textContent = sendBtnDefaultLabel;
  }

  function startCooldown() {
    cooldownUntil = Date.now() + CHAT_COOLDOWN_MS;
    if (cooldownTimerId) {
      clearInterval(cooldownTimerId);
      cooldownTimerId = null;
    }
    cooldownTimerId = setInterval(() => {
      updateSendBtnState();
      if (Date.now() >= cooldownUntil) {
        clearInterval(cooldownTimerId);
        cooldownTimerId = null;
        updateSendBtnState();
      }
    }, 200);
    updateSendBtnState();
  }

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderAssistantMarkdown(text) {
    let html = escapeHtml(text);

    // fenced code blocks
    html = html.replace(/```([\s\S]*?)```/g, "<pre class=\"mb-2\"><code>$1</code></pre>");
    // inline code
    html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    // bold + italic
    html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
    // bullet lines
    html = html.replace(/(?:^|\n)- (.+)/g, "<br>&bull; $1");
    // line breaks
    html = html.replace(/\n/g, "<br>");

    return html;
  }

  function isAssistantServiceMessage(text) {
    const normalized = String(text || "").trim().toLowerCase();
    return normalized.includes("ambra seems to be down at the moment")
      || normalized.includes("ambra is temporarily unavailable")
      || normalized.includes("please try again after some time")
      || normalized.includes("please try again later");
  }

  function openChatPanel() {
    panel.style.display = "";
    toggleBtn.style.display = "none";
    setTimeout(() => input.focus(), 0);
  }

  function isTypingTarget(el) {
    if (!el) return false;
    const tag = (el.tagName || "").toLowerCase();
    return tag === "input" || tag === "textarea" || tag === "select" || el.isContentEditable;
  }

  function addMessage(role, text = "", opts = {}) {
    const ts = opts.timestamp || new Date().toISOString();
    const wrap = document.createElement("div");
    wrap.className = role === "user" ? "d-flex justify-content-end mb-2" : "d-flex justify-content-start mb-2";

    const box = document.createElement("div");
    box.style.maxWidth = "85%";

    const bubble = document.createElement("div");
    const isServiceMessage = role === "assistant" && isAssistantServiceMessage(text);
    bubble.className = role === "user"
      ? "p-2 rounded bg-primary text-white"
      : isServiceMessage
      ? "p-2 rounded c1-chat-service-message"
      : "p-2 rounded bg-white border";
    bubble.style.whiteSpace = "pre-wrap";
    bubble.style.wordBreak = "break-word";
    if (role === "assistant") {
      bubble.innerHTML = renderAssistantMarkdown(text);
    } else {
      bubble.textContent = text;
    }

    const meta = document.createElement("div");
    meta.className = "small c1-chat-meta mt-1";
    meta.textContent = fmtTimestamp(ts);

    box.appendChild(bubble);
    box.appendChild(meta);
    wrap.appendChild(box);
    thread.appendChild(wrap);
    scrollThread();
    return { bubble, meta, timestamp: ts, role, rawText: text };
  }

  function downloadCurrentChat() {
    if (!chatHistory.length) return;
    const lines = [
      "Ambrosia C1 Chart Chat Export",
      `Generated: ${fmtTimestamp(new Date().toISOString())}`,
      "",
    ];

    chatHistory.forEach((entry, idx) => {
      lines.push(`#${idx + 1} [${fmtTimestamp(entry.timestamp)}] ${entry.role.toUpperCase()}`);
      lines.push(entry.text || "");
      if (entry.role === "assistant" && entry.metrics) {
        if (entry.metrics.firstTokenMs != null) {
          lines.push(
            `timing: thought=${fmtDuration(entry.metrics.firstTokenMs)}, answer=${fmtDuration(entry.metrics.answerMs)}, total=${fmtDuration(entry.metrics.totalMs)}`
          );
        } else {
          lines.push(`timing: total=${fmtDuration(entry.metrics.totalMs)}`);
        }
      }
      lines.push("");
    });

    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    downloadBlob(blob, `c1_chart_chat_${fileStamp()}.txt`);
  }

  async function askQuestion(question) {
    const chartIdentifier = form.getAttribute("data-chart-identifier") || "c1_toxin_over_time";
    const lowerId = chartIdentifier.toLowerCase();
    const chartKind = lowerId.includes("pathogen")
      ? "pathogen"
      : lowerId.includes("probability")
      ? "probability"
      : lowerId.includes("cases")
      ? "cases"
      : lowerId.includes("seasonal") || lowerId.includes("heatmap")
      ? "seasonal"
      : "toxin";

    function rowsForKind(kind) {
      if (kind === "pathogen") return window.__pathogenRowsCurrent || [];
      if (kind === "probability") return window.__probRowsCurrent || [];
      if (kind === "cases") return window.__casesRowsCurrent || [];
      if (kind === "seasonal") return window.__seasonalRowsCurrent || [];
      return window.__toxinsRowsCurrent || [];
    }

    function pointsForKind(kind, rows) {
      if (kind === "pathogen") {
        return rows.map((r) => ({
          date: r.date,
          pathogen_conc_units_per_g: r.pathogen_conc_units_per_g,
          baseline_pathogen_units_per_g: rows[0]?.pathogen_conc_units_per_g ?? null,
          toxin_ug_per_kg: r.toxin_level_ug_per_kg,
          temperature_c: r.temperature_c,
          humidity_pct: r.humidity_pct,
          event: r.event || "",
        }));
      }
      if (kind === "probability") {
        const baseline = rows[0]?.prob_illness_pct ?? null;
        return rows.map((r) => ({
          date: r.date,
          prob_illness_pct: r.prob_illness_pct,
          baseline_prob_illness_pct: baseline,
          risk_multiplier: baseline && baseline > 0 ? +(r.prob_illness_pct / baseline).toFixed(2) : null,
          toxin_ug_per_kg: r.toxin_level_ug_per_kg,
          event: r.event || "",
        }));
      }
      if (kind === "cases") {
        return rows.map((r) => ({
          date: r.date,
          cases_per_100k: r.cases_per_100k,
          rolling_mean_cases_per_100k: r.rolling_mean_cases_per_100k,
          prob_illness_pct: r.prob_illness_pct,
          event: r.event || "",
        }));
      }
      if (kind === "seasonal") {
        return rows.map((r) => ({
          date: r.date,
          year: r.year,
          month: r.month,
          prob_illness_pct: r.prob_illness_pct,
          risk_multiplier: r.risk_multiplier,
          mode: window.__seasonalModeCurrent || "risk_multiplier",
          event: r.event || "",
        }));
      }
      return rows.map((r) => ({
        date: r.date,
        toxin_ug_per_kg: r.toxin_level_ug_per_kg,
        toxin_limit_ug_per_kg: r.toxin_limit_ug_per_kg,
        temperature_c: r.temperature_c,
        humidity_pct: r.humidity_pct,
        event: r.event || "",
      }));
    }

    const rows = rowsForKind(chartKind);
    const first = rows[0] || {};
    const chartTitle = document.querySelector("h4 span")?.textContent?.trim() || "";
    const dashboardModeEl = document.getElementById("dashboard_mode");
    const dashboardViewCode = (dashboardModeEl?.value || "").trim();
    const dashboardViewLabel = (
      dashboardModeEl?.options?.[dashboardModeEl.selectedIndex]?.textContent || dashboardViewCode
    ).trim();
    const chartPoints = pointsForKind(chartKind, rows);
    const context = {
      chart_identifier: chartIdentifier,
      chart_kind: chartKind,
      chart_title: chartTitle,
      dashboard_view_code: dashboardViewCode,
      dashboard_view_label: dashboardViewLabel,
      crop: first.crop || localStorage.getItem("lx_selected_crop_label") || "",
      hazard: first.pathogen || localStorage.getItem("lx_selected_pathogen_label") || "",
      start_date: document.getElementById("rm-start")?.value || "",
      end_date: document.getElementById("rm-end")?.value || "",
      location: localStorage.getItem("lx_selected_location") || "",
      nuts2_id: localStorage.getItem("lx_selected_nuts2_id") || "",
      limit_ug_per_kg: first.toxin_limit_ug_per_kg ?? "",
      chart_points: chartPoints,
    };

    const qaUrl = `/api/risk-charts/${encodeURIComponent(chartIdentifier)}/qa-stream/`;

    const response = await fetch(qaUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify({ question, context }),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Request failed (${response.status})`);
    }

    if (!response.body) {
      throw new Error("No streaming response body.");
    }

    const startedAt = Date.now();
    let firstChunkAt = null;
    const answerMsg = addMessage("assistant", "");
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (firstChunkAt === null) firstChunkAt = Date.now();
      answerMsg.rawText += decoder.decode(value, { stream: true });
      answerMsg.bubble.innerHTML = renderAssistantMarkdown(answerMsg.rawText);
      scrollThread();
    }

    const endedAt = Date.now();
    const totalMs = endedAt - startedAt;
    const answerMs = firstChunkAt == null ? totalMs : endedAt - firstChunkAt;

    if (firstChunkAt != null) {
      answerMsg.meta.textContent = `${fmtTimestamp(answerMsg.timestamp)} • Thought ${fmtDuration(firstChunkAt - startedAt)} • Answered ${fmtDuration(answerMs)} • Total ${fmtDuration(totalMs)}`;
    } else {
      answerMsg.meta.textContent = `${fmtTimestamp(answerMsg.timestamp)} • Total ${fmtDuration(totalMs)}`;
    }

    chatHistory.push({
      role: "assistant",
      text: answerMsg.rawText,
      timestamp: answerMsg.timestamp,
      metrics: {
        firstTokenMs: firstChunkAt == null ? null : firstChunkAt - startedAt,
        answerMs,
        totalMs,
      },
    });
    updateDownloadBtnState();
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (Date.now() < cooldownUntil || requestInFlight) {
      updateSendBtnState();
      return;
    }
    const question = (input.value || "").trim();
    if (!question) return;

    const userMsg = addMessage("user", question);
    chatHistory.push({
      role: "user",
      text: question,
      timestamp: userMsg.timestamp,
    });
    updateDownloadBtnState();
    input.value = "";
    updateCharCounter();

    requestInFlight = true;
    startCooldown();
    try {
      await askQuestion(question);
    } catch (err) {
      const msg = (err && err.message) ? err.message : "I could not process this request right now. Please try again.";
      const errorMsg = addMessage("assistant", msg);
      chatHistory.push({
        role: "assistant",
        text: msg,
        timestamp: errorMsg.timestamp,
        metrics: null,
      });
      updateDownloadBtnState();
    } finally {
      requestInFlight = false;
      updateSendBtnState();
      input.focus();
    }
  });

  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      form.requestSubmit();
    }
  });
  input.addEventListener("input", updateCharCounter);

  downloadBtn.addEventListener("click", () => {
    downloadCurrentChat();
  });

  toggleBtn.addEventListener("click", () => {
    openChatPanel();
  });

  quickPromptBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = (btn.getAttribute("data-c1-quick-prompt") || "").trim();
      if (!prompt) return;
      input.value = prompt;
      updateCharCounter();
      if (!requestInFlight && Date.now() >= cooldownUntil) {
        form.requestSubmit();
      } else {
        openChatPanel();
      }
    });
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.defaultPrevented || ev.ctrlKey || ev.metaKey || ev.altKey) return;
    if (isTypingTarget(ev.target)) return;

    if (ev.key === "/") {
      ev.preventDefault();
      openChatPanel();
      input.focus();
      return;
    }

    if (String(ev.key || "").toLowerCase() === "c") {
      const contextPanel = document.getElementById("riskContextPanel");
      const contextFab = document.getElementById("riskContextFab");
      if (!contextPanel || !contextFab) return;
      if (!contextPanel.classList.contains("is-open")) {
        ev.preventDefault();
        contextFab.click();
      }
    }
  });

  updateCharCounter();
  updateSendBtnState();
}

document.addEventListener("DOMContentLoaded", function () {
  hydrateRiskDateFilters();
  persistRiskDateFilters();
  const RISK_CHART_DOM_IDS = [
    "toxinsChart",
    "toxinsChart3D",
    "pathogenConcChart",
    "probChart",
    "casesChart",
    "seasonalHeatmap",
  ];
  let renderLoadToken = 0;

  // 1) pull persisted crop/pathogen labels if present
  const storedCropLabel = localStorage.getItem("lx_selected_crop_label");
  const storedPathogenLabel = localStorage.getItem("lx_selected_pathogen_label");

  const pair = {
    crop: storedCropLabel || "Lettuce",
    pathogen: storedPathogenLabel || "Salmonella",
  };
  const pairLabel = `${pair.crop} - ${pair.pathogen}`;

  // Example events: short spikes around specified months
  const events = [
    { iso: "2022-07-01", type: "heatwave", boost: 3.0 },
    { iso: "2023-09-01", type: "heavy_rain", boost: 2.2 },
  ];

  // 2) build dummy rows (shared for all charts)
  const rows = window.buildDummyRiskSeries({
    ...pair,
    startISO: "2021-01-01",
    endISO: "2023-12-01",
    baseProb: 1.2,
    seasonAmp: 1.1,
    noise: 0.25,
    events,
  });

  function initRiskCardMotion() {
    const cards = Array.from(document.querySelectorAll(".page-content .card"));
    if (!cards.length) return;
    cards.forEach((card, idx) => {
      card.classList.add("risk-motion-card");
      card.style.setProperty("--risk-card-delay", `${Math.min(idx * 30, 240)}ms`);
    });
    requestAnimationFrame(() => {
      cards.forEach((card) => card.classList.add("is-visible"));
    });
  }

  function getVisibleChartDomIds() {
    return RISK_CHART_DOM_IDS.filter((id) => {
      const el = document.getElementById(id);
      return !!el && el.offsetParent !== null;
    });
  }

  function setChartsLoading(chartDomIds, isLoading) {
    chartDomIds.forEach((id) => {
      const chartEl = document.getElementById(id);
      if (!chartEl) return;
      chartEl.classList.toggle("risk-chart-skeleton", isLoading);
      chartEl.setAttribute("aria-busy", isLoading ? "true" : "false");
      const card = chartEl.closest(".card");
      if (card) card.classList.toggle("risk-card-loading", isLoading);
    });
  }

  // 3) render only charts that exist in the DOM
  function renderAllVisible(rerows, options = {}) {
    window.__riskBaseRowsCurrent = rerows;

    const withSkeleton = !!options.withSkeleton;
    const visibleIds = getVisibleChartDomIds();
    const loadToken = ++renderLoadToken;

    if (withSkeleton && visibleIds.length) {
      setChartsLoading(visibleIds, true);
    }

    const doRender = () => {
      // toxins (cfg-aware)
      if (document.getElementById("toxinsChart")) {
        const cfg = getCfg("toxinsChart");
        window.renderToxinChart("toxinsChart", rerows, pairLabel, cfg);

        if (cfg?.defaults?.enable_3d && document.getElementById("toxinsChart3D")) {
          window.renderToxinChart3D("toxinsChart3D", rerows, pairLabel);
        }
      }

      if (document.getElementById("pathogenConcChart")) {
        window.renderPathogenConcChart("pathogenConcChart", rerows, pairLabel);
      }

      if (document.getElementById("probChart")) {
        window.renderProbChart("probChart", rerows, pairLabel);
      }

      if (document.getElementById("casesChart")) {
        window.renderCasesChart("casesChart", rerows, pairLabel);
      }

      // heatmap needs risk_multiplier computed locally vs current period baseline
      let hmRows = null;
      if (document.getElementById("seasonalHeatmap")) {
        const b0 = rerows.length ? rerows[0].prob_illness_pct : 0;
        hmRows = rerows.map((r) => ({
          ...r,
          risk_multiplier: b0 > 0 ? +(r.prob_illness_pct / b0).toFixed(2) : 0,
        }));

        window.renderSeasonalHeatmap("seasonalHeatmap", hmRows, "risk_multiplier", pairLabel);
      }

      // explanations: only show where containers exist (renderExplanations already checks)
      renderExplanations(rerows, rerows, hmRows || rerows);

      document.dispatchEvent(
        new CustomEvent("risk:charts-rendered", {
          detail: {
            rows: rerows,
            heatmap_rows: hmRows || rerows,
            pair_label: pairLabel,
          },
        })
      );
    };

    if (!withSkeleton || !visibleIds.length) {
      doRender();
      return;
    }

    const startedAt = Date.now();
    requestAnimationFrame(() => {
      doRender();
      const elapsed = Date.now() - startedAt;
      const minSkeletonMs = 90;
      const delay = Math.max(0, minSkeletonMs - elapsed);
      window.setTimeout(() => {
        if (loadToken === renderLoadToken) {
          setChartsLoading(visibleIds, false);
        }
      }, delay);
    });
  }

  initRiskCardMotion();

  // initial render for current date range
  renderAllVisible(filterByPeriod(rows), { withSkeleton: true });
  initC1ChartChat();

  // Probability modal button (only if present)
  const btn = document.getElementById("probExplainBtn");
  if (btn) {
    btn.addEventListener("click", () => {
      const windowRows = filterByPeriod(rows);
      const idx = probSelectIndex();
      window.showProbPointInterpretation(windowRows, typeof idx === "number" ? idx : windowRows.length - 1);
    });
  }

  // Download charts and data exports
  document.addEventListener("click", async (ev) => {
    const btn = ev.target?.closest?.(".chart-export-action, .toxin-export-action");
    if (!btn) return;
    const chartKey = (
      btn.getAttribute("data-chart") ||
      (btn.classList.contains("toxin-export-action") ? "toxin" : "")
    ).toLowerCase();
    const fmt = (
      btn.getAttribute("data-chart-export") ||
      btn.getAttribute("data-toxin-export") ||
      ""
    ).toLowerCase();
    if (!chartKey || !fmt) return;
    try {
      await exportChartByFormat(chartKey, fmt);
    } catch (_err) {
      // no-op; keep UI quiet for now
    }
  });

  // Re-render when date/scale changes (only if those controls exist)
  ["rm-start", "rm-end", "rm-scale"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;

    el.addEventListener("input", () => {
      normalizeRiskDateRange();
      persistRiskDateFilters();
      renderAllVisible(filterByPeriod(rows), { withSkeleton: true });
    });
  });

  // OPTIONAL: expose a hook to re-render when switching crop/pathogen later
  window.renderRiskFor = function (opts) {
    const next = { ...opts };
    const newRows = window.buildDummyRiskSeries({ ...next, events });
    // Reuse label from opts (fallbacks)
    const label = `${next.crop || "Crop"} - ${next.pathogen || "Pathogen"}`;
    // Render visible charts using those new rows + label
    // (We do NOT touch localStorage here; caller can.)
    // Temporary override for label for this invocation:
    const oldPairLabel = label;
    renderAllVisible(filterByPeriod(newRows), { withSkeleton: true });
  };
});
