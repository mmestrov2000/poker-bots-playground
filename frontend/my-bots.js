(() => {
  const myBotsState = document.getElementById("my-bots-state");
  const myBotsList = document.getElementById("my-bots-list");

  function renderMyBotsList(bots) {
    myBotsList.innerHTML = "";

    if (!bots.length) {
      myBotsList.classList.add("hidden");
      myBotsState.textContent = "No bots uploaded yet.";
      myBotsState.classList.remove("hidden");
      return;
    }

    bots.forEach((bot) => {
      const item = document.createElement("li");
      item.className = "my-bot-card";
      item.innerHTML = `
        <h3>${bot.name || "Unnamed Bot"}</h3>
        <p><strong>ID:</strong> ${bot.bot_id || "-"}</p>
        <p><strong>Version:</strong> ${bot.version || "-"}</p>
        <p><strong>Status:</strong> ${bot.status || "-"}</p>
        <p><strong>Created:</strong> ${bot.created_at || "-"}</p>
      `;
      myBotsList.appendChild(item);
    });

    myBotsState.classList.add("hidden");
    myBotsList.classList.remove("hidden");
  }

  async function bootstrap() {
    const user = await window.AppShell.getCurrentUser();
    if (!user) {
      return;
    }

    window.AppShell.initHeader("my-bots", user);

    myBotsState.textContent = "Loading bots...";
    myBotsState.classList.remove("hidden");
    myBotsList.classList.add("hidden");

    try {
      const response = await window.AppShell.request("/my/bots");
      renderMyBotsList(response.bots || []);
    } catch (error) {
      if (error.statusCode === 401) {
        window.location.assign("/login");
        return;
      }
      myBotsState.textContent = error.message || "Failed to load bots.";
      myBotsState.classList.remove("hidden");
      myBotsList.classList.add("hidden");
    }
  }

  bootstrap().catch((error) => {
    console.error(error);
    myBotsState.textContent = "Failed to initialize My Bots page.";
    myBotsState.classList.remove("hidden");
  });
})();
