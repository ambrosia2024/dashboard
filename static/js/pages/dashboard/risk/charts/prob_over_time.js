// static/js/pages/dashboard/risk/charts/prob_over_time.js

window.renderProbChart = function (domId, rows, pairLabel = "") {
    const el = document.getElementById(domId);
    const chart = echarts.init(el);
    const baseline = rows.length ? rows[0].prob_illness_pct : null;

    window.addEventListener('resize', () => chart.resize());

    // const dataset = rows.map(r => [r.date, r.prob_illness_pct, r.risk_multiplier, r.baseline_prob_illness_pct]);
    const dataset = rows.map(r => {
        const rm = baseline ? (r.prob_illness_pct / Math.max(0.1, baseline)) : 1;
        return [r.date, r.prob_illness_pct, +rm.toFixed(2), baseline];
    });

    chart.setOption({
        title: { text: '', subtext: pairLabel },
        tooltip: {
            trigger: 'axis',
            formatter: (params) => {
                const i = params[0].dataIndex;
                const r = rows[i];
                const base = baseline ?? r.baseline_prob_illness_pct ?? r.prob_illness_pct;
                const pctDelta = base ? ((r.prob_illness_pct - base) / Math.max(0.1, base) * 100).toFixed(1) : '—';
                const rm = base ? (r.prob_illness_pct / Math.max(0.1, base)).toFixed(2) : '—';
                return [
                    `<strong>${r.date}</strong>`,
                    `P(illness): <strong>${r.prob_illness_pct}%</strong>`,
                    `Baseline: ${base}%`,
                    `× baseline: ${rm}`,
                    `Δ vs baseline: ${pctDelta}%`
                ].join('<br>');
            }
        },
        legend: { data: ['Probability', 'Baseline'] },
        xAxis: { type: 'category' },
        yAxis: { type: 'value', name: '%' },
        dataset: { source: dataset }, // [date, prob, multiplier, baseline]
        visualMap: {
            show: true,
            orient: 'horizontal',
            left: 'center',
            bottom: 0,
            pieces: [
                { min: 0,   max: 1.10, label: 'Small (<10%)',       color: '#6cc070' },
                { min: 1.10, max: 1.25, label: 'Moderate (10–25%)', color: '#ffbf00' },
                { min: 1.25, max: 1.50, label: 'Large (25–50%)',    color: '#ff7f0e' },
                { min: 1.50,             label: 'Significant (>50%)', color: '#d62728' }
            ],
            // pieces: window.RISK_CONFIG.riskMultiplierBands.map(b => ({
            //     min: b.min, max: b.max === 999 ? undefined : b.max, label: b.label, color: b.color
            // })),
            dimension: 2 // use risk_multiplier column for colour
        },
        series: [
            { name: 'Probability', type: 'line', encode: { x: 0, y: 1 }, showSymbol: false, lineStyle: { width: 2 } },
            { name: 'Baseline',    type: 'line', encode: { x: 0, y: 3 }, showSymbol: false, lineStyle: { width: 1, type: 'dashed' } }
        ]
    });
};
