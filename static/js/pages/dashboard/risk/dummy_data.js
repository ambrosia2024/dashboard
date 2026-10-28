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

            const pathogenSeason = 1.0
                + 0.30 * Math.sin((2 * Math.PI * ((month - 8) / 12)))   // shift peak to ~Sep/Oct
                + 0.06 * Math.cos((2 * Math.PI * ((month - 4) / 12)));

            let eventBoostPath = 1.0;
            if (ev) {
                if (ev.type === "heavy_rain") {
                    eventBoostPath += 0.16 * (ev.boost ?? 2.0); // pathogens react more to rain
                } else if (ev.type === "heatwave") {
                    eventBoostPath += 0.08 * (ev.boost ?? 2.0); // smaller heatwave effect
                } else {
                    eventBoostPath += 0.10 * (ev.boost ?? 2.0);
                }
            }

            // Near 20°C favours growth (small bump around 20°C)
            const tempBump = 0.06 * (20 - Math.abs(20 - temperature_c));

            // Independent noise so the curve shape diverges from toxins
            let pathogenConc = 7.5 * pathogenSeason * eventBoostPath + tempBump + randn(0, 2.1);

            const pathogen_conc_units_per_g = round1(Math.max(0, pathogenConc));

            // --- Growth potential (log10 CFU/g x h) ---
            // On its own temperature track, for two reasons: the growth charts need a
            // long-term warming signal to have anything to compare, and temperature_c
            // above is a half-sine that peaks in May and sits flat through winter, so
            // a growth curve built on it would peak in the wrong month. Changing that
            // curve would move the toxin and pathogen charts too, so this leaves it be.
            const growth_temp_c = round1(growthTemperature(month, year));
            const spread = 3 + 2 * Math.random();
            const growth_potential_index = growthPotentialIndex(growth_temp_c);
            const growth_potential_min = growthPotentialIndex(growth_temp_c - spread);
            const growth_potential_max = growthPotentialIndex(growth_temp_c + spread);

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
                pathogen_conc_units_per_g,
                growth_temp_c,
                growth_potential_index,
                growth_potential_min,
                growth_potential_max,
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

  // Coldest in January, warmest in July, plus an illustrative warming signal of
  // about +0.025 C a year from 1990 - so a 1991-2020 window sits roughly 1.9 C
  // below a 2066-2095 one. Shaped to look like the projection the real model is
  // driven by; it is not that projection.
  function growthTemperature(month, year) {
    const MEAN_C = 14.5;
    const AMPLITUDE_C = 5.0;
    const cycle = -Math.cos((2 * Math.PI * (month - 1)) / 12);
    const trend = 0.025 * Math.max(0, year - 1990);
    return MEAN_C + AMPLITUDE_C * cycle + trend + randn(0, 1.0);
  }

  // Saturating response of the growth model to temperature. Below TMIN nothing
  // grows; above it the index climbs steeply and then flattens, because within a
  // fixed 48-hour window a very warm day cannot score much more than a warm one.
  function growthPotentialIndex(tempC) {
    const TMIN = 3.0;    // no growth below this
    const TSPAN = 22.9;  // scales the rise
    const CEILING = 88;  // the flattening-out level
    const K = 2.4;
    const x = Math.max(0, (tempC - TMIN) / TSPAN);
    return round2(CEILING * (1 - Math.exp(-K * x * x)));
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
