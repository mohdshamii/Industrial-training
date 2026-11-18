(function () {
  const charts = {};
  function makeOrReplaceChart(key, canvasId, config) {
    if (charts[key]) charts[key].destroy();
    const ctx = document.getElementById(canvasId).getContext("2d");
    charts[key] = new Chart(ctx, config);
  }

  function formToObj(form) {
    const o = {};
    for (const [k, v] of new FormData(form).entries()) o[k] = Number(v);
    return o;
  }

  function kpiHtml(label, value, accent = "") {
    return `<div style="background:var(--bg-surface-2);border:1px solid var(--border-subtle);border-radius:12px;padding:12px;">
      <div class="kpi-label">${label}</div>
      <div class="mono" style="font-size:1.08rem;font-weight:700;margin-top:4px;${accent ? "color:" + accent + ";" : ""}">${value}</div>
    </div>`;
  }

  // Tab switching (ensure Chart.js resizes cleanly when un-hiding a tab)
  document.querySelectorAll("#calcTabBar .tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#calcTabBar .tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".calc-pane").forEach((p) => (p.style.display = "none"));
      const tab = btn.dataset.tab;
      document.getElementById(`pane-${tab}`).style.display = "block";
      requestAnimationFrame(() => {
        if (tab === "emi" && charts.emi) charts.emi.resize();
        if (tab === "yield" && charts.yield) charts.yield.resize();
        if (tab === "bvr" && charts.bvr) charts.bvr.resize();
        if (tab === "appreciation" && charts.app) charts.app.resize();
      });
    });
  });

  // 1. EMI
  async function runEmi(e) {
    if (e) e.preventDefault();
    const d = await EstateIQ.apiFetch("/api/analytics/emi", { method: "POST", body: JSON.stringify(formToObj(document.getElementById("emiForm"))) });
    document.getElementById("emiKpis").innerHTML =
      kpiHtml("Monthly EMI", EstateIQ.formatINR(d.monthly_emi, false), "var(--accent-emerald)") +
      kpiHtml("Upfront Cash Needed", EstateIQ.formatINR(d.upfront_cash_needed, true)) +
      kpiHtml("Total Interest", EstateIQ.formatINR(d.total_interest, true), "var(--accent-amber)");
    const c = EstateIQ.getChartColors();
    makeOrReplaceChart("emi", "emiChart", {
      type: "bar",
      data: {
        labels: d.schedule.map((s) => `Yr ${s.year}`),
        datasets: [
          { label: "Principal Paid", data: d.schedule.map((s) => s.principal_paid), backgroundColor: "rgba(37,99,235,0.88)" },
          { label: "Interest Paid", data: d.schedule.map((s) => s.interest_paid), backgroundColor: "rgba(244,184,208,0.9)" },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { stacked: true, grid: { display: false }, ticks: { color: c.text } },
          y: { stacked: true, grid: { color: c.grid }, ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) } },
        },
        plugins: { legend: { labels: { color: c.text } } },
      },
    });
  }

  // 2. Rental Yield
  async function runYield(e) {
    if (e) e.preventDefault();
    const d = await EstateIQ.apiFetch("/api/analytics/rental-yield", { method: "POST", body: JSON.stringify(formToObj(document.getElementById("yieldForm"))) });
    document.getElementById("yieldKpis").innerHTML =
      kpiHtml("Gross Yield", `${d.gross_yield_pct}%`, "var(--accent-emerald)") +
      kpiHtml("Net Yield", `${d.net_yield_pct}%`, "var(--accent-cyan)") +
      kpiHtml("Payback Period", d.payback_years ? `${d.payback_years} yrs` : "N/A");
    const c = EstateIQ.getChartColors();
    makeOrReplaceChart("yield", "yieldChart", {
      type: "doughnut",
      data: {
        labels: ["Net Annual Rental Income", "Vacancy Loss", "Annual Expenses"],
        datasets: [{ data: [Math.max(d.net_annual_income, 0), Math.max(d.gross_annual_rent - d.effective_annual_rent, 0), d.annual_expenses], backgroundColor: ["#f4b8d0", "#2563eb", c.monoContrast], borderWidth: 0 }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { color: c.text } } } },
    });
  }

  // 3. ROI
  async function runRoi(e) {
    if (e) e.preventDefault();
    const d = await EstateIQ.apiFetch("/api/analytics/roi", { method: "POST", body: JSON.stringify(formToObj(document.getElementById("roiForm"))) });
    document.getElementById("roiKpis").innerHTML =
      kpiHtml("Total Leveraged ROI", `${d.total_roi_pct}%`, d.total_roi_pct >= 0 ? "var(--accent-emerald)" : "var(--accent-rose)") +
      kpiHtml("Annualized Equity CAGR", `${d.annualized_roi_cagr_pct}%`, "var(--accent-indigo)") +
      kpiHtml(`Projected Value (Yr ${d.holding_years})`, EstateIQ.formatINR(d.projected_property_value, true)) +
      kpiHtml("Projected Net Profit", EstateIQ.formatINR(d.total_net_profit, true)) +
      kpiHtml("Initial Cash Invested", EstateIQ.formatINR(d.initial_cash_invested, true)) +
      kpiHtml("Year-1 Cash-on-Cash", `${d.year1_cash_on_cash_pct}%`);
  }

  // 4. Affordability
  async function runAfford(e) {
    if (e) e.preventDefault();
    const d = await EstateIQ.apiFetch("/api/analytics/affordability", { method: "POST", body: JSON.stringify(formToObj(document.getElementById("affordForm"))) });
    document.getElementById("affordKpis").innerHTML =
      kpiHtml("Max Property Budget", EstateIQ.formatINR(d.max_property_budget, true), "var(--accent-emerald)") +
      kpiHtml("Conservative Safe Budget", EstateIQ.formatINR(d.conservative_property_budget, true), "var(--accent-cyan)") +
      kpiHtml("Max Eligible Home Loan", EstateIQ.formatINR(d.max_eligible_loan, true)) +
      kpiHtml("Max Affordable Monthly EMI", EstateIQ.formatINR(d.max_affordable_emi, false));
  }

  // 5. Buy vs Rent
  async function runBvr(e) {
    if (e) e.preventDefault();
    const d = await EstateIQ.apiFetch("/api/analytics/buy-vs-rent", { method: "POST", body: JSON.stringify(formToObj(document.getElementById("bvrForm"))) });
    document.getElementById("bvrBanner").innerHTML = `<strong>${EstateIQ.escapeHtml(d.recommendation)}</strong> by <span class="mono">${EstateIQ.formatINR(d.net_wealth_difference, true)}</span> over ${d.horizon_years} years (Break-even: ${d.breakeven_year ? "Year " + d.breakeven_year : "Beyond horizon"}).`;
    const c = EstateIQ.getChartColors();
    makeOrReplaceChart("bvr", "bvrChart", {
      type: "line",
      data: {
        labels: d.timeline.map((t) => `Yr ${t.year}`),
        datasets: [
          { label: "Buyer Net Worth", data: d.timeline.map((t) => t.buyer_net_worth), borderColor: "#f4b8d0", backgroundColor: "rgba(244,184,208,0.18)", fill: true, tension: 0.3 },
          { label: "Renter + Investor Net Worth", data: d.timeline.map((t) => t.renter_net_worth), borderColor: "#2563eb", backgroundColor: "rgba(37,99,235,0.16)", fill: true, tension: 0.3 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false }, ticks: { color: c.text } },
          y: { grid: { color: c.grid }, ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) } },
        },
        plugins: { legend: { labels: { color: c.text } } },
      },
    });
  }

  // 6. Appreciation Scenarios
  async function runApp(e) {
    if (e) e.preventDefault();
    const d = await EstateIQ.apiFetch("/api/analytics/appreciation", { method: "POST", body: JSON.stringify(formToObj(document.getElementById("appForm"))) });
    const fv = d.final_values;
    document.getElementById("appKpis").innerHTML =
      kpiHtml(`Conservative (${d.rates.conservative_pct}%)`, EstateIQ.formatINR(fv.conservative, true)) +
      kpiHtml(`Moderate (${d.rates.moderate_pct}%)`, EstateIQ.formatINR(fv.moderate, true), "var(--accent-cyan)") +
      kpiHtml(`Optimistic (${d.rates.optimistic_pct}%)`, EstateIQ.formatINR(fv.optimistic, true), "var(--accent-emerald)");
    const c = EstateIQ.getChartColors();
    makeOrReplaceChart("app", "appChart", {
      type: "line",
      data: {
        labels: d.series.map((s) => `Yr ${s.year}`),
        datasets: [
          { label: "Conservative", data: d.series.map((s) => s.conservative), borderColor: c.monoContrast, borderDash: [5, 5], tension: 0.3 },
          { label: "Moderate", data: d.series.map((s) => s.moderate), borderColor: "#2563eb", tension: 0.3 },
          { label: "Optimistic", data: d.series.map((s) => s.optimistic), borderColor: "#f4b8d0", tension: 0.3 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false }, ticks: { color: c.text } },
          y: { grid: { color: c.grid }, ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) } },
        },
        plugins: { legend: { labels: { color: c.text } } },
      },
    });
  }

  // Historical Dataset Insights Charts
  async function loadDatasetCharts() {
    const ds = await EstateIQ.apiFetch("/api/market/dataset-insights", { method: "GET" });
    const rate = ds.fx ? ds.fx.rate : 84.5;
    const c = EstateIQ.getChartColors();

    makeOrReplaceChart("dsHist", "dsHistChart", {
      type: "bar",
      data: {
        labels: ds.histogram.map((b) => b.range_label),
        datasets: [{ label: "Sales Count", data: ds.histogram.map((b) => b.count), backgroundColor: "rgba(37,99,235,0.82)", borderRadius: 6 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { display: false }, ticks: { color: c.text, font: { size: 10 } } }, y: { grid: { color: c.grid }, ticks: { color: c.text } } },
      },
    });

    makeOrReplaceChart("dsDecade", "dsDecadeChart", {
      type: "line",
      data: {
        labels: ds.by_decade.map((x) => x.decade),
        datasets: [{ label: "Median Price (INR)", data: ds.by_decade.map((x) => Math.round(x.median_usd * rate)), borderColor: "#f4b8d0", backgroundColor: "rgba(244,184,208,0.18)", fill: true, tension: 0.3 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { display: false }, ticks: { color: c.text } }, y: { grid: { color: c.grid }, ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) } } },
      },
    });

    makeOrReplaceChart("dsBldg", "dsBldgChart", {
      type: "bar",
      data: {
        labels: ds.by_bldg_type.map((x) => x.label),
        datasets: [{ label: "Median Price (INR)", data: ds.by_bldg_type.map((x) => Math.round(x.median_usd * rate)), backgroundColor: "rgba(37,99,235,0.82)", borderRadius: 6 }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { color: c.grid }, ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) } }, y: { grid: { display: false }, ticks: { color: c.text } } },
      },
    });

    makeOrReplaceChart("dsZone", "dsZoneChart", {
      type: "bar",
      data: {
        labels: ds.by_zoning.map((x) => x.label),
        datasets: [{ label: "Median Price (INR)", data: ds.by_zoning.map((x) => Math.round(x.median_usd * rate)), backgroundColor: "rgba(244,184,208,0.9)", borderRadius: 6 }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { x: { grid: { color: c.grid }, ticks: { color: c.text, callback: (v) => EstateIQ.formatINR(v, true) } }, y: { grid: { display: false }, ticks: { color: c.text } } },
      },
    });
  }

  document.getElementById("emiForm").addEventListener("submit", runEmi);
  document.getElementById("yieldForm").addEventListener("submit", runYield);
  document.getElementById("roiForm").addEventListener("submit", runRoi);
  document.getElementById("affordForm").addEventListener("submit", runAfford);
  document.getElementById("bvrForm").addEventListener("submit", runBvr);
  document.getElementById("appForm").addEventListener("submit", runApp);

  // Run initial calculations & dataset charts on load
  runEmi();
  runYield();
  runRoi();
  runAfford();
  runBvr();
  runApp();
  loadDatasetCharts();
})();
