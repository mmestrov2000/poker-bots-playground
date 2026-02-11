const apiBase = "/api/v1";
const handDetailPlaceholder = "Select a hand to view full history.";
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
let pnlPointsA = [];
let pnlPointsB = [];
let pnlRefreshing = false;
let seatNames = { A: null, B: null };

const handDetailTabs = {
  logs: document.getElementById("hand-detail-logs"),
  replay: document.getElementById("hand-detail-replay"),
};

const pnlElements = {
  chart: document.getElementById("pnl-chart"),
  lineA: document.getElementById("pnl-line-a"),
  lineB: document.getElementById("pnl-line-b"),
  zeroLine: document.getElementById("pnl-zero-line"),
  empty: document.getElementById("pnl-empty"),
  labelA: document.getElementById("pnl-label-a"),
  labelB: document.getElementById("pnl-label-b"),
  valueA: document.getElementById("pnl-value-a"),
  valueB: document.getElementById("pnl-value-b"),
};

async function request(path, options = {}) {
  const response = await fetch(`${apiBase}${path}`, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

function updateSeatStatus(seats) {
  const byId = Object.fromEntries(seats.map((seat) => [seat.seat_id, seat]));
  const seatA = byId.A;
  const seatB = byId.B;

  const seatReadyA = Boolean(seatA?.ready);
  const seatReadyB = Boolean(seatB?.ready);

  seatNames = {
    A: seatA?.bot_name || null,
    B: seatB?.bot_name || null,
  };

  document.getElementById("seat-a-status").textContent = seatReadyA ? "Seat A taken" : "Seat A empty";
  document.getElementById("seat-b-status").textContent = seatReadyB ? "Seat B taken" : "Seat B empty";

  const seatAButton = document.getElementById("seat-a-take");
  const seatBButton = document.getElementById("seat-b-take");
  const seatAInput = document.getElementById("seat-a-file");
  const seatBInput = document.getElementById("seat-b-file");

  seatAButton.disabled = seatReadyA;
  seatBButton.disabled = seatReadyB;
  seatAInput.disabled = seatReadyA;
  seatBInput.disabled = seatReadyB;

  return seatReadyA && seatReadyB;
}

function formatCurrency(value) {
  const absolute = Math.abs(value);
  return `${value < 0 ? "-" : ""}$${absolute.toFixed(2)}`;
}

function updatePnlValueClass(element, value) {
  element.classList.remove("pnl-positive", "pnl-negative");
  if (value > 0) {
    element.classList.add("pnl-positive");
  } else if (value < 0) {
    element.classList.add("pnl-negative");
  }
}

function updatePnlLegend() {
  const labelA = seatNames.A ? `Seat A (${seatNames.A})` : "Seat A";
  const labelB = seatNames.B ? `Seat B (${seatNames.B})` : "Seat B";
  const valueA = pnlPointsA.length ? pnlPointsA[pnlPointsA.length - 1].value : 0;
  const valueB = pnlPointsB.length ? pnlPointsB[pnlPointsB.length - 1].value : 0;

  pnlElements.labelA.textContent = labelA;
  pnlElements.labelB.textContent = labelB;
  pnlElements.valueA.textContent = formatCurrency(valueA);
  pnlElements.valueB.textContent = formatCurrency(valueB);

  updatePnlValueClass(pnlElements.valueA, valueA);
  updatePnlValueClass(pnlElements.valueB, valueB);
}

function renderHandDetail() {
  const detail = document.getElementById("hand-detail");
  detail.textContent = handDetailMode === "logs" ? handDetailText : "";
}

function setHandDetailMode(mode) {
  handDetailMode = mode;
  if (handDetailTabs.logs) {
    handDetailTabs.logs.classList.toggle("active", mode === "logs");
  }
  if (handDetailTabs.replay) {
    handDetailTabs.replay.classList.toggle("active", mode === "replay");
  }
  renderHandDetail();
}

function renderPnlChart() {
  if (!pnlElements.chart) {
    return;
  }

  const width = 640;
  const height = 280;
  if (!pnlPointsA.length) {
    pnlElements.lineA.setAttribute("d", "");
    pnlElements.lineB.setAttribute("d", "");
    pnlElements.zeroLine.setAttribute("x1", "0");
    pnlElements.zeroLine.setAttribute("x2", width.toString());
    const mid = height / 2;
    pnlElements.zeroLine.setAttribute("y1", mid.toString());
    pnlElements.zeroLine.setAttribute("y2", mid.toString());
    pnlElements.empty.classList.remove("hidden");
    return;
  }

  pnlElements.empty.classList.add("hidden");

  const values = [
    ...pnlPointsA.map((point) => point.value),
    ...pnlPointsB.map((point) => point.value),
  ];
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

  const minHand = pnlPointsA[0].handId;
  const maxHand = pnlPointsA[pnlPointsA.length - 1].handId;
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

  pnlElements.lineA.setAttribute("d", buildPath(pnlPointsA));
  pnlElements.lineB.setAttribute("d", buildPath(pnlPointsB));

  const zeroY = yFor(0);
  pnlElements.zeroLine.setAttribute("x1", "0");
  pnlElements.zeroLine.setAttribute("x2", width.toString());
  pnlElements.zeroLine.setAttribute("y1", zeroY.toFixed(2));
  pnlElements.zeroLine.setAttribute("y2", zeroY.toFixed(2));
}

function resetPnlState() {
  pnlLastHandId = null;
  pnlPointsA = [];
  pnlPointsB = [];
  renderPnlChart();
  updatePnlLegend();
}

function applyPnlEntries(entries) {
  entries.forEach((entry) => {
    const handId = Number(entry.hand_id);
    if (!Number.isFinite(handId)) {
      return;
    }
    const lastHandId = pnlPointsA.length ? pnlPointsA[pnlPointsA.length - 1].handId : 0;
    if (handId <= lastHandId) {
      return;
    }
    const deltaA = Number(entry.delta_a) || 0;
    const deltaB = Number(entry.delta_b) || 0;
    const lastValueA = pnlPointsA.length ? pnlPointsA[pnlPointsA.length - 1].value : 0;
    const lastValueB = pnlPointsB.length ? pnlPointsB[pnlPointsB.length - 1].value : 0;

    pnlPointsA.push({ handId, value: lastValueA + deltaA });
    pnlPointsB.push({ handId, value: lastValueB + deltaB });
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
    const response = await request(`/pnl${query ? `?${query}` : ""}`);
    const entries = response.entries ?? [];
    applyPnlEntries(entries);
    if (response.last_hand_id !== null && response.last_hand_id !== undefined) {
      pnlLastHandId = response.last_hand_id;
    }
    renderPnlChart();
    updatePnlLegend();
  } catch (error) {
    console.error(error);
  } finally {
    pnlRefreshing = false;
  }
}

function updateMatchStatus(match) {
  latestMatch = match;
  document.getElementById("match-status").textContent = `Match: ${match.status}, hands played: ${match.hands_played}`;
}

function updateMatchControls(match, seatsReady) {
  const startButton = document.getElementById("start-match");
  const pauseButton = document.getElementById("pause-match");
  const resumeButton = document.getElementById("resume-match");
  const endButton = document.getElementById("end-match");

  startButton.disabled = !(seatsReady && (match.status === "waiting" || match.status === "stopped"));
  pauseButton.disabled = match.status !== "running";
  resumeButton.disabled = match.status !== "paused";
  endButton.disabled = !(match.status === "running" || match.status === "paused");
}

async function uploadSeat(seatId) {
  const input = document.getElementById(`seat-${seatId.toLowerCase()}-file`);
  const file = input.files?.[0];
  if (!file) {
    alert(`Select a .zip file for Seat ${seatId} first.`);
    return;
  }

  const formData = new FormData();
  formData.append("bot_file", file);

  await request(`/seats/${seatId}/bot`, {
    method: "POST",
    body: formData,
  });

  input.value = "";
  clearHandDetail();
  clearHandHistory();
  await refreshState();
}

function renderHands(hands) {
  const list = document.getElementById("hands-list");
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
  const body = document.getElementById("hands-body");
  const list = document.getElementById("hands-list");
  const controls = document.getElementById("hands-controls");
  body.classList.toggle("hidden", !isVisible);
  list.classList.toggle("hidden", !isVisible);
  controls.classList.toggle("hidden", !isVisible);
}

function updateHandsPagination() {
  const info = document.getElementById("hands-page-info");
  const prev = document.getElementById("hands-prev");
  const next = document.getElementById("hands-next");
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
  const response = await request(`/hands?${params.toString()}`);
  handsTotalHands = response.total_hands ?? 0;
  handsTotalPages = response.total_pages ?? (handsTotalHands ? Math.ceil(handsTotalHands / handsPageSize) : 0);
  renderHands(response.hands);
  updateHandsPagination();
}

async function showHandHistory() {
  const matchResponse = await request("/match");
  latestMatch = matchResponse.match;
  snapshotMaxHandId = latestMatch.hands_played;
  handHistoryVisible = true;
  handsPage = 1;
  handsPageSize = Number(document.getElementById("hands-page-size").value);
  setHandHistoryVisibility(true);
  await loadHandHistoryPage();
}

async function openHand(handId) {
  const hand = await request(`/hands/${handId}`);
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
  list.innerHTML = "";
  setHandHistoryVisibility(false);
  updateHandsPagination();
}

async function refreshState() {
  try {
    const [seats, match] = await Promise.all([request("/seats"), request("/match")]);

    const seatsReady = updateSeatStatus(seats.seats);
    updateMatchStatus(match.match);
    updateMatchControls(match.match, seatsReady);
    if (match.match.hands_played === 0 && (pnlPointsA.length || pnlPointsB.length)) {
      resetPnlState();
    }
    updatePnlLegend();
    await refreshPnl();
  } catch (error) {
    console.error(error);
  }
}

async function startMatch() {
  await request("/match/start", { method: "POST" });
  await refreshState();
}

async function pauseMatch() {
  await request("/match/pause", { method: "POST" });
  await refreshState();
}

async function resumeMatch() {
  await request("/match/resume", { method: "POST" });
  await refreshState();
}

async function endMatch() {
  await request("/match/end", { method: "POST" });
  await refreshState();
}

async function resetMatch() {
  await request("/match/reset", { method: "POST" });
  clearHandDetail();
  clearHandHistory();
  resetPnlState();
  await refreshState();
}

function wireEvents() {
  const seatAInput = document.getElementById("seat-a-file");
  const seatBInput = document.getElementById("seat-b-file");
  const logsTab = document.getElementById("hand-detail-logs");
  const replayTab = document.getElementById("hand-detail-replay");

  document.getElementById("seat-a-take").addEventListener("click", () => seatAInput.click());
  document.getElementById("seat-b-take").addEventListener("click", () => seatBInput.click());
  seatAInput.addEventListener("change", () => uploadSeat("A").catch((error) => alert(error.message)));
  seatBInput.addEventListener("change", () => uploadSeat("B").catch((error) => alert(error.message)));

  document.getElementById("start-match").addEventListener("click", () => startMatch().catch((error) => alert(error.message)));
  document.getElementById("pause-match").addEventListener("click", () => pauseMatch().catch((error) => alert(error.message)));
  document.getElementById("resume-match").addEventListener("click", () => resumeMatch().catch((error) => alert(error.message)));
  document.getElementById("end-match").addEventListener("click", () => endMatch().catch((error) => alert(error.message)));
  document.getElementById("reset-match").addEventListener("click", () => resetMatch().catch((error) => alert(error.message)));
  document.getElementById("hand-history-button").addEventListener("click", () => showHandHistory().catch((error) => alert(error.message)));
  document.getElementById("hands-page-size").addEventListener("change", (event) => {
    handsPageSize = Number(event.target.value);
    handsPage = 1;
    if (handHistoryVisible) {
      loadHandHistoryPage().catch((error) => alert(error.message));
    } else {
      updateHandsPagination();
    }
  });
  document.getElementById("hands-prev").addEventListener("click", () => {
    if (handsPage > 1) {
      handsPage -= 1;
      loadHandHistoryPage().catch((error) => alert(error.message));
    }
  });
  document.getElementById("hands-next").addEventListener("click", () => {
    if (handsPage < handsTotalPages) {
      handsPage += 1;
      loadHandHistoryPage().catch((error) => alert(error.message));
    }
  });
  if (logsTab) {
    logsTab.addEventListener("click", () => setHandDetailMode("logs"));
  }
  if (replayTab) {
    replayTab.addEventListener("click", () => setHandDetailMode("replay"));
  }
  handsPageSize = Number(document.getElementById("hands-page-size").value);
  updateHandsPagination();
}

wireEvents();
setHandDetailMode("logs");
resetPnlState();
refreshState();
setInterval(refreshState, 2000);
