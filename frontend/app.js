const apiBase = "/api/v1";
const handDetailPlaceholder = "Select a hand to view full history.";
let selectedHandId = null;

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

function updateMatchStatus(match) {
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
  await refreshState();
}

function renderHands(hands) {
  const list = document.getElementById("hands-list");
  list.innerHTML = "";

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

async function openHand(handId) {
  const hand = await request(`/hands/${handId}`);
  selectedHandId = handId;
  document.getElementById("hand-detail").textContent = hand.history || "No hand history available.";
}

function clearHandDetail() {
  selectedHandId = null;
  document.getElementById("hand-detail").textContent = handDetailPlaceholder;
}

async function refreshState() {
  try {
    const [seats, match, hands] = await Promise.all([
      request("/seats"),
      request("/match"),
      request("/hands?limit=50"),
    ]);

    const seatsReady = updateSeatStatus(seats.seats);
    updateMatchStatus(match.match);
    updateMatchControls(match.match, seatsReady);
    renderHands(hands.hands);
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
  await refreshState();
}

function wireEvents() {
  const seatAInput = document.getElementById("seat-a-file");
  const seatBInput = document.getElementById("seat-b-file");

  document.getElementById("seat-a-take").addEventListener("click", () => seatAInput.click());
  document.getElementById("seat-b-take").addEventListener("click", () => seatBInput.click());
  seatAInput.addEventListener("change", () => uploadSeat("A").catch((error) => alert(error.message)));
  seatBInput.addEventListener("change", () => uploadSeat("B").catch((error) => alert(error.message)));

  document.getElementById("start-match").addEventListener("click", () => startMatch().catch((error) => alert(error.message)));
  document.getElementById("pause-match").addEventListener("click", () => pauseMatch().catch((error) => alert(error.message)));
  document.getElementById("resume-match").addEventListener("click", () => resumeMatch().catch((error) => alert(error.message)));
  document.getElementById("end-match").addEventListener("click", () => endMatch().catch((error) => alert(error.message)));
  document.getElementById("reset-match").addEventListener("click", () => resetMatch().catch((error) => alert(error.message)));
}

wireEvents();
refreshState();
setInterval(refreshState, 2000);
