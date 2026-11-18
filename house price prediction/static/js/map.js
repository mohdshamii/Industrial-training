(function () {
  const mapEl = document.getElementById("estateMap");
  if (!mapEl) return;

  // Strict Black, White, Royal Blue & Baby Pink category markers
  const CAT_META = {
    schools: { label: "Schools", color: "#2563eb" },
    hospitals: { label: "Hospitals", color: "#f4b8d0" },
    metro_stations: { label: "Metro Stations", color: "#60a5fa" },
    railway_stations: { label: "Railway Stations", color: "#1d4ed8" },
    shopping_malls: { label: "Shopping Malls", color: "#f8c8dc" },
    restaurants: { label: "Restaurants", color: "#d46b99" },
    parks: { label: "Parks", color: "#ffffff" },
    airports: { label: "Airports", color: "#090b10" },
  };

  let currentState = {
    name: "Indiranagar, Bengaluru",
    display_name: "Indiranagar, Bengaluru, Karnataka, India",
    lat: 12.9784,
    lon: 77.6408,
    nearby: null,
    weather: null,
  };
  let activeCategory = "all";
  let pinnedLocations = [];

  const map = L.map("estateMap", { zoomControl: true }).setView([currentState.lat, currentState.lon], 14);
  let tileLayer = null;

  function applyMapTiles(theme) {
    if (tileLayer) map.removeLayer(tileLayer);
    const url =
      theme === "light"
        ? "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        : "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png";
    tileLayer = L.tileLayer(url, {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);
  }
  applyMapTiles(document.documentElement.getAttribute("data-theme") || "dark");
  window.addEventListener("estateiq:themechange", (e) => applyMapTiles(e.detail.theme));

  const mainMarkerLayer = L.layerGroup().addTo(map);
  const poiLayer = L.layerGroup().addTo(map);

  function makeSvgIcon(color, isMain = false) {
    const size = isMain ? 30 : 18;
    const lower = color.toLowerCase();
    const stroke = ["#ffffff", "#f4b8d0", "#f8c8dc"].includes(lower) ? "#090b10" : "#ffffff";
    const svg = isMain
      ? `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="${color}" stroke="#090b10" stroke-width="1.8"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3.2" fill="#090b10"/></svg>`
      : `<svg width="${size}" height="${size}" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="${color}" stroke="${stroke}" stroke-width="2.4"/></svg>`;
    return L.divIcon({
      html: svg,
      className: "",
      iconSize: [size, size],
      iconAnchor: [size / 2, isMain ? size : size / 2],
    });
  }

  async function inspectCoordinates(lat, lon, label) {
    currentState.lat = Number(lat);
    currentState.lon = Number(lon);
    if (label) {
      currentState.name = label.split(",")[0].trim();
      currentState.display_name = label;
    }

    const radius = Number(document.getElementById("mapRadiusSelect").value || 3000);
    document.getElementById("selectedLocLabel").textContent = currentState.display_name;
    document.getElementById("selectedCoordsLabel").textContent = `${currentState.lat.toFixed(4)}, ${currentState.lon.toFixed(4)}`;

    mainMarkerLayer.clearLayers();
    poiLayer.clearLayers();
    map.setView([currentState.lat, currentState.lon], radius <= 2000 ? 15 : 14);
    L.marker([currentState.lat, currentState.lon], { icon: makeSvgIcon("#f4b8d0", true) })
      .bindPopup(`<strong>${EstateIQ.escapeHtml(currentState.name)}</strong><br/>Selected Property Area`)
      .addTo(mainMarkerLayer);
    L.circle([currentState.lat, currentState.lon], {
      radius,
      color: "#2563eb",
      fillColor: "#2563eb",
      fillOpacity: 0.08,
      weight: 1.4,
    }).addTo(mainMarkerLayer);

    document.getElementById("amenityListBox").innerHTML = '<div style="padding:14px 0;color:var(--text-secondary);"><span class="spinner"></span> Scanning OpenStreetMap Overpass facilities...</div>';

    // Parallel fetch nearby POIs & Open-Meteo weather
    const [nearRes, weatherRes] = await Promise.allSettled([
      EstateIQ.apiFetch(`/api/nearby?lat=${currentState.lat}&lon=${currentState.lon}&radius=${radius}`, { method: "GET" }),
      EstateIQ.apiFetch(`/api/weather?lat=${currentState.lat}&lon=${currentState.lon}`, { method: "GET" }),
    ]);

    if (weatherRes.status === "fulfilled" && !weatherRes.value.error) {
      currentState.weather = weatherRes.value;
      renderWeather(weatherRes.value);
    } else {
      document.getElementById("weatherMain").textContent = "Weather unavailable";
    }

    if (nearRes.status === "fulfilled") {
      currentState.nearby = nearRes.value;
      renderAmenities(nearRes.value);
    } else {
      document.getElementById("amenityListBox").innerHTML = `<div class="alert alert-warning">Unable to fetch nearby POIs right now.</div>`;
    }
  }

  function renderWeather(w) {
    document.getElementById("weatherMain").textContent = `${w.temperature_c}°C · ${w.condition}`;
    document.getElementById("weatherDetails").innerHTML = `Humidity: <strong>${w.humidity_pct}%</strong><br/>Wind: <strong>${w.wind_kmh} km/h</strong>`;
    const row = document.getElementById("weatherForecastRow");
    row.innerHTML = (w.forecast || [])
      .map(
        (d) => `
      <div style="background:var(--bg-surface);border:1px solid var(--border-subtle);border-radius:8px;padding:7px;font-size:0.72rem;">
        <div style="font-weight:700;">${EstateIQ.escapeHtml(d.date.slice(5))}</div>
        <div class="mono" style="color:var(--accent-cyan);">${d.temp_min_c}° / ${d.temp_max_c}°C</div>
        <div style="color:var(--text-muted);">Rain ${d.rain_prob_pct ?? 0}%</div>
      </div>`
      )
      .join("");
  }

  function renderAmenities(data) {
    const scoreBadge = document.getElementById("connectivityBadge");
    if (data.connectivity_index !== null && data.connectivity_index !== undefined) {
      scoreBadge.textContent = `Amenity Index: ${data.connectivity_index}/100`;
    } else {
      scoreBadge.textContent = "Index: N/A";
    }
    document.getElementById("amenityTotalBadge").textContent = `${data.total_found || 0} POIs`;

    const bar = document.getElementById("categoryFilterBar");
    const counts = data.counts || {};
    bar.innerHTML = Object.entries(CAT_META)
      .map(([cat, meta]) => {
        const cnt = counts[cat] || 0;
        const activeStyle = activeCategory === cat ? `border-color:${meta.color};background:var(--bg-hover);` : "";
        return `
        <button type="button" class="cat-filter-btn" data-cat="${cat}" style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border-radius:10px;border:1px solid var(--border-subtle);background:var(--bg-surface-2);color:var(--text-primary);cursor:pointer;font-size:0.78rem;${activeStyle}">
          <span style="display:flex;align-items:center;gap:7px;">
            <span style="width:9px;height:9px;border-radius:50%;background:${meta.color};"></span>
            ${meta.label}
          </span>
          <strong class="mono">${cnt}</strong>
        </button>`;
      })
      .join("");

    bar.querySelectorAll(".cat-filter-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeCategory = activeCategory === btn.dataset.cat ? "all" : btn.dataset.cat;
        renderAmenities(data);
      });
    });

    poiLayer.clearLayers();
    const allItems = [];
    Object.entries(data.categories || {}).forEach(([cat, items]) => {
      if (activeCategory !== "all" && activeCategory !== cat) return;
      const meta = CAT_META[cat] || { label: cat, color: "#94a3b8" };
      items.forEach((it) => {
        allItems.push({ ...it, color: meta.color, catLabel: meta.label });
        L.marker([it.lat, it.lon], { icon: makeSvgIcon(meta.color, false) })
          .bindPopup(`<strong>${EstateIQ.escapeHtml(it.name)}</strong><br/>${meta.label} &middot; ${it.distance_km} km`)
          .addTo(poiLayer);
      });
    });

    allItems.sort((a, b) => a.distance_km - b.distance_km);
    const listBox = document.getElementById("amenityListBox");
    if (data.error) {
      listBox.innerHTML = `<div class="alert alert-warning">${EstateIQ.escapeHtml(data.error)}</div>`;
      return;
    }
    if (!allItems.length) {
      listBox.innerHTML = `<div style="color:var(--text-muted);font-size:0.83rem;padding:12px 0;">No facilities found in this filter/radius. Try expanding radius to 5 km.</div>`;
      return;
    }

    listBox.innerHTML = allItems
      .slice(0, 30)
      .map(
        (it) => `
      <div class="amenity-item">
        <div>
          <div style="font-weight:600;display:flex;align-items:center;gap:7px;">
            <span style="width:8px;height:8px;border-radius:50%;background:${it.color};flex-shrink:0;"></span>
            ${EstateIQ.escapeHtml(it.name)}
          </div>
          <div style="font-size:0.72rem;color:var(--text-muted);">${it.catLabel}</div>
        </div>
        <span class="badge badge-muted mono">${it.distance_km} km</span>
      </div>`
      )
      .join("");
  }

  async function searchLocation(q) {
    if (!q || q.length < 2) {
      EstateIQ.showToast("Enter a location name to search.", "error");
      return;
    }
    const btn = document.getElementById("mapSearchBtn");
    btn.disabled = true;
    try {
      const res = await EstateIQ.apiFetch(`/api/geocode?q=${encodeURIComponent(q)}&limit=5`, { method: "GET" });
      if (!res.results || !res.results.length) {
        EstateIQ.showToast(res.error || "Location not found.", "error");
        return;
      }
      const first = res.results[0];
      document.getElementById("mapSearchResults").style.display = "none";
      inspectCoordinates(first.lat, first.lon, first.display_name);
    } catch (err) {
      EstateIQ.showToast(err.message, "error");
    } finally {
      btn.disabled = false;
    }
  }

  document.getElementById("mapSearchBtn").addEventListener("click", () => {
    searchLocation(document.getElementById("mapSearchInput").value.trim());
  });
  document.getElementById("mapSearchInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      searchLocation(e.target.value.trim());
    }
  });
  document.getElementById("mapRadiusSelect").addEventListener("change", () => {
    inspectCoordinates(currentState.lat, currentState.lon, currentState.display_name);
  });

  document.querySelectorAll(".quick-city-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById("mapSearchInput").value = btn.dataset.q;
      searchLocation(btn.dataset.q);
    });
  });

  document.querySelectorAll(".jump-fav-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      inspectCoordinates(btn.dataset.lat, btn.dataset.lon, btn.dataset.name);
    });
  });

  map.on("click", (e) => {
    inspectCoordinates(e.latlng.lat, e.latlng.lng, `Pinned Point (${e.latlng.lat.toFixed(4)}, ${e.latlng.lng.toFixed(4)})`);
  });

  // Pin for Location-to-Location comparison
  document.getElementById("setCompareLocBtn").addEventListener("click", () => {
    if (!currentState.nearby) {
      EstateIQ.showToast("Wait for the current location scan to finish before pinning.", "info");
      return;
    }
    if (pinnedLocations.length >= 3) pinnedLocations.shift();
    pinnedLocations.push({
      name: currentState.name,
      lat: currentState.lat,
      lon: currentState.lon,
      counts: currentState.nearby.counts || {},
      nearest: currentState.nearby.nearest || {},
      score: currentState.nearby.connectivity_index,
      weather: currentState.weather,
    });
    renderLocationComparison();
    EstateIQ.showToast(`Pinned '${currentState.name}' for location comparison (${pinnedLocations.length} pinned).`, "success");
  });

  document.getElementById("clearLocCompareBtn").addEventListener("click", () => {
    pinnedLocations = [];
    document.getElementById("locCompareCard").style.display = "none";
  });

  function renderLocationComparison() {
    const card = document.getElementById("locCompareCard");
    if (!pinnedLocations.length) {
      card.style.display = "none";
      return;
    }
    card.style.display = "block";
    document.getElementById("locCompareHead").innerHTML = `<th>Infrastructure Metric</th>${pinnedLocations.map((l) => `<th>${EstateIQ.escapeHtml(l.name)}</th>`).join("")}`;
    const rows = [
      ["Amenity Density Index", (l) => `<span class="badge badge-emerald mono">${l.score ?? "N/A"} / 100</span>`],
      ["Live Temperature", (l) => (l.weather ? `${l.weather.temperature_c}°C (${l.weather.condition})` : "-")],
      ...Object.entries(CAT_META).map(([cat, m]) => [
        m.label,
        (l) => {
          const cnt = l.counts[cat] || 0;
          const near = l.nearest[cat];
          return `<span class="mono">${cnt}</span> ${near ? `<span style="color:var(--text-muted);font-size:0.74rem;">(nearest ${near.distance_km} km)</span>` : ""}`;
        },
      ]),
    ];
    document.getElementById("locCompareBody").innerHTML = rows
      .map(([lbl, fn]) => `<tr><td style="font-weight:600;">${lbl}</td>${pinnedLocations.map((l) => `<td>${fn(l)}</td>`).join("")}</tr>`)
      .join("");
  }

  // Save Favorite Location
  const saveFavBtn = document.getElementById("saveFavLocBtn");
  if (saveFavBtn) {
    saveFavBtn.addEventListener("click", async () => {
      try {
        await EstateIQ.apiFetch("/api/locations/favorite", {
          method: "POST",
          body: JSON.stringify({
            location_name: currentState.name,
            display_name: currentState.display_name,
            latitude: currentState.lat,
            longitude: currentState.lon,
            amenities_summary: currentState.nearby ? currentState.nearby.counts : {},
            weather: currentState.weather || {},
          }),
        });
        EstateIQ.showToast(`Bookmarked '${currentState.name}' to your dashboard.`, "success");
      } catch (err) {
        EstateIQ.showToast(err.message, "error");
      }
    });
  }

  // Support URL query params ?lat=...&lon=...&name=...
  const params = new URLSearchParams(window.location.search);
  if (params.get("lat") && params.get("lon")) {
    inspectCoordinates(params.get("lat"), params.get("lon"), params.get("name") || "Saved Location");
  } else {
    inspectCoordinates(currentState.lat, currentState.lon, currentState.display_name);
  }
})();
