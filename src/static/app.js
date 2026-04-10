/* ===================================================================
   InsightForge - Frontend Application Logic
   Upload - Chat - Visualization - Dashboard Builder
   =================================================================== */

const API = "";
const SESSION_ID = "sess_" + Math.random().toString(36).substring(2, 10);

// -- State ---------------------------------------------------------------
const state = {
  dataLoaded: false,
  profile: null,
  currentChart: null,
  currentChartConfig: null,
  allCharts: [],
  dashboardCharts: [],
  dashboardInstances: {},
  pickerInstances: {},
  isProcessing: false,
};

// -- DOM Elements --------------------------------------------------------
const $ = (id) => document.getElementById(id);
const uploadZone = $("upload-zone");
const fileInput = $("file-input");
const progressDiv = $("upload-progress");
const progressFill = $("progress-fill");
const progressText = $("progress-text");
const fileInfo = $("file-info");
const chatMessages = $("chat-messages");
const chatInput = $("chat-input");
const sendBtn = $("send-btn");
const mainChartCanvas = $("main-chart");
const chartPlaceholder = $("chart-placeholder");
const addToDashBtn = $("add-to-dash-btn");
const chartPicker = $("chart-picker");
const dashboardGrid = $("dashboard-grid");

// -- Navigation ----------------------------------------------------------
document.querySelectorAll(".nav-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    if (tab.classList.contains("disabled")) return;
    document.querySelectorAll(".nav-tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    tab.classList.add("active");
    const viewId = "view-" + tab.dataset.view;
    $(viewId).classList.add("active");

    if (tab.dataset.view === "dashboard") {
      fetchAllCharts().then(() => {
        renderChartPicker();
        setTimeout(resizeAllCharts, 120);
      });
    } else {
      setTimeout(resizeAllCharts, 120);
    }
  });
});

function enableTabs() {
  $("tab-chat").classList.remove("disabled");
  $("tab-dashboard").classList.remove("disabled");
}

// -- File Upload ---------------------------------------------------------
uploadZone.addEventListener("click", () => fileInput.click());

uploadZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  uploadZone.classList.add("dragover");
});

uploadZone.addEventListener("dragleave", () => {
  uploadZone.classList.remove("dragover");
});

uploadZone.addEventListener("drop", (e) => {
  e.preventDefault();
  uploadZone.classList.remove("dragover");
  const files = e.dataTransfer.files;
  if (files.length > 0) uploadFile(files[0]);
});

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) uploadFile(e.target.files[0]);
});

async function uploadFile(file) {
  if (!file.name.endsWith(".csv")) {
    showToast("Please upload a CSV file", "error");
    return;
  }

  progressDiv.classList.add("active");
  fileInfo.classList.remove("active");
  progressFill.style.width = "0%";
  progressText.textContent = "Uploading...";

  let progress = 0;
  const progressInterval = setInterval(() => {
    progress = Math.min(progress + Math.random() * 15, 85);
    progressFill.style.width = progress + "%";
  }, 200);

  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", SESSION_ID);

    const res = await fetch(`${API}/api/upload`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    clearInterval(progressInterval);

    if (data.success) {
      progressFill.style.width = "100%";
      progressText.textContent = "Upload complete - profiling data...";

      state.dataLoaded = true;
      state.profile = data.profile;

      setTimeout(() => {
        progressDiv.classList.remove("active");
        fileInfo.classList.add("active");
        $("file-name").textContent = data.filename;
        $("stat-rows").textContent = (data.profile.row_count || 0).toLocaleString();
        $("stat-cols").textContent = Object.keys(data.profile.columns || {}).length;
        $("stat-numeric").textContent = Object.values(data.profile.columns || {}).filter((c) => c.is_numeric).length;

        $("status-dot").classList.remove("inactive");
        $("status-text").textContent = data.filename;

        enableTabs();

        const dropped = data.profile.dropped_columns || [];
        const chunking = (data.profile && data.profile.chunking) || null;
        const chunkText = chunking && chunking.enabled
          ? " | Processed in " + chunking.chunk_count + " chunk(s)"
          : "";
        if (dropped.length > 0) {
          showToast("Auto-removed " + dropped.length + " ID column(s): " + dropped.join(", ") + chunkText, "info");
        } else {
          showToast("Data uploaded and profiled successfully!" + chunkText, "success");
        }

        // Pre-fetch charts for dashboard
        fetchAllCharts();
      }, 500);
    } else {
      progressFill.style.width = "0%";
      progressText.textContent = "Upload failed: " + (data.error || "Unknown error");
      showToast(data.error || "Upload failed", "error");
    }
  } catch (err) {
    clearInterval(progressInterval);
    progressFill.style.width = "0%";
    progressText.textContent = "Upload failed: " + err.message;
    showToast("Upload failed: " + err.message, "error");
  }
}

