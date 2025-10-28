// static/js/pages/dashboard/risk/config.js
// Central config so thresholds/legends are in one place.

window.RISK_CONFIG = {
    relativeBands: [
        { maxPct: 10,  label: "Small (<10%)",        color: "#6cc070" },
        { maxPct: 25,  label: "Moderate (10–25%)",   color: "#ffbf00" },
        { maxPct: 50,  label: "Large (25–50%)",      color: "#ff7f0e" },
        { maxPct: 1e9, label: "Significant (>50%)",  color: "#d62728" }
    ],
  // // Temporary legend logic (needs revision later)
  // riskMultiplierBands: [
  //   { min: 0, max: 2,   label: "≤2× baseline (low)",        color: "#2ca02c" }, // green
  //   { min: 2, max: 5,   label: ">2× (moderate)",            color: "#ff7f0e" }, // orange
  //   { min: 5, max: 999, label: ">5× (significant increase)", color: "#d62728" }  // red
  // ],
  // Default toxin action limit (μg/kg) for prototype; override per-toxin later
  defaultToxinLimit: 12,
  // Rolling window for cases smoothing
  rollingWindow: 3
};

// Small helper: map a risk multiplier (e.g. 3.1) to a colour
window.classifyRelativeIncrease = function (current, baseline) {
  if (baseline <= 0 || baseline == null) return window.RISK_CONFIG.relativeBands[3];
  const pct = ((current - baseline) / baseline) * 100;
  return window.RISK_CONFIG.relativeBands.find(b => pct < b.maxPct) || window.RISK_CONFIG.relativeBands.at(-1);
};
