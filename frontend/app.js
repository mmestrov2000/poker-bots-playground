const apiBase = "/api/v1";
let latestHandId = null;

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
  document.getElementById("hand-detail").textContent = hand.history || "No hand history available.";
}

async function refreshState() {
  try {
    const previousLatestHandId = latestHandId;
    const [seats, match, hands] = await Promise.all([
      request("/seats"),
      request("/match"),
      request("/hands?limit=50"),
    ]);

    updateSeatStatus(seats.seats);
    updateMatchStatus(match.match);
    renderHands(hands.hands);

    latestHandId = hands.hands.length > 0 ? hands.hands[hands.hands.length - 1].hand_id : null;
    if (latestHandId && previousLatestHandId !== latestHandId) {
      await openHand(latestHandId);
    }
  } catch (error) {
    console.error(error);
  }
}

async function resetMatch() {
  await request("/match/reset", { method: "POST" });
  document.getElementById("hand-detail").textContent = "Select a hand to view full history.";
  latestHandId = null;
  await refreshState();
}

function wireEvents() {
  document.getElementById("seat-a-upload").addEventListener("click", () => uploadSeat("A").catch((error) => alert(error.message)));
  document.getElementById("seat-b-upload").addEventListener("click", () => uploadSeat("B").catch((error) => alert(error.message)));
  document.getElementById("reset-match").addEventListener("click", () => resetMatch().catch((error) => alert(error.message)));
}

wireEvents();
refreshState();
setInterval(refreshState, 2000);
