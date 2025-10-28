// Simple line with baseline-relative colouring and optional threshold.
window.renderPathogenConcChart = function (domId, rows, pairLabel = "") {
  const el = document.getElementById(domId);
  if (!el) return;
  const chart = echarts.init(el);
  window.addEventListener('resize', () => chart.resize());

  // Use your toxin numeric as a stand-in if you don’t yet have a separate field:
  const x = rows.map(r => r.date);
  const y = rows.map(r => r.pathogen_conc_units_per_g ?? r.toxin_level_ug_per_kg);

  // Baseline = first point in the selected series (Jack’s rule)
  const baseline = y.length ? y[0] : null;

  function classifyBand(curr, base) {
    if (base <= 0 || base == null) return 'significant';
    const inc = ((curr - base) / base) * 100;
    if (inc < 10)  return 'small';
    if (inc < 25)  return 'moderate';
    if (inc < 50)  return 'large';
    return 'significant';
  }
  const colourFor = band => ({small:'#6cc070',moderate:'#ffbf00',large:'#ff7f0e',significant:'#d62728'})[band];

  chart.setOption({
    title: { text: '', subtext: pairLabel },
    tooltip: {
      trigger: 'axis',
      formatter: (p) => {
        const i = p[0].dataIndex;
        const v = y[i];
        const inc = baseline ? (((v - baseline) / baseline) * 100).toFixed(1) : '—';
        return `<strong>${x[i]}</strong><br>Conc: <strong>${v}</strong><br>Baseline: ${baseline ?? '—'}<br>Δ vs baseline: ${inc}%`;
      }
    },
    xAxis: { type: 'category', data: x, boundaryGap: false },
    yAxis: { type: 'value', name: 'units/g' },
    series: [{
      type: 'line',
      showSymbol: false,
      data: y.map(v => ({
        value: v,
        itemStyle: { color: colourFor(classifyBand(v, baseline)) }
      }))
    }]
  });
};
