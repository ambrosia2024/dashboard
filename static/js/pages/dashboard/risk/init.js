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

  const source = rows[0]?.source || "dummy";
  const hasRealLimit = Number.isFinite(rows[0]?.toxin_limit_ug_per_kg);
  const limit = hasRealLimit ? rows[0].toxin_limit_ug_per_kg : null;

  const y = rows.map((r) => r.toxin_level_ug_per_kg);
  const over = hasRealLimit
    ? rows.filter((r) => r.toxin_level_ug_per_kg > limit).length
    : 0;

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
  const overPct = hasRealLimit ? Math.round(pct(over, rows.length)) : null;

  return `
    <strong>What this shows</strong>
    <ul class="mb-2">
      <li><em>${period}</em> toxin concentrations for <strong>${rows[0].crop}</strong> - <strong>${rows[0].pathogen}</strong>.</li>
      <li>X axis: <strong>time series / date</strong>.</li>
      <li>Y axis: <strong>toxin concentration (μg/kg)</strong>.</li>
    </ul>
    <strong>Key numbers</strong>
    <ul class="mb-2">
      <li>Average: <strong>${avg.toFixed(1)}</strong> μg/kg (min <strong>${min.toFixed(
        1
      )}</strong>, max <strong>${max.toFixed(1)}</strong>).</li>
      ${
        hasRealLimit
          ? `<li>Above limit: <strong>${over}</strong> of ${rows.length} points (<strong>${overPct}%</strong>).</li>`
          : ""
      }
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
        hasRealLimit
          ? over
            ? `There are occasional exceedances over the ${limit} μg/kg limit.`
            : `No exceedances detected in the selected period.`
          : `No regulatory or action limit is shown here because no limit value is currently available for this dataset.`
      }
    </p>
    <strong>Note</strong>
    <p class="mb-2">
      ${
        source === "scio_api" || source === "scio_db"
          ? "Values are shown for the current crop, pathogen, location, and date range. Temperature is available in the underlying data but is not displayed on the current 2D toxin chart."
          : "Values are illustrative dummy outputs - illustrative only."
      }
    </p>
  `;
}

