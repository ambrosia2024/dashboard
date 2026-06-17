// Simple line for pathogen model output.
window.renderPathogenConcChart = function (domId, rows, pairLabel = "") {
    const BRAND_BLUE = '#376EB5';
    const el = document.getElementById(domId);
    if (!el) return;
    const chart = echarts.getInstanceByDom(el) || echarts.init(el);
    if (!el.dataset.riskResizeBound) {
        window.addEventListener('resize', () => chart.resize());
        el.dataset.riskResizeBound = "1";
    }

    const x = rows.map(r => r.date);
    const y = rows.map(r => r.pathogen_model_value ?? null);
    const unit = rows.find(r => r.pathogen_model_unit)?.pathogen_model_unit || 'model output';

    if (!rows.length) {
        chart.clear();
        chart.setOption({
            title: { text: '', subtext: pairLabel },
            xAxis: { type: 'category', data: [] },
            yAxis: { type: 'value', name: unit },
            graphic: {
                type: 'text',
                left: 'center',
                top: 'middle',
                style: { text: 'No synced data for the selected filters', fill: '#667085', fontSize: 14 }
            },
            series: []
        }, { notMerge: true });
        window.__pathogenChartInstance = chart;
        window.__pathogenRowsCurrent = [];
        return;
    }

    chart.setOption({
        animationDuration: 320,
        animationDurationUpdate: 420,
        animationEasing: 'cubicOut',
        animationEasingUpdate: 'cubicInOut',
        title: { text: '', subtext: pairLabel },
        tooltip: {
            trigger: 'axis',
            formatter: (p) => {
                const i = p[0].dataIndex;
                const r = rows[i] || {};
                const v = y[i];
                const temp = r.temperature_c == null ? '' : `<br>Temperature: <strong>${r.temperature_c}</strong>`;
                return `<strong>${x[i]}</strong><br>Model value: <strong>${v}</strong> ${unit}${temp}`;
            }
        },
        xAxis: { type: 'category', data: x, boundaryGap: false },
        yAxis: { type: 'value', name: unit },
        series: [{
            type: 'line',
            showSymbol: false,
            smooth: true,
            lineStyle: { width: 2, color: BRAND_BLUE },
            data: y
        }]
    }, { notMerge: false, lazyUpdate: true });

    window.__pathogenChartInstance = chart;
    window.__pathogenRowsCurrent = rows;
};
