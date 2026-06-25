(function () {
  const THEME_KEY = "narrative_theme";

  const PAGE_COPY = {
    dashboard: {
      eyebrow: "Command Center",
      title: "Executive Dashboard",
      subtitle: "Real-time visibility into narratives, sentiment, and emerging risk signals.",
    },
    monitoring: {
      eyebrow: "Collect & Detect",
      title: "Monitoring",
      subtitle: "Ingest mentions, scan sources, and track harmful narrative spread.",
    },
    intelligence: {
      eyebrow: "Understand & Prioritize",
      title: "Narrative Intelligence",
      subtitle: "Map narratives, identify influence networks, and analyze coordination patterns.",
    },
    response: {
      eyebrow: "Act",
      title: "Response Center",
      subtitle: "Plan counter-messaging, coordinate campaigns, and measure impact.",
    },
    reports: {
      eyebrow: "Measure",
      title: "Intelligence Reports",
      subtitle: "Export daily narrative intelligence for leadership and operations teams.",
    },
    profile: {
      eyebrow: "Account",
      title: "My Profile",
      subtitle: "Manage your account details, credentials, and access preferences.",
    },
    settings: {
      eyebrow: "Administration",
      title: "Settings",
      subtitle: "Configure platform connections, detection rules, users, and system controls.",
    },
  };

  function preferredTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  function updateToggleLabels(theme) {
    const label = theme === "light" ? "Dark mode" : "Light mode";
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.textContent = label;
      btn.setAttribute("aria-label", `Switch to ${theme === "light" ? "dark" : "light"} mode`);
    });
  }

  function applyTheme(theme) {
    const next = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
    updateToggleLabels(next);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme") || preferredTheme();
    applyTheme(current === "light" ? "dark" : "light");
  }

  function updatePageHero(page) {
    const copy = PAGE_COPY[page] || PAGE_COPY.dashboard;
    const eyebrow = document.getElementById("pageEyebrow");
    const title = document.getElementById("pageTitle");
    const subtitle = document.getElementById("pageSubtitle");
    if (eyebrow) eyebrow.textContent = copy.eyebrow;
    if (title) title.textContent = copy.title;
    if (subtitle) subtitle.textContent = copy.subtitle;
    document.title = `${copy.title} | Narrative`;
  }

  function closeSidebar() {
    document.body.classList.remove("sidebar-open");
  }

  function toggleSidebar() {
    document.body.classList.toggle("sidebar-open");
  }

  function initSidebar() {
    const toggle = document.getElementById("sidebarToggle");
    const backdrop = document.getElementById("sidebarBackdrop");
    const navLinks = document.querySelectorAll(".sidebar a[data-page]");

    if (toggle) toggle.addEventListener("click", toggleSidebar);
    if (backdrop) backdrop.addEventListener("click", closeSidebar);
    navLinks.forEach((link) => {
      link.addEventListener("click", () => {
        const page = link.dataset.page || "dashboard";
        updatePageHero(page);
        if (window.innerWidth <= 900) closeSidebar();
      });
    });
    window.addEventListener("resize", () => {
      if (window.innerWidth > 900) closeSidebar();
    });
  }

  window.NarrativeTheme = { updatePageHero };

  applyTheme(preferredTheme());

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.addEventListener("click", toggleTheme);
    });
    initSidebar();
    const hash = String(window.location.hash || "").replace("#", "").trim().toLowerCase();
    updatePageHero(hash || "dashboard");
  });
})();
