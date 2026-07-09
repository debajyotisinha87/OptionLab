const POLL_INTERVAL_MS = 2000;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function loadUnderlyings() {
  const select = document.getElementById("f-underlying");
  const response = await fetch("/api/underlyings");
  const underlyings = await response.json();

  select.innerHTML = "";
  for (const underlying of underlyings) {
    const option = document.createElement("option");
    option.value = underlying;
    option.textContent = underlying;
    select.appendChild(option);
  }
}

function setFormMessage(text, kind) {
  const el = document.getElementById("form-message");
  el.textContent = text;
  el.className = "message" + (kind ? " " + kind : "");
}

async function submitJob(event) {
  event.preventDefault();

  const optionTypes = Array.from(
    document.querySelectorAll('input[name="option-type"]:checked')
  ).map((el) => el.value);

  const payload = {
    underlying: document.getElementById("f-underlying").value,
    expiry_type: document.getElementById("f-expiry-type").value,
    option_types: optionTypes,
    start_date: document.getElementById("f-start-date").value,
    end_date: document.getElementById("f-end-date").value,
    job_id: document.getElementById("f-job-id").value || null,
    parquet_output_dir: document.getElementById("f-parquet-dir").value || null,
  };

  setFormMessage("Starting...", "");

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const body = await response.json();

    if (!response.ok) {
      const detail = body.detail || JSON.stringify(body);
      setFormMessage(typeof detail === "string" ? detail : formatValidationError(detail), "error");
      return;
    }

    setFormMessage(`Started job ${body.job_id}`, "success");
    refreshJobs();
  } catch (err) {
    setFormMessage("Request failed: " + err, "error");
  }
}

function formatValidationError(detail) {
  if (Array.isArray(detail)) {
    return detail.map((e) => e.msg).join("; ");
  }
  return String(detail);
}

async function browseFolder() {
  const field = document.getElementById("f-parquet-dir");

  try {
    const response = await fetch("/api/browse-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initial_dir: field.value || null }),
    });

    const body = await response.json();

    if (!response.ok) {
      alert(body.detail || "Failed to open folder picker");
      return;
    }

    if (body.path) {
      field.value = body.path;
    }
    // body.path is null when the user cancels - leave the field as-is.
  } catch (err) {
    alert("Request failed: " + err);
  }
}

async function resumeJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/resume`, {
      method: "POST",
    });
    const body = await response.json();
    if (!response.ok) {
      alert(body.detail || "Failed to resume job");
      return;
    }
    refreshJobs();
  } catch (err) {
    alert("Request failed: " + err);
  }
}

function renderJobs(jobs) {
  const tbody = document.getElementById("jobs-body");

  if (jobs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">No jobs yet.</td></tr>';
    return;
  }

  tbody.innerHTML = "";

  for (const job of jobs) {
    const tr = document.createElement("tr");
    tr.dataset.status = job.status;

    const resumeButton =
      (job.status === "FAILED" || job.status === "RUNNING") && !job.is_running
        ? `<button class="resume-btn" data-job-id="${escapeHtml(job.job_id)}">Resume</button>`
        : "";

    tr.innerHTML = `
      <td>${escapeHtml(job.job_id)}</td>
      <td>${job.underlying}</td>
      <td><span class="status-pill status-${job.status}">${job.status}</span></td>
      <td>
        <div class="progress-bar">
          <div class="progress-bar-fill" style="width:${job.percent_complete}%"></div>
        </div>
        <small>${job.percent_complete}% (${job.completed_batches + job.failed_batches}/${job.total_batches})</small>
      </td>
      <td>${job.total_rows ?? 0}</td>
      <td>${job.start_date} &rarr; ${job.end_date}</td>
      <td>${resumeButton}</td>
    `;

    tbody.appendChild(tr);
  }

  for (const button of tbody.querySelectorAll(".resume-btn")) {
    button.addEventListener("click", () => resumeJob(button.dataset.jobId));
  }
}

async function refreshJobs() {
  try {
    const response = await fetch("/api/jobs");
    const jobs = await response.json();
    renderJobs(jobs);
  } catch (err) {
    // Transient poll failures are not worth surfacing to the user -
    // the next poll will retry.
  }
}

function setTokenMessage(text, kind) {
  const el = document.getElementById("token-message");
  el.textContent = text;
  el.className = "message" + (kind ? " " + kind : "");
}

async function checkTokenStatus() {
  try {
    const response = await fetch("/api/token-status");
    const body = await response.json();
    document.getElementById("token-card").hidden = body.valid;
    return body.valid;
  } catch (err) {
    // Leave the token card in its current state on a transient failure.
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
      setTokenMessage("Token updated and verified.", "success");
      document.getElementById("token-card").hidden = true;
      refreshSyncStatus();
    } else {
      setTokenMessage("Saved, but DhanHQ still rejects it - check the value and try again.", "error");
    }
  } catch (err) {
    setTokenMessage("Request failed: " + err, "error");
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
    refreshJobs();
  } catch (err) {
    alert("Request failed: " + err);
    button.disabled = false;
  }
}

document.getElementById("job-form").addEventListener("submit", submitJob);
document.getElementById("f-parquet-browse").addEventListener("click", browseFolder);
document.getElementById("token-update-btn").addEventListener("click", updateToken);
document.getElementById("sync-btn").addEventListener("click", startSync);

loadUnderlyings();
refreshJobs();
checkTokenStatus();
refreshSyncStatus();
setInterval(refreshJobs, POLL_INTERVAL_MS);
setInterval(refreshSyncStatus, POLL_INTERVAL_MS);
