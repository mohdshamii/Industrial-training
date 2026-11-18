/* ==========================================================================
   EstateIQ AI — Global Engine (Theme, Spotlight, Scroll Reveals, Navbar, API)
   ========================================================================== */

window.EstateIQ = (function () {
  function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  async function apiFetch(url, options = {}) {
    const headers = Object.assign(
      { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      options.headers || {}
    );
    const resp = await fetch(url, Object.assign({}, options, { headers }));
    let data = {};
    try {
      data = await resp.json();
    } catch (_) {
      data = { error: "Unexpected server response." };
    }
    if (!resp.ok) {
      throw new Error(data.error || `Request failed (${resp.status})`);
    }
    return data;
  }

  function formatINR(val, compact = true) {
    if (val === null || val === undefined || isNaN(val)) return "INR 0";
    const num = Number(val);
    const abs = Math.abs(num);
    const sign = num < 0 ? "-" : "";
    if (compact) {
      if (abs >= 1e7) return `${sign}INR ${(abs / 1e7).toFixed(2)} Cr`;
      if (abs >= 1e5) return `${sign}INR ${(abs / 1e5).toFixed(2)} L`;
    }
    return `${sign}INR ${Math.round(abs).toLocaleString("en-IN")}`;
  }

  function formatUSD(val) {
    if (val === null || val === undefined || isNaN(val)) return "$0";
    return "$" + Math.round(Number(val)).toLocaleString("en-US");
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderSimpleMarkdown(text) {
    const escaped = escapeHtml(text);
    return escaped
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/`(.+?)`/g, "<code class='mono' style='background:var(--bg-hover);padding:2px 5px;border-radius:4px;'>$1</code>")
      .replace(/\n- /g, "<br>&bull; ")
      .replace(/\n/g, "<br>");
  }

  function showToast(message, type = "info") {
    const stack = document.getElementById("toastStack");
    if (!stack) return;
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${escapeHtml(message)}</span>`;
    stack.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateY(6px)";
      el.style.transition = "all 0.2s ease";
      setTimeout(() => el.remove(), 220);
    }, 3600);
  }

  function getChartColors() {
    const styles = getComputedStyle(document.documentElement);
    const isLight = (document.documentElement.getAttribute("data-theme") || "dark") === "light";
    return {
      grid: styles.getPropertyValue("--chart-grid").trim() || "rgba(255,255,255,0.1)",
      text: styles.getPropertyValue("--chart-text").trim() || "#d4dcee",
      pink: isLight ? "#d46b99" : "#f4b8d0",
      pinkLight: "#f8c8dc",
      blue: "#2563eb",
      blueLight: "#60a5fa",
      blueDeep: "#1e3a8a",
      monoContrast: isLight ? "#090b10" : "#ffffff",
      neutral: isLight ? "#4b5563" : "#9ca3af",
    };
  }

  function setTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("estateiq-theme", theme);
    const sun = document.getElementById("themeIconSun");
    const moon = document.getElementById("themeIconMoon");
    if (sun && moon) {
      sun.style.display = theme === "dark" ? "block" : "none";
      moon.style.display = theme === "light" ? "block" : "none";
    }
    window.dispatchEvent(new CustomEvent("estateiq:themechange", { detail: { theme } }));
  }

  function initSpotlightCards() {
    document.addEventListener("pointermove", (e) => {
      const card = e.target.closest(".card, .kpi-card");
      if (!card) return;
      const rect = card.getBoundingClientRect();
      card.style.setProperty("--mx", `${e.clientX - rect.left}px`);
      card.style.setProperty("--my", `${e.clientY - rect.top}px`);
    });
  }

  function initScrollRevealsAndCounters() {
    const reveals = document.querySelectorAll(".reveal");
    if (!reveals.length) return;
    const revealEl = (el) => {
      el.classList.add("visible");
      el.querySelectorAll("[data-countup]").forEach(animateCounter);
    };
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          revealEl(entry.target);
          io.unobserve(entry.target);
        });
      },
      { threshold: 0.01, rootMargin: "0px 0px -20px 0px" }
    );
    reveals.forEach((el) => io.observe(el));
    // Safety fallback so tall sections never remain invisible
    setTimeout(() => reveals.forEach(revealEl), 900);
  }

  function animateCounter(el) {
    if (el.dataset.counted) return;
    el.dataset.counted = "1";
    const target = parseFloat(el.dataset.countup);
    if (isNaN(target)) return;
    const suffix = el.dataset.suffix || "";
    const decimals = Number(el.dataset.decimals || 0);
    const duration = 900;
    const start = performance.now();
    function tick(now) {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      const val = target * eased;
      el.textContent = (decimals > 0 ? val.toFixed(decimals) : Math.round(val).toLocaleString()) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  function initGlobalUI() {
    const saved = localStorage.getItem("estateiq-theme") || "dark";
    setTheme(saved);

    const toggleBtn = document.getElementById("themeToggleBtn");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const curr = document.documentElement.getAttribute("data-theme") || "dark";
        setTheme(curr === "dark" ? "light" : "dark");
      });
    }

    // Floating navbar scroll accent
    const navWrap = document.getElementById("siteNavbarWrap");
    if (navWrap) {
      window.addEventListener(
        "scroll",
        () => {
          navWrap.classList.toggle("scrolled", window.scrollY > 18);
        },
        { passive: true }
      );
    }

    // Account dropdown
    const accBtn = document.getElementById("accountDropdownBtn");
    const accMenu = document.getElementById("accountDropdownMenu");
    if (accBtn && accMenu) {
      accBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        accMenu.classList.toggle("open");
      });
      document.addEventListener("click", () => accMenu.classList.remove("open"));
    }

    // Mobile Sidebar Drawer
    const menuBtn = document.getElementById("mobileMenuBtn");
    const sidebar = document.getElementById("appSidebar");
    const backdrop = document.getElementById("sidebarBackdrop");
    if (menuBtn && sidebar && backdrop) {
      const closeMenu = () => {
        sidebar.classList.remove("open");
        backdrop.classList.remove("open");
      };
      menuBtn.addEventListener("click", () => {
        sidebar.classList.toggle("open");
        backdrop.classList.toggle("open");
      });
      backdrop.addEventListener("click", closeMenu);
    }

    initSpotlightCards();
    initScrollRevealsAndCounters();

    // Hydrate navbar live FX badge
    const fxEl = document.getElementById("topbarFxText");
    if (fxEl) {
      fetch("/api/market/fx")
        .then((r) => r.json())
        .then((d) => {
          if (d && d.rate) {
            fxEl.textContent = `1 USD = ${Number(d.rate).toFixed(2)} INR${d.is_live ? "" : " (Fallback)"}`;
          }
        })
        .catch(() => {});
    }
  }

  document.addEventListener("DOMContentLoaded", initGlobalUI);

  return {
    apiFetch,
    formatINR,
    formatUSD,
    escapeHtml,
    renderSimpleMarkdown,
    showToast,
    getChartColors,
    setTheme,
  };
})();
