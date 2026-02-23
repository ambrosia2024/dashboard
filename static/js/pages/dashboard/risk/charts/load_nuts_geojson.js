// static/js/pages/dashboard/risk/charts/load_nuts_geojson.js
// Loads NUTS GeoJSON from /static and expands it into monthly features.
// Exposes:
//   - window.loadRiskGeoForCountry(countryCode) -> Promise<{type, features}>
//   - window.RISK_GEOJSON (last loaded FeatureCollection)
//   - window.RISK_GEOJSON_READY (Promise resolving to the last load)
//
// Notes:
// - The 'season' variable models annual seasonality (0–1), peaking in late summer/autumn.
//   Currently used only to generate realistic dummy fluctuations in risk values.
//   Later, this can drive visual features-e.g., highlighting peak months, adjusting colour
//   intensity, or dynamically scaling the map's heat layer.

(function () {
    const src = "/static/data/nuts/NUTS_RG_03M_2021_4326.geojson";

    // simple seasonal dummy used for now (peak late summer/autumn)
    function seasonal(base, month, noise = 0.25) {
        const season = Math.max(0, Math.sin((2 * Math.PI * (month - 2)) / 12));
        const v = base + season * 1.2 + (Math.random() - 0.5) * noise;
        return +v.toFixed(2);
    }

    // cache the raw GeoJSON so switching countries doesn’t refetch the file
    let RAW_GEOJSON = null;

    async function ensureRawGeo() {
        if (RAW_GEOJSON) return RAW_GEOJSON;
        const res = await fetch(src);
        if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${src}`);
        RAW_GEOJSON = await res.json();
        return RAW_GEOJSON;
    }

    async function buildForCountry(countryCode) {
        const geo = await ensureRawGeo();

        const feats = [];

        // Helper to read IDs/names (Eurostat GISCO standard props)
        const nutsId   = f => f.properties.NUTS_ID;
        const nutsName = f => f.properties.NAME_LATN;
        const level    = f => f.properties.LEVL_CODE;  // 0..3
        const country  = f => f.properties.CNTR_CODE;  // 'NL', 'DE', 'EL', ...

        // Restrict to the selected country's NUTS-2 regions for performance.
        const cc = (countryCode || "NL").toUpperCase();
        const selectedNuts2 = geo.features.filter(f => level(f) === 2 && country(f) === cc);

        // Dummy set for dropdowns to work
        const CROPS = ['Lettuce', 'Iceberg'];
        const PATHOGENS = ['Salmonella', 'Listeria'];

        for (const f of selectedNuts2) {
            const region_id = nutsId(f);
            const region_name = nutsName(f);

            for (const year of [2021, 2022, 2023]) {
                for (let month = 1; month <= 12; month++) {
                    for (const crop of CROPS) {
                        for (const pathogen of PATHOGENS) {
                            // small offsets so pairs are different but plausible
                            const off = (crop === 'Iceberg' ? 0.6 : 0) + (pathogen === 'Listeria' ? 0.4 : 0);

                            const prob = seasonal(2.0 + off, month);
                            const baseline = seasonal(1.4 + off * 0.5, month);

                            feats.push({
                                type: "Feature",
                                id: `${region_id}-${year}-${month}-${crop}-${pathogen}`,
                                properties: {
                                    region_id, region_name, year, month,
                                    crop, pathogen,
                                    toxin_level_ug_per_kg: seasonal(8 + off, month),
                                    prob_illness_pct: prob,
                                    cases_per_100k: Math.round(prob / 100 * 42000),
                                    risk_multiplier: +(prob / Math.max(0.1, baseline)).toFixed(2)
                                },
                                geometry: f.geometry
                            });
                        }
                    }
                }
            }
        }

        window.RISK_GEOJSON = { type: "FeatureCollection", features: feats };
            return window.RISK_GEOJSON;
    }

    // Public API: load for given country code
    window.loadRiskGeoForCountry = function (countryCode) {
        return buildForCountry(countryCode).catch(err => {
            console.error("Failed to build risk GeoJSON:", err);
            window.RISK_GEOJSON = { type: "FeatureCollection", features: [] };
            return window.RISK_GEOJSON;
        });
    };

    // Initial load: read from the DOM if present, else default to NL
    const initialCountry = (document.getElementById('rm-country')?.value || 'NL').toUpperCase();
    window.RISK_GEOJSON_READY = window.loadRiskGeoForCountry(initialCountry);
})();
