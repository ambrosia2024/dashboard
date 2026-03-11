// static/js/pages/dashboard/risk/charts/toxin_over_time.js

// shallow merge helper for simple overrides
function merge(base, extra) {
  return Object.assign({}, base, extra || {});
}

window.renderToxinChart = function (domId, rows, pairLabel = "", cfg = {}) {
    const BRAND_BLUE = '#376EB5';
    const el = document.getElementById(domId);
    if (!el) return;
    const chart = echarts.getInstanceByDom(el) || echarts.init(el, null, { renderer: 'canvas' });
    if (!el.dataset.riskResizeBound) {
      window.addEventListener('resize', () => chart.resize());
      el.dataset.riskResizeBound = "1";
    }

    const x = rows.map(r => r.date);
    const y = rows.map(r => r.toxin_level_ug_per_kg);
    const limit =
      cfg?.defaults?.toxin_limit_ug_per_kg
      ?? rows[0]?.toxin_limit_ug_per_kg
      ?? window.RISK_CONFIG.defaultToxinLimit;

    const baseTitle = {
      text: cfg?.title || 'Toxin concentration vs time',
      subtext: pairLabel || '',
      left: 'center',
      top: 10
    };

    const baseYAxis = {
      type: 'value',
      name: cfg?.y_axis_label || 'Toxin (μg/kg)',
      nameLocation: 'middle',
      nameGap: 45,
      nameTextStyle: { fontSize: 12, fontWeight: 'bold' },
      max: Math.max(Math.ceil(Math.max(...y, limit) + 1), 10)
    };

    chart.setOption({
        animationDuration: 320,
        animationDurationUpdate: 420,
        animationEasing: 'cubicOut',
        animationEasingUpdate: 'cubicInOut',
        title: merge(baseTitle, cfg?.overrides?.title),
        tooltip: {
            trigger: 'axis',
            formatter: (params) => {
                const p = params[0];
                const r = rows[p.dataIndex];
                return [
                `<strong>${r.date}</strong>`,
                `Toxin: <strong>${r.toxin_level_ug_per_kg} μg/kg</strong>`,
                `Limit: ${limit} μg/kg`,
                `Temp: ${r.temperature_c}°C · RH: ${r.humidity_pct}%`,
                r.event !== 'none' ? `Event: ${r.event}` : null
                ].filter(Boolean).join('<br>');
            }
        },
        xAxis: {
            type: 'category',
            data: x,
            boundaryGap: false,
            name: 'Date',
            nameLocation: 'middle',
            nameGap: 30,
            nameTextStyle: {
                fontSize: 12,
                fontWeight: 'bold'
            }
        },
        yAxis: merge(baseYAxis, cfg?.overrides?.yAxis),
        series: [{
            name: 'Toxin level',
            type: 'line',
            data: y,
            showSymbol: false,
            smooth: true,
            lineStyle: { width: 2, color: BRAND_BLUE },
            itemStyle: { color: BRAND_BLUE }
        },
        {
            // horizontal limit line
            type: 'line',
            markLine: {
                symbol: 'none',
                data: [{ yAxis: limit, name: 'Action limit' }],
                lineStyle: { color: '#d62728', width: 2 },
                label: { formatter: `Limit: ${limit} μg/kg` }
            }
        }]
    }, { notMerge: false, lazyUpdate: true });

    window.__toxinsChartInstance = chart;
    window.__toxinsRowsCurrent = rows;

    return chart;
};


window.renderToxinChart3D = function (domId, rows, pairLabel = "") {
    const el = document.getElementById(domId);
    if (!el) return;

    // initialise chart with WebGL renderer (needed for 3D)
    const chart = echarts.getInstanceByDom(el) || echarts.init(el, null, { renderer: 'canvas' });
    if (!el.dataset.riskResizeBound) {
      window.addEventListener('resize', () => chart.resize());
      el.dataset.riskResizeBound = "1";
    }

    // build [timeIndex, toxin, temperature] tuples
    const data3D = rows.map((r, idx) => [
        idx,                           // x: simple time index (0..N-1)
        r.toxin_level_ug_per_kg,       // y: toxin (μg/kg)
        r.temperature_c                // z: temperature (°C)
    ]);

    chart.setOption({
        animationDuration: 320,
        animationDurationUpdate: 420,
        animationEasing: 'cubicOut',
        animationEasingUpdate: 'cubicInOut',
        title: {
            text: '',
            subtext: pairLabel ? `${pairLabel} – 3D view (toxin vs temp vs time)` : '3D view: toxin vs temperature vs time',
            left: 'center'
        },
        tooltip: {
            formatter: (params) => {
                // params.data is [idx, toxin, temp]
                const idx = params.data[0];
                const r = rows[idx];

                // show human-readable date + values
                return [
                    `<strong>${r.date}</strong>`,
                    `Toxin: <strong>${r.toxin_level_ug_per_kg} μg/kg</strong>`,
                    `Temperature: <strong>${r.temperature_c}°C</strong>`,
                    `Humidity: ${r.humidity_pct}%`,
                    r.event !== 'none' ? `Event: ${r.event}` : null
                ].filter(Boolean).join('<br>');
            }
        },
        grid3D: {
            boxWidth: 120,
            boxDepth: 80,
            boxHeight: 60,
            viewControl: {
                // enable animation/rotation for a more "beautiful" feel
                projection: 'perspective',
                autoRotate: true,
                autoRotateSpeed: 5
            },
            light: {
                main: { intensity: 1.2, shadow: true },
                ambient: { intensity: 0.4 }
            }
        },
        xAxis3D: {
            type: 'value',
            name: 'Time index',
            axisLabel: {
                formatter: (value) => {
                    // show only some tick labels to avoid crowding
                    const idx = Math.round(value);
                    const r = rows[idx];
                    return r ? r.date.slice(0, 7) : ''; // YYYY-MM
                }
            }
        },
        yAxis3D: {
            type: 'value',
            name: 'Toxin (μg/kg)'
        },
        zAxis3D: {
            type: 'value',
            name: 'Temperature (°C)'
        },
        series: [{
            type: 'line3D',
            data: data3D,
            lineStyle: {
                width: 3
            },
            // small markers help see individual months
            symbolSize: 6,
            smooth: true // make the curve look more organic
        }]
    }, { notMerge: false, lazyUpdate: true });
};
