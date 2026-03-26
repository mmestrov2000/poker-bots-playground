(() => {
  const myBotsOpenUploadButton = document.getElementById("my-bots-open-upload");
  const myBotsUploadModal = document.getElementById("my-bots-upload-modal");
  const myBotsUploadCloseButton = document.getElementById("my-bots-upload-close");
  const myBotsUploadForm = document.getElementById("my-bots-upload-form");
  const myBotsUploadSubmit = document.getElementById("my-bots-upload-submit");
  const myBotsUploadFeedback = document.getElementById("my-bots-upload-feedback");
  const myBotsState = document.getElementById("my-bots-state");
  const myBotsTableShell = document.getElementById("my-bots-table-shell");
  const myBotsBody = document.getElementById("my-bots-body");

  let botsSignature = "";
  let lastFocusedElement = null;

  function formatTimestamp(value) {
    if (!value) {
      return "-";
    }
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return String(value);
    }
    return parsed.toLocaleString();
  }

  function clearUploadFeedback() {
    if (!myBotsUploadFeedback) {
      return;
    }
    myBotsUploadFeedback.textContent = "";
    myBotsUploadFeedback.classList.add("hidden");
    myBotsUploadFeedback.classList.remove("is-success", "is-error");
  }

  function setUploadFeedback(message, type) {
    if (!myBotsUploadFeedback) {
      return;
    }
    myBotsUploadFeedback.textContent = message;
    myBotsUploadFeedback.classList.remove("hidden");
    myBotsUploadFeedback.classList.toggle("is-success", type === "success");
    myBotsUploadFeedback.classList.toggle("is-error", type === "error");
  }

  function setListState(type, message) {
    myBotsState.textContent = message;
    myBotsState.classList.remove("hidden");
    myBotsTableShell?.classList.add("hidden");
    myBotsState.classList.remove("is-loading", "is-empty", "is-error");
    myBotsState.classList.add(`is-${type}`);
  }

  function getBotTimestamp(bot) {
    const candidates = [bot.uploaded_at, bot.created_at];
    for (const value of candidates) {
      const timestamp = Date.parse(value || "");
      if (Number.isFinite(timestamp)) {
        return timestamp;
      }
    }
    return 0;
  }

  function normalizeBotsForDisplay(bots) {
    return [...bots].sort((left, right) => {
      const timestampDelta = getBotTimestamp(right) - getBotTimestamp(left);
      if (timestampDelta !== 0) {
        return timestampDelta;
      }
      return String(right.bot_id || "").localeCompare(String(left.bot_id || ""));
    });
  }

  function buildBotsSignature(bots) {
    return bots
      .map((bot) => [bot.bot_id, bot.name, bot.version, bot.status, bot.created_at, bot.uploaded_at].join("|"))
      .join("||");
  }

  function createCell(text, className = "") {
    const cell = document.createElement("td");
    if (className) {
      cell.className = className;
    }
    cell.textContent = text;
    return cell;
  }

  function createStatusCell(status) {
    const cell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = "bot-status-pill";
    badge.textContent = status || "ready";
    cell.appendChild(badge);
    return cell;
  }

  function createPrimaryCell(bot) {
    const cell = document.createElement("td");
    cell.className = "my-bot-primary-cell";

    const wrapper = document.createElement("div");
    wrapper.className = "my-bot-primary";

    const title = document.createElement("strong");
    title.textContent = bot.name || "Unnamed Bot";

    const meta = document.createElement("span");
    meta.textContent = `Uploaded ${formatTimestamp(bot.uploaded_at || bot.created_at)}`;

    wrapper.append(title, meta);
    cell.appendChild(wrapper);
    return cell;
  }

  function renderMyBotsTable(bots) {
    const sortedBots = normalizeBotsForDisplay(bots);
    const nextSignature = buildBotsSignature(sortedBots);
    if (nextSignature === botsSignature) {
      myBotsState.classList.toggle("hidden", Boolean(sortedBots.length));
      myBotsTableShell?.classList.toggle("hidden", !sortedBots.length);
      return;
    }
    botsSignature = nextSignature;
    if (myBotsBody) {
      myBotsBody.innerHTML = "";
    }

    if (!sortedBots.length) {
      setListState("empty", "No bots uploaded yet. Upload your first bot to get started.");
      return;
    }

    sortedBots.forEach((bot) => {
      if (!myBotsBody) {
        return;
      }
      const row = document.createElement("tr");
      row.dataset.testid = `bot-row-${bot.bot_id}`;
      row.append(
        createPrimaryCell(bot),
        createCell(bot.version || "-", "my-bot-version-cell"),
        createStatusCell(bot.status || "ready"),
        createCell(formatTimestamp(bot.created_at), "my-bot-date-cell"),
        createCell(bot.bot_id || "-", "table-id")
      );
      myBotsBody.appendChild(row);
    });

    myBotsState.classList.add("hidden");
    myBotsTableShell?.classList.remove("hidden");
  }

  async function loadBots(options = {}) {
    const { showLoading = false } = options;
    if (showLoading || !botsSignature) {
      setListState("loading", "Loading bots...");
    }
    const response = await window.AppShell.request("/my/bots");
    renderMyBotsTable(response.bots || []);
  }

  function setUploadBusy(isBusy) {
    if (!myBotsUploadSubmit || !myBotsUploadForm) {
      return;
    }
    myBotsUploadSubmit.disabled = isBusy;
    myBotsUploadSubmit.textContent = isBusy ? "Uploading..." : "Upload Bot";
    myBotsOpenUploadButton?.toggleAttribute("disabled", isBusy);
    myBotsUploadCloseButton?.toggleAttribute("disabled", isBusy);
    myBotsUploadForm.setAttribute("aria-busy", isBusy ? "true" : "false");
  }

  function getModalFocusables() {
    if (!myBotsUploadModal) {
      return [];
    }
    return [...myBotsUploadModal.querySelectorAll("button, input, select, textarea, [href], [tabindex]:not([tabindex='-1'])")]
      .filter((element) => !element.disabled);
  }

  function openUploadModal() {
    if (!myBotsUploadModal) {
      return;
    }
    lastFocusedElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    clearUploadFeedback();
    myBotsUploadModal.classList.remove("hidden");
    myBotsUploadModal.setAttribute("aria-hidden", "false");
    window.setTimeout(() => {
      document.getElementById("bot-name")?.focus();
    }, 0);
  }

  function closeUploadModal(options = {}) {
    const { resetForm = false } = options;
    if (!myBotsUploadModal) {
      return;
    }
    if (resetForm) {
      myBotsUploadForm?.reset();
    }
    clearUploadFeedback();
    myBotsUploadModal.classList.add("hidden");
    myBotsUploadModal.setAttribute("aria-hidden", "true");
    if (lastFocusedElement instanceof HTMLElement) {
      lastFocusedElement.focus();
    }
  }

  function handleModalKeydown(event) {
    if (!myBotsUploadModal || myBotsUploadModal.classList.contains("hidden")) {
      return;
    }
    if (event.key === "Escape" && !myBotsUploadSubmit?.disabled) {
      closeUploadModal();
      return;
    }
    if (event.key !== "Tab") {
      return;
    }

    const focusables = getModalFocusables();
    if (!focusables.length) {
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  async function handleUploadSubmit(event) {
    event.preventDefault();
    clearUploadFeedback();

    if (!myBotsUploadForm) {
      return;
    }

    const formData = new FormData(myBotsUploadForm);
    const file = formData.get("bot_file");
    if (!(file instanceof File) || !file.name) {
      setUploadFeedback("Select a .zip bot package to upload.", "error");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".zip")) {
      setUploadFeedback("Only .zip bot uploads are supported.", "error");
      return;
    }

    setUploadBusy(true);
    try {
      const response = await window.AppShell.request("/my/bots", {
        method: "POST",
        body: formData,
      });
      const uploadedName = response?.bot?.name || "bot";
      window.AppShell.notify(`Upload successful: ${uploadedName}`, "success");
      await loadBots();
      closeUploadModal({ resetForm: true });
    } catch (error) {
      if (error.statusCode === 401) {
        window.location.assign("/login");
        return;
      }
      setUploadFeedback(error.message || "Upload failed.", "error");
      window.AppShell.notify(error.message || "Upload failed.", "error");
    } finally {
      setUploadBusy(false);
    }
  }

  async function bootstrap() {
    const user = await window.AppShell.getCurrentUser();
    if (!user) {
      return;
    }

    window.AppShell.initHeader("my-bots", user);
    clearUploadFeedback();
    myBotsOpenUploadButton?.addEventListener("click", openUploadModal);
    myBotsUploadCloseButton?.addEventListener("click", () => closeUploadModal({ resetForm: true }));
    myBotsUploadModal?.addEventListener("click", (event) => {
      if (event.target === myBotsUploadModal && !myBotsUploadSubmit?.disabled) {
        closeUploadModal({ resetForm: true });
      }
    });
    document.addEventListener("keydown", handleModalKeydown);
    myBotsUploadForm?.addEventListener("submit", (event) => {
      handleUploadSubmit(event).catch((error) => {
        console.error(error);
        setUploadFeedback("Upload failed.", "error");
      });
    });

    try {
      await loadBots({ showLoading: true });
    } catch (error) {
      if (error.statusCode === 401) {
        window.location.assign("/login");
        return;
      }
      setListState("error", error.message || "Failed to load bots.");
    }
  }

  bootstrap().catch((error) => {
    console.error(error);
    setListState("error", "Failed to initialize My Bots page.");
  });
})();