function explainPathogens(rows) {
  if (!rows?.length) return "<em>No synced pathogen data for the selected filters and date range.</em>";

  const y = rows.map((r) => r.pathogen_model_value).filter((v) => Number.isFinite(v));
  if (!y.length) return "<em>No pathogen model values in the selected period.</em>";

  const max = Math.max(...y);
  const min = Math.min(...y);
  const avg = mean(y);

  const last = y[y.length - 1];
  const first = y[0];

  const slope = linearSlopeYPerStep(y);
  const trend = slope > 0.05 ? "rising" : slope < -0.05 ? "falling" : "flat";
  const arrow = slope > 0.05 ? "↑" : slope < -0.05 ? "↓" : "→";
  const unit = rows.find((r) => r.pathogen_model_unit)?.pathogen_model_unit || "model output";

  const period = `${monthLabel(rows[0].date)} → ${monthLabel(
    rows[rows.length - 1].date
  )}`;

  return `
    <strong>What this shows</strong>
    <ul class="mb-2">
      <li><em>${period}</em> pathogen model output for <strong>${rows[0].crop}</strong> - <strong>${rows[0].pathogen}</strong>.</li>
      <li>Y axis: <strong>${unit}</strong>.</li>
    </ul>
    <strong>Key numbers</strong>
    <ul class="mb-2">
      <li>Average: <strong>${avg.toFixed(1)}</strong> ${unit} (min <strong>${min.toFixed(
        1
      )}</strong>, max <strong>${max.toFixed(1)}</strong>).</li>
      <li>Trend: <strong>${trend}</strong> ${arrow} (≈ ${slope.toFixed(
        2
      )} ${unit} per period).</li>
      <li>Latest value: <strong>${last.toFixed(
        1
      )}</strong> ${unit}; change vs first point: <strong>${(last - first >= 0
        ? "+"
        : "")}${(last - first).toFixed(1)}</strong>.</li>
    </ul>
    <strong>Note</strong>
    <p class="mb-2">
      Values are synced source model outputs for the selected crop, pathogen, location, and date range.
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

const RISK_MIN_DATE = "1940-01-01";
// Far-future upper bound for the pickers. This dataset legitimately contains
// future-dated values (e.g. out to 2040), so we must NOT cap selectable dates
// at "today" when the real data range is unknown.
const RISK_MAX_DATE = "2100-12-31";
const LEGACY_STATIC_START_DATE = "2023-01-01";
const LEGACY_STATIC_END_DATE = "2023-12-31";
// Earliest/latest dates actually present in the DB for the current toxin
// crop/pathogen/region, discovered via the /meta/ endpoint. The pickers clamp
// to this range on the dedicated toxin chart.
let PATHOGEN_AVAILABLE_MIN_DATE = null;
let PATHOGEN_AVAILABLE_MAX_DATE = null;

function getTodayISODate() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getRiskAbsoluteMaxDate() {
  // Selectable upper bound: the data's real max when known, otherwise a wide
  // far-future bound (NOT "today"). The dataset contains future-dated values,
  // so capping selection at today is wrong.
  if (isDedicatedPathogenChartContext() && isISODate(PATHOGEN_AVAILABLE_MAX_DATE)) {
    return PATHOGEN_AVAILABLE_MAX_DATE;
  }
  return RISK_MAX_DATE;
}

function getRiskAbsoluteMinDate() {
  if (isDedicatedPathogenChartContext() && isISODate(PATHOGEN_AVAILABLE_MIN_DATE)) {
    return PATHOGEN_AVAILABLE_MIN_DATE;
  }
  return RISK_MIN_DATE;
}

function clampRiskDate(value) {
  if (!isISODate(value)) return null;
  const minDate = getRiskAbsoluteMinDate();
  const maxDate = getRiskAbsoluteMaxDate();
  if (value < minDate) return minDate;
  if (value > maxDate) return maxDate;
  return value;
}

function getCurrentYearStartISODate() {
  return `${new Date().getFullYear()}-01-01`;
}

function getDefaultRiskStartDate() {
  return getCurrentYearStartISODate();
}

function getDefaultRiskEndDate() {
  // Default END *value*: the data's real max when known, else today. (The
  // selectable bound is wider, see getRiskAbsoluteMaxDate, so the user can
  // still pick beyond today.)
  if (isDedicatedPathogenChartContext() && isISODate(PATHOGEN_AVAILABLE_MAX_DATE)) {
    return PATHOGEN_AVAILABLE_MAX_DATE;
  }
  return getTodayISODate();
}

function getRiskDateStorageScope() {
  const selectedChart = (window.__AMBROSIA_SELECTED_RISK_CHART || "").trim().toLowerCase();
  if (selectedChart) return selectedChart;

  const path = window.location.pathname.replace(/\/+$/, "");
  if (path.endsWith("/risk-charts/toxin")) return "toxin_over_time";
  if (path.endsWith("/risk-charts/pathogen")) return "pathogen_concentration_over_time";
  if (path.endsWith("/risk-charts")) return "all_risk_charts";

  return "risk_default";
}

function getRiskDateStorageKeys() {
  const scope = getRiskDateStorageScope();
  return {
    start: `risk_filter_start__${scope}`,
    end: `risk_filter_end__${scope}`,
  };
}

/* -----------------------
   Air Datepicker date inputs

   Air Datepicker replaces the native picker and adds a days -> months -> years
   (decade grid) drill-down: click the calendar title to jump across years fast.
   We keep each input's .value in ISO (Y-m-d) via dateFormat, so every existing
   read/write site keeps working unchanged. The instance is stored on el._airDp.
------------------------ */

const AIR_DP_LOCALE = {
  days: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
  daysShort: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
  daysMin: ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"],
  months: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
  monthsShort: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
  today: "Today",
  clear: "Clear",
  dateFormat: "yyyy-MM-dd",
  timeFormat: "",
  firstDay: 1,
};

const AIR_DP_OPTIONS = {
  locale: AIR_DP_LOCALE,
  dateFormat: "yyyy-MM-dd", // ISO value kept on the input itself
  autoClose: true,
  isMobile: false,
  position: "bottom left",
  navTitles: { days: "MMMM yyyy" },
  // Single-date filter: never unselect on re-click. Also critical because
  // normalizeRiskDateRange() re-applies the value via selectDate(); with the
  // default toggleSelected:true that re-apply would toggle the just-picked
  // date back off, so the new date never "takes".
  toggleSelected: false,
};

function isoToLocalDate(iso) {
  if (!isISODate(iso)) return null;
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

// Set an ISO value on a date input, keeping the Air Datepicker selection in
// sync. Empty/invalid clears it. Never re-fires onSelect.
function setRiskDateValue(el, isoValue) {
  if (!el) return;
  const next = isISODate(isoValue) ? isoValue : "";
  if (el._airDp) {
    if (next) el._airDp.selectDate(isoToLocalDate(next), { silent: true });
    else el._airDp.clear({ silent: true });
  } else {
    el.value = next;
  }
}

// Mirror the absolute selectable range onto the pickers. The start<=end
// relationship is enforced separately by normalizeRiskDateRange, so the pickers
// only get the absolute bounds and never fight that logic.
function syncRiskPickerBounds() {
  const minDate = isoToLocalDate(getRiskAbsoluteMinDate()) || "";
  const maxDate = isoToLocalDate(getRiskAbsoluteMaxDate()) || "";
  ["rm-start", "rm-end"].forEach((id) => {
    const dp = document.getElementById(id)?._airDp;
    if (!dp) return;
    // IMPORTANT: pass { silent: true }. Air Datepicker's update() re-applies
    // opts.selectedDates via a non-silent selectDate(), which re-fires onSelect
    // (= handleRiskDateChange). Without silent this creates an infinite loop:
    // onSelect -> normalizeRiskDateRange -> syncRiskPickerBounds -> update ->
    // onSelect ..., and each pass fires a pathogen query, exhausting the browser
    // (net::ERR_INSUFFICIENT_RESOURCES). We only want to refresh the bounds here.
    dp.update({ minDate, maxDate }, { silent: true });
  });
}

function initRiskDateWidgets(onChange) {
  if (typeof window.AirDatepicker !== "function") return;
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl) return;

  const handleChange = typeof onChange === "function" ? () => onChange() : undefined;
  [startEl, endEl].forEach((el) => {
    if (el._airDp) return;
    const initialIso = el.value;
    // Switch off the native date UI so only Air Datepicker shows.
    el.type = "text";
    el.readOnly = true;
    el.autocomplete = "off";
    el._airDp = new window.AirDatepicker(el, {
      ...AIR_DP_OPTIONS,
      minDate: isoToLocalDate(getRiskAbsoluteMinDate()) || "",
      maxDate: isoToLocalDate(getRiskAbsoluteMaxDate()) || "",
      // Deliberately NOT passing selectedDates here. opts.selectedDates would
      // stay frozen at this initial value, and dp.update() (in
      // syncRiskPickerBounds) re-applies opts.selectedDates on every bounds
      // refresh — reverting the user's freshly picked date. Set the initial
      // selection via selectDate() below instead, which only updates the
      // instance state, so update() has nothing stale to re-apply.
      onSelect: handleChange ? () => handleChange() : undefined,
    });
    if (isISODate(initialIso)) {
      el._airDp.selectDate(isoToLocalDate(initialIso), { silent: true });
    }
    const labelText = document.querySelector(`label[for="${el.id}"]`)?.textContent?.trim();
    if (labelText) el.setAttribute("aria-label", labelText);
  });
  syncRiskPickerBounds();
}

function updateRiskDatePickerBounds(startEl, endEl, absoluteMin, absoluteMax) {
  if (!startEl || !endEl) return;
  startEl.min = absoluteMin;
  startEl.max = isISODate(endEl.value) ? endEl.value : absoluteMax;
  endEl.min = isISODate(startEl.value) ? startEl.value : absoluteMin;
  endEl.max = absoluteMax;
  syncRiskPickerBounds();
}

function initRiskDatePickers() {
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl) return;
  updateRiskDatePickerBounds(startEl, endEl, getRiskAbsoluteMinDate(), getRiskAbsoluteMaxDate());
}

function normalizeRiskDateRange() {
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl) return;

  const absoluteMin = getRiskAbsoluteMinDate();
  const absoluteMax = getRiskAbsoluteMaxDate();
  startEl.min = absoluteMin;
  startEl.max = absoluteMax;
  endEl.min = absoluteMin;
  endEl.max = absoluteMax;

  if (isISODate(startEl.value)) setRiskDateValue(startEl, clampRiskDate(startEl.value));
  if (isISODate(endEl.value)) setRiskDateValue(endEl, clampRiskDate(endEl.value));

  const start = startEl.value;
  const end = endEl.value;

  // Keep browser pickers constrained to a valid range.
  if (isISODate(start)) endEl.min = start;
  else endEl.min = absoluteMin;
  if (isISODate(end)) startEl.max = end;
  else startEl.max = absoluteMax;
  updateRiskDatePickerBounds(startEl, endEl, absoluteMin, absoluteMax);

  // Auto-fix invalid range if user typed dates manually.
  if (isISODate(start) && isISODate(end) && start > end) {
    setRiskDateValue(endEl, start);
    endEl.min = start;
    updateRiskDatePickerBounds(startEl, endEl, absoluteMin, absoluteMax);
  }
}

function hydrateRiskDateFilters() {
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl) return;

  const params = new URLSearchParams(window.location.search);
  const qStart = params.get("start");
  const qEnd = params.get("end");
  const storageKeys = getRiskDateStorageKeys();
  const lsStart = localStorage.getItem(storageKeys.start);
  const lsEnd = localStorage.getItem(storageKeys.end);

  const start = clampRiskDate(
    isISODate(qStart)
      ? qStart
      : isISODate(lsStart)
        ? lsStart
        : isISODate(startEl.value)
          ? startEl.value
          : getDefaultRiskStartDate()
  );
  const end = clampRiskDate(
    isISODate(qEnd)
      ? qEnd
      : isISODate(lsEnd)
        ? lsEnd
        : isISODate(endEl.value)
          ? endEl.value
          : getDefaultRiskEndDate()
  );

  if (isISODate(start)) setRiskDateValue(startEl, start);
  if (isISODate(end)) setRiskDateValue(endEl, end);
  normalizeRiskDateRange();
  setRiskDateRangeHint(startEl.value, endEl.value);
}

function persistRiskDateFilters() {
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl) return;

  const storageKeys = getRiskDateStorageKeys();
  if (isISODate(startEl.value)) localStorage.setItem(storageKeys.start, startEl.value);
  if (isISODate(endEl.value)) localStorage.setItem(storageKeys.end, endEl.value);

  const url = new URL(window.location.href);
  if (isISODate(startEl.value)) url.searchParams.set("start", startEl.value);
  else url.searchParams.delete("start");
  if (isISODate(endEl.value)) url.searchParams.set("end", endEl.value);
  else url.searchParams.delete("end");
  window.history.replaceState({}, "", url.toString());
}

const TOXIN_SCALE_STORAGE_KEY = "risk_toxin_scale";
const VALID_TOXIN_SCALES = new Set(["daily", "weekly", "monthly", "quarterly", "yearly"]);

function normalizeToxinScale(value) {
  const scale = (value || "").trim().toLowerCase();
  return VALID_TOXIN_SCALES.has(scale) ? scale : null;
}

function hydrateToxinScaleFilter() {
  const scaleEl = document.getElementById("toxinsScale");
  if (!scaleEl) return;

  const params = new URLSearchParams(window.location.search);
  const queryScale = normalizeToxinScale(params.get("toxinsScale"));
  const storedScale = normalizeToxinScale(localStorage.getItem(TOXIN_SCALE_STORAGE_KEY));
  const fallbackScale = normalizeToxinScale(scaleEl.value) || "monthly";

  scaleEl.value = queryScale || storedScale || fallbackScale;
}

function hasExplicitRiskDateSelection() {
  const params = new URLSearchParams(window.location.search);
  const qStart = params.get("start");
  const qEnd = params.get("end");
  if (isISODate(qStart) || isISODate(qEnd)) return true;

  const storageKeys = getRiskDateStorageKeys();
  const lsStart = localStorage.getItem(storageKeys.start);
  const lsEnd = localStorage.getItem(storageKeys.end);
  return isISODate(lsStart) || isISODate(lsEnd);
}

function hasLegacyStaticRiskDefaults(startEl, endEl) {
  return startEl?.value === LEGACY_STATIC_START_DATE && endEl?.value === LEGACY_STATIC_END_DATE;
}

function formatHintDate(isoDate) {
  if (!isISODate(isoDate)) return "";
  const [year, month, day] = isoDate.split("-");
  return `${day}/${month}/${year}`;
}

function setRiskDateRangeHint() {
  const hintEl = document.getElementById("riskDateRangeHint");
  if (!hintEl) return;

  // Show the AVAILABLE data range from /meta/ (what a "Data:" label implies),
  // not the selected start/end — those are already shown in the two inputs.
  // Only meaningful once a region's range has been discovered.
  if (
    !isDedicatedPathogenChartContext()
    || !isISODate(PATHOGEN_AVAILABLE_MIN_DATE)
    || !isISODate(PATHOGEN_AVAILABLE_MAX_DATE)
  ) {
    hintEl.textContent = "";
    hintEl.classList.add("d-none");
    return;
  }

  hintEl.textContent = `Data available: ${formatHintDate(PATHOGEN_AVAILABLE_MIN_DATE)} - ${formatHintDate(PATHOGEN_AVAILABLE_MAX_DATE)}`;
  hintEl.classList.remove("d-none");
}

function isDedicatedPathogenChartContext() {
  const selectedChart = (window.__AMBROSIA_SELECTED_RISK_CHART || "").trim().toLowerCase();
  if (selectedChart === "pathogen_concentration_over_time" || selectedChart === "c2_pathogen_over_time") {
    return true;
  }

  const path = window.location.pathname.replace(/\/+$/, "");
  return path.endsWith("/risk-charts/pathogen");
}

function isSystemGeneratedRiskRange(start, end) {
  if (!isISODate(start) || !isISODate(end)) return false;
  const currentMax = getRiskAbsoluteMaxDate();
  const today = getTodayISODate();
  // The auto-generated default end is either the available max or "today"
  // (when the available range is unknown); accept both.
  const isSystemEnd = (e) => e === currentMax || e === today;
  return (
    (start === LEGACY_STATIC_START_DATE && end === LEGACY_STATIC_END_DATE)
    || (start === RISK_MIN_DATE && isSystemEnd(end))
    || (start === getCurrentYearStartISODate() && isSystemEnd(end))
  );
}

let PATHOGEN_AVAILABLE_RANGE_PROMISE = null;

// Discover the earliest/latest synced dates for the current pathogen
// crop/pathogen/region and store them so the pickers can clamp to real data.
// Runs once per page load (cached) and is independent of the date defaults
// logic, so the bounds are correct even when an explicit range is in the URL.
async function loadPathogenAvailableRange() {
  if (!isDedicatedPathogenChartContext()) return null;
  if (PATHOGEN_AVAILABLE_RANGE_PROMISE) return PATHOGEN_AVAILABLE_RANGE_PROMISE;

  PATHOGEN_AVAILABLE_RANGE_PROMISE = (async () => {
    try {
      const pair = getCurrentRiskPair();
      const nutsCode =
        localStorage.getItem("lx_selected_nuts2_id")
        || document.getElementById("rm-country")?.value
        || "NL";
      const metaParams = new URLSearchParams({
        plant: toApiSlug(pair.crop, "lettuce"),
        pathogen: toApiSlug(pair.pathogen, "salmonella"),
        nutsCode,
      });
      const response = await fetch(`/api/risk-charts/pathogen-concentration/meta/?${metaParams.toString()}`);
      if (!response.ok) {
        PATHOGEN_AVAILABLE_MIN_DATE = null;
        PATHOGEN_AVAILABLE_MAX_DATE = null;
        return null;
      }
      const data = await response.json();
      PATHOGEN_AVAILABLE_MIN_DATE = isISODate(data?.available_start_date) ? data.available_start_date : null;
      PATHOGEN_AVAILABLE_MAX_DATE = isISODate(data?.available_end_date) ? data.available_end_date : null;
      return data;
    } catch (_err) {
      PATHOGEN_AVAILABLE_MIN_DATE = null;
      PATHOGEN_AVAILABLE_MAX_DATE = null;
      return null;
    }
  })();

  return PATHOGEN_AVAILABLE_RANGE_PROMISE;
}

async function applyPathogenDateRangeDefaultsIfNeeded() {
  const startEl = document.getElementById("rm-start");
  const endEl = document.getElementById("rm-end");
  if (!startEl || !endEl || !document.getElementById("pathogenConcChart")) return;
  if (!isDedicatedPathogenChartContext()) return;

  const params = new URLSearchParams(window.location.search);
  const qStart = params.get("start");
  const qEnd = params.get("end");
  const storageKeys = getRiskDateStorageKeys();
  const lsStart = localStorage.getItem(storageKeys.start);
  const lsEnd = localStorage.getItem(storageKeys.end);

  const hasRealExplicitSelection =
    hasExplicitRiskDateSelection()
    && !isSystemGeneratedRiskRange(qStart, qEnd)
    && !isSystemGeneratedRiskRange(lsStart, lsEnd);
  if (hasRealExplicitSelection) return;

  if (isSystemGeneratedRiskRange(qStart, qEnd)) {
    params.delete("start");
    params.delete("end");
    const url = new URL(window.location.href);
    url.search = params.toString();
    window.history.replaceState({}, "", url.toString());
  }
  if (isSystemGeneratedRiskRange(lsStart, lsEnd)) {
    localStorage.removeItem(storageKeys.start);
    localStorage.removeItem(storageKeys.end);
  }

  const shouldApply =
    (!isISODate(startEl.value) && !isISODate(endEl.value))
    || isSystemGeneratedRiskRange(startEl.value, endEl.value)
    || hasLegacyStaticRiskDefaults(startEl, endEl);
  if (!shouldApply) return;

  // Default the range to the full span of available data.
  await loadPathogenAvailableRange();
  const start = clampRiskDate(PATHOGEN_AVAILABLE_MIN_DATE);
  const end = clampRiskDate(PATHOGEN_AVAILABLE_MAX_DATE);
  if (isISODate(start)) setRiskDateValue(startEl, start);
  if (isISODate(end)) setRiskDateValue(endEl, end);
  updateRiskDatePickerBounds(startEl, endEl, getRiskAbsoluteMinDate(), getRiskAbsoluteMaxDate());
  setRiskDateRangeHint(startEl.value, endEl.value);
}

function persistToxinScaleFilter() {
  const scaleEl = document.getElementById("toxinsScale");
  if (!scaleEl) return;

  const scale = normalizeToxinScale(scaleEl.value);
  if (!scale) return;

  localStorage.setItem(TOXIN_SCALE_STORAGE_KEY, scale);

  const url = new URL(window.location.href);
  url.searchParams.set("toxinsScale", scale);
  window.history.replaceState({}, "", url.toString());
}

function filterByPeriod(rows) {
  const s = new Date(document.getElementById("rm-start")?.value || getDefaultRiskStartDate());
  const e = new Date(document.getElementById("rm-end")?.value || getDefaultRiskEndDate());

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

const PATHOGEN_DAILY_CACHE = new Map();

function toApiSlug(value, fallback = "") {
  return (value || fallback)
    .toString()
    .trim()
    .toLowerCase()
    .replace(/[_\s]+/g, "-");
}

function getCurrentRiskPair() {
  return {
    crop: localStorage.getItem("lx_selected_crop_label") || "Lettuce",
    pathogen: localStorage.getItem("lx_selected_pathogen_label") || "Salmonella",
  };
}

function getCurrentPairLabel() {
  const pair = getCurrentRiskPair();
  return `${pair.crop} - ${pair.pathogen}`;
}

function getSelectedToxinScale() {
  const chartScale = document.getElementById("toxinsScale")?.value;
  if (chartScale) return chartScale;

  const legacyScale = document.getElementById("rm-scale")?.value;
  switch ((legacyScale || "").toLowerCase()) {
    case "days":
      return "daily";
    case "months":
      return "monthly";
    case "years":
      return "yearly";
    default:
      return "monthly";
  }
}

function normalizeRequestDate(value, fallback) {
  const raw = (value || "").trim();
  if (!raw) return fallback;
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;

  const slashMatch = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (slashMatch) {
    const [, day, month, year] = slashMatch;
    return `${year}-${month}-${day}`;
  }

  const parsed = new Date(raw);
  if (!Number.isNaN(parsed.getTime())) {
    const yyyy = parsed.getFullYear();
    const mm = String(parsed.getMonth() + 1).padStart(2, "0");
    const dd = String(parsed.getDate()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd}`;
  }
  return fallback;
}

