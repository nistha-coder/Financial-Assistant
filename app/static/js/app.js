const API = "/api";

const state = {
  companies: [],
  ticker: null,
  period: null,
  benchmarkSelected: new Set(),
  memoSelected: new Set(),
  chart: null,
};

// ---------------- Helpers ----------------
function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.from(document.querySelectorAll(sel)); }

function fmtNum(value, opts = {}) {
  if (value === null || value === undefined) return "—";
  const { suffix = "", decimals = 1 } = opts;
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: decimals, minimumFractionDigits: 0 }) + suffix;
}

function toast(message, type = "success") {
  const container = $("#toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

function showSpinner(container) {
  container.innerHTML = '<div class="spinner"></div>';
}

function showSkeleton(container, lines = 4) {
  container.innerHTML = Array.from({ length: lines }).map(() => '<div class="skeleton"></div>').join("");
}

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

// ---------------- Companies / period selectors ----------------
async function loadCompanies(selectTicker, selectPeriod) {
  const tickerSelect = $("#ticker-select");
  const periodSelect = $("#period-select");
  try {
    state.companies = await api("/companies");
  } catch (e) {
    toast(`Failed to load companies: ${e.message}`, "error");
    return;
  }

  const tickers = [...new Set(state.companies.map((c) => c.ticker))];
  tickerSelect.innerHTML = tickers.map((t) => `<option value="${t}">${t}</option>`).join("");

  const wantTicker = selectTicker && tickers.includes(selectTicker) ? selectTicker : tickers[0];
  tickerSelect.value = wantTicker;
  state.ticker = wantTicker;
  populatePeriods(selectPeriod);
}

function populatePeriods(selectPeriod) {
  const periodSelect = $("#period-select");
  const periods = state.companies
    .filter((c) => c.ticker === state.ticker)
    .map((c) => c.period_label)
    .sort();
  periodSelect.innerHTML = periods.map((p) => `<option value="${p}">${p}</option>`).join("");
  const want = selectPeriod && periods.includes(selectPeriod) ? selectPeriod : periods[periods.length - 1];
  periodSelect.value = want;
  state.period = want;
}

// ---------------- Tabs ----------------
function setupTabs() {
  $all(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      $all(".tab").forEach((t) => t.classList.remove("active"));
      $all(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      $(`#panel-${tab.dataset.tab}`).classList.add("active");
      loadActiveTab();
    });
  });
}

function activeTab() {
  return $(".tab.active")?.dataset.tab;
}

function loadActiveTab() {
  const tab = activeTab();
  if (tab === "metrics") loadMetrics();
  if (tab === "comparison") loadComparison();
  if (tab === "tone") loadTone();
  if (tab === "risks") loadRisks();
  if (tab === "benchmark") renderBenchmarkChips();
  if (tab === "memo") renderMemoChips();
}

// ---------------- Metrics ----------------
const METRIC_LABELS = {
  revenue: "Revenue ($M)",
  gross_profit: "Gross Profit ($M)",
  operating_income: "Operating Income ($M)",
  ebitda: "EBITDA ($M)",
  net_income: "Net Income ($M)",
  gross_margin_pct: "Gross Margin",
  operating_margin_pct: "Operating Margin",
  net_margin_pct: "Net Margin",
  ebitda_margin_pct: "EBITDA Margin",
  operating_cash_flow: "Operating Cash Flow ($M)",
  free_cash_flow: "Free Cash Flow ($M)",
  capex: "Capex ($M)",
  total_debt: "Total Debt ($M)",
  cash_and_equivalents: "Cash & Equivalents ($M)",
};

