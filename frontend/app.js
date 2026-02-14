const apiBase = "/api/v1";
const ROUTES = {
  login: "/login",
  lobby: "/lobby",
  myBots: "/my-bots",
};
const protectedRoutes = new Set([ROUTES.lobby, ROUTES.myBots]);
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
let authUser = null;
let authPending = false;
let authMode = "login";
let lobbyRefreshTimer = null;
let myBotsLoading = false;

const loginPage = document.getElementById("login-page");
const appShell = document.getElementById("app-shell");
const authUserLabel = document.getElementById("auth-user");

const loginForm = document.getElementById("login-form");
const loginUsername = document.getElementById("login-username");
const loginPassword = document.getElementById("login-password");
const loginSubmit = document.getElementById("login-submit");
const loginUsernameError = document.getElementById("login-username-error");
const loginPasswordError = document.getElementById("login-password-error");
const loginFormError = document.getElementById("login-form-error");
const authSubtitle = document.getElementById("auth-subtitle");
const authModeLoginButton = document.getElementById("auth-mode-login");
const authModeRegisterButton = document.getElementById("auth-mode-register");

const lobbyPage = document.getElementById("page-lobby");
const myBotsPage = document.getElementById("page-my-bots");
const myBotsState = document.getElementById("my-bots-state");
const myBotsList = document.getElementById("my-bots-list");
const navLobby = document.getElementById("nav-lobby");
const navMyBots = document.getElementById("nav-my-bots");

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

function normalizeHashRoute() {
  const raw = window.location.hash.replace(/^#/, "").trim();
  if (!raw) {
    return null;
  }
  return raw.startsWith("/") ? raw : `/${raw}`;
}

function setRoute(route, { replace = false } = {}) {
  const targetHash = `#${route}`;
  if (replace) {
    window.history.replaceState(null, "", targetHash);
    return;
  }
  if (window.location.hash !== targetHash) {
    window.location.hash = targetHash;
  }
}

function getCurrentRoute() {
  return normalizeHashRoute() || ROUTES.lobby;
}

function setTextError(element, message) {
  if (!element) {
    return;
  }
  if (message) {
    element.textContent = message;
    element.classList.remove("hidden");
    return;
  }
  element.textContent = "";
  element.classList.add("hidden");
}

function setLoginBusy(isBusy) {
  authPending = isBusy;
  if (loginSubmit) {
    loginSubmit.disabled = isBusy;
    loginSubmit.textContent = isBusy
      ? authMode === "register"
        ? "Creating account..."
        : "Logging in..."
      : authMode === "register"
        ? "Create account"
        : "Login";
  }
}

function resetLoginErrors() {
  setTextError(loginUsernameError, "");
  setTextError(loginPasswordError, "");
  setTextError(loginFormError, "");
  loginUsername?.classList.remove("input-error");
  loginPassword?.classList.remove("input-error");
}

function validateLoginForm() {
  resetLoginErrors();
  const username = loginUsername?.value.trim() || "";
  const password = loginPassword?.value || "";
  let valid = true;

  if (!username) {
    valid = false;
    loginUsername?.classList.add("input-error");
    setTextError(loginUsernameError, "Username is required.");
  }

  if (!password) {
    valid = false;
    loginPassword?.classList.add("input-error");
    setTextError(loginPasswordError, "Password is required.");
  }

  return { valid, username, password };
}

function setAuthMode(mode) {
  authMode = mode;
  authModeLoginButton?.classList.toggle("active", mode === "login");
  authModeRegisterButton?.classList.toggle("active", mode === "register");
  if (authSubtitle) {
    authSubtitle.textContent =
      mode === "register"
        ? "Create an account to access Lobby and My Bots."
        : "Sign in to access Lobby and My Bots.";
  }
  resetLoginErrors();
  setLoginBusy(false);
}

function showLoginPage() {
  loginPage?.classList.remove("hidden");
  appShell?.classList.add("hidden");
}

function showAppShell() {
  loginPage?.classList.add("hidden");
  appShell?.classList.remove("hidden");
}

function setActiveNav(route) {
  navLobby?.classList.toggle("active", route === ROUTES.lobby);
  navMyBots?.classList.toggle("active", route === ROUTES.myBots);
}

function renderProtectedPage(route) {
  showAppShell();
  authUserLabel.textContent = authUser ? `Signed in as ${authUser.username}` : "";
  setActiveNav(route);
  lobbyPage.classList.toggle("hidden", route !== ROUTES.lobby);
  myBotsPage.classList.toggle("hidden", route !== ROUTES.myBots);
}

async function request(path, options = {}) {
  const requestOptions = { ...options };
  if (!requestOptions.credentials) {
    requestOptions.credentials = "same-origin";
  }
  const response = await fetch(`${apiBase}${path}`, requestOptions);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail;
    if (typeof detail === "string") {
      const error = new Error(detail);
      error.statusCode = response.status;
      error.detail = detail;
      throw error;
    }
    const message = detail?.message || payload.message || `Request failed: ${response.status}`;
    const error = new Error(message);
    error.statusCode = response.status;
    error.detail = detail;
    throw error;
  }
  return response.json();
}

