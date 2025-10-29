// static/js/pages/dashboard/risk/charts/map_init.js

(function () {
    const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const yearEl   = document.getElementById('rm-year');
    const monthLbl = document.getElementById('rm-month-label');

    const mapEl = document.getElementById('riskMap');
    if (!mapEl) return;     // page may not have the map section

    const map = L.map('riskMap', { scrollWheelZoom: true }).setView([52.1, 5.4], 7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    const monthEl  = document.getElementById('rm-month');
    const cropEl   = document.getElementById('rm-crop');
    const patEl    = document.getElementById('rm-pathogen');
    const metricEl = document.getElementById('rm-metric');
    const caption  = document.getElementById('rm-caption');
    const countryEl = document.getElementById('rm-country');

    let layer;

    function colour(v, metric) {
        if (metric === 'risk_multiplier') {
            // reuse risk bands
            if (v >= 5) return '#d62728';
            if (v >= 2) return '#ff7f0e';
            return '#2ca02c';
        }
        // simple ramp for other metrics
        if (metric === 'prob_illness_pct') return v > 5 ? '#d62728' : v > 3 ? '#ff7f0e' : '#6cc070';
        if (metric === 'toxin_level_ug_per_kg') return v > 12 ? '#d62728' : v > 9 ? '#ff7f0e' : '#6cc070';
        if (metric === 'cases_per_100k') return v > 1500 ? '#d62728' : v > 900 ? '#ff7f0e' : '#6cc070';
        return '#6cc070';
    }

    // Simple legend control
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = function () {
        const div = L.DomUtil.create('div', 'info legend card p-2');
        div.style.background = 'rgba(255,255,255,0.9)';
        div.style.border = '1px solid #ddd';
        div.style.fontSize = '12px';
        div.innerHTML = `
            <div><strong>Legend</strong></div>
            <div id="legend-entries"></div>
        `;
        return div;
    };
    legend.addTo(map);

    function setLegend(metric) {
        const el = document.getElementById('legend-entries');
        if (!el) return;
        if (metric === 'risk_multiplier') {
            el.innerHTML = `
                <div><span style="display:inline-block;width:12px;height:12px;background:#2ca02c;margin-right:6px;"></span> ≤2× baseline</div>
                <div><span style="display:inline-block;width:12px;height:12px;background:#ff7f0e;margin-right:6px;"></span> 2–5×</div>
                <div><span style="display:inline-block;width:12px;height:12px;background:#d62728;margin-right:6px;"></span> >5×</div>
            `;
        } else {
            el.innerHTML = `
                <div><span style="display:inline-block;width:12px;height:12px;background:#6cc070;margin-right:6px;"></span> Small (&lt;10%)</div>
                <div><span style="display:inline-block;width:12px;height:12px;background:#ffbf00;margin-right:6px;"></span> Moderate (10–25%)</div>
                <div><span style="display:inline-block;width:12px;height:12px;background:#ff7f0e;margin-right:6px;"></span> Large (25–50%)</div>
                <div><span style="display:inline-block;width:12px;height:12px;background:#d62728;margin-right:6px;"></span> Significant (&gt;50%)</div>
            `;
        }
    }

    function render() {
        const year = +yearEl.value;
        const month = +monthEl.value;
        const crop = cropEl.value;
        const pathogen = patEl.value;
        const metric = metricEl.value;

        monthLbl.textContent = MONTHS[month - 1];

        if (!window.RISK_GEOJSON) return;

        if (!window.RISK_GEOJSON) {
            console.warn('RISK_GEOJSON not loaded');
            return;
        }

        if (layer) map.removeLayer(layer);

        const feats = window.RISK_GEOJSON.features.filter(f =>
        f.properties.year === year &&
        f.properties.month === month &&
        f.properties.crop === crop &&
        f.properties.pathogen === pathogen
        );

        layer = L.geoJSON(feats, {
            style: f => ({
                color: '#ffffff',         // clean white borders
                weight: 1,
                fillColor: colour(f.properties[metric], metric),
                fillOpacity: 0.6          // a bit more transparent
            }),
            onEachFeature: (f, l) => {
                const p = f.properties;
                // hover highlight
                l.on('mouseover', () => l.setStyle({ weight: 2, color: '#333' }));
                l.on('mouseout',  () => l.setStyle({ weight: 1, color: '#ffffff' }));
                l.bindPopup(`
                    <strong>${p.region_name} (${p.region_id})</strong><br>
                    ${p.year}-${String(p.month).padStart(2,'0')} · ${crop} — ${pathogen}<br>
                    ${metric}: <strong>${p[metric]}</strong>
                `);
            }
        }).addTo(map);

        if (!feats.length) {
            caption.textContent = `${crop} — ${pathogen} · ${MONTHS[month-1]} ${year} · ${metric} — No data for this selection`;
            return;
        }

        if (layer && layer.getLayers().length) {
            map.fitBounds(layer.getBounds(), { padding: [10, 10] });
        } else {
            // fallback view (e.g., if the filter returns 0 features)
            map.setView([52.1, 5.4], 7);
        }
        setLegend(metric);
        caption.textContent = `${crop} — ${pathogen} · Month ${month} · Metric: ${metric}`;
    }

    // Wait for data, then render; re-render on control changes
    function initAfterData() {
        [yearEl, monthEl, cropEl, patEl, metricEl]
            .forEach(el => el && el.addEventListener('input', render));

        if (countryEl) {
            countryEl.addEventListener('change', () => {
                const cc = countryEl.value;
                // reload the FeatureCollection for the selected country
                window.RISK_GEOJSON_READY = window.loadRiskGeoForCountry(cc);
                window.RISK_GEOJSON_READY.then(() => {
                    // remove any previous layer bounds fitting issues
                    if (layer) { map.removeLayer(layer); layer = null; }
                    render();
                });
            });
        }

        render();
    }

    if (window.RISK_GEOJSON) {
        initAfterData();
    } else if (window.RISK_GEOJSON_READY && typeof window.RISK_GEOJSON_READY.then === 'function') {
        window.RISK_GEOJSON_READY.then(initAfterData);
    } else {
        console.warn("Risk GeoJSON not present and no loader promise found.");
    }
})();