async function loadMetrics() {
  const container = $("#metrics-content");
  if (!state.ticker || !state.period) return;
  showSkeleton(container, 6);
  try {
    const data = await api(`/metrics/${state.ticker}/${state.period}`);
    let html = '<div class="metric-grid">';
    for (const [key, label] of Object.entries(METRIC_LABELS)) {
      const val = data[key];
      const suffix = key.endsWith("_pct") ? "%" : "";
      html += `<div class="metric-tile"><div class="label">${label}</div><div class="value">${fmtNum(val, { suffix })}</div></div>`;
    }
    html += "</div>";

    if (data.guidance_revenue_low || data.guidance_eps_low) {
      html += `<div class="memo-section"><h3>Forward Guidance</h3><div class="metric-grid">`;
      html += `<div class="metric-tile"><div class="label">Revenue Guidance ($M)</div><div class="value">${fmtNum(data.guidance_revenue_low)} – ${fmtNum(data.guidance_revenue_high)}</div></div>`;
      html += `<div class="metric-tile"><div class="label">EPS Guidance ($)</div><div class="value">${fmtNum(data.guidance_eps_low, { decimals: 2 })} – ${fmtNum(data.guidance_eps_high, { decimals: 2 })}</div></div>`;
      html += `</div>`;
      if (data.guidance_notes) html += `<p class="muted" style="margin-top:8px;">${data.guidance_notes}</p>`;
      html += `</div>`;
    }
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<p class="muted">${e.message}</p>`;
  }
}

// ---------------- Comparison ----------------
async function loadComparison() {
  const container = $("#comparison-content");
  if (!state.ticker || !state.period) return;
  showSkeleton(container, 6);
  try {
    const data = await api(`/metrics/${state.ticker}/${state.period}/comparison`);
    let html = `<table><thead><tr><th>Metric</th><th>${data.prior_period}</th><th>${data.current_period}</th><th>Change</th><th>% Change</th></tr></thead><tbody>`;
    for (const d of data.deltas) {
      const label = METRIC_LABELS[d.metric] || d.metric;
      const cls = d.pct_change > 0 ? "delta-pos" : d.pct_change < 0 ? "delta-neg" : "delta-zero";
      const arrow = d.pct_change > 0 ? "▲" : d.pct_change < 0 ? "▼" : "•";
      html += `<tr><td>${label}</td><td>${fmtNum(d.prior_value)}</td><td>${fmtNum(d.current_value)}</td>`;
      html += `<td class="${cls}">${fmtNum(d.absolute_change)}</td>`;
      html += `<td class="${cls}">${arrow} ${fmtNum(d.pct_change, { suffix: "%" })}</td></tr>`;
    }
    html += "</tbody></table>";
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<p class="muted">${e.message}</p>`;
  }
}

// ---------------- Tone ----------------
async function loadTone() {
  const container = $("#tone-content");
  if (!state.ticker || !state.period) return;
  showSkeleton(container, 5);
  try {
    const tone = await api(`/tone/${state.ticker}/${state.period}`);
    let html = `<div class="badge badge-${tone.sentiment}">${tone.sentiment}</div>`;
    html += `<div class="score-bar"><div class="score-bar-fill" style="width:${tone.confidence_score * 100}%"></div></div>`;
    html += `<p class="muted">Confidence score: ${(tone.confidence_score * 100).toFixed(0)}/100</p>`;
    html += `<p>${tone.summary}</p>`;
    if (tone.confidence_phrases?.length) {
      html += `<div class="memo-section"><h3>Confidence Language</h3><ul class="quote-list">${tone.confidence_phrases.map((p) => `<li>"${p}"</li>`).join("")}</ul></div>`;
    }
    if (tone.hedging_phrases?.length) {
      html += `<div class="memo-section"><h3>Hedging / Cautious Language</h3><ul class="quote-list">${tone.hedging_phrases.map((p) => `<li>"${p}"</li>`).join("")}</ul></div>`;
    }
    container.innerHTML = html;

    // try the comparison too, append if available
    try {
      const cmp = await api(`/tone/${state.ticker}/${state.period}/comparison`);
      const extra = document.createElement("div");
      extra.className = "memo-section";
      extra.innerHTML = `<h3>Tone Shift vs ${cmp.prior_period}</h3><div class="badge badge-${cmp.tone_shift}">${cmp.tone_shift.replace("_", " ")}</div><p class="muted" style="margin-top:8px;">${cmp.explanation}</p>`;
      container.appendChild(extra);
    } catch (_) { /* prior period may not exist or LLM unavailable */ }
  } catch (e) {
    container.innerHTML = `<p class="muted">${e.message}</p>`;
  }
}

// ---------------- Risks ----------------
async function loadRisks() {
  const container = $("#risks-content");
  if (!state.ticker || !state.period) return;
  showSkeleton(container, 5);
  try {
    const risks = await api(`/risks/${state.ticker}/${state.period}`);
    let comparison = null;
    try {
      comparison = await api(`/risks/${state.ticker}/${state.period}/comparison`);
    } catch (_) { /* no prior period */ }

    const newTitles = new Set((comparison?.new_risks || []).map((r) => r.title));
    const escalatedTitles = new Set((comparison?.escalated_risks || []).map((r) => r.title));

    let html = "";
    if (comparison) {
      html += `<div class="chip-row">`;
      html += `<span class="muted">vs ${comparison.prior_period}:</span>`;
      html += `<span class="risk-tag risk-tag-new">${comparison.new_risks.length} new</span>`;
      html += `<span class="risk-tag risk-tag-escalated">${comparison.escalated_risks.length} escalated</span>`;
      html += `<span class="risk-tag risk-tag-removed">${comparison.removed_risks.length} removed</span>`;
      html += `</div>`;
    }

    for (const risk of risks.risks) {
      let tag = "";
      if (newTitles.has(risk.title)) tag = '<span class="risk-tag risk-tag-new">New</span>';
      else if (escalatedTitles.has(risk.title)) tag = '<span class="risk-tag risk-tag-escalated">Escalated</span>';
      html += `<div class="risk-card">`;
      html += `<div class="risk-title">${risk.title} ${tag}<span class="badge badge-${risk.severity}">${risk.severity}</span><span class="muted" style="font-weight:400;">${risk.category}</span></div>`;
      html += `<div class="risk-desc">${risk.description}</div>`;
      html += `</div>`;
    }
    container.innerHTML = html || '<p class="muted">No risk factors found.</p>';
  } catch (e) {
    container.innerHTML = `<p class="muted">${e.message}</p>`;
  }
}

