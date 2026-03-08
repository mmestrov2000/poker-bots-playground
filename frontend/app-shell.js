(() => {
  const apiBase = "/api/v1";
  let toastRegion = null;

  function ensureToastRegion() {
    if (toastRegion) {
      return toastRegion;
    }
    toastRegion = document.createElement("div");
    toastRegion.id = "app-toast-region";
    toastRegion.className = "toast-region";
    toastRegion.setAttribute("aria-live", "polite");
    toastRegion.setAttribute("aria-atomic", "false");
    document.body.appendChild(toastRegion);
    return toastRegion;
  }

  function request(path, options = {}) {
    const requestOptions = { ...options };
    if (!requestOptions.credentials) {
      requestOptions.credentials = "same-origin";
    }
    return fetch(`${apiBase}${path}`, requestOptions).then(async (response) => {
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const detail = payload.detail;
        const message =
          typeof detail === "string"
            ? detail
            : detail?.message || payload.message || `Request failed: ${response.status}`;
        const error = new Error(message);
        error.statusCode = response.status;
        error.detail = detail;
        throw error;
      }

      if (response.status === 204) {
        return null;
      }
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        return response.text();
      }
      return response.json();
    });
  }

  async function getCurrentUser(options = {}) {
    const { redirectOn401 = true } = options;
    try {
      const response = await request("/auth/me");
      return response.user;
    } catch (error) {
      if (error.statusCode === 401) {
        if (redirectOn401) {
          window.location.assign("/login");
        }
        return null;
      }
      throw error;
    }
  }

  function createToastNode(message, type) {
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.setAttribute("role", "status");

    const messageNode = document.createElement("p");
    messageNode.className = "toast-message";
    messageNode.textContent = message;

    const dismissButton = document.createElement("button");
    dismissButton.type = "button";
    dismissButton.className = "toast-dismiss";
    dismissButton.setAttribute("aria-label", "Dismiss notification");
    dismissButton.textContent = "Dismiss";

    toast.append(messageNode, dismissButton);
    return { toast, dismissButton };
  }

  function notify(message, type = "info", options = {}) {
    if (!message) {
      return null;
    }
    const { timeoutMs = 3600 } = options;
    const region = ensureToastRegion();
    const { toast, dismissButton } = createToastNode(message, type);
    region.appendChild(toast);

    let removed = false;
    const removeToast = () => {
      if (removed) {
        return;
      }
      removed = true;
      toast.classList.add("toast-exit");
      window.setTimeout(() => {
        toast.remove();
      }, 200);
    };

    dismissButton.addEventListener("click", removeToast);

    if (timeoutMs > 0) {
      window.setTimeout(removeToast, timeoutMs);
    }
    return toast;
  }

  function initHeader(pageName, user) {
    const userLabel = document.getElementById("auth-user");
    if (userLabel && user?.username) {
      userLabel.textContent = `Signed in as ${user.username}`;
    }

    document.querySelectorAll(".app-nav [data-nav]").forEach((link) => {
      const isActive = link.getAttribute("data-nav") === pageName;
      link.classList.toggle("active", isActive);
      if (isActive) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });

    const logoutButton = document.getElementById("logout-button");
    if (logoutButton) {
      logoutButton.addEventListener("click", async () => {
        logoutButton.disabled = true;
        try {
          await request("/auth/logout", { method: "POST" });
        } catch (error) {
          if (error.statusCode !== 401) {
            console.error(error);
            notify("Logout hit an error, but your session may already be closed.", "warning");
          }
        }
        window.location.assign("/login");
      });
    }
  }

  function startAdaptivePolling(task, options = {}) {
    const {
      activeMs = 5000,
      hiddenMs = Math.max(activeMs * 4, activeMs),
      runImmediately = true,
    } = options;
    let timeoutId = null;
    let stopped = false;
    let inFlight = false;

    const scheduleNext = () => {
      if (stopped) {
        return;
      }
      const delay = document.visibilityState === "hidden" ? hiddenMs : activeMs;
      timeoutId = window.setTimeout(tick, delay);
    };

    const tick = async () => {
      if (stopped) {
        return;
      }
      if (inFlight) {
        scheduleNext();
        return;
      }
      inFlight = true;
      try {
        await task();
      } finally {
        inFlight = false;
        scheduleNext();
      }
    };

    const handleVisibilityChange = () => {
      if (stopped) {
        return;
      }
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      timeoutId = window.setTimeout(tick, document.visibilityState === "hidden" ? hiddenMs : activeMs);
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    if (runImmediately) {
      tick().catch((error) => {
        console.error(error);
      });
    } else {
      scheduleNext();
    }

    return () => {
      stopped = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }

  window.AppShell = {
    request,
    getCurrentUser,
    initHeader,
    notify,
    startAdaptivePolling,
  };
})();
