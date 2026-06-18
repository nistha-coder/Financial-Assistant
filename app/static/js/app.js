/* ══════════════════════════════════════════════════════════════
   FinAnalyst AI — Dashboard JavaScript
   ══════════════════════════════════════════════════════════════ */

const API = "/api";
let currentTicker = "";
let currentPeriod = "";
let metricsChartInstance = null;
let benchmarkChartInstance = null;

// ── Initialisation ──────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadDocuments();
  setupUploadDragDrop();
});

// ── Tab Switching ───────────────────────────────────────────
function switchTab(tabId) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelector(`[data-tab="${tabId}"]`).classList.add("active");
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  document.getElementById(`panel-${tabId}`).classList.add("active");
}

// ── Toast Notifications ────────────────────────────────────
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  const icons = { success: "✓", error: "✕", info: "ℹ" };
  toast.innerHTML = `<span style="font-size:1.1rem">${icons[type] || "ℹ"}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => { toast.style.animation = "slideOut 0.3s ease forwards"; setTimeout(() => toast.remove(), 300); }, 4000);
}

// ── Loading Overlay ────────────────────────────────────────
function showLoading(text = "Processing…") {
  document.getElementById("loadingText").textContent = text;
  document.getElementById("loadingOverlay").classList.add("active");
  setStatus("Processing…");
}
function hideLoading() {
  document.getElementById("loadingOverlay").classList.remove("active");
  setStatus("Ready");
}
function setStatus(text) { document.getElementById("statusText").textContent = text; }

// ── API Helper ─────────────────────────────────────────────
async function apiFetch(url, options = {}) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `HTTP ${resp.status}`);
  }
  return resp.json();
}

// ── Load Documents & Populate Selectors ────────────────────
async function loadDocuments() {
  try {
    const docs = await apiFetch(`${API}/documents`);
    const companyMap = {};
    const periods = new Set();
    docs.forEach(d => {
      companyMap[d.ticker] = d.company;
      periods.add(d.period_label);
    });

    const cs = document.getElementById("companySelect");
    cs.innerHTML = '<option value="">— Select Company —</option>';
    Object.entries(companyMap).forEach(([ticker, company]) => {
      cs.innerHTML += `<option value="${ticker}">${company} (${ticker})</option>`;
    });

    const ps = document.getElementById("periodSelect");
    const pp = document.getElementById("priorPeriodSelect");
    ps.innerHTML = '<option value="">— Select Period —</option>';
    pp.innerHTML = '<option value="">— Auto (prior year) —</option>';
    [...periods].sort().reverse().forEach(p => {
      ps.innerHTML += `<option value="${p}">${p}</option>`;
      pp.innerHTML += `<option value="${p}">${p}</option>`;
    });

    if (docs.length > 0) showToast(`${docs.length} documents loaded`, "success");
    else showToast("No documents found — upload some filings", "info");
  } catch (e) {
    showToast(`Failed to load documents: ${e.message}`, "error");
  }
}

// ── Handle Analyze Button ──────────────────────────────────
function handleLoad() {
  currentTicker = document.getElementById("companySelect").value;
  currentPeriod = document.getElementById("periodSelect").value;
  if (!currentTicker || !currentPeriod) { showToast("Select a company and period first", "error"); return; }
  const activeTab = document.querySelector(".tab-btn.active").dataset.tab;
  const loaders = { metrics: loadMetrics, compare: loadCompare, tone: loadTone, risks: loadRisks, benchmark: loadBenchmark };
  (loaders[activeTab] || loadMetrics)();
}

// ── Metrics ────────────────────────────────────────────────
async function loadMetrics() {
  if (!currentTicker || !currentPeriod) return;
  showLoading("Extracting metrics…");
  try {
    const data = await apiFetch(`${API}/metrics?ticker=${currentTicker}&period=${currentPeriod}`);
    renderMetrics(data);
    showToast("Metrics loaded", "success");
  } catch (e) { showToast(`Metrics error: ${e.message}`, "error"); }
  finally { hideLoading(); }
}

function renderMetrics(data) {
  const grid = document.getElementById("metricsGrid");
  const fields = [
    { key: "revenue", label: "Revenue", unit: `${data.currency} ${data.unit}` },
    { key: "gross_profit", label: "Gross Profit", unit: `${data.currency} ${data.unit}` },
    { key: "operating_income", label: "Operating Income", unit: `${data.currency} ${data.unit}` },
    { key: "ebitda", label: "EBITDA", unit: `${data.currency} ${data.unit}` },
    { key: "net_income", label: "Net Income", unit: `${data.currency} ${data.unit}` },
    { key: "gross_margin_pct", label: "Gross Margin", unit: "%" },
    { key: "operating_margin_pct", label: "Operating Margin", unit: "%" },
    { key: "net_margin_pct", label: "Net Margin", unit: "%" },
    { key: "ebitda_margin_pct", label: "EBITDA Margin", unit: "%" },
    { key: "operating_cash_flow", label: "Operating Cash Flow", unit: `${data.currency} ${data.unit}` },
    { key: "free_cash_flow", label: "Free Cash Flow", unit: `${data.currency} ${data.unit}` },
    { key: "total_debt", label: "Total Debt", unit: `${data.currency} ${data.unit}` },
  ];

  grid.innerHTML = fields.filter(f => data[f.key] != null).map(f =>
    `<div class="metric-card">
       <div class="metric-label">${f.label}</div>
       <div class="metric-value">${formatNumber(data[f.key], f.unit === "%")}</div>
       <div class="metric-unit">${f.unit}</div>
     </div>`
  ).join("");

  renderMetricsChart(data, fields);
}

function renderMetricsChart(data, fields) {
  const chartFields = fields.filter(f => !f.unit.includes("%") && data[f.key] != null);
  const ctx = document.getElementById("metricsChart").getContext("2d");
  if (metricsChartInstance) metricsChartInstance.destroy();
  metricsChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: chartFields.map(f => f.label),
      datasets: [{ label: `${data.ticker} ${data.period_label}`, data: chartFields.map(f => data[f.key]),
        backgroundColor: "rgba(99,102,241,0.5)", borderColor: "#6366f1", borderWidth: 1, borderRadius: 6 }]
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: "#94a3b8" } } },
      scales: { x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
               y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } } } }
  });
}

// ── Compare ────────────────────────────────────────────────
async function loadCompare() {
  if (!currentTicker || !currentPeriod) { showToast("Select company and period first", "error"); return; }
  let priorPeriod = document.getElementById("priorPeriodSelect").value;
  if (!priorPeriod) {
    const match = currentPeriod.match(/FY(\d{4})/);
    priorPeriod = match ? `FY${parseInt(match[1]) - 1}` : "";
  }
  if (!priorPeriod) { showToast("Could not determine prior period", "error"); return; }
  showLoading("Comparing periods…");
  try {
    const data = await apiFetch(`${API}/compare?ticker=${currentTicker}&current_period=${currentPeriod}&prior_period=${priorPeriod}`);
    renderCompare(data);
    showToast("Comparison ready", "success");
  } catch (e) { showToast(`Compare error: ${e.message}`, "error"); }
  finally { hideLoading(); }
}

function renderCompare(data) {
  const el = document.getElementById("compareContent");
  const rows = data.deltas.filter(d => d.current_value != null || d.prior_value != null).map(d => {
    const cls = d.pct_change > 0 ? "positive" : d.pct_change < 0 ? "negative" : "";
    return `<tr><td>${formatMetricName(d.metric)}</td><td>${fmtVal(d.prior_value)}</td>
      <td>${fmtVal(d.current_value)}</td><td>${fmtVal(d.absolute_change)}</td>
      <td class="${cls}">${d.pct_change != null ? (d.pct_change > 0 ? "+" : "") + d.pct_change.toFixed(1) + "%" : "—"}</td></tr>`;
  }).join("");
  el.innerHTML = `<table class="data-table"><thead><tr><th>Metric</th><th>${data.prior_period}</th>
    <th>${data.current_period}</th><th>Change</th><th>% Change</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// ── Tone ───────────────────────────────────────────────────
