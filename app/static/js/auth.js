(function () {
  "use strict";

  const form = document.querySelector("[data-auth-form]");
  if (!form) {
    return;
  }

  const page = form.dataset.authForm;
  const submitButton = form.querySelector("[data-submit-button]");
  const errorElement = document.querySelector("[data-form-error]");
  const defaultButtonLabel = page === "login" ? "Sign in" : "Create account";

  function toggleForm(disabled) {
    form.querySelectorAll("input, button").forEach(function (control) {
      control.disabled = disabled;
    });
  }

  function setupPasswordToggle() {
    const toggle = form.querySelector("[data-password-toggle]");
    if (!toggle) {
      return;
    }
    const password = document.getElementById(toggle.getAttribute("aria-controls"));
    toggle.addEventListener("click", function () {
      const showing = password.type === "text";
      password.type = showing ? "password" : "text";
      toggle.textContent = showing ? "Show password" : "Hide password";
      toggle.setAttribute("aria-label", (showing ? "Show" : "Hide") + " password");
    });
  }

  function showQueryMessage() {
    const url = new URL(window.location.href);
    if (url.searchParams.get("registered") === "1") {
      window.RetailIQUI.showToast("Account created. Sign in to continue.", "success");
    } else if (url.searchParams.get("session") === "expired") {
      window.RetailIQUI.showToast("Your session has expired. Sign in again.", "info");
    } else if (url.searchParams.get("session") === "required") {
      window.RetailIQUI.showToast("Sign in to open your RetailIQ workspace.", "info");
    } else if (url.searchParams.get("logged_out") === "1") {
      window.RetailIQUI.showToast("You have been signed out.", "success");
    }

    if (url.search) {
      window.history.replaceState({}, "", url.pathname);
    }
  }

  async function checkExistingSession() {
    if (!window.RetailIQ.auth.hasToken()) {
      return;
    }

    toggleForm(true);
    window.RetailIQUI.setButtonLoading(submitButton, true, "Checking session");
    try {
      const user = await window.RetailIQ.restoreSession(false);
      if (user) {
        window.location.replace("/dashboard");
        return;
      }
    } catch (error) {
      window.RetailIQUI.showToast(error.message, "error");
    }
    toggleForm(false);
    window.RetailIQUI.setButtonLoading(submitButton, false, defaultButtonLabel);
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    window.RetailIQUI.clearInlineError(errorElement);

    if (!form.reportValidity()) {
      return;
    }

    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());
    Object.keys(payload).forEach(function (key) {
      if (key !== "password" && typeof payload[key] === "string") {
        payload[key] = payload[key].trim();
      }
    });

    const loadingLabel = page === "login" ? "Signing in" : "Creating account";
    toggleForm(true);
    window.RetailIQUI.setButtonLoading(submitButton, true, loadingLabel);

    try {
      if (page === "login") {
        const response = await window.RetailIQ.api.request("/auth/login", {
          auth: false,
          method: "POST",
          body: payload,
        });
        window.RetailIQ.auth.setToken(response.access_token);
        await window.RetailIQ.restoreSession(false);
        window.location.replace("/dashboard");
      } else {
        await window.RetailIQ.api.request("/auth/register", {
          auth: false,
          method: "POST",
          body: payload,
        });
        window.location.assign("/login?registered=1");
      }
    } catch (error) {
      window.RetailIQUI.showInlineError(errorElement, error.message);
      toggleForm(false);
      window.RetailIQUI.setButtonLoading(submitButton, false, defaultButtonLabel);
    }
  });

  setupPasswordToggle();
  showQueryMessage();
  checkExistingSession();
})();