// ---------------- Benchmark ----------------
function renderBenchmarkChips() {
  const row = $("#benchmark-tickers");
  const tickers = [...new Set(state.companies.map((c) => c.ticker))];
  if (state.benchmarkSelected.size === 0) tickers.forEach((t) => state.benchmarkSelected.add(t));
  row.innerHTML = tickers.map((t) => `<div class="chip ${state.benchmarkSelected.has(t) ? "selected" : ""}" data-ticker="${t}">${t}</div>`).join("");
  $all("#benchmark-tickers .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const t = chip.dataset.ticker;
      if (state.benchmarkSelected.has(t)) state.benchmarkSelected.delete(t);
      else state.benchmarkSelected.add(t);
      chip.classList.toggle("selected");
    });
  });
}

async function loadBenchmark() {
  const container = $("#benchmark-content");
  if (!state.period) return;
  const tickers = [...state.benchmarkSelected];
  if (tickers.length === 0) {
    toast("Select at least one ticker", "error");
    return;
  }
  showSkeleton(container, 4);
  try {
    const table = await api(`/benchmark/${state.period}?tickers=${tickers.join(",")}`);
    let html = `<table><thead><tr><th>Company</th><th>Revenue ($M)</th><th>YoY Growth</th><th>EBITDA Margin</th><th>Op. Margin</th><th>Net Margin</th><th>Capex % Rev</th><th>Debt/EBITDA</th></tr></thead><tbody>`;
    for (const row of table.rows) {
      html += `<tr><td>${row.company}</td><td>${fmtNum(row.revenue)}</td><td>${fmtNum(row.revenue_growth_yoy_pct, { suffix: "%" })}</td>`;
      html += `<td>${fmtNum(row.ebitda_margin_pct, { suffix: "%" })}</td><td>${fmtNum(row.operating_margin_pct, { suffix: "%" })}</td>`;
      html += `<td>${fmtNum(row.net_margin_pct, { suffix: "%" })}</td><td>${fmtNum(row.capex_pct_of_revenue, { suffix: "%" })}</td>`;
      html += `<td>${fmtNum(row.debt_to_ebitda, { decimals: 2 })}</td></tr>`;
    }
    html += "</tbody></table>";
    container.innerHTML = html;
    drawBenchmarkChart(table);
  } catch (e) {
    container.innerHTML = `<p class="muted">${e.message}</p>`;
  }
}

function drawBenchmarkChart(table) {
  const ctx = document.getElementById("benchmark-chart");
  const labels = table.rows.map((r) => r.ticker);
  const datasets = [
    { label: "EBITDA Margin %", data: table.rows.map((r) => r.ebitda_margin_pct), backgroundColor: "#7c5cff" },
    { label: "Operating Margin %", data: table.rows.map((r) => r.operating_margin_pct), backgroundColor: "#29d3c8" },
    { label: "Net Margin %", data: table.rows.map((r) => r.net_margin_pct), backgroundColor: "#ff6b9d" },
  ];
  if (state.chart) state.chart.destroy();
  state.chart = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#e7e9f3" } } },
      scales: {
        x: { ticks: { color: "#9097b3" }, grid: { color: "rgba(255,255,255,0.05)" } },
        y: { ticks: { color: "#9097b3" }, grid: { color: "rgba(255,255,255,0.05)" } },
      },
    },
  });
}

// ---------------- Memo ----------------
function renderMemoChips() {
  const row = $("#memo-tickers");
  const tickers = [...new Set(state.companies.map((c) => c.ticker))].filter((t) => t !== state.ticker);
  row.innerHTML = tickers.map((t) => `<div class="chip ${state.memoSelected.has(t) ? "selected" : ""}" data-ticker="${t}">${t}</div>`).join("");
  $all("#memo-tickers .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const t = chip.dataset.ticker;
      if (state.memoSelected.has(t)) state.memoSelected.delete(t);
      else state.memoSelected.add(t);
      chip.classList.toggle("selected");
    });
  });
}

