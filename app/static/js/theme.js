(function () {
  "use strict";

  const storageKey = "retailiq.theme";
  const root = document.documentElement;

  function preferredTheme() {
    const storedTheme = localStorage.getItem(storageKey);
    if (storedTheme === "light" || storedTheme === "dark") {
      return storedTheme;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function updateControls(theme) {
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      const nextTheme = theme === "dark" ? "light" : "dark";
      button.setAttribute("aria-label", "Switch to " + nextTheme + " theme");
      button.setAttribute("title", "Switch to " + nextTheme + " theme");
    });
  }

  function applyTheme(theme, persist) {
    root.setAttribute("data-theme", theme);
    if (persist) {
      localStorage.setItem(storageKey, theme);
    }
    updateControls(theme);
    document.dispatchEvent(new CustomEvent("retailiq:theme-changed", {
      detail: { theme: theme },
    }));
  }

  applyTheme(preferredTheme(), false);

  document.addEventListener("DOMContentLoaded", function () {
    updateControls(root.getAttribute("data-theme"));
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        const nextTheme = root.getAttribute("data-theme") === "dark"
          ? "light"
          : "dark";
        applyTheme(nextTheme, true);
      });
    });
  });
})();
