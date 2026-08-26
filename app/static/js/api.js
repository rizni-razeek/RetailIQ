(function () {
  "use strict";

  const apiBase = "/api";
  const tokenKey = "retailiq.auth.token";
  let activeRequests = 0;

  class ApiError extends Error {
    constructor(message, status, data) {
      super(message);
      this.name = "ApiError";
      this.status = status;
      this.data = data;
    }
  }

  const AuthStore = {
    getToken: function () {
      return localStorage.getItem(tokenKey);
    },
    setToken: function (token) {
      localStorage.setItem(tokenKey, token);
    },
    clear: function () {
      localStorage.removeItem(tokenKey);
    },
    hasToken: function () {
      return Boolean(localStorage.getItem(tokenKey));
    },
  };

  function updateLoading(change) {
    activeRequests = Math.max(0, activeRequests + change);
    document.dispatchEvent(new CustomEvent("retailiq:loading", {
      detail: { active: activeRequests > 0 },
    }));
  }

  async function parseResponse(response) {
    const text = await response.text();
    if (!text) {
      return null;
    }
    try {
      return JSON.parse(text);
    } catch (_error) {
      return null;
    }
  }

  async function request(path, options) {
    const settings = Object.assign({ auth: true, method: "GET" }, options || {});
    const headers = new Headers(settings.headers || {});
    const token = AuthStore.getToken();

    headers.set("Accept", "application/json");
    if (settings.auth && token) {
      headers.set("Authorization", "Bearer " + token);
    }

    let body = settings.body;
    if (body && !(body instanceof FormData) && typeof body !== "string") {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(body);
    }

    updateLoading(1);
    try {
      const response = await fetch(apiBase + path, {
        method: settings.method,
        headers: headers,
        body: body,
        signal: settings.signal,
      });
      const data = await parseResponse(response);

      if (!response.ok) {
        if (settings.auth && response.status === 401) {
          AuthStore.clear();
          document.dispatchEvent(new CustomEvent("retailiq:unauthorized"));
        }
        const message = data && (data.error || data.message || data.msg)
          ? data.error || data.message || data.msg
          : "The request could not be completed.";
        throw new ApiError(message, response.status, data);
      }

      return data;
    } catch (error) {
      if (error instanceof ApiError || error.name === "AbortError") {
        throw error;
      }
      throw new ApiError(
        "RetailIQ could not connect to the server. Check your connection and try again.",
        0,
        null
      );
    } finally {
      updateLoading(-1);
    }
  }

  async function restoreSession(redirectOnFailure) {
    const shouldRedirect = redirectOnFailure !== false;
    if (!AuthStore.hasToken()) {
      if (shouldRedirect) {
        window.location.replace("/login?session=required");
      }
      return null;
    }

    try {
      const response = await request("/auth/me");
      return response.user;
    } catch (error) {
      if (error.status === 401 || error.status === 422) {
        AuthStore.clear();
        if (shouldRedirect) {
          window.location.replace("/login?session=expired");
        }
        return null;
      }
      throw error;
    }
  }

  window.RetailIQ = {
    ApiError: ApiError,
    api: { request: request },
    auth: AuthStore,
    restoreSession: restoreSession,
  };
})();
