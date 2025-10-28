// static/js/pages/dashboard/risk/charts/toxin_over_time.js

window.renderToxinChart = function (domId, rows, pairLabel = "") {
    const el = document.getElementById(domId);
    const chart = echarts.init(el, null, { renderer: 'canvas' });
    window.addEventListener('resize', () => chart.resize());

    const x = rows.map(r => r.date);
    const y = rows.map(r => r.toxin_level_ug_per_kg);
    const limit = rows[0]?.toxin_limit_ug_per_kg ?? window.RISK_CONFIG.defaultToxinLimit;

    chart.setOption({
        title: { text: '', subtext: pairLabel, },
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
        xAxis: { type: 'category', data: x, boundaryGap: false },
        yAxis: {
            type: 'value',
            name: 'μg/kg',
            max: Math.max(Math.ceil(Math.max(...y, limit) + 1), 10) // always include the limit
        },
        series: [{
            name: 'Toxin level',
            type: 'line',
            data: y,
            showSymbol: false,
            lineStyle: { width: 2 }
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
    });
};
