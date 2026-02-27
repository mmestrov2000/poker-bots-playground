(() => {
  const createTableForm = document.getElementById("create-table-form");
  const createTableSubmit = document.getElementById("create-table-submit");
  const createTableFeedback = document.getElementById("create-table-feedback");
  const refreshTablesButton = document.getElementById("refresh-tables");
  const refreshLeaderboardButton = document.getElementById("refresh-leaderboard");

  const tablesState = document.getElementById("lobby-tables-state");
  const tablesTable = document.getElementById("lobby-tables-table");
  const tablesBody = document.getElementById("lobby-tables-body");

  const leaderboardState = document.getElementById("lobby-leaderboard-state");
  const leaderboardList = document.getElementById("lobby-leaderboard-list");

  let refreshTimer = null;

  function showCreateFeedback(message, type = "info") {
    if (!createTableFeedback) {
      return;
    }
    createTableFeedback.textContent = message;
    createTableFeedback.classList.remove("hidden", "is-success", "is-error");
    if (type === "success") {
      createTableFeedback.classList.add("is-success");
    }
    if (type === "error") {
      createTableFeedback.classList.add("is-error");
    }
  }

  function clearCreateFeedback() {
    if (!createTableFeedback) {
      return;
    }
    createTableFeedback.textContent = "";
    createTableFeedback.classList.add("hidden");
    createTableFeedback.classList.remove("is-success", "is-error");
  }

  function formatTimestamp(value) {
    if (!value) {
      return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "-";
    }
    return date.toLocaleString();
  }

  function formatNumber(value, digits = 2) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "0.00";
    }
    return numeric.toFixed(digits);
  }

  function extractSeatsFilled(table) {
    const candidates = [table.seats_filled, table.seatsFilled, table.ready_seats, table.readySeats];
    const numeric = candidates.map((value) => Number(value)).find((value) => Number.isFinite(value));
    return numeric ?? 0;
  }

  function extractTableStatus(table) {
    return table.state || table.status || "waiting";
  }

  function renderTables(tables) {
    if (!tablesBody || !tablesTable || !tablesState) {
      return;
    }

    tablesBody.innerHTML = "";
    if (!tables.length) {
      tablesState.textContent = "No tables yet. Create one to get started.";
      tablesState.classList.remove("hidden");
      tablesTable.classList.add("hidden");
      return;
    }

    tables.forEach((table) => {
      const row = document.createElement("tr");
      const tableId = table.table_id || table.tableId || "unknown";
      const smallBlind = Number(table.small_blind ?? table.smallBlind ?? 0.5);
      const bigBlind = Number(table.big_blind ?? table.bigBlind ?? 1);
      const seatsFilled = extractSeatsFilled(table);
      const status = extractTableStatus(table);
      const createdAt = table.created_at || table.createdAt;

      const openButton = document.createElement("button");
      openButton.type = "button";
      openButton.className = "button-secondary";
      openButton.dataset.tableOpen = tableId;
      openButton.textContent = "Open";
      openButton.addEventListener("click", () => {
        window.location.assign(`/tables/${encodeURIComponent(tableId)}`);
      });

      row.innerHTML = `
        <td class="table-id">${tableId}</td>
        <td>${formatNumber(smallBlind, 2)}/${formatNumber(bigBlind, 2)}</td>
        <td>${seatsFilled}/6</td>
        <td>${status}</td>
        <td>${formatTimestamp(createdAt)}</td>
      `;

      const actionCell = document.createElement("td");
      actionCell.appendChild(openButton);
      row.appendChild(actionCell);
      tablesBody.appendChild(row);
    });

    tablesState.classList.add("hidden");
    tablesTable.classList.remove("hidden");
  }

  function renderLeaderboard(leaderboard) {
    if (!leaderboardList || !leaderboardState) {
      return;
    }

    leaderboardList.innerHTML = "";
    if (!leaderboard.length) {
      leaderboardState.textContent = "No leaderboard data yet.";
      leaderboardState.classList.remove("hidden");
      leaderboardList.classList.add("hidden");
      return;
    }

    leaderboard.forEach((entry, index) => {
      const item = document.createElement("li");
      item.className = "lobby-leaderboard-item";

      const name = entry.bot_name || entry.name || entry.bot_id || "Unknown bot";
      const bbPerHand = formatNumber(entry.bb_per_hand, 3);
      const bbWon = formatNumber(entry.bb_won, 2);
      const handsPlayed = Number(entry.hands_played ?? 0);

      item.innerHTML = `
        <div>
          <p class="lobby-leaderboard-rank">#${index + 1} ${name}</p>
          <p class="lobby-leaderboard-meta">${handsPlayed} hands | ${bbWon} BB total</p>
        </div>
        <p class="lobby-leaderboard-stat">${bbPerHand} BB/hand</p>
      `;
      leaderboardList.appendChild(item);
    });

    leaderboardState.classList.add("hidden");
    leaderboardList.classList.remove("hidden");
  }

  async function loadTables() {
    if (!tablesState) {
      return;
    }
    tablesState.textContent = "Loading tables...";
    tablesState.classList.remove("hidden");

    const response = await window.AppShell.request("/lobby/tables");
    const tables = response.tables || [];
    renderTables(tables);
  }

  async function loadLeaderboard() {
    if (!leaderboardState) {
      return;
    }
    leaderboardState.textContent = "Loading leaderboard...";
    leaderboardState.classList.remove("hidden");

    const response = await window.AppShell.request("/lobby/leaderboard");
    const leaderboard = response.leaderboard || response.leaders || [];
    renderLeaderboard(leaderboard);
  }

  async function refreshLobbyData() {
    await Promise.all([loadTables(), loadLeaderboard()]);
  }

  async function handleCreateTableSubmit(event) {
    event.preventDefault();
    if (!createTableForm || !createTableSubmit) {
      return;
    }

    clearCreateFeedback();

    const formData = new FormData(createTableForm);
    const smallBlind = Number(formData.get("small_blind"));
    const bigBlind = Number(formData.get("big_blind"));

    if (!Number.isFinite(smallBlind) || !Number.isFinite(bigBlind) || smallBlind <= 0 || bigBlind <= 0) {
      showCreateFeedback("Small blind and big blind must be greater than zero.", "error");
      return;
    }

    if (bigBlind < smallBlind) {
      showCreateFeedback("Big blind must be greater than or equal to small blind.", "error");
      return;
    }

    createTableSubmit.disabled = true;
    try {
      const response = await window.AppShell.request("/lobby/tables", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          small_blind: smallBlind,
          big_blind: bigBlind,
        }),
      });

      const table = response.table;
      const tableId = table?.table_id || table?.tableId;
      showCreateFeedback("Table created successfully.", "success");
      await refreshLobbyData();

      if (tableId) {
        window.location.assign(`/tables/${encodeURIComponent(tableId)}`);
      }
    } catch (error) {
      showCreateFeedback(error.message || "Failed to create table.", "error");
    } finally {
      createTableSubmit.disabled = false;
    }
  }

  function bindEvents() {
    createTableForm?.addEventListener("submit", (event) => {
      handleCreateTableSubmit(event).catch((error) => {
        console.error(error);
        showCreateFeedback("Failed to create table.", "error");
      });
    });

    refreshTablesButton?.addEventListener("click", () => {
      loadTables().catch((error) => {
        console.error(error);
        if (tablesState) {
          tablesState.textContent = "Failed to load tables.";
        }
      });
    });

    refreshLeaderboardButton?.addEventListener("click", () => {
      loadLeaderboard().catch((error) => {
        console.error(error);
        if (leaderboardState) {
          leaderboardState.textContent = "Failed to load leaderboard.";
        }
      });
    });
  }

  async function bootstrap() {
    try {
      const user = await window.AppShell.getCurrentUser();
      if (!user) {
        return;
      }

      window.AppShell.initHeader("lobby", user);
      bindEvents();
      await refreshLobbyData();

      refreshTimer = window.setInterval(() => {
        refreshLobbyData().catch((error) => {
          console.error(error);
        });
      }, 15000);
    } catch (error) {
      console.error(error);
      if (tablesState) {
        tablesState.textContent = "Failed to initialize lobby.";
      }
      if (leaderboardState) {
        leaderboardState.textContent = "Failed to initialize lobby.";
      }
    }
  }

  bootstrap();

  window.addEventListener("beforeunload", () => {
    if (refreshTimer !== null) {
      window.clearInterval(refreshTimer);
    }
  });
})();
