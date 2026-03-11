// static/js/pages/dashboard/risk/charts/seasonal_heatmap.js

window.renderSeasonalHeatmap = function (domId, rows, mode = "risk_multiplier", pairLabel = "") {
    // mode: "risk_multiplier" or "prob_illness_pct"
    const el = document.getElementById(domId);
    if (!el) return;
    const chart = echarts.getInstanceByDom(el) || echarts.init(el);
    if (!el.dataset.riskResizeBound) {
        window.addEventListener('resize', () => chart.resize());
        el.dataset.riskResizeBound = "1";
    }

    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const years = Array.from(new Set(rows.map(r => r.year))).sort((a,b)=>a-b);

    // Heat data: [monthIdx, yearIdx, value]
    const data = rows.map(r => [r.month - 1, years.indexOf(r.year), mode === "risk_multiplier" ? r.risk_multiplier : r.prob_illness_pct]);

    chart.setOption({
        animationDuration: 320,
        animationDurationUpdate: 420,
        animationEasing: 'cubicOut',
        animationEasingUpdate: 'cubicInOut',
        title: { text: ``, subtext: pairLabel },
        tooltip: {
            position: 'top',
            formatter: (p) => {
                const m = months[p.data[0]];
                const y = years[p.data[1]];
                const val = p.data[2];
                return `<strong>${m} ${y}</strong><br>Value: ${val}`;
            }
        },
        grid: { left: 80, right: 20, top: 40, bottom: 40 },
        xAxis: { type: 'category', data: months, splitArea: { show: true } },
        yAxis: { type: 'category', data: years, splitArea: { show: true } },
        visualMap: {
            min: 0, max: mode === "risk_multiplier" ? 6 : 10, calculable: true,
            orient: 'horizontal', left: 'center', bottom: 0,
            inRange: { color: ['#2ca02c', '#ff7f0e', '#d62728'] }
        },
        series: [{ type: 'heatmap', data, label: { show: false } }]
    }, { notMerge: false, lazyUpdate: true });

    window.__seasonalHeatmapInstance = chart;
    window.__seasonalRowsCurrent = rows;
    window.__seasonalModeCurrent = mode;
};
