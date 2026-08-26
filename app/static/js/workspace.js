(function () {
  "use strict";

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function formatNumber(value, maximumFractionDigits) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return new Intl.NumberFormat(undefined, {
      maximumFractionDigits: maximumFractionDigits === undefined ? 2 : maximumFractionDigits,
    }).format(Number(value));
  }

  function formatPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    return new Intl.NumberFormat(undefined, {
      style: "percent",
      maximumFractionDigits: 2,
    }).format(Number(value));
  }

  function formatDate(value, includeTime) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(undefined, includeTime
      ? { dateStyle: "medium", timeStyle: "short" }
      : { dateStyle: "medium" }).format(date);
  }

  function setState(container, options) {
    if (!container) return;
    container.replaceChildren();
    const wrapper = element("div", "data-state");
    wrapper.dataset.kind = options.kind || "empty";
    wrapper.setAttribute("role", options.kind === "error" ? "alert" : "status");
    const title = element("h3", "data-state-title", options.title);
    const copy = element("p", "data-state-copy", options.message);
    wrapper.append(title, copy);
    if (options.action) wrapper.append(options.action);
    container.append(wrapper);
  }

  function configureTable(wrapper, table, label) {
    wrapper.tabIndex = 0;
    wrapper.setAttribute("aria-label", label);
    table.querySelectorAll("th").forEach(function (heading) {
      heading.scope = "col";
    });
    table.prepend(element("caption", "sr-only", label));
  }

  function scrollToElement(target, block) {
    target.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: block || "nearest",
    });
  }

  function statusBadge(status) {
    const normalized = String(status || "UNKNOWN").toUpperCase();
    const badge = element("span", "status-badge", normalized.replaceAll("_", " "));
    badge.dataset.status = normalized;
    return badge;
  }

  function onSessionReady(callback) {
    if (window.RetailIQ.currentUser) {
      callback(window.RetailIQ.currentUser);
      return;
    }
    document.addEventListener("retailiq:session-ready", function (event) {
      callback(event.detail.user);
    }, { once: true });
  }

  function errorMessage(error) {
    return error && error.message ? error.message : "The request could not be completed.";
  }

  window.RetailIQWorkspace = {
    element: element,
    configureTable: configureTable,
    errorMessage: errorMessage,
    formatDate: formatDate,
    formatNumber: formatNumber,
    formatPercent: formatPercent,
    onSessionReady: onSessionReady,
    scrollToElement: scrollToElement,
    setState: setState,
    statusBadge: statusBadge,
  };
})();