$("start-analysis-btn").addEventListener("click", () => {
  $("tab-chat").click();
});

// -- Chat ----------------------------------------------------------------
chatInput.addEventListener("input", () => {
  sendBtn.disabled = !chatInput.value.trim() || state.isProcessing;
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
});

chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!sendBtn.disabled) sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

document.querySelectorAll(".suggestion-chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    chatInput.value = chip.dataset.query;
    sendBtn.disabled = false;
    sendMessage();
  });
});

async function sendMessage() {
  const query = chatInput.value.trim();
  if (!query || state.isProcessing) return;

  const welcome = $("welcome-msg");
  if (welcome) welcome.style.display = "none";

  addMessage("user", query);
  chatInput.value = "";
  chatInput.style.height = "auto";
  sendBtn.disabled = true;

  const typingEl = showTyping();
  state.isProcessing = true;

  try {
    const res = await fetch(`${API}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, session_id: SESSION_ID }),
    });

    const data = await res.json();
    typingEl.remove();
    state.isProcessing = false;

    addMessage("assistant", data.narrative);

    if (data.provider) {
      $("llm-provider").textContent = data.provider === "groq" ? "Groq" : "Gemini";
    }

    if (data.chart_config && data.chart_config.data) {
      renderMainChart(data.chart_config);
      state.currentChartConfig = data.chart_config;
      addToDashBtn.style.display = "flex";
      $("viz-type-badge").textContent = data.chart_config.type || "Chart";
    }

    fetchAllCharts();
  } catch (err) {
    typingEl.remove();
    state.isProcessing = false;
    addMessage("assistant", "Sorry, I encountered an error. Please try again.\n\n`" + err.message + "`");
    showToast("Error: " + err.message, "error");
  }

  sendBtn.disabled = !chatInput.value.trim();
}

function addMessage(role, content) {
  const div = document.createElement("div");
  div.className = "message " + role;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "assistant" ? "\u26A1" : "\uD83D\uDC64";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  if (role === "assistant") {
    bubble.innerHTML = marked.parse(content || "", { breaks: true });
  } else {
    bubble.textContent = content;
  }

  div.appendChild(avatar);
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "message assistant";
  div.innerHTML =
    '<div class="message-avatar">\u26A1</div>' +
    '<div class="typing-indicator active">' +
    '<div class="typing-dot"></div>' +
    '<div class="typing-dot"></div>' +
    '<div class="typing-dot"></div>' +
    '</div>';
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

// -- Chart Rendering -----------------------------------------------------
function renderMainChart(config) {
  chartPlaceholder.style.display = "none";
  mainChartCanvas.style.display = "block";

  if (state.currentChart) {
    state.currentChart.destroy();
  }

  const ctx = mainChartCanvas.getContext("2d");
  state.currentChart = new Chart(ctx, normalizeChartConfig(config, "main"));
  setTimeout(resizeAllCharts, 80);
}

function renderChartInCanvas(canvas, config, context) {
  const ctx = canvas.getContext("2d");
  return new Chart(ctx, normalizeChartConfig(config, context || "dashboard"));
}

function normalizeChartConfig(config, context) {
  var cfg = JSON.parse(JSON.stringify(config || {}));
  cfg.options = cfg.options || {};
  cfg.options.responsive = true;
  cfg.options.maintainAspectRatio = false;

  cfg.options.plugins = cfg.options.plugins || {};
  cfg.options.layout = cfg.options.layout || {};
  if (cfg.options.layout.padding == null) cfg.options.layout.padding = 8;

  if (context === "picker") {
    cfg.options.plugins.title = { display: false };
    if (cfg.type !== "radar" && cfg.type !== "polarArea" && cfg.type !== "pie" && cfg.type !== "doughnut") {
      cfg.options.plugins.legend = { display: false };
    }
  }

  if (cfg.options.scales) {
    if (cfg.options.scales.x) {
      cfg.options.scales.x.ticks = cfg.options.scales.x.ticks || {};
      if (cfg.options.scales.x.ticks.maxRotation == null) cfg.options.scales.x.ticks.maxRotation = 30;
      if (cfg.options.scales.x.ticks.autoSkip == null) cfg.options.scales.x.ticks.autoSkip = true;
    }
  }

  return cfg;
}

function resizeAllCharts() {
  try {
    if (state.currentChart && state.currentChart.resize) state.currentChart.resize();
  } catch (e) {}

  Object.values(state.pickerInstances).forEach((inst) => {
    try { if (inst && inst.resize) inst.resize(); } catch (e) {}
  });
  Object.values(state.dashboardInstances).forEach((inst) => {
    try { if (inst && inst.resize) inst.resize(); } catch (e) {}
  });
}

// -- KPI Card Rendering --------------------------------------------------
function renderKPICards(container, kpiData) {
  const grid = document.createElement("div");
  grid.className = "kpi-grid";

  const icons = {
    "database": "\uD83D\uDDC4\uFE0F",
    "trending-up": "\uD83D\uDCC8",
    "bar-chart": "\uD83D\uDCCA",
    "check-circle": "\u2705",
  };

  (kpiData.kpis || []).forEach((kpi) => {
    const card = document.createElement("div");
    card.className = "kpi-card";
    card.setAttribute("data-color", kpi.color || "#6366f1");

    let html =
      '<div class="kpi-icon">' + (icons[kpi.icon] || "\uD83D\uDCCA") + '</div>' +
      '<div class="kpi-value">' + kpi.value + '</div>' +
      '<div class="kpi-label">' + kpi.label + '</div>';
    if (kpi.delta) {
      html += '<div class="kpi-delta">' + kpi.delta + '</div>';
    }
    card.innerHTML = html;
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

// -- Add to Dashboard ----------------------------------------------------
addToDashBtn.addEventListener("click", () => {
  if (!state.currentChartConfig) return;

  const id = "dash_" + Math.random().toString(36).substring(2, 8);
  const title = (state.currentChartConfig.options &&
                 state.currentChartConfig.options.plugins &&
                 state.currentChartConfig.options.plugins.title &&
                 state.currentChartConfig.options.plugins.title.text) || "Chart";

  state.dashboardCharts.push({
    id: id,
    title: title,
    config: JSON.parse(JSON.stringify(state.currentChartConfig)),
  });

  renderDashboard();
  showToast("Chart added to dashboard!", "success");
});

// -- Dashboard -----------------------------------------------------------
async function fetchAllCharts() {
  try {
    const res = await fetch(API + "/api/charts?session_id=" + SESSION_ID);
    const data = await res.json();
    state.allCharts = data.charts || [];
  } catch (err) {
    console.error("Error fetching charts:", err);
  }
}

function renderChartPicker() {
  // Destroy existing picker instances
  Object.values(state.pickerInstances).forEach((inst) => {
    try { if (inst && inst.destroy) inst.destroy(); } catch (e) {}
  });
  state.pickerInstances = {};
  chartPicker.innerHTML = "";

  if (state.allCharts.length === 0) {
    chartPicker.innerHTML =
      '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);">' +
      '<div style="font-size:2rem;margin-bottom:8px;">\uD83D\uDCCA</div>' +
      '<div>No charts yet. Chat with your data to generate visualizations!</div>' +
      '</div>';
    return;
  }

  state.allCharts.forEach((chart, idx) => {
    const card = document.createElement("div");
    card.className = "chart-pick-card";
    card.dataset.chartId = chart.id;

    if (state.dashboardCharts.some((d) => d.id === chart.id)) {
      card.classList.add("selected");
    }

    const isKPI = chart.config && chart.config.type === "kpi_cards";

    if (isKPI) {
      card.innerHTML =
        '<div class="chart-pick-title">' + (chart.title || "KPI Cards") + '</div>' +
        '<div class="chart-pick-preview" id="picker-' + chart.id + '"></div>';
    } else {
      card.innerHTML =
        '<div class="chart-pick-title">' + (chart.title || "Chart") + '</div>' +
        '<div class="chart-pick-preview">' +
        '<canvas id="picker-' + chart.id + '"></canvas>' +
        '</div>';
    }

    card.addEventListener("click", () => toggleDashboardChart(chart, card));
    chartPicker.appendChild(card);

    // Render chart preview
    setTimeout(() => {
      if (isKPI) {
        const container = $("picker-" + chart.id);
        if (container) renderKPICards(container, chart.config);
      } else {
        const canvas = $("picker-" + chart.id);
        if (canvas && chart.config) {
          try {
            state.pickerInstances[chart.id] = renderChartInCanvas(canvas, chart.config, "picker");
          } catch (e) {
            console.error("Picker chart error:", e);
          }
        }
      }
    }, 100);
  });
  setTimeout(resizeAllCharts, 160);
}

function toggleDashboardChart(chart, card) {
  const idx = state.dashboardCharts.findIndex((d) => d.id === chart.id);
  if (idx >= 0) {
    state.dashboardCharts.splice(idx, 1);
    card.classList.remove("selected");
  } else {
    state.dashboardCharts.push({
      id: chart.id,
      title: chart.title,
      config: JSON.parse(JSON.stringify(chart.config)),
    });
    card.classList.add("selected");
  }
  renderDashboard();
}

function renderDashboard() {
  // Destroy existing
  Object.values(state.dashboardInstances).forEach((inst) => {
    try { if (inst && inst.destroy) inst.destroy(); } catch (e) {}
  });
  state.dashboardInstances = {};
  dashboardGrid.innerHTML = "";

  if (state.dashboardCharts.length === 0) {
    dashboardGrid.innerHTML =
      '<div class="dashboard-empty">' +
      '<div class="dashboard-empty-icon">\uD83D\uDCCB</div>' +
      '<div class="dashboard-empty-text">Your dashboard is empty</div>' +
      '<div class="dashboard-empty-sub">Select charts above or chat to generate insights</div>' +
      '</div>';
    return;
  }

  state.dashboardCharts.forEach((chart) => {
    const isKPI = chart.config && chart.config.type === "kpi_cards";
    const card = document.createElement("div");
    card.className = "dashboard-card" + (isKPI ? " dashboard-kpi-row" : "");

    if (isKPI) {
      card.innerHTML =
        '<div class="dashboard-card-title">' + (chart.title || "KPI") + '</div>' +
        '<button class="remove-btn" data-id="' + chart.id + '">X</button>' +
        '<div class="dashboard-card-chart" id="dash-' + chart.id + '"></div>';
    } else {
      card.innerHTML =
        '<div class="dashboard-card-title">' + (chart.title || "Chart") + '</div>' +
        '<button class="remove-btn" data-id="' + chart.id + '">X</button>' +
        '<div class="dashboard-card-chart">' +
        '<canvas id="dash-' + chart.id + '"></canvas>' +
        '</div>';
    }

    card.querySelector(".remove-btn").addEventListener("click", (e) => {
      e.stopPropagation();
      removeDashboardChart(chart.id);
    });

    dashboardGrid.appendChild(card);

    setTimeout(() => {
      if (isKPI) {
        const container = $("dash-" + chart.id);
        if (container) renderKPICards(container, chart.config);
      } else {
        const canvas = $("dash-" + chart.id);
        if (canvas && chart.config) {
          try {
            state.dashboardInstances[chart.id] = renderChartInCanvas(canvas, chart.config, "dashboard");
          } catch (e) {
            console.error("Dashboard chart error:", e);
          }
        }
      }
    }, 100);
  });
  setTimeout(resizeAllCharts, 160);
}

function removeDashboardChart(id) {
  const idx = state.dashboardCharts.findIndex((d) => d.id === id);
  if (idx >= 0) {
    state.dashboardCharts.splice(idx, 1);
    if (state.dashboardInstances[id]) {
      try { state.dashboardInstances[id].destroy(); } catch (e) {}
      delete state.dashboardInstances[id];
    }
    renderDashboard();

    const pickerCard = chartPicker.querySelector('[data-chart-id="' + id + '"]');
    if (pickerCard) pickerCard.classList.remove("selected");
  }
}

// -- Custom Chart Modal --------------------------------------------------
$("custom-chart-btn").addEventListener("click", () => {
  if (!state.profile) {
    showToast("Upload data first!", "error");
    return;
  }
  populateModalColumns();
  $("chart-modal").classList.add("active");
});

$("modal-cancel").addEventListener("click", () => {
  $("chart-modal").classList.remove("active");
});

$("chart-modal").addEventListener("click", (e) => {
  if (e.target === $("chart-modal")) {
    $("chart-modal").classList.remove("active");
  }
});

function populateModalColumns() {
  const xSelect = $("modal-x-col");
  const ySelect = $("modal-y-col");

  xSelect.innerHTML = "";
  ySelect.innerHTML = '<option value="">None (count)</option>';

  if (state.profile && state.profile.columns) {
    Object.entries(state.profile.columns).forEach(function(entry) {
      var name = entry[0];
      var info = entry[1];
      var xOpt = document.createElement("option");
      xOpt.value = name;
      xOpt.textContent = name + " (" + (info.is_numeric ? "numeric" : "categorical") + ")";
      xSelect.appendChild(xOpt);

      if (info.is_numeric) {
        var yOpt = document.createElement("option");
        yOpt.value = name;
        yOpt.textContent = name;
        ySelect.appendChild(yOpt);
      }
    });
  }
}

$("modal-create").addEventListener("click", async () => {
  const chartType = $("modal-chart-type").value;
  const xCol = $("modal-x-col").value;
  const yCol = $("modal-y-col").value;
  const agg = $("modal-agg").value;

  if (!xCol) {
    showToast("Select at least an X-axis column", "error");
    return;
  }

  $("chart-modal").classList.remove("active");

  try {
    const res = await fetch(API + "/api/quick-chart", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: SESSION_ID,
        chart_type: chartType,
        x_column: xCol,
        y_column: yCol || null,
        aggregation: agg,
      }),
    });

    const data = await res.json();

    if (data.success && data.chart) {
      state.allCharts.push(data.chart);
      state.dashboardCharts.push({
        id: data.chart.id,
        title: data.chart.title,
        config: data.chart.config,
      });
      renderChartPicker();
      renderDashboard();
      showToast("Custom chart created!", "success");
    } else {
      showToast(data.error || "Failed to create chart", "error");
    }
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
});

// -- Save Dashboard ------------------------------------------------------
$("save-dashboard-btn").addEventListener("click", async () => {
  if (state.dashboardCharts.length === 0) {
    showToast("Add charts to dashboard first!", "error");
    return;
  }

  try {
    const res = await fetch(API + "/api/dashboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: SESSION_ID,
        name: "My Dashboard",
        chart_ids: state.dashboardCharts.map((c) => c.id),
      }),
    });

    const data = await res.json();
    if (data.success) {
      showToast("Dashboard saved!", "success");
    }
  } catch (err) {
    showToast("Error: " + err.message, "error");
  }
});

// -- Download Dashboard as HTML ------------------------------------------
$("download-html-btn").addEventListener("click", () => {
  if (state.dashboardCharts.length === 0) {
    showToast("Add charts to dashboard first!", "error");
    return;
  }

  showToast("Generating HTML file...", "info");

  // Serialize all chart configs & KPI data for the standalone page
  const chartsJSON = JSON.stringify(state.dashboardCharts);

  const htmlContent = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>InsightForge Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"><\/script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: #0a0a0f;
      color: #f0f0f5;
      padding: 32px;
      min-height: 100vh;
    }
    body::before {
      content: '';
      position: fixed; top: -50%; left: -50%;
      width: 200%; height: 200%;
      background:
        radial-gradient(ellipse at 20% 50%, rgba(99,102,241,0.08) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, rgba(168,85,247,0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 80%, rgba(236,72,153,0.04) 0%, transparent 50%);
      z-index: -1;
      pointer-events: none;
    }
    .header {
      text-align: center;
      margin-bottom: 32px;
      padding-bottom: 20px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
    }
    .header h1 {
      font-size: 1.8rem;
      font-weight: 800;
      background: linear-gradient(135deg, #6366f1, #a855f7, #ec4899);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 6px;
    }
    .header p {
      color: #8b8b9e;
      font-size: 0.85rem;
    }
    .dashboard-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 20px;
    }
    .card {
      padding: 20px;
      background: linear-gradient(145deg, rgba(20,20,35,0.9), rgba(15,15,25,0.95));
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
    }
    .card-title {
      font-size: 0.85rem;
      font-weight: 600;
      color: #8b8b9e;
      margin-bottom: 12px;
    }
    .card-chart { height: 260px; position: relative; }
    .kpi-row { grid-column: 1 / -1; }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 14px;
    }
    .kpi-card {
      padding: 18px;
      background: linear-gradient(145deg, rgba(20,20,35,0.9), rgba(15,15,25,0.95));
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      position: relative;
      overflow: hidden;
    }
    .kpi-card::before {
      content: '';
      position: absolute; top: 0; left: 0;
      width: 3px; height: 100%;
      border-radius: 3px 0 0 3px;
    }
    .kpi-card[data-color="#6366f1"]::before { background: #6366f1; }
    .kpi-card[data-color="#a855f7"]::before { background: #a855f7; }
    .kpi-card[data-color="#ec4899"]::before { background: #ec4899; }
    .kpi-card[data-color="#10b981"]::before { background: #10b981; }
    .kpi-icon { font-size: 1.3rem; margin-bottom: 6px; opacity: 0.7; }
    .kpi-value {
      font-size: 1.5rem; font-weight: 800;
      color: #f0f0f5; line-height: 1.2; letter-spacing: -0.5px;
    }
    .kpi-label {
      font-size: 0.72rem; color: #5a5a6e;
      text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px;
    }
    .kpi-delta { font-size: 0.7rem; color: #8b8b9e; margin-top: 4px; }
    .footer {
      text-align: center;
      margin-top: 32px;
      padding-top: 16px;
      border-top: 1px solid rgba(255,255,255,0.08);
      color: #5a5a6e;
      font-size: 0.75rem;
    }
    @media (max-width: 800px) {
      .dashboard-grid { grid-template-columns: 1fr; }
      body { padding: 16px; }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>⚡ InsightForge Dashboard</h1>
    <p>Generated on ${new Date().toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
  </div>
  <div class="dashboard-grid" id="grid"></div>
  <div class="footer">Powered by InsightForge — AI Data Analytics</div>

  <script>
    var charts = ${chartsJSON};
    var icons = {"database":"\\uD83D\\uDDC4\\uFE0F","trending-up":"\\uD83D\\uDCC8","bar-chart":"\\uD83D\\uDCCA","check-circle":"\\u2705"};
    var grid = document.getElementById("grid");

    charts.forEach(function(chart) {
      var isKPI = chart.config && chart.config.type === "kpi_cards";
      var card = document.createElement("div");
      card.className = "card" + (isKPI ? " kpi-row" : "");

      if (isKPI) {
        var html = '<div class="card-title">' + (chart.title || "KPI") + '</div>';
        html += '<div class="kpi-grid">';
        (chart.config.kpis || []).forEach(function(kpi) {
          html += '<div class="kpi-card" data-color="' + (kpi.color || "#6366f1") + '">';
          html += '<div class="kpi-icon">' + (icons[kpi.icon] || "\\uD83D\\uDCCA") + '</div>';
          html += '<div class="kpi-value">' + kpi.value + '</div>';
          html += '<div class="kpi-label">' + kpi.label + '</div>';
          if (kpi.delta) html += '<div class="kpi-delta">' + kpi.delta + '</div>';
          html += '</div>';
        });
        html += '</div>';
        card.innerHTML = html;
      } else {
        card.innerHTML = '<div class="card-title">' + (chart.title || "Chart") + '</div>' +
          '<div class="card-chart"><canvas id="c-' + chart.id + '"></canvas></div>';
      }

      grid.appendChild(card);

      if (!isKPI) {
        setTimeout(function() {
          var canvas = document.getElementById("c-" + chart.id);
          if (canvas && chart.config) {
            var cfg = JSON.parse(JSON.stringify(chart.config));
            cfg.options = cfg.options || {};
            cfg.options.responsive = true;
            cfg.options.maintainAspectRatio = false;
            new Chart(canvas.getContext("2d"), cfg);
          }
        }, 100);
      }
    });
  <\/script>
</body>
</html>`;

  // Create download
  const blob = new Blob([htmlContent], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "insightforge-dashboard-" + new Date().toISOString().slice(0, 10) + ".html";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast("Dashboard downloaded as HTML!", "success");
});

// -- Download Dashboard as Image -----------------------------------------
$("download-img-btn").addEventListener("click", async () => {
  if (state.dashboardCharts.length === 0) {
    showToast("Add charts to dashboard first!", "error");
    return;
  }

  showToast("Capturing dashboard image...", "info");

  try {
    const target = $("dashboard-grid");
    const canvas = await html2canvas(target, {
      backgroundColor: "#0a0a0f",
      scale: 2,
      useCORS: true,
      logging: false,
      onclone: function(clonedDoc) {
        // Ensure cloned element is visible
        var clonedGrid = clonedDoc.getElementById("dashboard-grid");
        if (clonedGrid) {
          clonedGrid.style.display = "grid";
        }
      }
    });

    canvas.toBlob(function(blob) {
      var url = URL.createObjectURL(blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = "insightforge-dashboard-" + new Date().toISOString().slice(0, 10) + ".png";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast("Dashboard image downloaded!", "success");
    }, "image/png");
  } catch (err) {
    console.error("Screenshot error:", err);
    showToast("Error capturing: " + err.message, "error");
  }
});

// -- Toast ---------------------------------------------------------------
function showToast(message, type) {
  type = type || "info";
  const toast = $("toast");
  var icon = "";
  if (type === "success") icon = "OK ";
  else if (type === "error") icon = "ERR ";
  else icon = "i ";
  toast.textContent = icon + message;
  toast.className = "toast " + type + " show";

  setTimeout(() => {
    toast.classList.remove("show");
  }, 3500);
}

// -- Init ----------------------------------------------------------------
let resizeTimer = null;
window.addEventListener("resize", () => {
  if (resizeTimer) clearTimeout(resizeTimer);
  resizeTimer = setTimeout(resizeAllCharts, 150);
});

console.log("%cInsightForge Loaded", "color: #6366f1; font-size: 14px; font-weight: bold;");
