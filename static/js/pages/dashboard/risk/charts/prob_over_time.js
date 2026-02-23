// static/js/pages/dashboard/risk/charts/prob_over_time.js

window.renderProbChart = function (domId, rows, pairLabel = "") {
    function applyPinnedMarker(idx) {
        // We draw a vertical dashed line at the pinned x (date).
        const x = rows.map(r => r.date);
        const markLine =
            (typeof idx === 'number') ? [{ xAxis: x[idx], lineStyle: { type: 'dashed', color: '#888', width: 1 }, label: { formatter: x[idx], position: 'insideEndTop' }}]
        : [];
        const opt = chart.getOption();

        // Ensure series[0] exists
        if (opt.series && opt.series[0]) {
            opt.series[0].markLine = { symbol: 'none', data: markLine };
            chart.setOption(opt, false, true);
        }
    }

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
                const pctDelta = base ? ((r.prob_illness_pct - base) / Math.max(0.1, base) * 100).toFixed(1) : '-';
                const rm = base ? (r.prob_illness_pct / Math.max(0.1, base)).toFixed(2) : '-';
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

    chart.off('updateAxisPointer');
    chart.on('updateAxisPointer', (e) => {
        // Only update hover index if nothing is pinned
        if (typeof window.__probPinnedIndex === 'number') return;
        const i = e?.dataIndex ?? e?.axesInfo?.[0]?.value ?? null;
        if (typeof i === 'number') window.__probLastIndex = i;
    });

    chart.off('click');
    chart.on('click', (p) => {
        if (typeof p?.dataIndex === 'number') {
            window.__probPinnedIndex = p.dataIndex;
            applyPinnedMarker(window.__probPinnedIndex);

            // Show interpretation immediately:
            if (window.showProbPointInterpretation) {
                window.showProbPointInterpretation(rows, window.__probPinnedIndex);
            }
        }
    });

    // Double-click anywhere to unpin
    chart.off('dblclick');
    chart.on('dblclick', () => {
        window.__probPinnedIndex = null;
        applyPinnedMarker(null);
    });

    // Global Esc unpins
    document.removeEventListener('keydown', window.__probEscHandler || (()=>{}));
    window.__probEscHandler = (ev) => {
        if (ev.key === 'Escape') {
            window.__probPinnedIndex = null;
            applyPinnedMarker(null);
        }
    };

    document.addEventListener('keydown', window.__probEscHandler);

    // If there was a previously pinned index, re-apply marker on rerender
    applyPinnedMarker(window.__probPinnedIndex);
};
