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

document.getElementById("job-form").addEventListener("submit", submitJob);
document.getElementById("f-parquet-browse").addEventListener("click", browseFolder);

loadUnderlyings();
refreshJobs();
setInterval(refreshJobs, POLL_INTERVAL_MS);
