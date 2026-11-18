(function () {
  let factorsChart = null;
  let treesChart = null;
  let latestPredictionId = null;
  let attachedAmenities = null;

  const form = document.getElementById("predictionForm");
  const submitBtn = document.getElementById("predictSubmitBtn");
  const geoLookupBtn = document.getElementById("geoLookupBtn");
  const geoInput = document.getElementById("location_search");
  const geoSuggestions = document.getElementById("geoSuggestions");
  const saveBtn = document.getElementById("savePropertyBtn");

  if (!form) return;

  // Geocode lookup for optional location tagging + nearby amenity snapshot
  if (geoLookupBtn) {
    geoLookupBtn.addEventListener("click", async () => {
      const q = geoInput.value.trim();
      if (q.length < 2) {
        EstateIQ.showToast("Enter at least 2 characters to search a location.", "error");
        return;
      }
      geoLookupBtn.disabled = true;
      geoLookupBtn.innerHTML = '<span class="spinner"></span>';
      try {
        const data = await EstateIQ.apiFetch(`/api/geocode?q=${encodeURIComponent(q)}&limit=4`, { method: "GET" });
        if (!data.results || !data.results.length) {
          EstateIQ.showToast(data.error || "No matching locations found.", "error");
          geoSuggestions.style.display = "none";
          return;
        }
        geoSuggestions.innerHTML = data.results
          .map(
            (r, i) => `
          <button type="button" class="geo-pick-btn" data-idx="${i}" style="width:100%;text-align:left;padding:9px 12px;border:none;border-bottom:1px solid var(--border-subtle);background:transparent;color:var(--text-primary);cursor:pointer;font-size:0.8rem;">
            <strong>${EstateIQ.escapeHtml(r.name)}</strong>
            <div style="font-size:0.72rem;color:var(--text-muted);">${EstateIQ.escapeHtml(r.display_name)}</div>
          </button>`
          )
          .join("");
        geoSuggestions.style.display = "block";
        geoSuggestions.querySelectorAll(".geo-pick-btn").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const picked = data.results[Number(btn.dataset.idx)];
            geoInput.value = picked.display_name;
            document.getElementById("predLat").value = picked.lat;
            document.getElementById("predLon").value = picked.lon;
            geoSuggestions.style.display = "none";
            const badge = document.getElementById("locationTagStatus");
            badge.style.display = "inline-flex";
            badge.className = "badge badge-emerald";
            badge.textContent = "Coordinates Tagged";
            EstateIQ.showToast("Location tagged. Scanning nearby facilities...", "info");
            try {
              const near = await EstateIQ.apiFetch(`/api/nearby?lat=${picked.lat}&lon=${picked.lon}&radius=3000`, { method: "GET" });
              if (!near.error) {
                attachedAmenities = near;
                badge.textContent = `Tagged (${near.total_found} POIs)`;
                EstateIQ.showToast(`Attached ${near.total_found} nearby OSM facilities for your PDF report.`, "success");
              }
            } catch (_) {}
          });
        });
      } catch (err) {
        EstateIQ.showToast(err.message, "error");
      } finally {
        geoLookupBtn.disabled = false;
        geoLookupBtn.innerHTML =
          '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg> Locate';
      }
    });
  }

  function renderCharts(result) {
    const c = EstateIQ.getChartColors();
    const nonZero = (result.factors || []).filter((f) => Math.abs(f.delta_inr) >= 1000);
    const topFactors = (nonZero.length >= 3 ? nonZero : result.factors || []).slice(0, 7);

    if (factorsChart) factorsChart.destroy();
    const fCtx = document.getElementById("factorsChart").getContext("2d");
    factorsChart = new Chart(fCtx, {
      type: "bar",
      data: {
        labels: topFactors.map((f) => f.label.replace(/\s*\(.+?\)/g, "")),
        datasets: [
          {
            label: "Impact vs Baseline (INR)",
            data: topFactors.map((f) => f.delta_inr),
            backgroundColor: topFactors.map((f) => (f.delta_inr >= 0 ? "rgba(244,184,208,0.9)" : "rgba(37,99,235,0.85)")),
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            grid: { color: c.grid },
            ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) },
          },
          y: { grid: { display: false }, ticks: { color: c.text, font: { size: 11 } } },
        },
      },
    });

    const trees = result.ensemble_uncertainty.tree_predictions_inr || [];
    if (treesChart) treesChart.destroy();
    const tCtx = document.getElementById("treesChart").getContext("2d");
    treesChart = new Chart(tCtx, {
      type: "bar",
      data: {
        labels: trees.map((_, i) => `Tree ${i + 1}`),
        datasets: [
          {
            label: "Tree Estimate (INR)",
            data: trees,
            backgroundColor: "rgba(37,99,235,0.82)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: {
            grid: { color: c.grid },
            ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) },
          },
          x: { grid: { display: false }, ticks: { color: c.text, font: { size: 10 } } },
        },
      },
    });
  }

  function renderPredictionResult(res) {
    latestPredictionId = res.id;
    document.getElementById("emptyResultState").style.display = "none";
    document.getElementById("activeResultState").style.display = "block";

    document.getElementById("resInrValue").textContent = EstateIQ.formatINR(res.predicted_price_inr, false);
    document.getElementById("resUsdSub").textContent =
      `${EstateIQ.formatINR(res.predicted_price_inr, true)}  |  Native ML Output: ${EstateIQ.formatUSD(res.predicted_price_usd)}`;

    const fx = res.exchange_rate || {};
    document.getElementById("resFxNote").textContent = `FX: 1 USD = ${Number(fx.rate || 84.5).toFixed(2)} INR (${fx.source || "live"})`;

    const u = res.ensemble_uncertainty;
    const badge = document.getElementById("resAgreementBadge");
    badge.textContent = u.agreement_tier;
    badge.className = "badge " + (u.cv <= 0.12 ? "badge-emerald" : u.cv <= 0.25 ? "badge-amber" : "badge-rose");

    document.getElementById("resMinInr").textContent = EstateIQ.formatINR(u.min_inr, true);
    document.getElementById("resMaxInr").textContent = EstateIQ.formatINR(u.max_inr, true);
    document.getElementById("resUncertaintyNote").textContent = u.agreement_note;

    const span = Math.max(u.max_inr - u.min_inr, 1);
    const p25Pct = ((u.p25_inr - u.min_inr) / span) * 100;
    const p75Pct = ((u.p75_inr - u.min_inr) / span) * 100;
    const ptPct = ((res.predicted_price_inr - u.min_inr) / span) * 100;
    document.getElementById("rangeBarIqr").style.left = `${Math.max(0, p25Pct)}%`;
    document.getElementById("rangeBarIqr").style.width = `${Math.max(4, p75Pct - p25Pct)}%`;
    document.getElementById("rangeBarPoint").style.left = `${Math.min(98, Math.max(2, ptPct))}%`;

    document.getElementById("resPpsfLot").textContent = `${EstateIQ.formatINR(res.price_per_sqft_lot_inr, false)}/sq ft`;
    document.getElementById("resPercentile").textContent =
      res.dataset_benchmark && res.dataset_benchmark.dataset_percentile !== null
        ? `${res.dataset_benchmark.dataset_percentile}th pct`
        : "N/A";
    document.getElementById("resCv").textContent = `${u.cv_pct}%`;

    const pdfBtn = document.getElementById("downloadPdfBtn");
    pdfBtn.href = res.report_url || `/api/predictions/${res.id}/report.pdf`;

    if (saveBtn) {
      saveBtn.disabled = false;
      saveBtn.textContent = res.is_saved ? "Saved in Portfolio" : "Save to Portfolio";
    }

    renderCharts(res);
    prependHistoryRow(res);
  }

  function prependHistoryRow(res) {
    const tbody = document.getElementById("historyTableBody");
    const noRow = document.getElementById("noHistoryRow");
    if (noRow) noRow.remove();

    const tr = document.createElement("tr");
    tr.dataset.predId = res.id;
    tr.innerHTML = `
      <td>
        <div style="font-weight:600;">${EstateIQ.escapeHtml(res.property_title)}</div>
        <div style="font-size:0.74rem;color:var(--text-muted);">${EstateIQ.escapeHtml(res.location_name || res.input_features.MSZoning)}</div>
      </td>
      <td class="mono" style="font-weight:700;color:var(--accent-emerald);">${EstateIQ.formatINR(res.predicted_price_inr, true)}</td>
      <td style="font-size:0.78rem;color:var(--text-secondary);">Lot ${Number(res.input_features.LotArea).toLocaleString()} | Built ${res.input_features.YearBuilt}</td>
      <td>
        <div style="display:flex;gap:6px;">
          <a href="/api/predictions/${res.id}/report.pdf" class="btn btn-secondary btn-sm">PDF</a>
          <button type="button" class="btn btn-danger btn-sm delete-pred-btn" data-id="${res.id}">Delete</button>
        </div>
      </td>`;
    tbody.prepend(tr);
    bindDeleteButtons();
    const countBadge = document.getElementById("historyCountBadge");
    if (countBadge) countBadge.textContent = `${tbody.querySelectorAll("tr").length} records`;
  }

  async function runPrediction(e) {
    if (e) e.preventDefault();
    const fd = new FormData(form);
    const payload = {};
    for (const [k, v] of fd.entries()) {
      payload[k] = v;
    }
    if (attachedAmenities) payload.amenities = attachedAmenities;

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Computing Valuation...';
    try {
      const res = await EstateIQ.apiFetch("/api/predict", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      renderPredictionResult(res);
      EstateIQ.showToast("Valuation computed using preserved RandomForest model.", "success");
    } catch (err) {
      EstateIQ.showToast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg> Run AI Valuation';
    }
  }

  form.addEventListener("submit", runPrediction);

  const quickSampleBtn = document.getElementById("quickSampleBtn");
  if (quickSampleBtn) quickSampleBtn.addEventListener("click", () => runPrediction());

  const resetBtn = document.getElementById("resetPresetBtn");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      form.reset();
      document.getElementById("condDisplay").textContent = "6 / 9";
      document.getElementById("predLat").value = "";
      document.getElementById("predLon").value = "";
      attachedAmenities = null;
      const badge = document.getElementById("locationTagStatus");
      if (badge) badge.style.display = "none";
      EstateIQ.showToast("Form reset to baseline values.", "info");
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      if (!latestPredictionId) return;
      saveBtn.disabled = true;
      try {
        await EstateIQ.apiFetch(`/api/predictions/${latestPredictionId}/save`, {
          method: "POST",
          body: JSON.stringify({ notes: "Saved from Valuation Studio" }),
        });
        saveBtn.textContent = "Saved in Portfolio";
        EstateIQ.showToast("Property saved to your dashboard portfolio.", "success");
      } catch (err) {
        saveBtn.disabled = false;
        EstateIQ.showToast(err.message, "error");
      }
    });
  }

  function bindDeleteButtons() {
    document.querySelectorAll(".delete-pred-btn").forEach((btn) => {
      if (btn.dataset.bound) return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        try {
          await EstateIQ.apiFetch(`/api/predictions/${id}`, { method: "DELETE" });
          const row = document.querySelector(`tr[data-pred-id="${id}"]`);
          if (row) row.remove();
          EstateIQ.showToast("Valuation record deleted.", "info");
        } catch (err) {
          EstateIQ.showToast(err.message, "error");
        }
      });
    });
  }

  bindDeleteButtons();
})();
