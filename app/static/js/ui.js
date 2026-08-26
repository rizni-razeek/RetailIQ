(function () {
  "use strict";

  function showToast(message, type) {
    const region = document.querySelector("[data-toast-region]");
    if (!region || !message) {
      return;
    }

    const toast = document.createElement("div");
    toast.className = "toast";
    toast.dataset.type = type || "info";
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    toast.textContent = message;
    region.appendChild(toast);

    window.setTimeout(function () {
      toast.classList.add("is-leaving");
      window.setTimeout(function () {
        toast.remove();
      }, 220);
    }, 4500);
  }

  function showInlineError(element, message) {
    if (!element) {
      return;
    }
    element.textContent = message || "Something went wrong. Please try again.";
    element.hidden = false;
    element.focus({ preventScroll: true });
  }

  function clearInlineError(element) {
    if (!element) {
      return;
    }
    element.textContent = "";
    element.hidden = true;
  }

  function setButtonLoading(button, isLoading, label) {
    if (!button) {
      return;
    }
    const labelElement = button.querySelector("[data-button-label]");
    button.disabled = isLoading;
    button.classList.toggle("is-loading", isLoading);
    button.setAttribute("aria-busy", String(isLoading));
    if (labelElement && label) {
      labelElement.textContent = label;
    }
  }

  document.addEventListener("retailiq:loading", function (event) {
    document.body.dataset.apiLoading = String(event.detail.active);
  });

  window.RetailIQUI = {
    clearInlineError: clearInlineError,
    setButtonLoading: setButtonLoading,
    showInlineError: showInlineError,
    showToast: showToast,
  };
})();
