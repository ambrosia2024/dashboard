(function () {
  const STORAGE_ALERTS_KEY = "lx_alerts_cache_v1";
  const STORAGE_READ_IDS_KEY = "lx_alerts_read_ids_v1";
  const STORAGE_NOTIFIED_IDS_KEY = "lx_alerts_notified_ids_v1";

  const badgeEl = document.getElementById("alerts-badge");
  const currentContextEl = document.getElementById("alerts-current-context");
  const allAlertsEl = document.getElementById("alerts-all");
  const markAllReadBtn = document.getElementById("alerts-mark-all-read");
  const alertDropdownBtn = document.getElementById("page-header-alert-dropdown");
  const currentShowMoreBtn = document.getElementById("alerts-current-show-more");
  const allShowMoreBtn = document.getElementById("alerts-all-show-more");
  const filterBtns = Array.from(document.querySelectorAll("[data-alert-filter]"));

  if (
    !badgeEl ||
    !currentContextEl ||
    !allAlertsEl ||
    !markAllReadBtn ||
    !alertDropdownBtn ||
    !currentShowMoreBtn ||
    !allShowMoreBtn
  ) {
    return;
  }

  const PAGE_SIZE = 4;
  let filterMode = "all"; // all | current | unread | high
  let currentVisibleLimit = PAGE_SIZE;
  let allVisibleLimit = PAGE_SIZE;

  const currentSectionWrap = currentContextEl.closest(".px-3");
  const allSectionWrap = allAlertsEl.closest(".px-3");

  function loadJson(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value ? JSON.parse(value) : fallback;
    } catch (_err) {
      return fallback;
    }
  }

  function saveJson(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function getActiveAlerts() {
    return loadJson(STORAGE_ALERTS_KEY, []);
  }

  function setActiveAlerts(alerts) {
    saveJson(STORAGE_ALERTS_KEY, alerts);
  }

  function getReadIdsSet() {
    return new Set(loadJson(STORAGE_READ_IDS_KEY, []));
  }

  function setReadIdsSet(idsSet) {
    saveJson(STORAGE_READ_IDS_KEY, Array.from(idsSet));
  }

  function getNotifiedIdsSet() {
    return new Set(loadJson(STORAGE_NOTIFIED_IDS_KEY, []));
  }

  function setNotifiedIdsSet(idsSet) {
    saveJson(STORAGE_NOTIFIED_IDS_KEY, Array.from(idsSet));
  }

  function pruneIds(activeAlerts) {
    const activeIds = new Set((activeAlerts || []).map((a) => a.id));

    const currentRead = getReadIdsSet();
    const nextRead = new Set(Array.from(currentRead).filter((id) => activeIds.has(id)));
    setReadIdsSet(nextRead);

    const currentNotified = getNotifiedIdsSet();
    const nextNotified = new Set(Array.from(currentNotified).filter((id) => activeIds.has(id)));
    setNotifiedIdsSet(nextNotified);

    return { readIds: nextRead, notifiedIds: nextNotified };
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function severityRank(severity) {
    const map = { critical: 4, high: 3, medium: 2, low: 1 };
    return map[String(severity || "").toLowerCase()] || 0;
  }

  function severityMeta(severity) {
    const key = String(severity || "low").toLowerCase();
    if (key === "critical") {
      return {
        key,
        label: "CRITICAL",
        icon: "bi-exclamation-octagon-fill",
        badgeClass: "bg-danger text-white",
      };
    }
    if (key === "high") {
      return {
        key,
        label: "HIGH",
        icon: "bi-exclamation-triangle-fill",
        badgeClass: "bg-danger-subtle text-danger",
      };
    }
    if (key === "medium") {
      return {
        key,
        label: "MEDIUM",
        icon: "bi-exclamation-circle-fill",
        badgeClass: "bg-warning-subtle text-warning-emphasis",
      };
    }
    return {
      key: "low",
      label: "LOW",
      icon: "bi-info-circle-fill",
      badgeClass: "bg-success-subtle text-success-emphasis",
    };
  }

  function compareAlerts(a, b) {
    const sev = severityRank(b.severity) - severityRank(a.severity);
    if (sev !== 0) return sev;
    return String(b.created_at || "").localeCompare(String(a.created_at || ""));
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function timeAgo(iso) {
    if (!iso) return "";
    const ts = Date.parse(iso);
    if (!Number.isFinite(ts)) return "";
    const diffSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    if (diffSec < 60) return `${diffSec}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return `${Math.floor(diffSec / 86400)}d ago`;
  }

  function getCurrentContextChartIdentifiers() {
    const path = window.location.pathname || "";
    const chartMatch = path.match(/\/risk-charts\/chart\/([^/]+)\/?/);
    if (chartMatch?.[1]) return [decodeURIComponent(chartMatch[1])];
    if (path.startsWith("/risk-charts/toxin")) return ["toxin_over_time"];
    if (path.startsWith("/risk-charts/pathogen")) return ["pathogen_concentration_over_time"];
    if (path.startsWith("/risk-charts/")) {
      return [
        "toxin_over_time",
        "pathogen_concentration_over_time",
        "probability_over_time",
        "cases_over_time",
        "seasonal_heatmap",
      ];
    }
    return [];
  }

  function normalizeChartIdentifier(value) {
    const v = String(value || "").trim().toLowerCase();
    if (!v) return "";
    return v.replace(/^c\d+_/, "");
  }

  function buildClientAlertsFromRows() {
    const alerts = [];
    const createdAt = nowIso();

    const baseRows = window.__riskBaseRowsCurrent || [];
    const rowsForToxin = (window.__toxinsRowsCurrent && window.__toxinsRowsCurrent.length)
      ? window.__toxinsRowsCurrent
      : baseRows;
    const rowsForProbability = (window.__probRowsCurrent && window.__probRowsCurrent.length)
      ? window.__probRowsCurrent
      : baseRows;

    const toxinRows = rowsForToxin || [];
    if (toxinRows.length) {
      const overLimit = toxinRows.filter((r) => {
        const limit = Number(r.toxin_limit_ug_per_kg || 0);
        const value = Number(r.toxin_level_ug_per_kg || 0);
        return limit > 0 && value > limit;
      });

      if (overLimit.length) {
        const maxRow = overLimit.reduce((max, row) => {
          return Number(row.toxin_level_ug_per_kg || 0) > Number(max.toxin_level_ug_per_kg || 0) ? row : max;
        }, overLimit[0]);

        const limit = Number(maxRow.toxin_limit_ug_per_kg || 0);
        const maxValue = Number(maxRow.toxin_level_ug_per_kg || 0);
        const exceedPct = limit > 0 ? ((maxValue - limit) / limit) * 100 : 0;
        const severity = exceedPct >= 50 ? "high" : "medium";
        const first = toxinRows[0] || {};
        const last = toxinRows[toxinRows.length - 1] || {};

        const id = [
          "client_rule",
          "toxin_limit_exceeded",
          first.crop || "",
          first.pathogen || "",
          first.date || "",
          last.date || "",
        ].join("|");

        alerts.push({
          id,
          source: "client_rule",
          scope: "chart",
          chart_identifier: "toxin_over_time",
          chart_label: "Toxin concentration vs time",
          severity,
          title: "Toxin limit exceeded",
          message: `${overLimit.length} point(s) exceeded limit. Peak ${maxValue.toFixed(1)} vs ${limit.toFixed(1)} ug/kg.`,
          created_at: createdAt,
          expires_at: null,
          rule_key: "toxin_limit_exceeded",
          context: {
            exceed_count: overLimit.length,
            max_value: maxValue,
            limit,
          },
        });
      }
    }

    const probRows = rowsForProbability || [];
    if (probRows.length) {
      const baseline = Number(probRows[0].prob_illness_pct || 0);
      const multipliers = probRows.map((r) => {
        const v = Number(r.prob_illness_pct || 0);
        return baseline > 0 ? v / baseline : 1;
      });
      const maxMultiplier = Math.max(...multipliers);

      if (maxMultiplier >= 1.25) {
        const severity = maxMultiplier >= 1.5 ? "high" : "medium";
        const first = probRows[0] || {};
        const last = probRows[probRows.length - 1] || {};

        const id = [
          "client_rule",
          "probability_risk_multiplier",
          first.crop || "",
          first.pathogen || "",
          first.date || "",
          last.date || "",
        ].join("|");

        alerts.push({
          id,
          source: "client_rule",
          scope: "chart",
          chart_identifier: "probability_over_time",
          chart_label: "Probability of illness vs time",
          severity,
          title: "Probability trend elevated",
          message: `Peak risk reached ${maxMultiplier.toFixed(2)}x baseline in current range.`,
          created_at: createdAt,
          expires_at: null,
          rule_key: "probability_risk_multiplier",
          context: {
            max_multiplier: +maxMultiplier.toFixed(2),
            baseline_prob_illness_pct: baseline,
          },
        });
      }
    }

    return alerts.sort(compareAlerts);
  }

  function applyFilter(alerts, readIds) {
    if (filterMode === "unread") {
      return alerts.filter((a) => !readIds.has(a.id));
    }
    if (filterMode === "high") {
      return alerts.filter((a) => severityRank(a.severity) >= 3);
    }
    return alerts;
  }

  function renderAlertItems(container, alerts, readIds, emptyText, limit, showMoreBtn) {
    const visible = alerts.slice(0, limit);
    const hasMore = alerts.length > limit;

    if (!visible.length) {
      container.innerHTML = `<div class="text-muted">${escapeHtml(emptyText)}</div>`;
      if (showMoreBtn) showMoreBtn.classList.add("d-none");
      return;
    }

    container.innerHTML = visible
      .map((alert) => {
        const isRead = readIds.has(alert.id);
        const sev = severityMeta(alert.severity);
        const chartId = String(alert.chart_identifier || "");
        const navUrl = chartId
          ? `/risk-charts/chart/${encodeURIComponent(chartId)}/`
          : "";

        return `
          <div class="alerts-item ${isRead ? "" : "is-unread"} severity-${escapeHtml(sev.key)}"
               data-alert-id="${escapeHtml(alert.id)}"
               data-nav-url="${escapeHtml(navUrl)}">
            <div class="d-flex justify-content-between align-items-start">
              <div class="alerts-item-title">
                <i class="bi ${escapeHtml(sev.icon)} me-1"></i>${escapeHtml(alert.title)}
              </div>
              <span class="badge ${escapeHtml(sev.badgeClass)}">${escapeHtml(sev.label)}</span>
            </div>
            <div>${escapeHtml(alert.message)}</div>
            <div class="alerts-item-meta mt-1">${escapeHtml(alert.chart_label || "General")} · ${timeAgo(alert.created_at)} · ${isRead ? "Read" : "Unread"}</div>
            <div class="alerts-item-actions mt-1">
              ${isRead ? "" : `<button type="button" class="btn btn-link btn-sm p-0 alerts-mark-read">Mark read</button>`}
              ${navUrl ? `<button type="button" class="btn btn-link btn-sm p-0 alerts-open-chart">Go to chart</button>` : ""}
            </div>
          </div>
        `;
      })
      .join("");

    if (showMoreBtn) {
      if (hasMore) {
        const remaining = alerts.length - visible.length;
        showMoreBtn.textContent = `Show more (${remaining})`;
        showMoreBtn.classList.remove("d-none");
      } else {
        showMoreBtn.classList.add("d-none");
      }
    }
  }

  function updateBadge(allAlerts, readIds) {
    const unreadCount = allAlerts.filter((a) => !readIds.has(a.id)).length;
    if (unreadCount > 0) {
      badgeEl.textContent = String(unreadCount);
      badgeEl.classList.remove("d-none");
      return;
    }
    badgeEl.classList.add("d-none");
  }

  function setFilterButtons() {
    filterBtns.forEach((btn) => {
      const mode = btn.getAttribute("data-alert-filter");
      btn.classList.toggle("active", mode === filterMode);
    });
  }

  function renderSectionsVisibility() {
    if (!currentSectionWrap || !allSectionWrap) return;
    if (filterMode === "current") {
      currentSectionWrap.classList.remove("d-none");
      allSectionWrap.classList.add("d-none");
      return;
    }
    currentSectionWrap.classList.remove("d-none");
    allSectionWrap.classList.remove("d-none");
  }

  function maybePlayHighPrioritySignal(newAlerts) {
    const highAlerts = (newAlerts || []).filter((a) => severityRank(a.severity) >= 3);
    if (!highAlerts.length) return;

    // Sound
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        const ctx = new AudioCtx();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.value = 880;
        gain.gain.value = 0.05;
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.12);
      }
    } catch (_err) {
      // ignore sound failures
    }

    // Toast
    if (!window.bootstrap || !window.bootstrap.Toast) return;
    const top = highAlerts[0];

    let holder = document.getElementById("alerts-toast-holder");
    if (!holder) {
      holder = document.createElement("div");
      holder.id = "alerts-toast-holder";
      holder.className = "toast-container position-fixed top-0 end-0 p-3";
      holder.style.zIndex = "2000";
      document.body.appendChild(holder);
    }

    const toastEl = document.createElement("div");
    toastEl.className = "toast align-items-center text-bg-danger border-0";
    toastEl.setAttribute("role", "alert");
    toastEl.setAttribute("aria-live", "assertive");
    toastEl.setAttribute("aria-atomic", "true");
    toastEl.innerHTML = `
      <div class="d-flex">
        <div class="toast-body">
          ${escapeHtml(top.title)}: ${escapeHtml(top.message)}
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    `;
    holder.appendChild(toastEl);
    const toast = new window.bootstrap.Toast(toastEl, { delay: 4500 });
    toast.show();
    toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove(), { once: true });
  }

  function maybeNotifyNewHighPriority(allAlerts, readIds, notifiedIds) {
    const newHigh = allAlerts.filter((a) => {
      if (severityRank(a.severity) < 3) return false;
      if (readIds.has(a.id)) return false;
      return !notifiedIds.has(a.id);
    });

    if (!newHigh.length) return;
    maybePlayHighPrioritySignal(newHigh);

    const nextNotified = new Set(notifiedIds);
    newHigh.forEach((a) => nextNotified.add(a.id));
    setNotifiedIdsSet(nextNotified);
  }

  function refreshAlertsUI() {
    const allAlerts = getActiveAlerts();
    const pruned = pruneIds(allAlerts);
    const readIds = pruned.readIds;
    const notifiedIds = pruned.notifiedIds;

    const currentIdsRaw = getCurrentContextChartIdentifiers();
    const currentIds = new Set(
      currentIdsRaw.flatMap((id) => {
        const norm = normalizeChartIdentifier(id);
        return norm && norm !== id ? [id, norm] : [id];
      })
    );

    const currentContextAlertsRaw = allAlerts.filter((a) => {
      if (!a.chart_identifier) return false;
      const id = String(a.chart_identifier || "");
      const norm = normalizeChartIdentifier(id);
      return currentIds.has(id) || currentIds.has(norm);
    });

    const allNonContextRaw = allAlerts.filter((a) => !currentContextAlertsRaw.includes(a));

    const currentContextAlerts = applyFilter(currentContextAlertsRaw, readIds);
    const allNonContextAlerts = applyFilter(allNonContextRaw, readIds);

    setFilterButtons();
    renderSectionsVisibility();

    renderAlertItems(
      currentContextEl,
      currentContextAlerts,
      readIds,
      "No alerts for this chart.",
      currentVisibleLimit,
      currentShowMoreBtn
    );

    renderAlertItems(
      allAlertsEl,
      allNonContextAlerts,
      readIds,
      "No alerts outside current context.",
      allVisibleLimit,
      allShowMoreBtn
    );

    updateBadge(allAlerts, readIds);
    maybeNotifyNewHighPriority(allAlerts, readIds, notifiedIds);
  }

  function markAlertRead(alertId) {
    const readIds = getReadIdsSet();
    readIds.add(alertId);
    setReadIdsSet(readIds);
    refreshAlertsUI();
  }

  function navigateToAlertChart(item) {
    const navUrl = item.getAttribute("data-nav-url") || "";
    if (!navUrl) return;
    const current = window.location.pathname || "";
    if (current !== navUrl) {
      window.location.href = navUrl;
    }
  }

  function generateAndPersistClientAlerts() {
    const hasAnyRiskRows = !!(
      (window.__riskBaseRowsCurrent && window.__riskBaseRowsCurrent.length) ||
      (window.__toxinsRowsCurrent && window.__toxinsRowsCurrent.length) ||
      (window.__probRowsCurrent && window.__probRowsCurrent.length) ||
      (window.__pathogenRowsCurrent && window.__pathogenRowsCurrent.length) ||
      (window.__casesRowsCurrent && window.__casesRowsCurrent.length) ||
      (window.__seasonalRowsCurrent && window.__seasonalRowsCurrent.length)
    );

    if (!hasAnyRiskRows) {
      refreshAlertsUI();
      return;
    }

    const alerts = buildClientAlertsFromRows();
    setActiveAlerts(alerts);
    refreshAlertsUI();
  }

  function resetPagination() {
    currentVisibleLimit = PAGE_SIZE;
    allVisibleLimit = PAGE_SIZE;
  }

  currentShowMoreBtn.addEventListener("click", () => {
    currentVisibleLimit += PAGE_SIZE;
    refreshAlertsUI();
  });

  allShowMoreBtn.addEventListener("click", () => {
    allVisibleLimit += PAGE_SIZE;
    refreshAlertsUI();
  });

  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.getAttribute("data-alert-filter") || "all";
      filterMode = next;
      resetPagination();
      refreshAlertsUI();
    });
  });

  allAlertsEl.addEventListener("click", (ev) => {
    const markBtn = ev.target.closest(".alerts-mark-read");
    if (markBtn) {
      const item = markBtn.closest(".alerts-item");
      const id = item?.getAttribute("data-alert-id");
      if (id) markAlertRead(id);
      ev.stopPropagation();
      return;
    }

    const openBtn = ev.target.closest(".alerts-open-chart");
    if (openBtn) {
      const item = openBtn.closest(".alerts-item");
      if (!item) return;
      const id = item.getAttribute("data-alert-id");
      if (id) markAlertRead(id);
      navigateToAlertChart(item);
      ev.stopPropagation();
      return;
    }

    const item = ev.target.closest(".alerts-item");
    if (!item) return;
    const id = item.getAttribute("data-alert-id");
    if (!id) return;
    markAlertRead(id);
    navigateToAlertChart(item);
  });

  currentContextEl.addEventListener("click", (ev) => {
    const markBtn = ev.target.closest(".alerts-mark-read");
    if (markBtn) {
      const item = markBtn.closest(".alerts-item");
      const id = item?.getAttribute("data-alert-id");
      if (id) markAlertRead(id);
      ev.stopPropagation();
      return;
    }

    const openBtn = ev.target.closest(".alerts-open-chart");
    if (openBtn) {
      const item = openBtn.closest(".alerts-item");
      if (!item) return;
      const id = item.getAttribute("data-alert-id");
      if (id) markAlertRead(id);
      navigateToAlertChart(item);
      ev.stopPropagation();
      return;
    }

    const item = ev.target.closest(".alerts-item");
    if (!item) return;
    const id = item.getAttribute("data-alert-id");
    if (!id) return;
    markAlertRead(id);
  });

  markAllReadBtn.addEventListener("click", () => {
    const allIds = getActiveAlerts().map((a) => a.id);
    setReadIdsSet(new Set(allIds));
    refreshAlertsUI();
  });

  alertDropdownBtn.addEventListener("click", () => {
    refreshAlertsUI();
  });

  document.addEventListener("risk:charts-rendered", () => {
    generateAndPersistClientAlerts();
  });

  document.addEventListener("DOMContentLoaded", () => {
    refreshAlertsUI();
  });

  window.setTimeout(() => {
    generateAndPersistClientAlerts();
  }, 0);
})();