async function fetchAuthenticatedUser() {
  try {
    const response = await request("/auth/me");
    authUser = response.user;
    return authUser;
  } catch (error) {
    if (error.statusCode === 401) {
      authUser = null;
      return null;
    }
    throw error;
  }
}

function stopLobbyRefreshTimer() {
  if (lobbyRefreshTimer !== null) {
    window.clearInterval(lobbyRefreshTimer);
    lobbyRefreshTimer = null;
  }
}

function ensureLobbyRefreshTimer() {
  if (lobbyRefreshTimer !== null) {
    return;
  }
  lobbyRefreshTimer = window.setInterval(() => {
    if (getCurrentRoute() === ROUTES.lobby && authUser) {
      refreshState();
    }
  }, 2000);
}

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
    const seatInput = document.getElementById(`seat-${seatId}-file`);
    if (seatButton) {
      seatButton.disabled = seatReady;
    }
    if (seatInput) {
      seatInput.disabled = seatReady;
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

  const values = visibleSeries.flatMap((seatId) =>
    pnlPoints[seatId].map((point) => point.value)
  );
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
    const response = await request(`/pnl${query ? `?${query}` : ""}`);
    const entries = response.entries ?? [];
    applyPnlEntries(entries);
    if (response.last_hand_id !== null && response.last_hand_id !== undefined) {
      pnlLastHandId = response.last_hand_id;
    }
    renderPnlChart();
  } catch (error) {
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

async function uploadSeat(seatId) {
  const input = document.getElementById(`seat-${seatId}-file`);
  const file = input?.files?.[0];
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
  const body = document.getElementById("hands-body");
  const list = document.getElementById("hands-list");
  const controls = document.getElementById("hands-controls");
  body?.classList.toggle("hidden", !isVisible);
  list?.classList.toggle("hidden", !isVisible);
  controls?.classList.toggle("hidden", !isVisible);
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
  handsPageSize = Number(document.getElementById("hands-page-size")?.value || "100");
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
  if (list) {
    list.innerHTML = "";
  }
  setHandHistoryVisibility(false);
  updateHandsPagination();
}

async function refreshState() {
  if (!authUser || getCurrentRoute() !== ROUTES.lobby) {
    return;
  }
  try {
    const [seats, match, leaderboard] = await Promise.all([
      request("/seats"),
      request("/match"),
      request("/leaderboard"),
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
      authUser = null;
      stopLobbyRefreshTimer();
      setRoute(ROUTES.login, { replace: true });
      await renderRoute();
      return;
    }
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

async function loadMyBots() {
  if (myBotsLoading) {
    return;
  }
  myBotsLoading = true;
  myBotsState.textContent = "Loading bots...";
  myBotsState.classList.remove("hidden");
  myBotsList.classList.add("hidden");
  try {
    const response = await request("/my/bots");
    renderMyBotsList(response.bots || []);
  } catch (error) {
    if (error.statusCode === 401) {
      authUser = null;
      setRoute(ROUTES.login, { replace: true });
      await renderRoute();
      return;
    }
    myBotsList.classList.add("hidden");
    myBotsState.textContent = error.message || "Failed to load bots.";
    myBotsState.classList.remove("hidden");
  } finally {
    myBotsLoading = false;
  }
}

async function loginWithCredentials(username, password) {
  const response = await request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  authUser = response.user;
  return response.user;
}

async function registerWithCredentials(username, password) {
  const response = await request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  authUser = response.user;
  return response.user;
}

async function handleLoginSubmit(event) {
  event.preventDefault();
  if (authPending) {
    return;
  }

  const { valid, username, password } = validateLoginForm();
  if (!valid) {
    return;
  }

  setLoginBusy(true);
  try {
    if (authMode === "register") {
      await registerWithCredentials(username, password);
    } else {
      await loginWithCredentials(username, password);
    }
    resetLoginErrors();
    loginPassword.value = "";
    setRoute(ROUTES.lobby, { replace: true });
    await renderRoute();
  } catch (error) {
    if (error.statusCode === 401) {
      setTextError(loginFormError, "Invalid username or password.");
    } else if (error.statusCode === 409) {
      setTextError(loginFormError, "Username is already taken.");
    } else if (error.statusCode === 429) {
      const retry = Number(error.detail?.retry_after_seconds);
      const detail = Number.isFinite(retry)
        ? `Too many attempts. Retry in ${retry} seconds.`
        : "Too many attempts. Please retry later.";
      setTextError(loginFormError, detail);
    } else {
      setTextError(loginFormError, error.message || "Login failed.");
    }
  } finally {
    setLoginBusy(false);
  }
}

async function logout() {
  try {
    await request("/auth/logout", { method: "POST" });
  } catch (error) {
    if (error.statusCode !== 401) {
      console.error(error);
    }
  }
  authUser = null;
  stopLobbyRefreshTimer();
  setRoute(ROUTES.login, { replace: true });
  await renderRoute();
}

async function renderRoute() {
  const route = getCurrentRoute();

  if (route === ROUTES.login) {
    stopLobbyRefreshTimer();
    if (authUser) {
      setRoute(ROUTES.lobby, { replace: true });
      return renderRoute();
    }
    showLoginPage();
    setActiveNav(route);
    return;
  }

  if (protectedRoutes.has(route)) {
    if (!authUser) {
      stopLobbyRefreshTimer();
      setRoute(ROUTES.login, { replace: true });
      return renderRoute();
    }

    renderProtectedPage(route);
    if (route === ROUTES.lobby) {
      ensureLobbyRefreshTimer();
      await refreshState();
    } else {
      stopLobbyRefreshTimer();
      await loadMyBots();
    }
    return;
  }

  if (!authUser) {
    setRoute(ROUTES.login, { replace: true });
    return renderRoute();
  }
  setRoute(ROUTES.lobby, { replace: true });
  return renderRoute();
}

function wireEvents() {
  authModeLoginButton?.addEventListener("click", () => setAuthMode("login"));
  authModeRegisterButton?.addEventListener("click", () => setAuthMode("register"));

  loginForm?.addEventListener("submit", (event) => {
    handleLoginSubmit(event).catch((error) => {
      setTextError(loginFormError, error.message || "Login failed.");
      setLoginBusy(false);
    });
  });

  const logsTab = document.getElementById("hand-detail-logs");
  const replayTab = document.getElementById("hand-detail-replay");

  seatIds.forEach((seatId) => {
    const seatInput = document.getElementById(`seat-${seatId}-file`);
    const seatButton = document.getElementById(`seat-${seatId}-take`);
    if (!seatInput || !seatButton) {
      return;
    }
    seatButton.addEventListener("click", () => seatInput.click());
    seatInput.addEventListener("change", () =>
      uploadSeat(seatId).catch((error) => alert(error.message))
    );
  });

  document
    .getElementById("start-match")
    ?.addEventListener("click", () => startMatch().catch((error) => alert(error.message)));
  document
    .getElementById("pause-match")
    ?.addEventListener("click", () => pauseMatch().catch((error) => alert(error.message)));
  document
    .getElementById("resume-match")
    ?.addEventListener("click", () => resumeMatch().catch((error) => alert(error.message)));
  document
    .getElementById("end-match")
    ?.addEventListener("click", () => endMatch().catch((error) => alert(error.message)));
  document
    .getElementById("reset-match")
    ?.addEventListener("click", () => resetMatch().catch((error) => alert(error.message)));
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

  if (logsTab) {
    logsTab.addEventListener("click", () => setHandDetailMode("logs"));
  }
  if (replayTab) {
    replayTab.addEventListener("click", () => setHandDetailMode("replay"));
  }

  document.getElementById("logout-button")?.addEventListener("click", () => {
    logout().catch((error) => console.error(error));
  });

  window.addEventListener("hashchange", () => {
    renderRoute().catch((error) => console.error(error));
  });

  handsPageSize = Number(document.getElementById("hands-page-size")?.value || "100");
  updateHandsPagination();
}

async function bootstrap() {
  wireEvents();
  setAuthMode("login");
  setHandDetailMode("logs");
  resetPnlState();
  await fetchAuthenticatedUser();

  if (normalizeHashRoute() === null) {
    setRoute(authUser ? ROUTES.lobby : ROUTES.login, { replace: true });
  }

  await renderRoute();
}

bootstrap().catch((error) => {
  console.error(error);
  setTextError(loginFormError, "Failed to initialize application.");
  showLoginPage();
});
