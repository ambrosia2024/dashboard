// static/js/pages/dashboard/risk/charts/cases_over_time.js

window.renderCasesChart = function (domId, rows, pairLabel = "") {
    const el = document.getElementById(domId);
    const chart = echarts.init(el);
    window.addEventListener('resize', () => chart.resize());

    const x = rows.map(r => r.date);
    const y = rows.map(r => r.cases_per_100k);

    // simple centred rolling mean
    const w = window.RISK_CONFIG.rollingWindow;
    const roll = y.map((_, i, arr) => {
        const s = Math.max(0, i - Math.floor((w - 1) / 2));
        const e = Math.min(arr.length, s + w);
        const slice = arr.slice(s, e);
        const mean = slice.reduce((a, b) => a + b, 0) / slice.length;
        return Math.round(mean);
    });

    chart.setOption({
        title: { text: '', subtext: pairLabel },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: x },
        yAxis: { type: 'value', name: 'per 100k' },
        legend: { data: ['Cases', `${w}-period mean`] },
        series: [
            { type: 'bar', name: 'Cases', data: y, barMaxWidth: 18 },
            { type: 'line', name: `${w}-period mean`, data: roll, showSymbol: false, smooth: true }
        ]
    });
};
