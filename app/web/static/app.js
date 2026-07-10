const POLL_INTERVAL_MS = 2000;

function setMenuStatusDot(state) {
  // state is one of "checking" | "form" | "connected" - drives the
  // small dot on the hamburger icon so connection status is visible
  // at a glance without opening the menu.
  const dot = document.getElementById("menu-status-dot");
  dot.className = "menu-status-dot menu-status-dot-" + state;
}

function setConnectionState(state) {
  // state is one of "checking" | "form" | "connected".
  document.getElementById("connection-checking").hidden = state !== "checking";
  document.getElementById("connection-form").hidden = state !== "form";
  document.getElementById("connection-connected").hidden = state !== "connected";

  setMenuStatusDot(state);
}

function setTokenMessage(text, kind) {
  const el = document.getElementById("token-message");
  el.textContent = text;
  el.className = "message" + (kind ? " " + kind : "");
}

function showConnectionForm(cancelable) {
  // cancelable is true only when the user opened the form via "Change
  // token" while already connected, so they can back out without
  // losing the existing, still-working connection.
  document.getElementById("connection-cancel-btn").hidden = !cancelable;
  setTokenMessage("", "");
  setConnectionState("form");
}

async function checkTokenStatus() {
  setConnectionState("checking");

  try {
    const response = await fetch("/api/token-status");
    const body = await response.json();

    if (body.valid) {
      setConnectionState("connected");
    } else {
      showConnectionForm(false);
    }

    return body.valid;
  } catch (err) {
    // Transient failure - leave the checking state, next load retries.
    return null;
  }
}

async function updateToken() {
  const field = document.getElementById("f-token");
  const value = field.value.trim();

  if (!value) {
    setTokenMessage("Paste a token first.", "error");
    return;
  }

  const button = document.getElementById("token-update-btn");
  button.disabled = true;
  setTokenMessage("Checking...", "");

  try {
    const response = await fetch("/api/token", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ access_token: value }),
    });

    const body = await response.json();

    if (!response.ok) {
      setTokenMessage(body.detail || "Failed to update token", "error");
      return;
    }

    if (body.valid) {
      field.value = "";
      setConnectionState("connected");
      refreshSyncStatus();
    } else {
      setTokenMessage("Saved, but DhanHQ still rejects it - check the value and try again.", "error");
    }
  } catch (err) {
    setTokenMessage("Request failed: " + err, "error");
  } finally {
    button.disabled = false;
  }
}

function openMenu() {
  document.getElementById("menu-panel").hidden = false;
  document.getElementById("menu-toggle").setAttribute("aria-expanded", "true");
}

function closeMenu() {
  document.getElementById("menu-panel").hidden = true;
  document.getElementById("menu-toggle").setAttribute("aria-expanded", "false");
}

function toggleMenu(event) {
  event.stopPropagation();

  const isOpen = !document.getElementById("menu-panel").hidden;

  if (isOpen) {
    closeMenu();
  } else {
    openMenu();
  }
}

function renderComboGrid(combos) {
  const grid = document.getElementById("combo-grid");
  grid.innerHTML = "";

  for (const combo of combos) {
    const tile = document.createElement("div");
    tile.className = "combo-tile" + (combo.up_to_date ? "" : " combo-tile-stale");

    tile.innerHTML = `
      <div class="combo-tile-top">
        <span class="combo-underlying">${combo.underlying}</span>
        <span class="combo-expiry">${combo.expiry_type}</span>
      </div>
      <div class="combo-date">${combo.latest_date || "no data"}</div>
      <span class="status-pill status-dot ${combo.up_to_date ? "status-COMPLETED" : "status-FAILED"}">
        ${combo.up_to_date ? "Up to date" : "Behind"}
      </span>
    `;

    grid.appendChild(tile);
  }
}

function renderSyncStatus(status) {
  const pill = document.getElementById("sync-status-pill");
  const button = document.getElementById("sync-btn");
  const progress = document.getElementById("sync-progress");

  const syncing = status.queue !== null;

  if (syncing) {
    const job = status.queue.current_job;
    pill.textContent = "Syncing";
    pill.className = "status-pill status-RUNNING";
    button.disabled = true;
    progress.hidden = false;

    const percent = job ? job.percent_complete : 0;
    document.getElementById("sync-progress-fill").style.width = percent + "%";
    document.getElementById("sync-progress-label").textContent = job
      ? `Job ${status.queue.position} of ${status.queue.total}: ${job.underlying} ${job.expiry_type} - ${percent}%`
      : `Job ${status.queue.position} of ${status.queue.total}`;
  } else {
    progress.hidden = true;
    button.disabled = false;

    if (status.up_to_date) {
      pill.textContent = "Data Up to Date";
      pill.className = "status-pill status-COMPLETED";
    } else {
      pill.textContent = "Data Not Up to Date";
      pill.className = "status-pill status-FAILED";
    }
  }

  renderComboGrid(status.combos);
}

async function refreshSyncStatus() {
  try {
    const response = await fetch("/api/sync-status");
    const status = await response.json();
    renderSyncStatus(status);
  } catch (err) {
    // Transient poll failures are not worth surfacing - next poll retries.
  }
}

async function startSync() {
  const button = document.getElementById("sync-btn");
  button.disabled = true;

  try {
    const response = await fetch("/api/sync", { method: "POST" });
    const body = await response.json();

    if (!response.ok) {
      alert(body.detail || "Failed to start sync");
      button.disabled = false;
      return;
    }

    refreshSyncStatus();
  } catch (err) {
    alert("Request failed: " + err);
    button.disabled = false;
  }
}

document.getElementById("menu-toggle").addEventListener("click", toggleMenu);
document.getElementById("menu-panel").addEventListener("click", (event) => event.stopPropagation());
document.addEventListener("click", closeMenu);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeMenu();
  }
});

document.getElementById("token-update-btn").addEventListener("click", updateToken);
document.getElementById("connection-change-btn").addEventListener("click", () => showConnectionForm(true));
document.getElementById("connection-cancel-btn").addEventListener("click", () => setConnectionState("connected"));
document.getElementById("sync-btn").addEventListener("click", startSync);

checkTokenStatus();
refreshSyncStatus();
setInterval(refreshSyncStatus, POLL_INTERVAL_MS);
