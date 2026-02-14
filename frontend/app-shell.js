(() => {
  const apiBase = "/api/v1";

  async function request(path, options = {}) {
    const requestOptions = { ...options };
    if (!requestOptions.credentials) {
      requestOptions.credentials = "same-origin";
    }
    const response = await fetch(`${apiBase}${path}`, requestOptions);
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
    return response.json();
  }

  async function getCurrentUser() {
    try {
      const response = await request("/auth/me");
      return response.user;
    } catch (error) {
      if (error.statusCode === 401) {
        window.location.assign("/login");
        return null;
      }
      throw error;
    }
  }

  function initHeader(pageName, user) {
    const userLabel = document.getElementById("auth-user");
    if (userLabel && user?.username) {
      userLabel.textContent = `Signed in as ${user.username}`;
    }

    document.querySelectorAll(".app-nav [data-nav]").forEach((link) => {
      const isActive = link.getAttribute("data-nav") === pageName;
      link.classList.toggle("active", isActive);
    });

    const logoutButton = document.getElementById("logout-button");
    if (logoutButton) {
      logoutButton.addEventListener("click", async () => {
        try {
          await request("/auth/logout", { method: "POST" });
        } catch (error) {
          if (error.statusCode !== 401) {
            console.error(error);
          }
        }
        window.location.assign("/login");
      });
    }
  }

  window.AppShell = {
    request,
    getCurrentUser,
    initHeader,
  };
})();