async function loadTone() {
  if (!currentTicker || !currentPeriod) return;
  showLoading("Analyzing management tone…");
  try {
    const data = await apiFetch(`${API}/tone?ticker=${currentTicker}&period=${currentPeriod}`);
    renderTone(data);
    showToast("Tone analysis complete", "success");
  } catch (e) { showToast(`Tone error: ${e.message}`, "error"); }
  finally { hideLoading(); }
}

function renderTone(data) {
  const el = document.getElementById("toneContent");
  const pct = Math.round(data.confidence_score * 100);
  const color = data.sentiment === "confident" ? "var(--green)" : data.sentiment === "cautious" ? "var(--red)" : "var(--amber)";
  const hedging = data.hedging_phrases.map(p => `<span class="phrase-tag">"${p}"</span>`).join("");
  const confidence = data.confidence_phrases.map(p => `<span class="phrase-tag">"${p}"</span>`).join("");
  el.innerHTML = `
    <div class="tone-card">
      <div class="tone-header">
        <span class="tone-badge ${data.sentiment}">${data.sentiment}</span>
        <div class="score-bar"><div class="score-fill" style="width:${pct}%;background:${color}"></div></div>
        <span class="score-label">${pct}%</span>
      </div>
      <p style="color:var(--text-secondary);font-size:0.9rem;line-height:1.7">${data.summary}</p>
      ${hedging ? `<div class="phrases-section"><h4>⚠ Hedging Phrases</h4>${hedging}</div>` : ""}
      ${confidence ? `<div class="phrases-section"><h4>✓ Confidence Phrases</h4>${confidence}</div>` : ""}
    </div>`;
}

