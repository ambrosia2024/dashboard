// static/js/pages/dashboard/risk/charts/dummy_geojson.js
// Very small demo dataset: 3 regions × 12 months.
// TO DO: Replace with real NUTS GeoJSON + model outputs.

(function () {
  // helper to make a rectangle polygon [minLon, minLat, maxLon, maxLat]
  function rect(minLon, minLat, maxLon, maxLat) {
    return {
      type: "Polygon",
      coordinates: [[
        [minLon, minLat], [maxLon, minLat], [maxLon, maxLat],
        [minLon, maxLat], [minLon, minLat]
      ]]
    };
  }

  // three coarse “regions” over NL/BE area (purely for demo)
  const REGIONS = [
    { id: "NL41", name: "Noord-Brabant", geom: rect(4.0, 51.3, 6.0, 51.8) },
    { id: "NL42", name: "Limburg (NL)",  geom: rect(5.6, 50.7, 6.1, 51.3) },
    { id: "BE22", name: "Limburg (BE)",  geom: rect(5.2, 50.9, 5.9, 51.3) }
  ];

  function seasonal(base, month, noise=0.25) {
    // peak in late summer / early autumn
    const season = Math.max(0, Math.sin((2 * Math.PI * (month - 2)) / 12));
    return +(base + season * 1.2 + (Math.random() - 0.5) * noise).toFixed(2);
  }

  const feats = [];
  for (const r of REGIONS) {
    for (const year of [2021, 2022, 2023]) {
      for (let month = 1; month <= 12; month++) {
        const prob = seasonal(2.2, month);              // %
        const baseline = seasonal(1.4, month);          // %
        feats.push({
          type: "Feature",
          id: `${r.id}-${year}-${month}`,
          properties: {
            region_id: r.id,
            region_name: r.name,
            year, month,
            crop: "Lettuce",
            pathogen: "Salmonella",
            toxin_level_ug_per_kg: seasonal(8, month),  // μg/kg
            prob_illness_pct: prob,                     // %
            cases_per_100k: Math.round(prob / 100 * 42000),
            risk_multiplier: +(prob / Math.max(0.1, baseline)).toFixed(2)
          },
          geometry: r.geom
        });
      }
    }
  }

  window.RISK_GEOJSON = { type: "FeatureCollection", features: feats };
})();
