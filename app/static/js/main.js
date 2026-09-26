(function () {
  "use strict";

  const form = document.getElementById("search-form");
  if (!form) return; // not on the dashboard page

  const findBtn = document.getElementById("find-btn");
  const statusPanel = document.getElementById("status-panel");
  const statusText = document.getElementById("status-text");
  const progressFill = document.getElementById("progress-fill");
  const resultsGrid = document.getElementById("results-grid");
  const resultsMeta = document.getElementById("results-meta");
  const cardTemplate = document.getElementById("job-card-template");

  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

  let pollTimer = null;

  function setBusy(isBusy) {
    findBtn.disabled = isBusy;
    findBtn.classList.toggle("is-busy", isBusy);
  }

  function showStatus(text, pct) {
    statusPanel.hidden = false;
    statusText.textContent = text;
    if (typeof pct === "number") {
      progressFill.style.width = Math.max(4, Math.min(100, pct)) + "%";
    }
  }

  function hideStatus() {
    statusPanel.hidden = true;
    progressFill.style.width = "0%";
  }

  function renderJobs(jobs) {
    resultsGrid.innerHTML = "";
    if (!jobs || jobs.length === 0) {
      resultsMeta.hidden = false;
      resultsMeta.textContent = "No postings found for that combination of filters. Try widening the date range or country.";
      return;
    }

    resultsMeta.hidden = false;
    resultsMeta.textContent = `${jobs.length} posting${jobs.length === 1 ? "" : "s"} found`;

    jobs.forEach((job, i) => {
      const node = cardTemplate.content.cloneNode(true);
      node.querySelector(".job-title").textContent = job.title || "Untitled role";
      node.querySelector(".job-date").textContent = job.post_date || "";
      node.querySelector(".job-company").textContent = job.company || "N/A";
      node.querySelector(".job-location").textContent = job.location || "";
      node.querySelector(".job-snippet").textContent = job.description_snippet || "";
      const link = node.querySelector(".job-link");
      link.href = job.full_url || "#";

      const article = node.querySelector(".job-card");
      article.style.animationDelay = `${Math.min(i, 12) * 40}ms`;

      resultsGrid.appendChild(node);
    });
  }

  async function pollStatus(jobId, meta) {
    try {
      const params = new URLSearchParams({
        search_key: meta.search_key,
        keyword: meta.keyword,
        country: meta.country,
        date_posted_key: meta.date_posted,
        workplace_key: meta.workplace_type,
      });
      const resp = await fetch(`/api/search/status/${jobId}?${params.toString()}`);
      const data = await resp.json();

      if (data.status === "running") {
        const pct = data.total ? (data.progress / data.total) * 100 : 10;
        showStatus(`Found ${data.progress || 0} of up to ${data.total || meta.max_results} postings so far…`, pct);
        pollTimer = setTimeout(() => pollStatus(jobId, meta), 1500);
        return;
      }

      if (data.status === "error") {
        hideStatus();
        setBusy(false);
        resultsMeta.hidden = false;
        resultsMeta.textContent = "Something went wrong while searching. Please try again.";
        return;
      }

      if (data.status === "done") {
        showStatus("Done", 100);
        setTimeout(hideStatus, 300);
        setBusy(false);
        renderJobs(data.jobs);
        return;
      }

      // not_found or unknown
      hideStatus();
      setBusy(false);
    } catch (err) {
      hideStatus();
      setBusy(false);
      resultsMeta.hidden = false;
      resultsMeta.textContent = "Lost connection while searching. Please try again.";
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (pollTimer) clearTimeout(pollTimer);

    const payload = {
      keyword: document.getElementById("keyword").value.trim(),
      country: document.getElementById("country").value,
      date_posted: document.getElementById("date_posted").value,
      workplace_type: document.getElementById("workplace_type").value,
      max_results: parseInt(document.getElementById("max_results").value, 10) || 25,
    };

    if (!payload.keyword) return;

    setBusy(true);
    resultsMeta.hidden = true;
    resultsGrid.innerHTML = "";
    showStatus("Starting search…", 6);

    try {
      const resp = await fetch("/api/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
        },
        body: JSON.stringify(payload),
      });

      if (resp.status === 429) {
        hideStatus();
        setBusy(false);
        resultsMeta.hidden = false;
        resultsMeta.textContent = "You've hit the search limit for now — please wait a bit and try again.";
        return;
      }

      const data = await resp.json();

      if (!resp.ok) {
        hideStatus();
        setBusy(false);
        resultsMeta.hidden = false;
        resultsMeta.textContent = data.error || "Please check your filters and try again.";
        return;
      }

      if (data.cached) {
        showStatus("Loaded from today's cache", 100);
        setTimeout(hideStatus, 250);
        setBusy(false);
        renderJobs(data.jobs);
        return;
      }

      pollStatus(data.job_id, data.meta);
    } catch (err) {
      hideStatus();
      setBusy(false);
      resultsMeta.hidden = false;
      resultsMeta.textContent = "Couldn't reach the server. Please try again.";
    }
  });
})();