// ── Risks ──────────────────────────────────────────────────
async function loadRisks() {
  if (!currentTicker || !currentPeriod) return;
  showLoading("Extracting risk factors…");
  try {
    const data = await apiFetch(`${API}/risks?ticker=${currentTicker}&period=${currentPeriod}`);
    renderRisks(data);
    showToast(`${data.risks.length} risk factors extracted`, "success");
  } catch (e) { showToast(`Risks error: ${e.message}`, "error"); }
  finally { hideLoading(); }
}

function renderRisks(data) {
  const el = document.getElementById("risksContent");
  if (!data.risks.length) { el.innerHTML = '<div class="empty-state"><p>No risk factors found</p></div>'; return; }
  el.innerHTML = data.risks.map(r =>
    `<div class="risk-card ${r.severity}">
       <div class="risk-title">${r.title}</div>
       <div class="risk-meta">
         <span class="risk-tag">${r.category}</span>
         <span class="risk-tag" style="color:${r.severity === "high" ? "var(--red)" : r.severity === "medium" ? "var(--amber)" : "var(--green)"}">${r.severity.toUpperCase()}</span>
       </div>
       <div class="risk-desc">${r.description}</div>
     </div>`
  ).join("");
}

// ── Benchmark ──────────────────────────────────────────────
async function loadBenchmark() {
  const tickers = document.getElementById("benchmarkTickers").value || currentTicker;
  if (!tickers || !currentPeriod) { showToast("Enter tickers and select a period", "error"); return; }
  showLoading("Building benchmark…");
  try {
    const data = await apiFetch(`${API}/benchmark?tickers=${tickers}&period=${currentPeriod}`);
    renderBenchmark(data);
    showToast("Benchmark table ready", "success");
  } catch (e) { showToast(`Benchmark error: ${e.message}`, "error"); }
  finally { hideLoading(); }
}