function buildPathogenQueryPayload() {
  const pair = getCurrentRiskPair();
  const startDate = normalizeRequestDate(document.getElementById("rm-start")?.value, getDefaultRiskStartDate());
  const endDate = normalizeRequestDate(document.getElementById("rm-end")?.value, getDefaultRiskEndDate());
  const nutsCode =
    localStorage.getItem("lx_selected_nuts2_id")
    || document.getElementById("rm-country")?.value
    || "NL";

  return {
    plant: toApiSlug(pair.crop, "lettuce"),
    pathogen: toApiSlug(pair.pathogen, "salmonella"),
    nutsCode,
    startDate,
    endDate,
    timeScale: "daily",
  };
}

async function fetchRealPathogenRows() {
  const payload = buildPathogenQueryPayload();
  const cacheKey = JSON.stringify(payload);
  // Cache the in-flight PROMISE (not just the resolved value). This dedups
  // concurrent identical requests, so even if some caller fires repeatedly,
  // at most one network request per payload is ever in flight. Defensive
  // guard against request floods (net::ERR_INSUFFICIENT_RESOURCES).
  if (PATHOGEN_DAILY_CACHE.has(cacheKey)) {
    return PATHOGEN_DAILY_CACHE.get(cacheKey);
  }

  const requestPromise = (async () => {
    const response = await fetch("/api/risk-charts/pathogen-concentration/query/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken(),
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let detail = `Pathogen query failed (${response.status})`;
      try {
        const data = await response.json();
        if (data?.error) detail = data.error;
      } catch (_err) {
        // no-op
      }
      throw new Error(detail);
    }

    return response.json();
  })();

  // Don't keep a rejected promise cached, so a later attempt can retry.
  requestPromise.catch(() => PATHOGEN_DAILY_CACHE.delete(cacheKey));
  PATHOGEN_DAILY_CACHE.set(cacheKey, requestPromise);
  return requestPromise;
}

