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

  document.getElementById("seat-a-status").textContent = `Status: ${seatA.ready ? `ready (${seatA.bot_name})` : "empty"}`;
  document.getElementById("seat-b-status").textContent = `Status: ${seatB.ready ? `ready (${seatB.bot_name})` : "empty"}`;
}

function updateMatchStatus(match) {
  latestMatch = match;
  document.getElementById("match-status").textContent = `Match: ${match.status}, hands played: ${match.hands_played}`;
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
  const list = document.getElementById("hands-list");
  const controls = document.getElementById("hands-controls");
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
  document.getElementById("hand-detail").textContent = hand.history || "No hand history available.";
}

function clearHandDetail() {
  selectedHandId = null;
  document.getElementById("hand-detail").textContent = handDetailPlaceholder;
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

    updateSeatStatus(seats.seats);
    updateMatchStatus(match.match);
  } catch (error) {
    console.error(error);
  }
}

async function resetMatch() {
  await request("/match/reset", { method: "POST" });
  clearHandDetail();
  clearHandHistory();
  await refreshState();
}

function wireEvents() {
  document.getElementById("seat-a-upload").addEventListener("click", () => uploadSeat("A").catch((error) => alert(error.message)));
  document.getElementById("seat-b-upload").addEventListener("click", () => uploadSeat("B").catch((error) => alert(error.message)));
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
  handsPageSize = Number(document.getElementById("hands-page-size").value);
  updateHandsPagination();
}

wireEvents();
refreshState();
setInterval(refreshState, 2000);
