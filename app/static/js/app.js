(function () {
  "use strict";

  const body = document.body;
  const sidebar = document.getElementById("app-sidebar");
  const menuButton = document.querySelector("[data-sidebar-open]");
  const closeButtons = document.querySelectorAll("[data-sidebar-close]");
  const loadingState = document.querySelector("[data-session-loading]");
  const errorState = document.querySelector("[data-session-error]");
  const errorMessage = document.querySelector("[data-session-error-message]");
  const retryButton = document.querySelector("[data-session-retry]");
  const content = document.querySelector("[data-dashboard-content]");

  function openSidebar() {
    sidebar.removeAttribute("inert");
    sidebar.setAttribute("aria-hidden", "false");
    body.classList.add("sidebar-open");
    menuButton.setAttribute("aria-expanded", "true");
    const firstLink = sidebar.querySelector("a, button");
    firstLink.focus();
  }

  function closeSidebar(restoreFocus) {
    body.classList.remove("sidebar-open");
    menuButton.setAttribute("aria-expanded", "false");
    if (window.innerWidth <= 920) {
      sidebar.setAttribute("inert", "");
      sidebar.setAttribute("aria-hidden", "true");
      if (restoreFocus !== false) {
        menuButton.focus();
      }
    } else {
      sidebar.removeAttribute("inert");
      sidebar.removeAttribute("aria-hidden");
    }
  }

  function populateUser(user) {
    document.querySelectorAll("[data-user-name]").forEach(function (element) {
      element.textContent = user.name;
    });
    document.querySelectorAll("[data-business-name], [data-ready-business]").forEach(function (element) {
      element.textContent = user.business_name;
    });
    const initial = user.name.trim().charAt(0).toUpperCase() || "R";
    document.querySelectorAll("[data-user-initial]").forEach(function (element) {
      element.textContent = initial;
    });
  }

  async function loadSession() {
    loadingState.hidden = false;
    errorState.hidden = true;
    content.hidden = true;

    try {
      const user = await window.RetailIQ.restoreSession(true);
      if (!user) {
        return;
      }
      populateUser(user);
      loadingState.hidden = true;
      content.hidden = false;
    } catch (error) {
      loadingState.hidden = true;
      errorMessage.textContent = error.message;
      errorState.hidden = false;
    }
  }

  menuButton.addEventListener("click", openSidebar);
  closeButtons.forEach(function (button) {
    button.addEventListener("click", closeSidebar);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && body.classList.contains("sidebar-open")) {
      closeSidebar();
      return;
    }

    if (event.key === "Tab" && body.classList.contains("sidebar-open")) {
      const focusable = Array.from(
        sidebar.querySelectorAll("a[href], button:not([disabled])")
      );
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });

  window.addEventListener("resize", function () {
    if (window.innerWidth > 920 && body.classList.contains("sidebar-open")) {
      closeSidebar(false);
    } else if (window.innerWidth <= 920 && !body.classList.contains("sidebar-open")) {
      sidebar.setAttribute("inert", "");
      sidebar.setAttribute("aria-hidden", "true");
    }
  });

  document.addEventListener("retailiq:unauthorized", function () {
    window.location.replace("/login?session=expired");
  });

  document.querySelector("[data-logout]").addEventListener("click", function () {
    window.RetailIQ.auth.clear();
    window.location.replace("/login?logged_out=1");
  });

  document.querySelectorAll("[data-unavailable-view]").forEach(function (button) {
    button.addEventListener("click", function () {
      window.RetailIQUI.showToast(
        button.dataset.unavailableView + " is not available yet.",
        "info"
      );
      if (window.innerWidth <= 920) {
        closeSidebar();
      }
    });
  });

  retryButton.addEventListener("click", loadSession);
  closeSidebar(false);
  loadSession();
})();