function aggregateToxinRows(rows, scale) {
  if (!Array.isArray(rows) || !rows.length || scale === "daily") {
    return rows || [];
  }

  const buckets = new Map();
  rows.forEach((row) => {
    const date = new Date(row.date || row.time || "");
    if (Number.isNaN(date.getTime())) return;

    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    let key = "";
    let displayLabel = "";
    let bucketDate = "";

    if (scale === "weekly") {
      const bucketStart = new Date(date);
      const day = bucketStart.getDay();
      const mondayOffset = day === 0 ? -6 : 1 - day;
      bucketStart.setDate(bucketStart.getDate() + mondayOffset);
      const yyyy = bucketStart.getFullYear();
      const mm = String(bucketStart.getMonth() + 1).padStart(2, "0");
      const dd = String(bucketStart.getDate()).padStart(2, "0");
      key = `${yyyy}-W${mm}${dd}`;
      displayLabel = `Week of ${yyyy}-${mm}-${dd}`;
      bucketDate = `${yyyy}-${mm}-${dd}`;
    } else if (scale === "monthly") {
      key = `${year}-${String(month).padStart(2, "0")}`;
      displayLabel = key;
      bucketDate = `${key}-01`;
    } else if (scale === "quarterly") {
      const quarter = Math.floor((month - 1) / 3) + 1;
      const startMonth = (quarter - 1) * 3 + 1;
      key = `${year}-Q${quarter}`;
      displayLabel = key;
      bucketDate = `${year}-${String(startMonth).padStart(2, "0")}-01`;
    } else if (scale === "yearly") {
      key = String(year);
      displayLabel = key;
      bucketDate = `${year}-01-01`;
    } else {
      return;
    }

    if (!buckets.has(key)) {
      buckets.set(key, {
        key,
        displayLabel,
        date: bucketDate,
        rows: [],
      });
    }
    buckets.get(key).rows.push(row);
  });

  return Array.from(buckets.values()).map((bucket) => {
    const sample = bucket.rows[0];
    const avg = (values) => {
      const nums = values.filter((v) => Number.isFinite(v));
      if (!nums.length) return null;
      return nums.reduce((sum, v) => sum + v, 0) / nums.length;
    };

    return {
      ...sample,
      date: bucket.date,
      display_label: bucket.displayLabel,
      time: null,
      period: bucket.displayLabel,
      toxin_level_ug_per_kg: avg(bucket.rows.map((r) => r.toxin_level_ug_per_kg)),
      pathogen_model_value: avg(bucket.rows.map((r) => r.pathogen_model_value)),
      temperature_c: avg(bucket.rows.map((r) => r.temperature_c)),
      humidity_pct: avg(bucket.rows.map((r) => r.humidity_pct)),
      source_scale: scale,
      outcome: [],
    };
  });
}
function aggregatePathogenRows(rows, scale) {
  return aggregateToxinRows(rows, scale).map((row) => ({
    ...row,
    pathogen_model_value: row.pathogen_model_value ?? row.toxin_level_ug_per_kg ?? null,
    pathogen_model_unit: row.pathogen_model_unit || "model output",
  }));
}

