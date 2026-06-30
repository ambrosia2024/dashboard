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
            title: { show: false },
            // Hide the empty axes so the card reads as a clean message, not a blank plot.
            xAxis: { type: 'category', data: [], show: false },
            yAxis: { type: 'value', show: false },
            graphic: {
                type: 'group',
                left: 'center',
                top: 'middle',
                children: [
                    // Simple "no data" glyph: a soft ring with a dash.
                    { type: 'circle', x: 0, y: -40, shape: { cx: 0, cy: 0, r: 17 },
                      style: { fill: '#f2f4f7', stroke: '#d0d5dd', lineWidth: 1.5 } },
                    { type: 'line', shape: { x1: -7, y1: -40, x2: 7, y2: -40 },
                      style: { stroke: '#98a2b3', lineWidth: 2 } },
                    { type: 'text', x: 0, y: -10,
                      style: { text: 'No synced data', textAlign: 'center', textVerticalAlign: 'middle',
                               fill: '#475467', fontSize: 15, fontWeight: 600 } },
                    { type: 'text', x: 0, y: 14,
                      style: { text: 'for the selected location / crop / hazard combination',
                               textAlign: 'center', textVerticalAlign: 'middle',
                               fill: '#98a2b3', fontSize: 13 } },
                ],
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
