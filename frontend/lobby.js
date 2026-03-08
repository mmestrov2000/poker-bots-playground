(() => {
  const createTableForm = document.getElementById("create-table-form");
  const createTableSubmit = document.getElementById("create-table-submit");
  const createTableFeedback = document.getElementById("create-table-feedback");
  const refreshTablesButton = document.getElementById("refresh-tables");
  const refreshLeaderboardButton = document.getElementById("refresh-leaderboard");

  const tablesState = document.getElementById("lobby-tables-state");
  const tablesTable = document.getElementById("lobby-tables-table");
  const tablesBody = document.getElementById("lobby-tables-body");
  const tableCards = document.getElementById("lobby-table-cards");

  const leaderboardState = document.getElementById("lobby-leaderboard-state");
  const leaderboardList = document.getElementById("lobby-leaderboard-list");

  let createRequestInFlight = false;
  let knownTables = [];
  let stopPolling = null;
  let tablesSignature = "";
  let leaderboardSignature = "";

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

  function normalizeTable(table) {
    const tableId = table?.table_id || table?.tableId;
    if (!tableId) {
      return null;
    }
    const status = extractTableStatus(table);
    const createdAt = table.created_at || table.createdAt || null;
    return {
      table_id: tableId,
      state: status,
      status,
      small_blind: Number(table.small_blind ?? table.smallBlind ?? 0.5),
      big_blind: Number(table.big_blind ?? table.bigBlind ?? 1),
      seats_filled: extractSeatsFilled(table),
      max_seats: Number(table.max_seats ?? table.maxSeats ?? 6),
      created_at: createdAt,
    };
  }

  function buildTablesSignature(tables) {
    return tables
      .map((table) =>
        [
          table.table_id,
          table.state,
          table.small_blind,
          table.big_blind,
          table.seats_filled,
          table.max_seats,
          table.created_at,
        ].join("|")
      )
      .join("||");
  }

  function buildLeaderboardSignature(leaderboard) {
    return leaderboard
      .map((entry) =>
        [
          entry.bot_id || entry.bot_name || entry.name,
          entry.bb_per_hand,
          entry.bb_won,
          entry.hands_played,
          entry.updated_at,
        ].join("|")
      )
      .join("||");
  }

  function setCreateSubmitting(isSubmitting) {
    createRequestInFlight = isSubmitting;
    if (!createTableForm || !createTableSubmit) {
      return;
    }
    createTableSubmit.disabled = isSubmitting;
    createTableSubmit.textContent = isSubmitting ? "Creating..." : "Create Table";
    createTableForm.setAttribute("aria-busy", isSubmitting ? "true" : "false");
    createTableForm.querySelectorAll("input, button").forEach((element) => {
      element.disabled = isSubmitting;
    });
  }

  function createOpenButton(tableId, className = "button-secondary") {
    const openButton = document.createElement("button");
    openButton.type = "button";
    openButton.className = className;
    openButton.dataset.tableOpen = tableId;
    openButton.setAttribute("data-testid", `open-table-${tableId}`);
    openButton.textContent = "Open Table";
    openButton.addEventListener("click", () => {
      window.location.assign(`/tables/${encodeURIComponent(tableId)}`);
    });
    return openButton;
  }

  function renderTables(tables) {
    if (!tablesBody || !tablesTable || !tablesState || !tableCards) {
      return;
    }

    const normalizedTables = tables.map(normalizeTable).filter(Boolean);
    const nextSignature = buildTablesSignature(normalizedTables);
    knownTables = normalizedTables.slice();
    if (nextSignature === tablesSignature) {
      tablesState.classList.add("hidden");
      tablesTable.classList.toggle("hidden", !normalizedTables.length);
      tableCards.classList.toggle("hidden", !normalizedTables.length);
      return;
    }
    tablesSignature = nextSignature;

    tablesBody.innerHTML = "";
    tableCards.innerHTML = "";

    if (!normalizedTables.length) {
      tablesState.textContent = "No tables yet. Create one to get started.";
      tablesState.classList.remove("hidden");
      tablesTable.classList.add("hidden");
      tableCards.classList.add("hidden");
      return;
    }

    normalizedTables.forEach((table) => {
      const row = document.createElement("tr");
      row.dataset.testid = `table-row-${table.table_id}`;
      row.innerHTML = `
        <td class="table-id">${table.table_id}</td>
        <td>${formatNumber(table.small_blind, 2)}/${formatNumber(table.big_blind, 2)}</td>
        <td>${table.seats_filled}/${table.max_seats}</td>
        <td><span class="table-state-pill" data-state="${table.state}">${table.state}</span></td>
        <td>${formatTimestamp(table.created_at)}</td>
      `;
      const actionCell = document.createElement("td");
      actionCell.appendChild(createOpenButton(table.table_id));
      row.appendChild(actionCell);
      tablesBody.appendChild(row);

      const card = document.createElement("article");
      card.className = "lobby-table-card";
      card.dataset.testid = `table-card-${table.table_id}`;
      card.innerHTML = `
        <div class="lobby-table-card-header">
          <div>
            <p class="table-id">${table.table_id}</p>
            <p class="lobby-card-meta">${formatNumber(table.small_blind, 2)}/${formatNumber(table.big_blind, 2)} blinds</p>
          </div>
          <span class="table-state-pill" data-state="${table.state}">${table.state}</span>
        </div>
        <div class="lobby-card-stats">
          <p>${table.seats_filled}/${table.max_seats} seats filled</p>
          <p>${formatTimestamp(table.created_at)}</p>
        </div>
      `;
      card.appendChild(createOpenButton(table.table_id, "button-secondary button-full"));
      tableCards.appendChild(card);
    });

    tablesState.classList.add("hidden");
    tablesTable.classList.remove("hidden");
    tableCards.classList.remove("hidden");
  }

  function renderLeaderboard(leaderboard) {
    if (!leaderboardList || !leaderboardState) {
      return;
    }

    const nextSignature = buildLeaderboardSignature(leaderboard);
    if (nextSignature === leaderboardSignature) {
      leaderboardState.classList.toggle("hidden", Boolean(leaderboard.length));
      leaderboardList.classList.toggle("hidden", !leaderboard.length);
      return;
    }
    leaderboardSignature = nextSignature;
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
      item.dataset.testid = `leaderboard-entry-${index + 1}`;

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
    if (!knownTables.length) {
      tablesState.textContent = "Loading tables...";
      tablesState.classList.remove("hidden");
    }

    const response = await window.AppShell.request("/lobby/tables");
    const tables = response.tables || [];
    renderTables(tables);
  }

  async function loadLeaderboard() {
    if (!leaderboardState) {
      return;
    }
    if (leaderboardList.classList.contains("hidden")) {
      leaderboardState.textContent = "Loading leaderboard...";
      leaderboardState.classList.remove("hidden");
    }

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

    if (bigBlind <= smallBlind) {
      showCreateFeedback("Big blind must be greater than small blind.", "error");
      return;
    }

    setCreateSubmitting(true);
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

      const normalizedTable = normalizeTable(response.table);
      if (normalizedTable) {
        knownTables = [normalizedTable, ...knownTables.filter((item) => item.table_id !== normalizedTable.table_id)];
        renderTables(knownTables);
      }
      showCreateFeedback("Table created successfully. It is now listed below.", "success");
      window.AppShell.notify("Table created successfully.", "success");
      await Promise.all([loadTables(), loadLeaderboard()]);
    } catch (error) {
      showCreateFeedback(error.message || "Failed to create table.", "error");
      window.AppShell.notify(error.message || "Failed to create table.", "error");
    } finally {
      setCreateSubmitting(false);
    }
  }

  function bindEvents() {
    createTableForm?.addEventListener("submit", (event) => {
      if (createRequestInFlight) {
        event.preventDefault();
        return;
      }
      handleCreateTableSubmit(event).catch((error) => {
        console.error(error);
        showCreateFeedback("Failed to create table.", "error");
        setCreateSubmitting(false);
      });
    });

    refreshTablesButton?.addEventListener("click", () => {
      loadTables().catch((error) => {
        console.error(error);
        if (tablesState) {
          tablesState.textContent = "Failed to load tables.";
        }
        window.AppShell.notify("Failed to load tables.", "error");
      });
    });

    refreshLeaderboardButton?.addEventListener("click", () => {
      loadLeaderboard().catch((error) => {
        console.error(error);
        if (leaderboardState) {
          leaderboardState.textContent = "Failed to load leaderboard.";
        }
        window.AppShell.notify("Failed to load leaderboard.", "error");
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
      stopPolling = window.AppShell.startAdaptivePolling(refreshLobbyData, {
        activeMs: 15000,
        hiddenMs: 60000,
        runImmediately: false,
      });
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
    if (stopPolling) {
      stopPolling();
    }
  });
})();
