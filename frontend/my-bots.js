(() => {
  const myBotsUploadForm = document.getElementById("my-bots-upload-form");
  const myBotsUploadSubmit = document.getElementById("my-bots-upload-submit");
  const myBotsUploadFeedback = document.getElementById("my-bots-upload-feedback");
  const myBotsState = document.getElementById("my-bots-state");
  const myBotsList = document.getElementById("my-bots-list");

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
    myBotsList.classList.add("hidden");
    myBotsState.classList.remove("is-loading", "is-empty", "is-error");
    myBotsState.classList.add(`is-${type}`);
  }

  function createMetadataRow(label, value) {
    const row = document.createElement("p");
    const labelElement = document.createElement("strong");
    labelElement.textContent = `${label}: `;
    const valueElement = document.createElement("span");
    valueElement.textContent = value;
    row.append(labelElement, valueElement);
    return row;
  }

  function renderMyBotsList(bots) {
    myBotsList.innerHTML = "";

    if (!bots.length) {
      setListState("empty", "No bots uploaded yet. Upload your first bot to get started.");
      return;
    }

    bots.forEach((bot) => {
      const item = document.createElement("li");
      item.className = "my-bot-card";
      const title = document.createElement("h4");
      title.textContent = bot.name || "Unnamed Bot";

      item.append(
        title,
        createMetadataRow("Bot ID", bot.bot_id || "-"),
        createMetadataRow("Version", bot.version || "-"),
        createMetadataRow("Status", bot.status || "-"),
        createMetadataRow("Created", formatTimestamp(bot.created_at)),
        createMetadataRow("Uploaded", formatTimestamp(bot.uploaded_at || bot.created_at))
      );
      myBotsList.appendChild(item);
    });

    myBotsState.classList.add("hidden");
    myBotsList.classList.remove("hidden");
  }

  async function loadBots() {
    setListState("loading", "Loading bots...");
    const response = await window.AppShell.request("/my/bots");
    renderMyBotsList(response.bots || []);
  }

  function setUploadBusy(isBusy) {
    if (!myBotsUploadSubmit) {
      return;
    }
    myBotsUploadSubmit.disabled = isBusy;
    myBotsUploadSubmit.textContent = isBusy ? "Uploading..." : "Upload Bot";
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
      setUploadFeedback(`Upload successful: ${uploadedName}`, "success");
      myBotsUploadForm.reset();
      await loadBots();
    } catch (error) {
      if (error.statusCode === 401) {
        window.location.assign("/login");
        return;
      }
      setUploadFeedback(error.message || "Upload failed.", "error");
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
    myBotsUploadForm?.addEventListener("submit", (event) => {
      handleUploadSubmit(event).catch((error) => {
        console.error(error);
        setUploadFeedback("Upload failed.", "error");
      });
    });

    try {
      await loadBots();
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
