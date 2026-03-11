(function () {
  const LS_KEY_LOCATION = "lx_selected_location";
  const LS_KEY_CROP = "lx_selected_crop";
  const LS_KEY_PATHOGEN = "lx_selected_pathogen";
  const LS_KEY_CROP_LABEL = "lx_selected_crop_label";
  const LS_KEY_PATHOGEN_LABEL = "lx_selected_pathogen_label";
  const LS_KEY_START = "risk_filter_start";
  const LS_KEY_END = "risk_filter_end";
  const LS_KEY_LOCATION_LAT = "lx_selected_location_lat";
  const LS_KEY_LOCATION_LON = "lx_selected_location_lon";
  const LS_KEY_NUTS2_ID = "lx_selected_nuts2_id";
  const LS_KEY_NUTS2_NAME = "lx_selected_nuts2_name";
  let NUTS2_FEATURES_PROMISE = null;

  function isISODate(value) {
    return /^\d{4}-\d{2}-\d{2}$/.test(value || "");
  }

  function currentRouteName() {
    const p = window.location.pathname || "";
    if (p.startsWith("/risk-charts/")) return "risk";
    if (p.startsWith("/dashboard/") || p === "/") return "dashboard";
    return "other";
  }

  function setPanelOpen(panel, open) {
    if (!panel) return;
    panel.classList.toggle("is-open", open);
  }

  function setNuts2Text(text) {
    const el = document.getElementById("ctx-nuts2");
    if (el) el.textContent = text;
  }

  function setNuts2Badge(nutsId, nutsName) {
    const badge = document.getElementById("riskContextNutsBadge");
    if (!badge) return;
    if (!nutsId) {
      badge.classList.add("d-none");
      badge.textContent = "";
      badge.removeAttribute("title");
      return;
    }
    const label = nutsName ? `${nutsId} – ${nutsName}` : `${nutsId}`;
    badge.textContent = label;
    badge.title = label;
    badge.classList.remove("d-none");
  }

  function pointInRing(point, ring) {
    const x = point[0];
    const y = point[1];
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1];
      const xj = ring[j][0], yj = ring[j][1];
      const intersect = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-12) + xi);
      if (intersect) inside = !inside;
    }
    return inside;
  }

  function pointInPolygon(point, polygonCoords) {
    if (!polygonCoords?.length) return false;
    if (!pointInRing(point, polygonCoords[0])) return false;
    for (let i = 1; i < polygonCoords.length; i++) {
      if (pointInRing(point, polygonCoords[i])) return false; // hole
    }
    return true;
  }

  function pointInFeature(point, feature) {
    const g = feature?.geometry;
    if (!g) return false;
    if (g.type === "Polygon") return pointInPolygon(point, g.coordinates);
    if (g.type === "MultiPolygon") return g.coordinates.some((poly) => pointInPolygon(point, poly));
    return false;
  }

  async function getNuts2Features() {
    if (!NUTS2_FEATURES_PROMISE) {
      NUTS2_FEATURES_PROMISE = fetch("/static/data/nuts/NUTS_RG_03M_2021_4326.geojson", {
        headers: { Accept: "application/json" }
      })
        .then((r) => {
          if (!r.ok) throw new Error(`NUTS2 fetch failed (${r.status})`);
          return r.json();
        })
        .then((fc) => {
          const all = Array.isArray(fc?.features) ? fc.features : [];
          const lvl2 = all.filter((f) => String(f?.properties?.LEVL_CODE ?? "") === "2");
          return lvl2.length ? lvl2 : all;
        });
    }
    return NUTS2_FEATURES_PROMISE;
  }

  async function resolveAndStoreNuts2(lat, lon) {
    const x = parseFloat(lon);
    const y = parseFloat(lat);
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      setNuts2Text("NUTS2: not selected");
      setNuts2Badge("", "");
      return;
    }

    setNuts2Text("NUTS2: resolving...");
    try {
      const features = await getNuts2Features();
      const match = features.find((f) => pointInFeature([x, y], f));
      if (!match) {
        localStorage.removeItem(LS_KEY_NUTS2_ID);
        localStorage.removeItem(LS_KEY_NUTS2_NAME);
        setNuts2Text("NUTS2: not found for this point");
        setNuts2Badge("", "");
        return;
      }

      const nutsId = match.properties?.NUTS_ID || "";
      const nutsName = match.properties?.NAME_LATN || "";
      localStorage.setItem(LS_KEY_NUTS2_ID, nutsId);
      localStorage.setItem(LS_KEY_NUTS2_NAME, nutsName);
      setNuts2Text(`NUTS2: ${nutsId}${nutsName ? " – " + nutsName : ""}`);
      setNuts2Badge(nutsId, nutsName);
    } catch (_err) {
      setNuts2Text("NUTS2: unavailable");
      setNuts2Badge("", "");
    }
  }

  function syncRangeGuards(startEl, endEl) {
    if (!startEl || !endEl) return;
    if (isISODate(startEl.value)) endEl.min = startEl.value;
    else endEl.removeAttribute("min");
    if (isISODate(endEl.value)) startEl.max = endEl.value;
    else startEl.removeAttribute("max");
    if (isISODate(startEl.value) && isISODate(endEl.value) && startEl.value > endEl.value) {
      endEl.value = startEl.value;
      endEl.min = startEl.value;
    }
  }

  function hydratePanel() {
    const loc = document.getElementById("ctx-location");
    const crop = document.getElementById("ctx-crop");
    const hazard = document.getElementById("ctx-hazard");
    const start = document.getElementById("ctx-start");
    const end = document.getElementById("ctx-end");
    if (!loc || !crop || !hazard || !start || !end) return;

    const qp = new URLSearchParams(window.location.search);
    const qs = qp.get("start");
    const qe = qp.get("end");

    loc.value = localStorage.getItem(LS_KEY_LOCATION) || "";
    crop.value = localStorage.getItem(LS_KEY_CROP) || "";
    hazard.value = localStorage.getItem(LS_KEY_PATHOGEN) || "";
    start.value = isISODate(qs) ? qs : (localStorage.getItem(LS_KEY_START) || "");
    end.value = isISODate(qe) ? qe : (localStorage.getItem(LS_KEY_END) || "");

    syncRangeGuards(start, end);
    const nutsId = localStorage.getItem(LS_KEY_NUTS2_ID) || "";
    const nutsName = localStorage.getItem(LS_KEY_NUTS2_NAME) || "";
    setNuts2Text(nutsId ? `NUTS2: ${nutsId}${nutsName ? " – " + nutsName : ""}` : "NUTS2: not selected");
    setNuts2Badge(nutsId, nutsName);
  }

  function setLocationLoading(show) {
    const loading = document.getElementById("ctx-location-loading");
    const btn = document.getElementById("ctx-location-search");
    if (loading) loading.style.display = show ? "block" : "none";
    if (btn) btn.disabled = !!show;
  }

  function renderLocationResults(items) {
    const list = document.getElementById("ctx-location-results");
    if (!list) return;

    list.innerHTML = "";
    if (!items || !items.length) {
      list.style.display = "none";
      return;
    }

    for (const it of items) {
      const li = document.createElement("li");
      li.className = "list-group-item";
      li.textContent = it.display_name || `${it.lat}, ${it.lon}`;
      li.dataset.lat = it.lat;
      li.dataset.lon = it.lon;
      list.appendChild(li);
    }

    list.style.display = "block";
  }

  async function searchLocationOptions() {
    const input = document.getElementById("ctx-location");
    if (!input) return;
    const query = (input.value || "").trim();
    if (!query) return;

    setLocationLoading(true);
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&addressdetails=1`;
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      if (!response.ok) throw new Error(`Location search failed (${response.status})`);
      const data = await response.json();
      renderLocationResults(Array.isArray(data) ? data : []);
    } catch (_err) {
      renderLocationResults([]);
    } finally {
      setLocationLoading(false);
    }
  }

  function syncHeaderDateInputs(startVal, endVal) {
    const rmStart = document.getElementById("rm-start");
    const rmEnd = document.getElementById("rm-end");
    if (!rmStart || !rmEnd) return;

    if (isISODate(startVal)) rmStart.value = startVal;
    if (isISODate(endVal)) rmEnd.value = endVal;
    rmStart.dispatchEvent(new Event("input", { bubbles: true }));
    rmEnd.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function syncHomeInputs(locVal, cropVal, hazardVal) {
    const loc = document.getElementById("searchAddress");
    const crop = document.getElementById("crop_list");
    const hazard = document.getElementById("pathogen_list");

    if (loc) {
      loc.value = locVal || "";
      loc.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (crop) {
      crop.value = cropVal || "";
      crop.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (hazard) {
      hazard.value = hazardVal || "";
      hazard.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function persistDateToUrl(startVal, endVal) {
    const url = new URL(window.location.href);
    if (isISODate(startVal)) url.searchParams.set("start", startVal);
    else url.searchParams.delete("start");
    if (isISODate(endVal)) url.searchParams.set("end", endVal);
    else url.searchParams.delete("end");
    window.history.replaceState({}, "", url.toString());
  }

  function applyContext() {
    const loc = document.getElementById("ctx-location");
    const crop = document.getElementById("ctx-crop");
    const hazard = document.getElementById("ctx-hazard");
    const start = document.getElementById("ctx-start");
    const end = document.getElementById("ctx-end");
    if (!loc || !crop || !hazard || !start || !end) return;

    syncRangeGuards(start, end);

    const prevCrop = localStorage.getItem(LS_KEY_CROP) || "";
    const prevHaz = localStorage.getItem(LS_KEY_PATHOGEN) || "";

    localStorage.setItem(LS_KEY_LOCATION, loc.value || "");
    localStorage.setItem(LS_KEY_CROP, crop.value || "");
    localStorage.setItem(LS_KEY_PATHOGEN, hazard.value || "");

    const cropLabel = crop.options[crop.selectedIndex]?.textContent?.trim() || "";
    const hazLabel = hazard.options[hazard.selectedIndex]?.textContent?.trim() || "";
    localStorage.setItem(LS_KEY_CROP_LABEL, cropLabel);
    localStorage.setItem(LS_KEY_PATHOGEN_LABEL, hazLabel);

    if (isISODate(start.value)) localStorage.setItem(LS_KEY_START, start.value);
    if (isISODate(end.value)) localStorage.setItem(LS_KEY_END, end.value);

    persistDateToUrl(start.value, end.value);
    syncHeaderDateInputs(start.value, end.value);
    syncHomeInputs(loc.value, crop.value, hazard.value);
    const lat = localStorage.getItem(LS_KEY_LOCATION_LAT) || "";
    const lon = localStorage.getItem(LS_KEY_LOCATION_LON) || "";
    if (lat && lon) resolveAndStoreNuts2(lat, lon);

    // Risk pages read crop/hazard labels at load; reload if those changed.
    if (currentRouteName() === "risk" && (prevCrop !== (crop.value || "") || prevHaz !== (hazard.value || ""))) {
      window.location.reload();
    }
  }

  function clearContext() {
    localStorage.removeItem(LS_KEY_LOCATION);
    localStorage.removeItem(LS_KEY_LOCATION_LAT);
    localStorage.removeItem(LS_KEY_LOCATION_LON);
    localStorage.removeItem(LS_KEY_CROP);
    localStorage.removeItem(LS_KEY_PATHOGEN);
    localStorage.removeItem(LS_KEY_CROP_LABEL);
    localStorage.removeItem(LS_KEY_PATHOGEN_LABEL);
    localStorage.removeItem(LS_KEY_START);
    localStorage.removeItem(LS_KEY_END);
    localStorage.removeItem(LS_KEY_NUTS2_ID);
    localStorage.removeItem(LS_KEY_NUTS2_NAME);

    const url = new URL(window.location.href);
    url.searchParams.delete("start");
    url.searchParams.delete("end");
    window.history.replaceState({}, "", url.toString());

    hydratePanel();
    syncHomeInputs("", "", "");
    setNuts2Text("NUTS2: not selected");
    setNuts2Badge("", "");
  }

    document.addEventListener("DOMContentLoaded", function () {
    const fab = document.getElementById("riskContextFab");
    const inlineOpen = document.getElementById("riskContextOpenInline");
    const panel = document.getElementById("riskContextPanel");
    const closeBtn = document.getElementById("riskContextClose");
    const applyBtn = document.getElementById("riskContextApply");
    const clearBtn = document.getElementById("riskContextClear");
    const start = document.getElementById("ctx-start");
    const end = document.getElementById("ctx-end");
    const locInput = document.getElementById("ctx-location");
    const locBtn = document.getElementById("ctx-location-search");
    const locResults = document.getElementById("ctx-location-results");

    if (!panel) return;

    hydratePanel();

    fab?.addEventListener("click", () => setPanelOpen(panel, !panel.classList.contains("is-open")));
    inlineOpen?.addEventListener("click", () => setPanelOpen(panel, true));
    closeBtn?.addEventListener("click", () => setPanelOpen(panel, false));
    applyBtn?.addEventListener("click", () => {
      applyContext();
      setPanelOpen(panel, false);
    });
    clearBtn?.addEventListener("click", clearContext);

    start?.addEventListener("input", () => syncRangeGuards(start, end));
    end?.addEventListener("input", () => syncRangeGuards(start, end));

    locBtn?.addEventListener("click", searchLocationOptions);
    locInput?.addEventListener("input", () => {
      localStorage.removeItem(LS_KEY_LOCATION_LAT);
      localStorage.removeItem(LS_KEY_LOCATION_LON);
      localStorage.removeItem(LS_KEY_NUTS2_ID);
      localStorage.removeItem(LS_KEY_NUTS2_NAME);
      setNuts2Text("NUTS2: not selected");
      setNuts2Badge("", "");
    });
    locInput?.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") {
        ev.preventDefault();
        searchLocationOptions();
      }
    });

    locResults?.addEventListener("click", (ev) => {
      const li = ev.target?.closest?.(".list-group-item");
      if (!li) return;

      const lat = (li.dataset.lat || "").trim();
      const lon = (li.dataset.lon || "").trim();
      if (locInput) locInput.value = li.textContent || "";

      if (lat && lon) {
        localStorage.setItem(LS_KEY_LOCATION_LAT, lat);
        localStorage.setItem(LS_KEY_LOCATION_LON, lon);
        resolveAndStoreNuts2(lat, lon);
      }
      localStorage.setItem(LS_KEY_LOCATION, locInput?.value || "");
      renderLocationResults([]);
    });

    document.addEventListener("click", function (ev) {
      const target = ev.target;
      if (!panel.classList.contains("is-open")) return;
      if (panel.contains(target) || fab?.contains(target) || inlineOpen?.contains(target)) return;
      renderLocationResults([]);
      setPanelOpen(panel, false);
    });
  });
})();