async function loadMemo() {
  const container = $("#memo-content");
  if (!state.ticker || !state.period) return;
  showSpinner(container);
  const peers = [...state.memoSelected].join(",");
  const url = `/memo/${state.ticker}/${state.period}` + (peers ? `?peers=${peers}` : "");
  try {
    const memo = await api(url);
    let html = `<div class="memo-section"><h3>Company Overview</h3><p>${memo.company_overview}</p></div>`;
    html += `<div class="memo-section"><h3>Financial Summary</h3><p>${memo.financial_summary}</p></div>`;
    html += `<div class="memo-section"><h3>🐂 Bull Case</h3><ul>${memo.bull_case.map((b) => `<li>${b}</li>`).join("")}</ul></div>`;
    html += `<div class="memo-section"><h3>🐻 Bear Case</h3><ul>${memo.bear_case.map((b) => `<li>${b}</li>`).join("")}</ul></div>`;
    html += `<div class="memo-section"><h3>Key Risks</h3><ul>${memo.key_risks.map((b) => `<li>${b}</li>`).join("")}</ul></div>`;
    html += `<div class="memo-section"><h3>Questions to Investigate</h3><ul>${memo.questions_to_investigate.map((b) => `<li>${b}</li>`).join("")}</ul></div>`;
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = `<p class="muted">${e.message}</p>`;
  }
}

// ---------------- Chat ----------------
async function sendChat(query) {
  const log = $("#chat-log");
  const userMsg = document.createElement("div");
  userMsg.className = "chat-msg user";
  userMsg.textContent = query;
  log.appendChild(userMsg);

  const botMsg = document.createElement("div");
  botMsg.className = "chat-msg bot";
  botMsg.innerHTML = '<div class="spinner" style="margin:0 auto;"></div>';
  log.appendChild(botMsg);
  log.scrollTop = log.scrollHeight;

  try {
    const data = await api("/rag/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        ticker: state.ticker || null,
        period_label: state.period || null,
      }),
    });
    botMsg.innerHTML = `<div>${data.answer}</div>` + (data.sources?.length ? `<div class="sources">Sources: ${data.sources.join(" · ")}</div>` : "");
  } catch (e) {
    botMsg.innerHTML = `<div>${e.message}</div>`;
  }
  log.scrollTop = log.scrollHeight;
}

// ---------------- Upload ----------------
function setupUpload() {
  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");
  const dropzoneText = $("#dropzone-text");

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      dropzoneText.textContent = e.dataTransfer.files[0].name;
    }
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) dropzoneText.textContent = fileInput.files[0].name;
  });

  $("#upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = fileInput.files[0];
    const ticker = $("#upload-ticker").value.trim();
    const year = $("#upload-year").value;
    const docType = $("#upload-doctype").value;
    if (!file || !ticker || !year) {
      toast("Please choose a file, ticker, and fiscal year", "error");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("ticker", ticker);
    formData.append("fiscal_year", year);
    formData.append("doc_type", docType);

    const btn = $("#upload-btn");
    btn.disabled = true;
    btn.textContent = "Uploading…";
    try {
      const result = await api("/upload", { method: "POST", body: formData });
      const sections = Array.isArray(result.sections) ? result.sections.join(", ") : "";
      toast(`Indexed ${result.ticker} ${result.period_label} (${result.doc_type})${sections ? " — " + sections : ""}`, "success");
      try {
        await loadCompanies(result.ticker, result.period_label);
        const sel = document.getElementById("ticker-select");
        if (sel) { sel.value = result.ticker; state.ticker = result.ticker; }
        populatePeriods(result.period_label);
        loadActiveTab();
      } catch (uiErr) {
        console.warn("Post-upload UI refresh error (non-fatal):", uiErr);
      }
      fileInput.value = "";
      dropzoneText.textContent = "Drag & drop a file here, or click to browse";
    } catch (err) {
      console.error("Upload error:", err);
      toast(`Upload failed: ${err?.message || String(err)}`, "error");
    } finally {
      btn.disabled = false;
      btn.textContent = "Upload & Analyze";
    }
  });
}

// ---------------- Init ----------------
function setupSelectors() {
  $("#ticker-select").addEventListener("change", (e) => {
    state.ticker = e.target.value;
    populatePeriods();
    loadActiveTab();
  });
  $("#period-select").addEventListener("change", (e) => {
    state.period = e.target.value;
    loadActiveTab();
  });
}

function setupActions() {
  document.body.addEventListener("click", (e) => {
    const action = e.target.dataset?.action;
    if (!action) return;
    if (action === "load-metrics") loadMetrics();
    if (action === "load-comparison") loadComparison();
    if (action === "load-tone") loadTone();
    if (action === "load-risks") loadRisks();
    if (action === "load-benchmark") loadBenchmark();
    if (action === "load-memo") loadMemo();
  });

  $("#chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#chat-input");
    const query = input.value.trim();
    if (!query) return;
    input.value = "";
    sendChat(query);
  });
}

(async function init() {
  setupTabs();
  setupSelectors();
  setupActions();
  setupUpload();
  await loadCompanies();
  loadActiveTab();
})();
