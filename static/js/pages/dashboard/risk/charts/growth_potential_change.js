// static/js/pages/dashboard/risk/charts/growth_potential_change.js
// Baseline vs future window, averaged per calendar month. The demo twin of the
// comparison chart on the assessment outcome page: same shape and same reading,
// but fed by the shared dummy generator instead of the model output.

(function () {
  const BASELINE_COLOR = '#376EB5';
  const FUTURE_COLOR = '#E8842A';
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const INDEX_UNIT = 'log₁₀ CFU/g × h';

  function mean(values) {
    const nums = values.filter((v) => typeof v === 'number' && !Number.isNaN(v));
    if (!nums.length) return null;
    return nums.reduce((a, b) => a + b, 0) / nums.length;
  }

  // Twelve calendar-month means for the rows whose year falls inside the window.
  function monthlyMeans(rows, from, to, key) {
    const buckets = MONTHS.map(() => []);
    for (const row of rows) {
      if (row.year < from || row.year > to) continue;
      buckets[row.month - 1].push(row[key]);
    }
    return buckets.map((bucket) => {
      const m = mean(bucket);
      return m === null ? null : Math.round(m * 100) / 100;
    });
  }

  function round1(x) { return x === null ? null : Math.round(x * 10) / 10; }

  function line(name, data, color, dashed, axisIndex) {
    return {
      name,
      type: 'line',
      data,
      yAxisIndex: axisIndex || 0,
      smooth: true,
      symbol: 'circle',
      symbolSize: dashed ? 0 : 6,
      connectNulls: true,
      lineStyle: { width: dashed ? 1.5 : 2.4, color, type: dashed ? 'dashed' : 'solid' },
      itemStyle: { color },
      z: dashed ? 2 : 3,
    };
  }

  function fillSummary(el, baseMeans, futureMeans, baseTemps, futureTemps, baseline, future) {
    if (!el) return;
    const b = mean(baseMeans);
    const f = mean(futureMeans);
    if (b === null || f === null) {
      el.textContent = 'One of the two windows has no data in the generated series.';
      return;
    }
    const deltaPct = b > 0 ? Math.round(((f - b) / b) * 100) : 0;
    const bt = mean(baseTemps);
    const ft = mean(futureTemps);
    const tempPart = (bt === null || ft === null)
      ? ''
      : ` The average temperature moves from ${round1(bt)} °C to ${round1(ft)} °C (${ft >= bt ? '+' : ''}${round1(ft - bt)} °C).`;
    el.textContent =
      `Across all months, mean growth potential moves from ${b.toFixed(2)} (${baseline[0]}–${baseline[1]})`
      + ` to ${f.toFixed(2)} (${future[0]}–${future[1]}), ${deltaPct >= 0 ? '+' : ''}${deltaPct}%.${tempPart}`;
  }

  function fillTable(table, baseMeans, futureMeans, baseTemps, futureTemps) {
    if (!table) return;
    const body = table.querySelector('tbody');
    if (!body) return;

    const rows = MONTHS.map((label, i) => {
      const b = baseMeans[i];
      const f = futureMeans[i];
      const bt = baseTemps[i];
      const ft = futureTemps[i];
      if (b === null || f === null) return '';
      const dIndex = f - b;
      const dPct = b > 0 ? Math.round((dIndex / b) * 100) : null;
      const temp = (bt === null || ft === null)
        ? '<td>—</td><td>—</td>'
        : `<td>${round1(bt)} → ${round1(ft)} °C</td><td>${ft >= bt ? '+' : ''}${round1(ft - bt)}</td>`;
      return `<tr><td>${label}</td>${temp}`
        + `<td>${b.toFixed(2)} → ${f.toFixed(2)}</td>`
        + `<td>${dIndex >= 0 ? '+' : ''}${dIndex.toFixed(2)}</td>`
        + `<td>${dPct === null ? '—' : (dPct >= 0 ? '+' : '') + dPct + '%'}</td></tr>`;
    });

    body.innerHTML = rows.join('');
    table.hidden = false;
  }

  window.renderGrowthPotentialChange = function (domId, rows, pairLabel = '', opts = {}) {
    const el = document.getElementById(domId);
    if (!el) return;
    const chart = echarts.getInstanceByDom(el) || echarts.init(el);
    if (!el.dataset.riskResizeBound) {
      window.addEventListener('resize', () => chart.resize());
      el.dataset.riskResizeBound = '1';
    }

    const baseline = opts.baseline || [1991, 2020];
    const future = opts.future || [2066, 2095];
    const showTemp = opts.showTemp !== false;

    const baseMeans = monthlyMeans(rows, baseline[0], baseline[1], 'growth_potential_index');
    const futureMeans = monthlyMeans(rows, future[0], future[1], 'growth_potential_index');
    const baseTemps = monthlyMeans(rows, baseline[0], baseline[1], 'growth_temp_c');
    const futureTemps = monthlyMeans(rows, future[0], future[1], 'growth_temp_c');

    const baseLabel = `Baseline climate conditions (${baseline[0]}–${baseline[1]})`;
    const futureLabel = `Future climate conditions (${future[0]}–${future[1]})`;
    const series = [
      line(baseLabel, baseMeans, BASELINE_COLOR, false, 0),
      line(futureLabel, futureMeans, FUTURE_COLOR, false, 0),
    ];
    if (showTemp) {
      series.push(line('Baseline temperature', baseTemps, BASELINE_COLOR, true, 1));
      series.push(line('Future temperature', futureTemps, FUTURE_COLOR, true, 1));
    }

    chart.setOption({
      animationDuration: 320,
      animationDurationUpdate: 420,
      animationEasing: 'cubicOut',
      animationEasingUpdate: 'cubicInOut',
      title: { text: '', subtext: pairLabel },
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v) => (v === null || v === undefined ? '—' : Number(v).toFixed(2)),
      },
      legend: { top: 0, type: 'scroll' },
      grid: { left: 60, right: showTemp ? 60 : 20, top: 44, bottom: 40 },
      xAxis: { type: 'category', data: MONTHS, boundaryGap: false },
      yAxis: [
        { type: 'value', name: INDEX_UNIT, nameTextStyle: { align: 'left' } },
        { type: 'value', name: '°C', show: showTemp, splitLine: { show: false } },
      ],
      series,
    }, { notMerge: true, lazyUpdate: true });

    fillSummary(
      document.getElementById('growthChangeSummary'),
      baseMeans, futureMeans, baseTemps, futureTemps, baseline, future,
    );
    fillTable(document.getElementById('growthChangeTable'), baseMeans, futureMeans, baseTemps, futureTemps);

    window.__growthChangeInstance = chart;
    window.__growthChangeRowsCurrent = rows;
  };
})();
