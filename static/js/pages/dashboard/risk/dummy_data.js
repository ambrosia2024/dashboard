// static/js/pages/dashboard/risk/dummy_data.js
// Generates a single crop–pathogen time series with seasonality + noise + optional event spikes.
// No chart code changes needed, when replacing it with actual model outputs.

(function () {
  /**
   * Build monthly points between start and end (inclusive) with controlled seasonality.
   * @param {Object} opts
   * @param {string} opts.crop
   * @param {string} opts.pathogen
   * @param {string} opts.startISO - e.g. "2021-01-01"
   * @param {string} opts.endISO   - e.g. "2023-12-31"
   * @param {number} [opts.baseProb=1.2] - baseline probability (%)
   * @param {number} [opts.seasonAmp=1.0] - amplitude added by seasonality (summer/autumn higher)
   * @param {number} [opts.noise=0.3] - random noise magnitude
   * @param {Array<{iso:string,type:string,boost:number}>} [opts.events] - event spikes (e.g., drought)
   * @param {number} [opts.toxinLimit] - action limit μg/kg
   * @returns {Array<Object>} rows
   */
  function buildDummyRiskSeries(opts) {
    const crop = opts.crop || "wheat";
    const pathogen = opts.pathogen || "Fusarium";
    const start = new Date(opts.startISO || "2021-01-01");
    const end = new Date(opts.endISO || "2023-12-31");
    const baseProb = opts.baseProb ?? 1.2;
    const seasonAmp = opts.seasonAmp ?? 1.0;
    const noiseMag = opts.noise ?? 0.3;
    const limit = opts.toxinLimit ?? window.RISK_CONFIG.defaultToxinLimit;

    const events = (opts.events || []).reduce((acc, e) => {
      acc[e.iso] = e; // quick lookup by month ISO
      return acc;
    }, {});

    const rows = [];
    const d = new Date(start);

    // Walk month by month
    while (d <= end) {
      const year = d.getFullYear();
      const month = d.getMonth() + 1; // 1..12
      const iso = d.toISOString().slice(0, 10);

      // --- Seasonality: higher in summer(6–8) & autumn(9–10) ---
      // Sine wave for smooth annual cycle (peak ~Aug/Sep)
      const season = Math.sin((2 * Math.PI * (month - 2)) / 12); // shift so summer/autumn peak
      const seasonalBoost = seasonAmp * Math.max(0, season);     // set winter negative portions to 0

      // Approximate environmental variables to show in tooltips (dummy):
      const temperature_c = 8 + 12 * Math.max(0, season) + randn(0, 1.2); // cool --> warm
      const humidity_pct  = 60 + 20 * Math.max(0, season) + randn(0, 4);

      // --- Toxin level (μg/kg): baseline + season + noise + events ---
      let toxin = 8 + 6 * seasonalBoost + randn(0, 1.5);
      // Events (e.g., drought/heavy_rain) add short spikes
      const ev = events[iso];
      if (ev) toxin += ev.boost;

      // --- Probability of illness (%): logistic-ish growth around toxin limit ---
      const x = (toxin - limit) / 5.0; // scale sensitivity
      let prob = baseProb + 6 / (1 + Math.exp(-x)); // 1–7% typical band in dummy
      prob += randn(0, noiseMag);

      // --- Baseline probability (%): smoother seasonality only (no events) ---
      const baselineProb = baseProb + 4 * seasonalBoost;

      // --- Risk multiplier + level colour ---
      const riskMultiplier = Math.max(0.1, prob / Math.max(0.1, baselineProb));
      const band = window.classifyRelativeIncrease(prob, baselineProb); // returns a band object
        const color = band.color;


      // --- Cases per 100k: proportional to prob & a dummy exposure factor ---
      const exposurePer100k = 40000; // 40k consumers per 100k pop (dummy)
      const cases = Math.round((prob / 100) * exposurePer100k);

      rows.push({
        date: iso,
        year, month,
        crop, pathogen,
        temperature_c: round1(temperature_c),
        humidity_pct:  round1(humidity_pct),
        toxin_level_ug_per_kg: round1(toxin),
        toxin_limit_ug_per_kg: limit,
        prob_illness_pct: round2(Math.max(0.1, prob)),
        baseline_prob_illness_pct: round2(Math.max(0.1, baselineProb)),
        risk_multiplier: round2(riskMultiplier),
        risk_color: color,
        cases_per_100k: cases,
        event: ev ? ev.type : "none"
      });

      // next month
      d.setMonth(d.getMonth() + 1);
    }
    return rows;
  }

  // Gaussian noise helper
  function randn(mean, sd) {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    const z = Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
    return mean + z * sd;
  }
  function round1(x) { return Math.round(x * 10) / 10; }
  function round2(x) { return Math.round(x * 100) / 100; }

  // Expose builder
  window.buildDummyRiskSeries = buildDummyRiskSeries;
})();