// Per-chart "data source" indicator: a small icon next to the chart title that
// distinguishes live DB data from illustrative sample data (icon + tooltip).
function setChartDataSourceBadge(domId, isLive, tooltip) {
  // No-op: superseded by the template-rendered Live/Demo badge driven by
  // default_config.data_source. Kept so existing call sites stay valid.
  return;
}

function toxinSourceTooltip(isLive) {
  if (!isLive) return "Illustrative sample data (live query unavailable for this selection)";
  const p = window.__toxinsProvenanceCurrent;
  return p && p.model_title ? `Live data - source model "${p.model_title}"` : "Live data from the database";
}

function pathogenSourceTooltip(isLive) {
  if (!isLive) return "Illustrative sample data (live query unavailable for this selection)";
  const p = window.__pathogenProvenanceCurrent;
  return p && p.model_title ? `Live data - source model "${p.model_title}"` : "Live data from the database";
}

async function renderRealPathogenChart(fallbackRows) {
  if (!document.getElementById("pathogenConcChart")) {
    return;
  }

  const pairLabel = getCurrentPairLabel();
  const scale = getSelectedToxinScale();

  try {
    const data = await fetchRealPathogenRows();
    const usedReal = Array.isArray(data?.rows) && data.rows.length > 0;
    const dailyRows = usedReal ? data.rows : fallbackRows;
    const pathogenRows = aggregatePathogenRows(dailyRows, scale);
    window.__pathogenProvenanceCurrent = usedReal ? (data?.provenance || null) : null;
    window.renderPathogenConcChart("pathogenConcChart", pathogenRows, pairLabel);
    const pathEl = document.getElementById("pathogenExplain");
    if (pathEl) pathEl.innerHTML = explainPathogens(pathogenRows);
    setChartDataSourceBadge("pathogenConcChart", usedReal, pathogenSourceTooltip(usedReal));
  } catch (err) {
    window.__pathogenProvenanceCurrent = null;
    window.renderPathogenConcChart("pathogenConcChart", [], pairLabel);
    const pathEl = document.getElementById("pathogenExplain");
    if (pathEl) pathEl.innerHTML = `<em>${err?.message || "No synced pathogen data for the selected filters and date range."}</em>`;
    setChartDataSourceBadge("pathogenConcChart", false, "No synced data for the selected filters");
  }
}

