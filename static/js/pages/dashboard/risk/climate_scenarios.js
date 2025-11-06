// static/js/pages/dashboard/risk/climate_scenarios.js

(function () {
    // simple scenario config
    const SCENARIOS = {
        optimistic: {
            label: "Optimistic",
            rcp: "RCP4.5",
            tempTrendPerYear: 0.02,      // +0.2°C / decade
            rainTrendPerYear: 0.01,
            probLift: 0.15,              // small extra risk
        },
        central: {
            label: "Central",
            rcp: "RCP4.5",
            tempTrendPerYear: 0.03,
            rainTrendPerYear: 0.015,
            probLift: 0.25,
        },
        pessimistic: {
            label: "Pessimistic",
            rcp: "RCP8.5",
            tempTrendPerYear: 0.05,
            rainTrendPerYear: 0.03,
            probLift: 0.4,
        }
    };

    function monthRange(startISO, endISO) {
        const out = [];
        const d = new Date(startISO);
        const end = new Date(endISO);
        while (d <= end) {
            out.push(d.toISOString().slice(0, 10));
            d.setMonth(d.getMonth() + 1);
        }
        return out;
    }

    // build one scenario series (lightweight, no server)
    function buildScenarioRows({ crop, pathogen, scenarioKey, startISO, endISO }) {
        const cfg = SCENARIOS[scenarioKey] || SCENARIOS.central;
        const months = monthRange(startISO, endISO);
        const startYear = new Date(startISO).getFullYear();

        return months.map((iso) => {
            const d = new Date(iso);
            const years = d.getFullYear() - startYear;
            const temp_anomaly_c = +(cfg.tempTrendPerYear * years).toFixed(2);

            // base seasonal temp just to make it less flat
            const m = d.getMonth() + 1;
            const seasonal = Math.sin((2 * Math.PI * (m - 1)) / 12); // -1..1
            const temperature_c = +(10 + 8 * Math.max(0, seasonal) + temp_anomaly_c).toFixed(1);

            // risk: start from 1.2% and lift it slowly with anomaly
            const prob_illness_pct = +(1.2 + cfg.probLift * years + temp_anomaly_c * 0.2).toFixed(2);

            return {
                date: iso,
                crop,
                pathogen,
                scenario_label: cfg.label,
                rcp: cfg.rcp,
                temp_anomaly_c,
                temperature_c,
                prob_illness_pct
            };
        });
    }

    function renderChart(rows) {
        const el = document.getElementById("rc-climate-chart");
        if (!el) return;
        const chart = echarts.init(el);

        const x = rows.map(r => r.date);
        const temps = rows.map(r => r.temp_anomaly_c);
        const probs = rows.map(r => r.prob_illness_pct);

        chart.setOption({
            tooltip: { trigger: 'axis' },
            legend: { data: ['Δ temp (°C)', 'P(illness) %'] },
            xAxis: { type: 'category', data: x },
            yAxis: [
                { type: 'value', name: 'Δ °C', position: 'left' },
                { type: 'value', name: '%', position: 'right' }
            ],
            series: [
                {
                    name: 'Δ temp (°C)',
                    type: 'line',
                    data: temps,
                    showSymbol: false,
                    lineStyle: { width: 2 }
                },
                {
                    name: 'P(illness) %',
                    type: 'line',
                    yAxisIndex: 1,
                    data: probs,
                    showSymbol: false,
                    lineStyle: { width: 2, type: 'dashed' }
                }
            ]
        });

        window.addEventListener("resize", () => chart.resize());
    }

    function renderScenarioExplanation(rows) {
        const el = document.getElementById("rc-climateExplain");
        if (!el || !rows.length) return;

        const first = rows[0];
        const last = rows[rows.length - 1];
        const diff = (last.temp_anomaly_c - first.temp_anomaly_c).toFixed(2);
        const deltaProb = (last.prob_illness_pct - first.prob_illness_pct).toFixed(2);

        el.innerHTML = `
            <strong>What this shows</strong>
            <ul class="mb-2">
              <li><em>${first.date}</em> → <em>${last.date}</em> for
                  <strong>${first.crop}</strong> — <strong>${first.pathogen}</strong>.</li>
              <li>Each line represents change in temperature (Δ °C) and probability of illness (%).</li>
            </ul>
            <strong>Key trends</strong>
            <ul class="mb-2">
              <li>Temperature anomaly: <strong>${diff >= 0 ? '+' : ''}${diff} °C</strong> increase by 2035.</li>
              <li>Illness probability: <strong>${deltaProb >= 0 ? '+' : ''}${deltaProb}%</strong> change vs baseline.</li>
            </ul>
            <strong>Interpretation</strong>
            <p class="mb-0">
              Scenario: <strong>${first.scenario_label}</strong> (${first.rcp}). The trajectory shows how gradual or severe
              climatic warming could influence foodborne risk patterns under hypothetical conditions.
            </p>
        `;
    }


    document.addEventListener("DOMContentLoaded", function () {
        const sel = document.getElementById("rc-scenario-select");
        const cropLabel = localStorage.getItem("lx_selected_crop_label") || "Lettuce";
        const pathLabel = localStorage.getItem("lx_selected_pathogen_label") || "Salmonella";

        function rerender(scenKey) {
            const rows = buildScenarioRows({
                crop: cropLabel,
                pathogen: pathLabel,
                scenarioKey: scenKey,
                startISO: "2025-01-01",
                endISO: "2035-12-01"
            });
            renderChart(rows);
            renderScenarioExplanation(rows);
        }

        // initial render
        rerender(sel ? sel.value : "central");

        // on change
        sel?.addEventListener("change", function () {
            rerender(this.value);
        });
    });
})();
