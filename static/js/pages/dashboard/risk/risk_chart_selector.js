// static/js/pages/dashboard/risk/risk_chart_selector.js

(function () {
  const sel = document.getElementById("riskChartSelect");
  if (!sel) return;

  sel.addEventListener("change", () => {
    const url = new URL(window.location.href);
    url.searchParams.set("chart", sel.value);

    // keep current view param if present
    // (so chart switching doesn't reset view)
    // nothing else needed; the param stays.

    window.location.href = url.toString();
  });
})();