async function renderRealToxinChart(fallbackRows) {
  if (!document.getElementById("toxinsChart")) {
    return;
  }

  const cfg = getCfg("toxinsChart");
  const pairLabel = getCurrentPairLabel();
  const scale = getSelectedToxinScale();
  const toxinRows = aggregateToxinRows(fallbackRows, scale);
  window.__toxinsProvenanceCurrent = null;
  window.renderToxinChart("toxinsChart", toxinRows, pairLabel, cfg);
  if (cfg?.defaults?.enable_3d && document.getElementById("toxinsChart3D")) {
    window.renderToxinChart3D("toxinsChart3D", toxinRows, pairLabel);
  }
  const toxEl = document.getElementById("toxinsExplain");
  if (toxEl) toxEl.innerHTML = explainToxins(toxinRows);
  setChartDataSourceBadge("toxinsChart", false, toxinSourceTooltip(false));
}

function initC1ChartChat() {
  const toggleBtn = document.getElementById("c1-chat-toggle");
  const fab = document.getElementById("ambra-fab");
  const closeBtn = document.getElementById("ambra-close");
  const backdrop = document.getElementById("ambra-backdrop");
  const panel = document.getElementById("c1-chat-panel");
  const form = document.getElementById("c1-chat-form");
  const input = document.getElementById("c1-chat-input");
  const sendBtn = document.getElementById("c1-chat-send");
  const charCountEl = document.getElementById("c1-chat-char-count");
  const downloadBtn = document.getElementById("c1-chat-download");
  const thread = document.getElementById("c1-chat-thread");
  const quickPromptBtns = Array.from(document.querySelectorAll(".c1-chat-quick-prompt[data-c1-quick-prompt]"));
  if (!form || !input || !sendBtn || !thread || !downloadBtn || !panel) return;

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
    panel.classList.add("open");
    backdrop?.classList.add("open");
    fab?.classList.add("is-hidden");
    if (toggleBtn?.style) toggleBtn.style.display = "none";
    setTimeout(() => input.focus(), 0);
  }

  function closeChatPanel() {
    panel.classList.remove("open");
    backdrop?.classList.remove("open");
    fab?.classList.remove("is-hidden");
    if (toggleBtn?.style) toggleBtn.style.display = "";
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

  toggleBtn?.addEventListener("click", () => openChatPanel());
  fab?.addEventListener("click", () => openChatPanel());
  closeBtn?.addEventListener("click", () => closeChatPanel());
  backdrop?.addEventListener("click", () => closeChatPanel());
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panel.classList.contains("open")) closeChatPanel();
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

