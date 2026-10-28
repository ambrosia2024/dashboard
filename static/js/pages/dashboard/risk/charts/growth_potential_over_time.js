// static/js/pages/dashboard/risk/charts/growth_potential_over_time.js
// The whole generated span as a line of period means, with an optional min-max
// band. The demo twin of the series chart on the assessment outcome page.

(function () {
  const BRAND_BLUE = '#376EB5';
  const BAND_FILL = 'rgba(55, 110, 181, 0.16)';
  const INDEX_UNIT = 'log₁₀ CFU/g × h';
  // How much of the series the zoom slider shows on first paint. The full span
  // is a century and a half of monthly points, which is unreadable unzoomed.
  const INITIAL_WINDOW_YEARS = 25;

  function setStat(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function fillStats(rows) {
    const values = rows.map((r) => r.growth_potential_index).filter((v) => typeof v === 'number');
    if (!values.length) {
      ['gpSeriesMean', 'gpSeriesPeak', 'gpSeriesLowest', 'gpSeriesCount'].forEach((id) => setStat(id, '—'));
      setStat('gpSeriesPeakDate', '');
      return;
    }
    // The band holds the extremes of the individual days inside each period, so
    // the peak reported here is higher than the highest point on the line.
    const highs = rows.map((r) => r.growth_potential_max ?? r.growth_potential_index);
    const lows = rows.map((r) => r.growth_potential_min ?? r.growth_potential_index);
    const peakIdx = highs.indexOf(Math.max(...highs));

    setStat('gpSeriesMean', (values.reduce((a, b) => a + b, 0) / values.length).toFixed(3));
    setStat('gpSeriesPeak', Number(highs[peakIdx]).toFixed(4));
    setStat('gpSeriesPeakDate', rows[peakIdx] ? rows[peakIdx].date : '');
    setStat('gpSeriesLowest', Math.min(...lows).toFixed(1));
    setStat('gpSeriesCount', String(rows.length));
  }

  // Start the slider at the end of the series, where the projected values are.
  function initialZoom(rows) {
    if (rows.length < 2) return { start: 0, end: 100 };
    const lastYear = rows[rows.length - 1].year;
    const firstShown = rows.findIndex((r) => r.year >= lastYear - INITIAL_WINDOW_YEARS);
    if (firstShown <= 0) return { start: 0, end: 100 };
    return { start: (firstShown / rows.length) * 100, end: 100 };
  }

  window.renderGrowthPotentialSeries = function (domId, rows, pairLabel = '', opts = {}) {
    const el = document.getElementById(domId);
    if (!el) return;
    const chart = echarts.getInstanceByDom(el) || echarts.init(el);
    if (!el.dataset.riskResizeBound) {
      window.addEventListener('resize', () => chart.resize());
      el.dataset.riskResizeBound = '1';
    }

    const showBand = opts.showBand !== false;
    const x = rows.map((r) => r.date);
    const means = rows.map((r) => r.growth_potential_index ?? null);
    const lows = rows.map((r) => r.growth_potential_min ?? null);
    // The band is drawn as two stacked series: an invisible floor at the minimum,
    // then the min-to-max distance filled on top of it.
    const spans = rows.map((r) => {
      if (r.growth_potential_max == null || r.growth_potential_min == null) return null;
      return Math.round((r.growth_potential_max - r.growth_potential_min) * 100) / 100;
    });

    const series = [];
    if (showBand) {
      series.push({
        name: 'band-floor', type: 'line', stack: 'band', data: lows,
        lineStyle: { opacity: 0 }, areaStyle: { opacity: 0 }, symbol: 'none',
        silent: true, z: 1,
      });
      series.push({
        name: 'band-span', type: 'line', stack: 'band', data: spans,
        lineStyle: { opacity: 0 }, areaStyle: { color: BAND_FILL }, symbol: 'none',
        silent: true, z: 1,
      });
    }
    series.push({
      name: 'Growth potential', type: 'line', data: means,
      showSymbol: false, smooth: false,
      lineStyle: { width: 1.6, color: BRAND_BLUE }, itemStyle: { color: BRAND_BLUE },
      z: 3,
    });

    const zoom = initialZoom(rows);

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
          const band = (r.growth_potential_min == null || r.growth_potential_max == null)
            ? ''
            : `<br>Range: <strong>${r.growth_potential_min}</strong> – <strong>${r.growth_potential_max}</strong>`;
          return `<strong>${x[i]}</strong><br>Mean: <strong>${r.growth_potential_index}</strong> ${INDEX_UNIT}${band}`;
        },
      },
      grid: { left: 60, right: 20, top: 30, bottom: 72 },
      xAxis: { type: 'category', data: x, boundaryGap: false },
      yAxis: { type: 'value', name: 'AUC index', min: 0 },
      dataZoom: [
        { type: 'inside', start: zoom.start, end: zoom.end },
        { type: 'slider', start: zoom.start, end: zoom.end, bottom: 10, height: 22 },
      ],
      series,
    }, { notMerge: true, lazyUpdate: true });

    fillStats(rows);

    window.__growthSeriesInstance = chart;
    window.__growthSeriesRowsCurrent = rows;
  };
})();
