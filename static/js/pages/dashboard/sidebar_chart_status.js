// static/js/pages/dashboard/sidebar_chart_status.js
// Shows a small coloured dot next to each chart link in the sidebar:
//   green = backed by real DB data, amber = illustrative/demo data.
// Mirrors the Live/Demo badge on the chart pages. Runs site-wide (sidebar is global).
(function () {
  // Charts backed by a real data source. Keep in sync with each chart's
  // DashboardChart.default_config.data_source (only pathogen is wired to real data).
  const REAL = new Set(["c2_pathogen_over_time"]);
  const LIVE_TIP = "Live data";
  const DEMO_TIP = "Demo / illustrative data";

  function setDot(link, isLive) {
    let dot = link.querySelector(".chart-source-indicator");
    if (!dot) {
      dot = document.createElement("span");
      dot.className = "chart-source-indicator ms-1";
      dot.setAttribute("role", "img");
      link.appendChild(dot);
    }
    dot.classList.toggle("is-live", isLive);
    dot.classList.toggle("is-sample", !isLive);
    const tip = isLive ? LIVE_TIP : DEMO_TIP;
    dot.setAttribute("title", tip);
    dot.setAttribute("aria-label", tip);
    dot.textContent = "●"; // ● filled dot
  }

  document.addEventListener("DOMContentLoaded", function () {
    const links = Array.from(
      document.querySelectorAll('#side-menu a[href*="/risk-charts/chart/"]')
    );
    for (const link of links) {
      const match = link.getAttribute("href").match(/\/risk-charts\/chart\/([^/]+)\//);
      if (!match) continue;
      setDot(link, REAL.has(match[1]));
    }
  });
})();
