(() => {
  const form = document.getElementById("auth-form");
  const usernameInput = document.getElementById("auth-username");
  const passwordInput = document.getElementById("auth-password");
  const submitButton = document.getElementById("auth-submit");
  const subtitle = document.getElementById("auth-subtitle");
  const modeLoginButton = document.getElementById("auth-mode-login");
  const modeRegisterButton = document.getElementById("auth-mode-register");

  const usernameError = document.getElementById("auth-username-error");
  const passwordError = document.getElementById("auth-password-error");
  const formSuccess = document.getElementById("auth-form-success");
  const formError = document.getElementById("auth-form-error");

  let authMode = "login";
  let submitting = false;

  function setTextMessage(element, message) {
    if (!element) {
      return;
    }
    if (message) {
      element.textContent = message;
      element.classList.remove("hidden");
      return;
    }
    element.textContent = "";
    element.classList.add("hidden");
  }

  function clearErrors() {
    setTextMessage(usernameError, "");
    setTextMessage(passwordError, "");
    setTextMessage(formError, "");
    setTextMessage(formSuccess, "");
    usernameInput.classList.remove("input-error");
    passwordInput.classList.remove("input-error");
  }

  function setSubmitting(isSubmitting) {
    submitting = isSubmitting;
    submitButton.disabled = isSubmitting;
    form?.setAttribute("aria-busy", isSubmitting ? "true" : "false");
    if (isSubmitting) {
      submitButton.textContent = authMode === "register" ? "Creating account..." : "Logging in...";
      return;
    }
    submitButton.textContent = authMode === "register" ? "Create account" : "Login";
  }

  function setMode(mode) {
    authMode = mode;
    form?.setAttribute("data-mode", mode);
    modeLoginButton.classList.toggle("active", mode === "login");
    modeRegisterButton.classList.toggle("active", mode === "register");
    subtitle.textContent =
      mode === "register"
        ? "Create an account to access Lobby and My Bots."
        : "Sign in to access Lobby and My Bots.";
    clearErrors();
    setSubmitting(false);
  }

  function validateForm() {
    clearErrors();
    const username = usernameInput.value.trim();
    const password = passwordInput.value;
    let valid = true;

    if (!username) {
      valid = false;
      usernameInput.classList.add("input-error");
      setTextMessage(usernameError, "Username is required.");
    }
    if (!password) {
      valid = false;
      passwordInput.classList.add("input-error");
      setTextMessage(passwordError, "Password is required.");
    } else if (authMode === "register" && password.length < 12) {
      valid = false;
      passwordInput.classList.add("input-error");
      setTextMessage(passwordError, "Password must be at least 12 characters.");
    }

    return { valid, username, password };
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) {
      return;
    }

    const { valid, username, password } = validateForm();
    if (!valid) {
      return;
    }

    setSubmitting(true);
    try {
      const endpoint = authMode === "register" ? "/auth/register" : "/auth/login";
      await window.AppShell.request(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (authMode === "register") {
        setTextMessage(formSuccess, "Account created successfully. Signing you in...");
        window.AppShell.notify("Account created. Redirecting to the lobby.", "success", { timeoutMs: 1200 });
      }
      window.setTimeout(
        () => {
          window.location.assign("/lobby");
        },
        authMode === "register" ? 650 : 0
      );
    } catch (error) {
      if (error.statusCode === 401) {
        setTextMessage(formError, "Invalid username or password.");
      } else if (error.statusCode === 409) {
        setTextMessage(formError, "Username is already taken.");
      } else if (error.statusCode === 429) {
        const retry = Number(error.detail?.retry_after_seconds);
        const message = Number.isFinite(retry)
          ? `Too many attempts. Retry in ${retry} seconds.`
          : "Too many attempts. Please retry later.";
        setTextMessage(formError, message);
      } else {
        setTextMessage(formError, error.message || "Authentication failed.");
      }
      setSubmitting(false);
    }
  }

  async function bootstrap() {
    setMode("login");

    try {
      const currentUser = await window.AppShell.getCurrentUser({ redirectOn401: false });
      if (currentUser) {
        window.location.replace("/lobby");
        return;
      }
    } catch (error) {
      setTextMessage(formError, "Unable to verify current session.");
    }

    modeLoginButton.addEventListener("click", () => setMode("login"));
    modeRegisterButton.addEventListener("click", () => setMode("register"));
    form.addEventListener("submit", (event) => {
      handleSubmit(event).catch((error) => {
        console.error(error);
        setTextMessage(formError, "Authentication failed.");
        setSubmitting(false);
      });
    });
  }

  bootstrap().catch((error) => {
    console.error(error);
    setTextMessage(formError, "Failed to initialize login page.");
  });
})();
