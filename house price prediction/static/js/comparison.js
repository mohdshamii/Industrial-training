(function () {
  const slotsGrid = document.getElementById("compareSlotsGrid");
  const addSlotBtn = document.getElementById("addSlotBtn");
  const runCompareBtn = document.getElementById("runCompareBtn");
  if (!slotsGrid) return;

  const savedPreds = JSON.parse(document.getElementById("savedPredsData").textContent || "[]");
  const schema = JSON.parse(document.getElementById("schemaData").textContent || "{}");

  let priceChart = null;
  let radarChart = null;
  let slotCounter = 0;

  const PRESETS = [
    { title: "Modern 2-Story Detached", location_name: "Whitefield, Bengaluru", MSSubClass: 60, LotArea: 10500, TotalBsmtSF: 1350, BsmtFinSF2: 0, YearBuilt: 2008, YearRemodAdd: 2010, OverallCond: 7, BldgType: "1Fam", MSZoning: "RL", LotConfig: "Corner", Exterior1st: "VinylSd", monthly_rent: 55000 },
    { title: "Classic Family Bungalow", location_name: "Indiranagar, Bengaluru", MSSubClass: 20, LotArea: 8400, TotalBsmtSF: 1020, BsmtFinSF2: 0, YearBuilt: 1986, YearRemodAdd: 2002, OverallCond: 6, BldgType: "1Fam", MSZoning: "RL", LotConfig: "Inside", Exterior1st: "BrkFace", monthly_rent: 48000 },
    { title: "End-Unit Townhouse", location_name: "HSR Layout, Bengaluru", MSSubClass: 120, LotArea: 5200, TotalBsmtSF: 1240, BsmtFinSF2: 200, YearBuilt: 2005, YearRemodAdd: 2005, OverallCond: 6, BldgType: "TwnhsE", MSZoning: "FV", LotConfig: "CulDSac", Exterior1st: "CemntBd", monthly_rent: 52000 },
    { title: "Compact Residential Duplex", location_name: "Baner, Pune", MSSubClass: 90, LotArea: 7600, TotalBsmtSF: 900, BsmtFinSF2: 0, YearBuilt: 1995, YearRemodAdd: 1998, OverallCond: 5, BldgType: "Duplex", MSZoning: "RM", LotConfig: "Inside", Exterior1st: "MetalSd", monthly_rent: 42000 },
  ];

  function buildOptionTags(options, selected) {
    return (options || [])
      .map((o) => `<option value="${EstateIQ.escapeHtml(o.value)}" ${String(o.value) === String(selected) ? "selected" : ""}>${EstateIQ.escapeHtml(o.label)}</option>`)
      .join("");
  }

  function addSlot(preset) {
    const existing = slotsGrid.querySelectorAll(".compare-slot").length;
    if (existing >= 4) {
      EstateIQ.showToast("Maximum of 4 properties can be compared simultaneously.", "info");
      return;
    }
    const idx = slotCounter++;
    const p = preset || PRESETS[existing % PRESETS.length];
    const bldgOpts = schema.categorical_features.find((f) => f.name === "BldgType")?.options || [];
    const zoneOpts = schema.categorical_features.find((f) => f.name === "MSZoning")?.options || [];
    const lotOpts = schema.categorical_features.find((f) => f.name === "LotConfig")?.options || [];
    const extOpts = schema.categorical_features.find((f) => f.name === "Exterior1st")?.options || [];

    const savedSelect = savedPreds.length
      ? `<div class="form-group full">
           <label class="form-label">Load Saved Valuation (Optional)</label>
           <select class="form-select slot-saved-select">
             <option value="">-- Custom Specifications Below --</option>
             ${savedPreds.map((sp) => `<option value="${sp.id}">${EstateIQ.escapeHtml(sp.property_title)} (${EstateIQ.formatINR(sp.predicted_price_inr, true)})</option>`).join("")}
           </select>
         </div>`
      : "";

    const card = document.createElement("div");
    card.className = "compare-slot";
    card.style.cssText = "background:var(--bg-surface-2);border:1px solid var(--border-subtle);border-radius:14px;padding:16px;";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <span class="badge badge-indigo">Property #${existing + 1}</span>
        <button type="button" class="btn btn-ghost btn-sm remove-slot-btn">Remove</button>
      </div>
      <div class="form-grid">
        ${savedSelect}
        <div class="form-group"><label class="form-label">Title</label><input type="text" class="form-control f-title" value="${EstateIQ.escapeHtml(p.title)}" /></div>
        <div class="form-group"><label class="form-label">Location</label><input type="text" class="form-control f-loc" value="${EstateIQ.escapeHtml(p.location_name)}" /></div>
        <div class="form-group"><label class="form-label">Lot Area (sq ft)</label><input type="number" class="form-control mono f-lot" value="${p.LotArea}" min="500" /></div>
        <div class="form-group"><label class="form-label">Basement Area (sq ft)</label><input type="number" class="form-control mono f-bsmt" value="${p.TotalBsmtSF}" min="0" /></div>
        <div class="form-group"><label class="form-label">Year Built</label><input type="number" class="form-control mono f-year" value="${p.YearBuilt}" min="1872" max="2026" /></div>
        <div class="form-group"><label class="form-label">Condition (1-9)</label><input type="number" class="form-control mono f-cond" value="${p.OverallCond}" min="1" max="9" /></div>
        <div class="form-group"><label class="form-label">Building Type</label><select class="form-select f-bldg">${buildOptionTags(bldgOpts, p.BldgType)}</select></div>
        <div class="form-group"><label class="form-label">Zoning</label><select class="form-select f-zone">${buildOptionTags(zoneOpts, p.MSZoning)}</select></div>
        <div class="form-group"><label class="form-label">Lot Config</label><select class="form-select f-lotcfg">${buildOptionTags(lotOpts, p.LotConfig)}</select></div>
        <div class="form-group"><label class="form-label">Exterior</label><select class="form-select f-ext">${buildOptionTags(extOpts, p.Exterior1st)}</select></div>
        <div class="form-group full"><label class="form-label">Expected Monthly Rent INR (Optional, for Yield)</label><input type="number" class="form-control mono f-rent" value="${p.monthly_rent || ""}" placeholder="Leave blank if rental data unavailable" /></div>
      </div>`;

    card.querySelector(".remove-slot-btn").addEventListener("click", () => {
      if (slotsGrid.querySelectorAll(".compare-slot").length <= 2) {
        EstateIQ.showToast("At least 2 properties are required for comparison.", "info");
        return;
      }
      card.remove();
      renumberSlots();
    });

    const sel = card.querySelector(".slot-saved-select");
    if (sel) {
      sel.addEventListener("change", () => {
        const found = savedPreds.find((x) => String(x.id) === sel.value);
        if (!found) return;
        card.querySelector(".f-title").value = found.property_title;
        card.querySelector(".f-loc").value = found.location_name || "";
        card.querySelector(".f-lot").value = found.lot_area;
        card.querySelector(".f-bsmt").value = found.total_bsmt_sf;
        card.querySelector(".f-year").value = found.year_built;
        card.querySelector(".f-cond").value = found.overall_cond;
        card.querySelector(".f-bldg").value = found.bldg_type;
        card.querySelector(".f-zone").value = found.ms_zoning;
      });
    }

    slotsGrid.appendChild(card);
    renumberSlots();
  }

  function renumberSlots() {
    slotsGrid.querySelectorAll(".compare-slot").forEach((el, i) => {
      el.querySelector(".badge").textContent = `Property #${i + 1}`;
    });
  }

  async function runCompare() {
    const slots = Array.from(slotsGrid.querySelectorAll(".compare-slot"));
    const payload = slots.map((s) => ({
      title: s.querySelector(".f-title").value.trim() || "Property",
      location_name: s.querySelector(".f-loc").value.trim(),
      MSSubClass: 60,
      LotArea: Number(s.querySelector(".f-lot").value),
      TotalBsmtSF: Number(s.querySelector(".f-bsmt").value),
      BsmtFinSF2: 0,
      YearBuilt: Number(s.querySelector(".f-year").value),
      YearRemodAdd: Math.max(1950, Number(s.querySelector(".f-year").value)),
      OverallCond: Number(s.querySelector(".f-cond").value),
      BldgType: s.querySelector(".f-bldg").value,
      MSZoning: s.querySelector(".f-zone").value,
      LotConfig: s.querySelector(".f-lotcfg").value,
      Exterior1st: s.querySelector(".f-ext").value,
      monthly_rent: s.querySelector(".f-rent").value,
    }));

    runCompareBtn.disabled = true;
    runCompareBtn.innerHTML = '<span class="spinner"></span> Comparing...';
    try {
      const res = await EstateIQ.apiFetch("/api/properties/compare", {
        method: "POST",
        body: JSON.stringify({ properties: payload }),
      });
      renderComparison(res);
      EstateIQ.showToast(`Compared ${res.properties.length} properties successfully.`, "success");
    } catch (err) {
      EstateIQ.showToast(err.message, "error");
    } finally {
      runCompareBtn.disabled = false;
      runCompareBtn.innerHTML =
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Compare Now';
    }
  }

  function renderComparison(res) {
    document.getElementById("compareResultsSection").style.display = "block";
    document.getElementById("hlBestValue").textContent = res.highlights.lowest_price_per_sqft;
    document.getElementById("hlBestSuit").textContent = res.highlights.highest_structural_score;
    document.getElementById("compareMethodNote").textContent = res.highlights.methodology_note;

    const props = res.properties;
    const head = document.getElementById("compareMatrixHead");
    head.innerHTML = `<th>Metric</th>${props.map((p) => `<th>${EstateIQ.escapeHtml(p.title)}</th>`).join("")}`;

    const rows = [
      ["Location", (p) => EstateIQ.escapeHtml(p.location_name)],
      ["Estimated Value (INR)", (p) => `<strong class="mono" style="color:var(--accent-emerald);">${EstateIQ.formatINR(p.predicted_price_inr, true)}</strong>`],
      ["Native ML Output (USD)", (p) => `<span class="mono">${EstateIQ.formatUSD(p.predicted_price_usd)}</span>`],
      ["10-Tree Ensemble Range", (p) => `<span class="mono">${EstateIQ.formatINR(p.ensemble_min_inr, true)} - ${EstateIQ.formatINR(p.ensemble_max_inr, true)}</span>`],
      ["Price / Sq Ft (Lot)", (p) => `<span class="mono">${EstateIQ.formatINR(p.price_per_sqft_lot_inr, false)}</span>`],
      ["Lot Area", (p) => `<span class="mono">${Number(p.lot_area).toLocaleString()} sq ft</span>`],
      ["Basement Footprint", (p) => `<span class="mono">${Number(p.total_bsmt_sf).toLocaleString()} sq ft</span>`],
      ["Building / Zoning", (p) => `${EstateIQ.escapeHtml(p.bldg_type)} / ${EstateIQ.escapeHtml(p.ms_zoning)}`],
      ["Year Built / Condition", (p) => `<span class="mono">${p.year_built} &middot; ${p.overall_cond}/9</span>`],
      ["Est. Monthly EMI (20% down, 8.5%)", (p) => `<span class="mono">${EstateIQ.formatINR(p.monthly_emi_inr, false)}/mo</span>`],
      ["Gross / Net Rental Yield", (p) => (p.rental_yield ? `<span class="mono">${p.rental_yield.gross_yield_pct}% / ${p.rental_yield.net_yield_pct}%</span>` : "<span style='color:var(--text-muted);'>Not entered</span>")],
      ["Structural Suitability Score", (p) => `<span class="badge badge-indigo mono">${p.suitability_score} / 100</span>`],
    ];

    document.getElementById("compareMatrixBody").innerHTML = rows
      .map(([label, fn]) => `<tr><td style="font-weight:600;color:var(--text-secondary);">${label}</td>${props.map((p) => `<td>${fn(p)}</td>`).join("")}</tr>`)
      .join("");

    // Render Charts (Strict Black, White, Blue & Baby Pink Palette)
    const c = EstateIQ.getChartColors();
    const palette = ["rgba(37,99,235,0.86)", "rgba(244,184,208,0.92)", "rgba(96,165,250,0.86)", "rgba(212,107,153,0.86)"];

    if (priceChart) priceChart.destroy();
    priceChart = new Chart(document.getElementById("comparePriceChart").getContext("2d"), {
      type: "bar",
      data: {
        labels: props.map((p) => p.title),
        datasets: [
          { label: "Estimated Price (INR)", data: props.map((p) => p.predicted_price_inr), backgroundColor: palette.slice(0, props.length), borderRadius: 8 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { grid: { color: c.grid }, ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) } },
          x: { grid: { display: false }, ticks: { color: c.text } },
        },
      },
    });

    if (radarChart) radarChart.destroy();
    const maxLot = Math.max(...props.map((p) => p.lot_area), 1);
    const maxBsmt = Math.max(...props.map((p) => p.total_bsmt_sf), 1);
    radarChart = new Chart(document.getElementById("compareRadarChart").getContext("2d"), {
      type: "radar",
      data: {
        labels: ["Condition", "Modernity", "Lot Size", "Basement Area", "Tree Agreement", "Suitability"],
        datasets: props.map((p, i) => ({
          label: p.title,
          data: [
            Math.round((p.overall_cond / 9) * 100),
            Math.round(Math.max(0, Math.min(100, ((p.year_built - 1940) / 80) * 100))),
            Math.round((p.lot_area / maxLot) * 100),
            Math.round((p.total_bsmt_sf / maxBsmt) * 100),
            Math.round(Math.max(10, 100 - p.ensemble_cv_pct * 2.5)),
            p.suitability_score,
          ],
          borderColor: palette[i].replace("0.86", "1"),
          backgroundColor: palette[i].replace("0.86", "0.18"),
          borderWidth: 2,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            min: 0,
            max: 100,
            grid: { color: c.grid },
            angleLines: { color: c.grid },
            pointLabels: { color: c.text, font: { size: 11 } },
            ticks: { display: false },
          },
        },
        plugins: { legend: { labels: { color: c.text } } },
      },
    });
  }

  addSlotBtn.addEventListener("click", () => addSlot());
  runCompareBtn.addEventListener("click", runCompare);

  // Initialize with 2 default slots & run an immediate comparison
  addSlot(PRESETS[0]);
  addSlot(PRESETS[1]);
  runCompare();
})();