document.addEventListener("DOMContentLoaded", async function () {
  // Always learn the available data range first so the pickers clamp to it,
  // even when an explicit date range is already present in the URL/storage.
  await loadPathogenAvailableRange();
  await applyPathogenDateRangeDefaultsIfNeeded();
  hydrateRiskDateFilters();
  initRiskDatePickers();
  normalizeRiskDateRange();
  persistRiskDateFilters();
  hydrateToxinScaleFilter();
  persistToxinScaleFilter();
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

  // 2) build dummy rows (shared for all charts that have no real data wired).
  // Span the full selectable window so the dummy fallback always overlaps the
  // chosen date range (filterByPeriod then slices it to the selection). If this
  // is kept narrow, charts go blank whenever the range sits outside it.
  const rows = window.buildDummyRiskSeries({
    ...pair,
    startISO: RISK_MIN_DATE,
    endISO: `${new Date().getFullYear() + 15}-12-01`,
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
      // Toxin does not have a confirmed live endpoint in this dashboard yet.
      if (document.getElementById("toxinsChart")) {
        const cfg = getCfg("toxinsChart");
        const toxinRows = aggregateToxinRows(rerows, getSelectedToxinScale());
        window.__toxinsProvenanceCurrent = null;
        window.renderToxinChart("toxinsChart", toxinRows, pairLabel, cfg);
        if (cfg?.defaults?.enable_3d && document.getElementById("toxinsChart3D")) {
          window.renderToxinChart3D("toxinsChart3D", toxinRows, pairLabel);
        }
        const toxEl = document.getElementById("toxinsExplain");
        if (toxEl) toxEl.innerHTML = explainToxins(toxinRows);
        setChartDataSourceBadge("toxinsChart", false, toxinSourceTooltip(false));
      }

      if (document.getElementById("pathogenConcChart")) {
        renderRealPathogenChart(rerows);
      }

      if (document.getElementById("probChart")) {
        window.renderProbChart("probChart", rerows, pairLabel);
        setChartDataSourceBadge("probChart", false);
      }

      if (document.getElementById("casesChart")) {
        window.renderCasesChart("casesChart", rerows, pairLabel);
        setChartDataSourceBadge("casesChart", false);
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
        setChartDataSourceBadge("seasonalHeatmap", false);
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

  // Shared handler for any date-range change (Air Datepicker selection or native input).
  function handleRiskDateChange() {
    normalizeRiskDateRange();
    persistRiskDateFilters();
    setRiskDateRangeHint(
      document.getElementById("rm-start")?.value,
      document.getElementById("rm-end")?.value
    );
    renderAllVisible(filterByPeriod(rows), { withSkeleton: true });
  }

  // Enhance the date inputs with Air Datepicker (values stay ISO via dateFormat).
  // Done here, after the hydrate/normalize sequence has set the initial values.
  initRiskDateWidgets(handleRiskDateChange);

  // Re-render when date/scale changes. Air Datepicker drives rm-start / rm-end via
  // its onSelect callback above; the "input" listener stays as a graceful fallback
  // for when the picker is unavailable and for the legacy rm-scale control.
  ["rm-start", "rm-end", "rm-scale"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", handleRiskDateChange);
  });

  const toxinScaleEl = document.getElementById("toxinsScale");
  if (toxinScaleEl) {
    toxinScaleEl.addEventListener("input", () => {
      persistToxinScaleFilter();
      renderAllVisible(filterByPeriod(rows), { withSkeleton: true });
    });
  }

  // OPTIONAL: expose a hook to re-render when switching crop/pathogen later
  window.renderRiskFor = function (opts) {
    const next = { ...opts };
    // Keep the same wide span so the dummy fallback still covers any date range.
    const newRows = window.buildDummyRiskSeries({
      startISO: RISK_MIN_DATE,
      endISO: `${new Date().getFullYear() + 15}-12-01`,
      ...next,
      events,
    });
    // Reuse label from opts (fallbacks)
    const label = `${next.crop || "Crop"} - ${next.pathogen || "Pathogen"}`;
    // Render visible charts using those new rows + label
    // (We do NOT touch localStorage here; caller can.)
    // Temporary override for label for this invocation:
    const oldPairLabel = label;
    renderAllVisible(filterByPeriod(newRows), { withSkeleton: true });
  };
});
