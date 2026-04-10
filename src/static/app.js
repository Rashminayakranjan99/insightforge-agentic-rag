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
      fetchAllCharts().then(() => renderChartPicker());
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
        if (dropped.length > 0) {
          showToast("Auto-removed " + dropped.length + " ID column(s): " + dropped.join(", "), "info");
        } else {
          showToast("Data uploaded and profiled successfully!", "success");
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
  state.currentChart = new Chart(ctx, JSON.parse(JSON.stringify(config)));
}

function renderChartInCanvas(canvas, config) {
  const ctx = canvas.getContext("2d");
  return new Chart(ctx, JSON.parse(JSON.stringify(config)));
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
          const miniConfig = JSON.parse(JSON.stringify(chart.config));
          miniConfig.options = miniConfig.options || {};
          miniConfig.options.responsive = true;
          miniConfig.options.maintainAspectRatio = false;
          miniConfig.options.plugins = miniConfig.options.plugins || {};
          miniConfig.options.plugins.title = { display: false };
          if (miniConfig.type !== "radar" && miniConfig.type !== "polarArea") {
            miniConfig.options.plugins.legend = { display: false };
          }
          try {
            state.pickerInstances[chart.id] = renderChartInCanvas(canvas, miniConfig);
          } catch (e) {
            console.error("Picker chart error:", e);
          }
        }
      }
    }, 100);
  });
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
            state.dashboardInstances[chart.id] = renderChartInCanvas(canvas, chart.config);
          } catch (e) {
            console.error("Dashboard chart error:", e);
          }
        }
      }
    }, 100);
  });
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
console.log("%cInsightForge Loaded", "color: #6366f1; font-size: 14px; font-weight: bold;");
