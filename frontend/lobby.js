(() => {
  const handDetailPlaceholder = "Select a hand to view full history.";
  const seatIds = ["1", "2", "3", "4", "5", "6"];

  let selectedHandId = null;
  let handHistoryVisible = false;
  let snapshotMaxHandId = null;
  let handsPage = 1;
  let handsPageSize = 100;
  let handsTotalHands = 0;
  let handsTotalPages = 0;
  let latestMatch = null;
  let handDetailMode = "logs";
  let handDetailText = handDetailPlaceholder;
  let pnlLastHandId = null;
  let pnlPoints = {};
  let pnlRefreshing = false;
  let seatNames = {};
  let pnlVisibility = {};
  let refreshTimer = null;
  let activeSeatId = null;
  let myBotsCache = [];
  let seatAssignmentBusy = false;

  const handDetailTabs = {
    logs: document.getElementById("hand-detail-logs"),
    replay: document.getElementById("hand-detail-replay"),
  };

  const pnlElements = {
    chart: document.getElementById("pnl-chart"),
    zeroLine: document.getElementById("pnl-zero-line"),
    empty: document.getElementById("pnl-empty"),
    lines: Object.fromEntries(
      seatIds.map((seatId) => [seatId, document.getElementById(`pnl-line-${seatId}`)])
    ),
  };
  const leaderboardList = document.getElementById("leaderboard-list");
  const seatAssignmentPanel = document.getElementById("seat-assignment-panel");
  const seatAssignmentTitle = document.getElementById("seat-assignment-title");
  const seatAssignmentFeedback = document.getElementById("seat-assignment-feedback");
  const seatExistingSelect = document.getElementById("seat-existing-bot-id");
  const seatSelectExistingSubmit = document.getElementById("seat-select-existing-submit");
  const seatCreateNewSubmit = document.getElementById("seat-create-new-submit");
  const seatSelectExistingForm = document.getElementById("seat-select-existing-form");
  const seatCreateNewForm = document.getElementById("seat-create-new-form");

  function updateSeatStatus(seats) {
    const byId = Object.fromEntries(seats.map((seat) => [seat.seat_id, seat]));
    let readyCount = 0;

    seatIds.forEach((seatId) => {
      const seat = byId[seatId];
      const seatReady = Boolean(seat?.ready);
      const name = seat?.bot_name || "Open seat";
      seatNames[seatId] = seat?.bot_name || null;

      const nameEl = document.getElementById(`seat-${seatId}-name`);
      if (nameEl) {
        nameEl.textContent = name;
      }

      const seatButton = document.getElementById(`seat-${seatId}-take`);
      if (seatButton) {
        seatButton.disabled = seatReady;
      }

      if (seatReady) {
        readyCount += 1;
      }
    });

    return readyCount >= 2;
  }

  function renderHandDetail() {
    const detail = document.getElementById("hand-detail");
    if (!detail) {
      return;
    }
    detail.textContent = handDetailMode === "logs" ? handDetailText : "";
  }

  function setHandDetailMode(mode) {
    handDetailMode = mode;
    handDetailTabs.logs?.classList.toggle("active", mode === "logs");
    handDetailTabs.replay?.classList.toggle("active", mode === "replay");
    renderHandDetail();
  }

  function renderPnlChart() {
    if (!pnlElements.chart) {
      return;
    }

    const width = 640;
    const height = 280;
    const anyPoints = seatIds.some((seatId) => pnlPoints[seatId]?.length);
    const visibleSeats = seatIds.filter((seatId) => pnlVisibility[seatId]);
    const visibleSeries = visibleSeats.filter((seatId) => pnlPoints[seatId]?.length);

    seatIds.forEach((seatId) => {
      const line = pnlElements.lines[seatId];
      if (line) {
        line.setAttribute("d", "");
      }
    });

    pnlElements.zeroLine.setAttribute("x1", "0");
    pnlElements.zeroLine.setAttribute("x2", width.toString());
    const mid = height / 2;
    pnlElements.zeroLine.setAttribute("y1", mid.toString());
    pnlElements.zeroLine.setAttribute("y2", mid.toString());

    if (!anyPoints) {
      pnlElements.empty.textContent = "No hands yet.";
      pnlElements.empty.classList.remove("hidden");
      return;
    }

    if (!visibleSeries.length) {
      pnlElements.empty.textContent = "Select bots to display P&L.";
      pnlElements.empty.classList.remove("hidden");
      return;
    }

    pnlElements.empty.classList.add("hidden");

    const values = visibleSeries.flatMap((seatId) => pnlPoints[seatId].map((point) => point.value));
    let minValue = Math.min(...values);
    let maxValue = Math.max(...values);
    if (minValue === maxValue) {
      minValue -= 1;
      maxValue += 1;
    } else {
      const padding = (maxValue - minValue) * 0.1;
      minValue -= padding;
      maxValue += padding;
    }

    const handIds = visibleSeries.flatMap((seatId) =>
      pnlPoints[seatId].map((point) => point.handId)
    );
    const minHand = Math.min(...handIds);
    const maxHand = Math.max(...handIds);
    const xFor = (handId) => {
      if (maxHand === minHand) {
        return width / 2;
      }
      return ((handId - minHand) / (maxHand - minHand)) * width;
    };
    const yFor = (value) => height - ((value - minValue) / (maxValue - minValue)) * height;
    const buildPath = (points) =>
      points
        .map((point, index) => {
          const x = xFor(point.handId).toFixed(2);
          const y = yFor(point.value).toFixed(2);
          return `${index === 0 ? "M" : "L"}${x},${y}`;
        })
        .join(" ");

    visibleSeries.forEach((seatId) => {
      const line = pnlElements.lines[seatId];
      if (!line) {
        return;
      }
      line.setAttribute("d", buildPath(pnlPoints[seatId]));
    });

    const zeroY = yFor(0);
    pnlElements.zeroLine.setAttribute("x1", "0");
    pnlElements.zeroLine.setAttribute("x2", width.toString());
    pnlElements.zeroLine.setAttribute("y1", zeroY.toFixed(2));
    pnlElements.zeroLine.setAttribute("y2", zeroY.toFixed(2));
  }

  function resetPnlState() {
    pnlLastHandId = null;
    pnlPoints = Object.fromEntries(seatIds.map((seatId) => [seatId, []]));
    renderPnlChart();
  }

  function applyPnlEntries(entries) {
    entries.forEach((entry) => {
      const handId = Number(entry.hand_id);
      if (!Number.isFinite(handId)) {
        return;
      }
      if (pnlLastHandId !== null && handId <= pnlLastHandId) {
        return;
      }
      seatIds.forEach((seatId) => {
        const delta = Number(entry.deltas?.[seatId]) || 0;
        const lastValue = pnlPoints[seatId].length
          ? pnlPoints[seatId][pnlPoints[seatId].length - 1].value
          : 0;
        pnlPoints[seatId].push({ handId, value: lastValue + delta });
      });
      pnlLastHandId = handId;
    });
  }

  function updateLeaderboard(leaderboard) {
    if (!leaderboardList) {
      return;
    }
    leaderboardList.innerHTML = "";
    const leaders = leaderboard?.leaders ?? [];
    if (!leaders.length) {
      const item = document.createElement("li");
      item.className = "leaderboard-empty";
      item.textContent = "No bots seated yet.";
      leaderboardList.appendChild(item);
      return;
    }

    leaders.forEach((leader) => {
      const seatId = leader.seat_id;
      if (!(seatId in pnlVisibility)) {
        pnlVisibility[seatId] = true;
      }
      const item = document.createElement("li");
      item.className = "leaderboard-item";

      const label = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = Boolean(pnlVisibility[seatId]);
      checkbox.addEventListener("change", () => {
        pnlVisibility[seatId] = checkbox.checked;
        renderPnlChart();
      });
      const dot = document.createElement("span");
      dot.className = `leaderboard-dot leaderboard-dot-${seatId}`;
      const name = document.createElement("span");
      name.textContent = `Seat ${seatId}${leader.bot_name ? ` (${leader.bot_name})` : ""}`;
      label.append(checkbox, dot, name);

      const stat = document.createElement("span");
      const bbPerHand = Number(leader.bb_per_hand) || 0;
      stat.className = "leaderboard-stat";
      stat.textContent = `${bbPerHand.toFixed(2)} BB/hand`;

      item.append(label, stat);
      leaderboardList.appendChild(item);
    });
  }

  async function refreshPnl() {
    if (pnlRefreshing) {
      return;
    }
    pnlRefreshing = true;
    try {
      const params = new URLSearchParams();
      if (pnlLastHandId !== null) {
        params.set("since_hand_id", pnlLastHandId.toString());
      }
      const query = params.toString();
      const response = await window.AppShell.request(`/pnl${query ? `?${query}` : ""}`);
      const entries = response.entries ?? [];
      applyPnlEntries(entries);
      if (response.last_hand_id !== null && response.last_hand_id !== undefined) {
        pnlLastHandId = response.last_hand_id;
      }
      renderPnlChart();
    } catch (error) {
      if (error.statusCode === 401) {
        window.location.assign("/login");
        return;
      }
      console.error(error);
    } finally {
      pnlRefreshing = false;
    }
  }

  function updateMatchStatus(match) {
    latestMatch = match;
    const statusElement = document.getElementById("match-status");
    if (statusElement) {
      statusElement.textContent = `Match: ${match.status}, hands played: ${match.hands_played}`;
    }
  }

  function updateMatchControls(match, seatsReady) {
    const startButton = document.getElementById("start-match");
    const pauseButton = document.getElementById("pause-match");
    const resumeButton = document.getElementById("resume-match");
    const endButton = document.getElementById("end-match");

    if (!startButton || !pauseButton || !resumeButton || !endButton) {
      return;
    }

    startButton.disabled = !(seatsReady && (match.status === "waiting" || match.status === "stopped"));
    pauseButton.disabled = match.status !== "running";
    resumeButton.disabled = match.status !== "paused";
    endButton.disabled = !(match.status === "running" || match.status === "paused");
  }

  function setSeatAssignmentFeedback(message, type = "error") {
    if (!seatAssignmentFeedback) {
      return;
    }
    seatAssignmentFeedback.textContent = message;
    seatAssignmentFeedback.classList.remove("hidden", "is-success", "is-error");
    seatAssignmentFeedback.classList.add(type === "success" ? "is-success" : "is-error");
  }

  function clearSeatAssignmentFeedback() {
    if (!seatAssignmentFeedback) {
      return;
    }
    seatAssignmentFeedback.textContent = "";
    seatAssignmentFeedback.classList.add("hidden");
    seatAssignmentFeedback.classList.remove("is-success", "is-error");
  }

  function closeSeatAssignmentPanel() {
    activeSeatId = null;
    clearSeatAssignmentFeedback();
    seatAssignmentPanel?.classList.add("hidden");
    seatAssignmentPanel?.setAttribute("aria-hidden", "true");
  }

  function renderOwnedBotOptions() {
    if (!seatExistingSelect) {
      return;
    }
    seatExistingSelect.innerHTML = "";
    if (!myBotsCache.length) {
      const emptyOption = document.createElement("option");
      emptyOption.value = "";
      emptyOption.textContent = "No bots uploaded yet";
      seatExistingSelect.appendChild(emptyOption);
      seatExistingSelect.disabled = true;
      if (seatSelectExistingSubmit) {
        seatSelectExistingSubmit.disabled = true;
      }
      return;
    }
    myBotsCache.forEach((bot) => {
      const option = document.createElement("option");
      option.value = bot.bot_id;
      option.textContent = `${bot.name} (${bot.version || "-"})`;
      seatExistingSelect.appendChild(option);
    });
    seatExistingSelect.disabled = false;
    if (seatSelectExistingSubmit) {
      seatSelectExistingSubmit.disabled = false;
    }
  }

  async function loadMyBotsForSeatPanel() {
    const response = await window.AppShell.request("/my/bots");
    myBotsCache = response.bots || [];
    renderOwnedBotOptions();
  }

  async function seatExistingBot(botId) {
    if (!activeSeatId) {
      throw new Error("Select a seat first.");
    }
    await window.AppShell.request(`/tables/default/seats/${activeSeatId}/bot-select`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bot_id: botId }),
    });
  }

  async function createAndSeatBot() {
    if (!activeSeatId) {
      throw new Error("Select a seat first.");
    }
    if (!seatCreateNewForm) {
      throw new Error("Seat form is unavailable.");
    }
    const formData = new FormData(seatCreateNewForm);
    const file = formData.get("bot_file");
    if (!(file instanceof File) || !file.name) {
      throw new Error("Select a .zip bot package.");
    }
    if (!file.name.toLowerCase().endsWith(".zip")) {
      throw new Error("Only .zip bot uploads are supported.");
    }

    const created = await window.AppShell.request("/my/bots", {
      method: "POST",
      body: formData,
    });
    const botId = created?.bot?.bot_id;
    if (!botId) {
      throw new Error("Bot creation failed.");
    }
    await seatExistingBot(botId);
    seatCreateNewForm.reset();
  }

  async function completeSeatAssignment(successMessage) {
    clearHandDetail();
    clearHandHistory();
    await refreshState();
    setSeatAssignmentFeedback(successMessage, "success");
    closeSeatAssignmentPanel();
  }

  function setSeatAssignmentBusy(isBusy) {
    seatAssignmentBusy = isBusy;
    if (seatSelectExistingSubmit) {
      seatSelectExistingSubmit.disabled = isBusy || Boolean(seatExistingSelect?.disabled);
    }
    if (seatCreateNewSubmit) {
      seatCreateNewSubmit.disabled = isBusy;
    }
  }

  async function openSeatAssignmentPanel(seatId) {
    activeSeatId = seatId;
    clearSeatAssignmentFeedback();
    if (seatAssignmentTitle) {
      seatAssignmentTitle.textContent = `Seat ${seatId} Assignment`;
    }
    seatAssignmentPanel?.classList.remove("hidden");
    seatAssignmentPanel?.setAttribute("aria-hidden", "false");
    await loadMyBotsForSeatPanel();
    seatExistingSelect?.focus();
  }

  function renderHands(hands) {
    const list = document.getElementById("hands-list");
    if (!list) {
      return;
    }
    list.innerHTML = "";

    if (!hands.length) {
      const item = document.createElement("li");
      item.textContent = "No hands available yet.";
      list.appendChild(item);
      return;
    }

    hands.forEach((hand) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = hand.summary;
      button.addEventListener("click", () => openHand(hand.hand_id));
      item.appendChild(button);
      list.appendChild(item);
    });
  }

  function setHandHistoryVisibility(isVisible) {
    document.getElementById("hands-body")?.classList.toggle("hidden", !isVisible);
    document.getElementById("hands-list")?.classList.toggle("hidden", !isVisible);
    document.getElementById("hands-controls")?.classList.toggle("hidden", !isVisible);
  }

  function updateHandsPagination() {
    const info = document.getElementById("hands-page-info");
    const prev = document.getElementById("hands-prev");
    const next = document.getElementById("hands-next");
    if (!info || !prev || !next) {
      return;
    }
    if (!handHistoryVisible) {
      info.textContent = "Page 1 of 1";
      prev.disabled = true;
      next.disabled = true;
      return;
    }
    if (!handsTotalHands) {
      info.textContent = "No hands yet.";
      prev.disabled = true;
      next.disabled = true;
      return;
    }
    info.textContent = `Page ${handsPage} of ${handsTotalPages}`;
    prev.disabled = handsPage <= 1;
    next.disabled = handsPage >= handsTotalPages;
  }

  async function loadHandHistoryPage() {
    if (!handHistoryVisible) {
      return;
    }
    const params = new URLSearchParams();
    params.set("page", handsPage.toString());
    params.set("page_size", handsPageSize.toString());
    if (snapshotMaxHandId !== null) {
      params.set("max_hand_id", snapshotMaxHandId.toString());
    }
    const response = await window.AppShell.request(`/hands?${params.toString()}`);
    handsTotalHands = response.total_hands ?? 0;
    handsTotalPages = response.total_pages ?? (handsTotalHands ? Math.ceil(handsTotalHands / handsPageSize) : 0);
    renderHands(response.hands);
    updateHandsPagination();
  }

  async function showHandHistory() {
    const matchResponse = await window.AppShell.request("/match");
    latestMatch = matchResponse.match;
    snapshotMaxHandId = latestMatch.hands_played;
    handHistoryVisible = true;
    handsPage = 1;
    handsPageSize = Number(document.getElementById("hands-page-size")?.value || "100");
    setHandHistoryVisibility(true);
    await loadHandHistoryPage();
  }

  async function openHand(handId) {
    const hand = await window.AppShell.request(`/hands/${handId}`);
    selectedHandId = handId;
    handDetailText = hand.history || "No hand history available.";
    renderHandDetail();
  }

  function clearHandDetail() {
    selectedHandId = null;
    handDetailText = handDetailPlaceholder;
    renderHandDetail();
  }

  function clearHandHistory() {
    handHistoryVisible = false;
    snapshotMaxHandId = null;
    handsPage = 1;
    handsTotalHands = 0;
    handsTotalPages = 0;
    const list = document.getElementById("hands-list");
    if (list) {
      list.innerHTML = "";
    }
    setHandHistoryVisibility(false);
    updateHandsPagination();
  }

  async function refreshState() {
    try {
      const [seats, match, leaderboard] = await Promise.all([
        window.AppShell.request("/seats"),
        window.AppShell.request("/match"),
        window.AppShell.request("/leaderboard"),
      ]);

      const seatsReady = updateSeatStatus(seats.seats);
      updateMatchStatus(match.match);
      updateMatchControls(match.match, seatsReady);
      updateLeaderboard(leaderboard);
      const hasPnlPoints = seatIds.some((seatId) => pnlPoints[seatId]?.length);
      if (match.match.hands_played === 0 && hasPnlPoints) {
        resetPnlState();
      }
      await refreshPnl();
    } catch (error) {
      if (error.statusCode === 401) {
        window.location.assign("/login");
        return;
      }
      console.error(error);
    }
  }

  async function startMatch() {
    await window.AppShell.request("/match/start", { method: "POST" });
    await refreshState();
  }

  async function pauseMatch() {
    await window.AppShell.request("/match/pause", { method: "POST" });
    await refreshState();
  }

  async function resumeMatch() {
    await window.AppShell.request("/match/resume", { method: "POST" });
    await refreshState();
  }

  async function endMatch() {
    await window.AppShell.request("/match/end", { method: "POST" });
    await refreshState();
  }

  async function resetMatch() {
    await window.AppShell.request("/match/reset", { method: "POST" });
    clearHandDetail();
    clearHandHistory();
    resetPnlState();
    await refreshState();
  }

  function wireEvents() {
    seatIds.forEach((seatId) => {
      const seatButton = document.getElementById(`seat-${seatId}-take`);
      if (!seatButton) {
        return;
      }
      seatButton.addEventListener("click", () =>
        openSeatAssignmentPanel(seatId).catch((error) => alert(error.message))
      );
    });

    document.getElementById("seat-assignment-close")?.addEventListener("click", closeSeatAssignmentPanel);
    seatAssignmentPanel?.addEventListener("click", (event) => {
      if (event.target === seatAssignmentPanel) {
        closeSeatAssignmentPanel();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !seatAssignmentPanel?.classList.contains("hidden")) {
        closeSeatAssignmentPanel();
      }
    });
    seatSelectExistingForm?.addEventListener("submit", (event) => {
      event.preventDefault();
      if (seatAssignmentBusy) {
        return;
      }
      const selectedBotId = seatExistingSelect?.value;
      if (!selectedBotId) {
        setSeatAssignmentFeedback("Select one of your bots first.");
        return;
      }
      setSeatAssignmentBusy(true);
      seatExistingBot(selectedBotId)
        .then(() => completeSeatAssignment("Bot seated successfully."))
        .catch((error) => {
          if (error.statusCode === 401) {
            window.location.assign("/login");
            return;
          }
          setSeatAssignmentFeedback(error.message || "Failed to seat bot.");
        })
        .finally(() => setSeatAssignmentBusy(false));
    });
    seatCreateNewForm?.addEventListener("submit", (event) => {
      event.preventDefault();
      if (seatAssignmentBusy) {
        return;
      }
      setSeatAssignmentBusy(true);
      createAndSeatBot()
        .then(() => completeSeatAssignment("New bot created and seated successfully."))
        .catch((error) => {
          if (error.statusCode === 401) {
            window.location.assign("/login");
            return;
          }
          setSeatAssignmentFeedback(error.message || "Failed to create and seat bot.");
        })
        .finally(() => setSeatAssignmentBusy(false));
    });

    document.getElementById("start-match")?.addEventListener("click", () => startMatch().catch((error) => alert(error.message)));
    document.getElementById("pause-match")?.addEventListener("click", () => pauseMatch().catch((error) => alert(error.message)));
    document.getElementById("resume-match")?.addEventListener("click", () => resumeMatch().catch((error) => alert(error.message)));
    document.getElementById("end-match")?.addEventListener("click", () => endMatch().catch((error) => alert(error.message)));
    document.getElementById("reset-match")?.addEventListener("click", () => resetMatch().catch((error) => alert(error.message)));
    document
      .getElementById("hand-history-button")
      ?.addEventListener("click", () => showHandHistory().catch((error) => alert(error.message)));

    document.getElementById("hands-page-size")?.addEventListener("change", (event) => {
      handsPageSize = Number(event.target.value);
      handsPage = 1;
      if (handHistoryVisible) {
        loadHandHistoryPage().catch((error) => alert(error.message));
      } else {
        updateHandsPagination();
      }
    });
    document.getElementById("hands-prev")?.addEventListener("click", () => {
      if (handsPage > 1) {
        handsPage -= 1;
        loadHandHistoryPage().catch((error) => alert(error.message));
      }
    });
    document.getElementById("hands-next")?.addEventListener("click", () => {
      if (handsPage < handsTotalPages) {
        handsPage += 1;
        loadHandHistoryPage().catch((error) => alert(error.message));
      }
    });

    handDetailTabs.logs?.addEventListener("click", () => setHandDetailMode("logs"));
    handDetailTabs.replay?.addEventListener("click", () => setHandDetailMode("replay"));

    handsPageSize = Number(document.getElementById("hands-page-size")?.value || "100");
    updateHandsPagination();
  }

  async function bootstrap() {
    const user = await window.AppShell.getCurrentUser();
    if (!user) {
      return;
    }

    window.AppShell.initHeader("lobby", user);
    setHandDetailMode("logs");
    resetPnlState();
    wireEvents();
    await refreshState();

    if (refreshTimer !== null) {
      window.clearInterval(refreshTimer);
    }
    refreshTimer = window.setInterval(refreshState, 2000);
  }

  bootstrap().catch((error) => {
    console.error(error);
    window.location.assign("/login");
  });
})();