function renderBenchmark(data) {
  const el = document.getElementById("benchmarkContent");
  if (!data.rows.length) { el.innerHTML = '<div class="empty-state"><p>No benchmark data</p></div>'; return; }
  const headers = ["Company", "Ticker", "Revenue", "Rev Growth %", "EBITDA Margin %", "Op Margin %", "Net Margin %", "CapEx % Rev", "Debt/EBITDA"];
  const rows = data.rows.map(r =>
    `<tr><td>${r.company}</td><td>${r.ticker}</td><td>${fmtVal(r.revenue)}</td>
     <td>${fmtVal(r.revenue_growth_yoy_pct)}</td><td>${fmtVal(r.ebitda_margin_pct)}</td>
     <td>${fmtVal(r.operating_margin_pct)}</td><td>${fmtVal(r.net_margin_pct)}</td>
     <td>${fmtVal(r.capex_pct_of_revenue)}</td><td>${fmtVal(r.debt_to_ebitda)}</td></tr>`
  ).join("");
  el.innerHTML = `<table class="data-table"><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
  renderBenchmarkChart(data);
}

function renderBenchmarkChart(data) {
  const ctx = document.getElementById("benchmarkChart").getContext("2d");
  if (benchmarkChartInstance) benchmarkChartInstance.destroy();
  const labels = data.rows.map(r => r.ticker);
  const colors = ["rgba(99,102,241,0.6)", "rgba(34,211,238,0.6)", "rgba(52,211,153,0.6)", "rgba(248,113,113,0.6)", "rgba(251,191,36,0.6)"];
  const datasets = [
    { label: "EBITDA Margin %", data: data.rows.map(r => r.ebitda_margin_pct) },
    { label: "Op Margin %", data: data.rows.map(r => r.operating_margin_pct) },
    { label: "Net Margin %", data: data.rows.map(r => r.net_margin_pct) },
  ].map((ds, i) => ({ ...ds, backgroundColor: colors[i], borderColor: colors[i].replace("0.6", "1"), borderWidth: 1, borderRadius: 4 }));
  benchmarkChartInstance = new Chart(ctx, {
    type: "bar", data: { labels, datasets },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: "#94a3b8" } } },
      scales: { x: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } },
               y: { ticks: { color: "#64748b" }, grid: { color: "rgba(255,255,255,0.04)" } } } }
  });
}

// ── Memo ───────────────────────────────────────────────────
async function generateMemo() {
  if (!currentTicker || !currentPeriod) { showToast("Select company and period first", "error"); return; }
  const peers = document.getElementById("memoPeers").value;
  const url = `${API}/memo?ticker=${currentTicker}&period=${currentPeriod}${peers ? "&peers=" + peers : ""}`;
  showLoading("Generating investment memo (this may take a moment)…");
  try {
    const data = await apiFetch(url, { method: "POST" });
    renderMemo(data);
    showToast("Investment memo generated", "success");
  } catch (e) { showToast(`Memo error: ${e.message}`, "error"); }
  finally { hideLoading(); }
}

function renderMemo(data) {
  const el = document.getElementById("memoContent");
  const listHtml = (items) => items.map(i => `<li>${i}</li>`).join("");
  el.innerHTML = `
    <div class="memo-section"><h3>Company Overview</h3><p>${data.company_overview}</p></div>
    <div class="memo-section"><h3>Financial Summary</h3><p>${data.financial_summary}</p></div>
    <div class="memo-section"><h3>🐂 Bull Case</h3><ul>${listHtml(data.bull_case)}</ul></div>
    <div class="memo-section"><h3>🐻 Bear Case</h3><ul>${listHtml(data.bear_case)}</ul></div>
    <div class="memo-section"><h3>⚠ Key Risks</h3><ul>${listHtml(data.key_risks)}</ul></div>
    <div class="memo-section"><h3>❓ Questions to Investigate</h3><ul>${listHtml(data.questions_to_investigate)}</ul></div>`;
}

// ── Ask AI ─────────────────────────────────────────────────
async function askQuestion() {
  const q = document.getElementById("askInput").value.trim();
  if (!q) { showToast("Enter a question first", "error"); return; }
  showLoading("Searching documents…");
  try {
    const params = new URLSearchParams({ question: q });
    if (currentTicker) params.append("ticker", currentTicker);
    if (currentPeriod) params.append("period", currentPeriod);
    const data = await apiFetch(`${API}/ask?${params}`);
    renderAnswer(data);
    showToast("Answer ready", "success");
  } catch (e) { showToast(`Ask error: ${e.message}`, "error"); }
  finally { hideLoading(); }
}

function renderAnswer(data) {
  const el = document.getElementById("askContent");
  const sources = data.sources && data.sources.length
    ? `<div class="ask-sources"><h4>Sources</h4>${data.sources.map(s => `<span class="phrase-tag">${s.ticker} ${s.period_label} — ${s.section}</span>`).join("")}</div>` : "";
  el.innerHTML = `<p style="white-space:pre-wrap">${data.answer}</p>${sources}`;
}

// ── Upload ─────────────────────────────────────────────────
function setupUploadDragDrop() {
  const dz = document.getElementById("dropzone");
  const fi = document.getElementById("fileInput");
  ["dragenter", "dragover"].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach(e => dz.addEventListener(e, ev => { ev.preventDefault(); dz.classList.remove("dragover"); }));
  dz.addEventListener("drop", ev => { fi.files = ev.dataTransfer.files; showFileName(); });
  fi.addEventListener("change", showFileName);
}

function showFileName() {
  const fi = document.getElementById("fileInput");
  document.getElementById("fileName").textContent = fi.files.length ? `📄 ${fi.files[0].name}` : "";
}

async function uploadFile() {
  const fi = document.getElementById("fileInput");
  if (!fi.files.length) { showToast("Select a file first", "error"); return; }
  const ticker = document.getElementById("uploadTicker").value.trim().toUpperCase();
  const period = document.getElementById("uploadPeriod").value.trim();
  const docType = document.getElementById("uploadDocType").value;
  if (!ticker || !period) { showToast("Ticker and period are required", "error"); return; }
  const fd = new FormData();
  fd.append("file", fi.files[0]);
  fd.append("ticker", ticker);
  fd.append("period", period);
  fd.append("doc_type", docType);
  showLoading("Uploading and ingesting…");
  try {
    const data = await apiFetch(`${API}/upload`, { method: "POST", body: fd });
    showToast(data.message, "success");
    document.getElementById("uploadForm").reset();
    document.getElementById("fileName").textContent = "";
    loadDocuments();
  } catch (e) { showToast(`Upload error: ${e.message}`, "error"); }
  finally { hideLoading(); }
}

// ── Utilities ──────────────────────────────────────────────
function formatNumber(val, isPct) {
  if (val == null) return "—";
  if (isPct) return val.toFixed(1);
  if (Math.abs(val) >= 1000) return val.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return val.toLocaleString("en-US", { maximumFractionDigits: 2 });
}
function fmtVal(v) { return v != null ? formatNumber(v) : "—"; }
function formatMetricName(name) { return name.replace(/_/g, " ").replace(/\bpct\b/g, "%").replace(/\b\w/g, c => c.toUpperCase()); }
