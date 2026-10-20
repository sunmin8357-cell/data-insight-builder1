/**
 * AI Data Insight Builder - Vanilla JavaScript Frontend
 * Strict Console Log Rules & Educational Step-by-Step Flow
 */

// Global state
let currentInspectionData = null;
let currentChartInstance = null;
let lastRunResult = null;

// Initialize on DOMContentLoaded
document.addEventListener("DOMContentLoaded", () => {
  console.log("[PAGE] 페이지 로드 완료");
  checkServerHealth();
  setupUploadEvents();
  setupNlQueryEvents();
  setupModeButtons();
  setupChatEvents();
});

/**
 * 1. Check Server Health (/health)
 */
async function checkServerHealth() {
  const statusEl = document.getElementById("serverStatus");
  try {
    const res = await fetch("/health");
    if (!res.ok) throw new Error("서버 응답 오류");
    const data = await res.json();
    if (data.status === "healthy") {
      statusEl.className = "status-indicator healthy";
      statusEl.innerHTML = `<span class="dot"></span> 서버 정상 (AI: ${data.api_key_configured ? "연결됨" : "키 미설정"})`;
    }
  } catch (err) {
    statusEl.className = "status-indicator warning";
    statusEl.innerHTML = `<span class="dot"></span> 서버 연결 실패`;
    console.error("[ERROR] 헬스체크 실패:", err);
  }
}

/**
 * 2. Setup Upload Events (Drag & Drop + File Input)
 */
function setupUploadEvents() {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("csvFileInput");

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("drag-over");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileSelected(e.target.files[0]);
    }
  });
}

function handleFileSelected(file) {
  if (!file.name.toLowerCase().endsWith(".csv")) {
    alert("CSV 파일(.csv)만 업로드할 수 있습니다.");
    console.error("[ERROR] 잘못된 확장자 선택:", file.name);
    return;
  }

  console.log(`[UPLOAD] 파일 선택 (파일명: ${file.name}, 크기: ${file.size} bytes)`);
  uploadAndInspect(file);
}

/**
 * 3. Step 1: Upload and Inspect (/inspect)
 */
async function uploadAndInspect(file) {
  const loading = document.getElementById("inspectLoading");
  const diagBox = document.getElementById("diagnosticsResult");
  const step2 = document.getElementById("step2Section");
  const step3 = document.getElementById("step3Section");
  const step4 = document.getElementById("step4Section");

  loading.classList.remove("hidden");
  diagBox.classList.add("hidden");
  step2.classList.add("hidden");
  step3.classList.add("hidden");
  step4.classList.add("hidden");

  console.log("[INSPECT] 진단 요청 시작");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/inspect", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    loading.classList.add("hidden");

    if (!res.ok) {
      console.error("[ERROR] 진단 실패:", data.error);
      alert(data.error || "파일 진단 중 오류가 발생했습니다.");
      return;
    }

    currentInspectionData = data;
    console.log(`[INSPECT] 응답 수신 (행 수: ${data.row_count}, 열 수: ${data.column_count}, 경고 수: ${data.warnings.length})`);

    // Render Diagnostics UI
    renderDiagnostics(data);

    // Unhide Natural Language query section
    const nlSection = document.getElementById("nlSection");
    if (nlSection) nlSection.classList.remove("hidden");

    // Automatically trigger Step 2 (Gemini Suggestions)
    requestSuggestions(data);

  } catch (err) {
    loading.classList.add("hidden");
    console.error("[ERROR] /inspect 통신 오류:", err);
    alert("네트워크 오류로 서버와 통신하지 못했습니다.");
  }
}

/**
 * 3.5 Setup Natural Language Query Events (/ask-nl)
 */
function setupNlQueryEvents() {
  const form = document.getElementById("nlQueryForm");
  const input = document.getElementById("nlQueryInput");
  const chips = document.querySelectorAll(".nl-example-chip");

  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      const q = chip.getAttribute("data-query");
      if (q) {
        input.value = q;
        sendNlQuery(q);
      }
    });
  });

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (q) {
        sendNlQuery(q);
      }
    });
  }
}

async function sendNlQuery(query) {
  const loading = document.getElementById("nlLoading");
  const resultBox = document.getElementById("nlResultBox");
  const answerEl = document.getElementById("nlAnswerText");
  const actionArea = document.getElementById("nlActionArea");

  loading.classList.remove("hidden");
  resultBox.classList.add("hidden");
  actionArea.innerHTML = "";

  console.log(`[NL] 자연어 분석 요청: "${query}"`);

  try {
    const res = await fetch("/ask-nl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query })
    });

    const data = await res.json();
    loading.classList.add("hidden");

    if (!res.ok) {
      alert(data.error || "자연어 질의 분석에 실패했습니다.");
      return;
    }

    resultBox.classList.remove("hidden");
    answerEl.innerHTML = parseSimpleMarkdown(data.answer || "");

    // Create custom dynamic chart visualization button if suggested
    if (data.chart_button && data.chart_button.tool) {
      const btn = document.createElement("button");
      btn.className = "btn-chart-action";
      btn.innerHTML = `📊 ${escapeHtml(data.chart_button.title || "맞춤 시각화 그래프 보기")}`;
      btn.addEventListener("click", () => {
        executeTool(data.chart_button.tool, data.chart_button.params, data.chart_button.params.reference_period);
      });
      actionArea.appendChild(btn);
    }

  } catch (err) {
    loading.classList.add("hidden");
    console.error("[ERROR] /ask-nl 통신 오류:", err);
  }
}

function renderDiagnostics(data) {
  const diagBox = document.getElementById("diagnosticsResult");
  diagBox.classList.remove("hidden");

  document.getElementById("statFilename").textContent = data.filename;
  document.getElementById("statEncoding").textContent = data.encoding;
  document.getElementById("statHeader").textContent = `${data.skipped_rows + 1}번째 줄 (${data.skipped_rows}줄 건너뜀)`;
  document.getElementById("statShape").textContent = `${data.row_count}행 × ${data.column_count}열`;
  document.getElementById("statBestYear").textContent = data.recommended_year ? `${data.recommended_year}년` : "판별 불가";

  // Warnings
  const warningsBox = document.getElementById("warningsBox");
  const warningsList = document.getElementById("warningsList");
  warningsList.innerHTML = "";
  if (data.warnings && data.warnings.length > 0) {
    warningsBox.classList.remove("hidden");
    data.warnings.forEach(w => {
      const li = document.createElement("li");
      li.textContent = w;
      warningsList.appendChild(li);
    });
  } else {
    warningsBox.classList.add("hidden");
  }

  // Preview Table
  const tableContainer = document.getElementById("previewTableContainer");
  tableContainer.innerHTML = "";
  if (data.preview_rows && data.preview_rows.length > 0) {
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const trHead = document.createElement("tr");

    // Show first 8 columns for preview readability
    const previewCols = data.columns.slice(0, 8);
    previewCols.forEach(col => {
      const th = document.createElement("th");
      th.textContent = col || "(빈열)";
      trHead.appendChild(th);
    });
    thead.appendChild(trHead);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    data.preview_rows.forEach(row => {
      const tr = document.createElement("tr");
      previewCols.forEach(col => {
        const td = document.createElement("td");
        td.textContent = row[col] !== null && row[col] !== undefined ? row[col] : "-";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableContainer.appendChild(table);
  }
}

/**
 * 4. Step 2: Request AI Suggestions (/suggest)
 */
async function requestSuggestions(inspectionData) {
  const step2 = document.getElementById("step2Section");
  const loading = document.getElementById("suggestLoading");
  const listContainer = document.getElementById("suggestionsList");

  step2.classList.remove("hidden");
  loading.classList.remove("hidden");
  listContainer.innerHTML = "";

  console.log("[SUGGEST] 제안 요청 시작");

  try {
    const res = await fetch("/suggest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recommended_year: inspectionData.recommended_year
      })
    });

    const data = await res.json();
    loading.classList.add("hidden");

    if (!res.ok) {
      console.error("[ERROR] 제안 요청 실패:", data.error);
      listContainer.innerHTML = `<p class="error-msg">⚠️ AI 제안을 불러오지 못했습니다: ${data.error}</p>`;
      return;
    }

    const suggestions = data.suggestions || [];
    console.log(`[SUGGEST] 응답 수신 (제안 개수: ${suggestions.length})`);

    if (suggestions.length === 0) {
      listContainer.innerHTML = "<p>제안 가능한 도구가 없습니다.</p>";
      return;
    }

    suggestions.forEach(item => {
      const card = document.createElement("div");
      card.className = "suggest-card";

      card.innerHTML = `
        <div class="suggest-card-top">
          <span class="badge">${item.tool}</span>
          <h3>기준시점: ${item.reference_period || "기본"}</h3>
          <p class="why"><strong>💡 왜 이 분석인가:</strong> ${escapeHtml(item.why)}</p>
          <p class="caution"><strong>⚠️ 주의:</strong> ${escapeHtml(item.caution)}</p>
        </div>
        <button class="btn btn-primary btn-run">이 분석 실행하기 (Pandas)</button>
      `;

      card.querySelector(".btn-run").addEventListener("click", () => {
        executeTool(item.tool, item.params, item.reference_period);
      });

      listContainer.appendChild(card);
    });

  } catch (err) {
    loading.classList.add("hidden");
    console.error("[ERROR] /suggest 통신 오류:", err);
  }
}

/**
 * 5. Step 3: Run Tool with Pandas (/run)
 */
async function executeTool(toolName, params, refPeriod) {
  const step3 = document.getElementById("step3Section");
  const loading = document.getElementById("runLoading");
  const resultBox = document.getElementById("runResultBox");
  const step4 = document.getElementById("step4Section");

  step3.classList.remove("hidden");
  loading.classList.remove("hidden");
  resultBox.classList.add("hidden");
  step4.classList.add("hidden");

  // Scroll to step 3 smoothly
  step3.scrollIntoView({ behavior: "smooth" });

  console.log(`[RUN] 도구 실행 시작 (도구명: ${toolName}, 기준시점: ${refPeriod || params.reference_period || "미지정"})`);

  try {
    const res = await fetch("/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tool: toolName, params })
    });

    const data = await res.json();
    loading.classList.add("hidden");

    if (!res.ok) {
      console.error("[ERROR] 도구 실행 실패:", data.error);
      alert(data.error || "도구 실행 중 오류가 발생했습니다.");
      return;
    }

    lastRunResult = data;
    console.log(`[RUN] 결과 수신 완료 (사용한 행: ${data.rows_used}, 제외한 행: ${data.rows_excluded})`);

    // Render results
    renderRunResult(data);

    // Trigger Step 4 automatically in default Mode B
    requestExplain("B");

  } catch (err) {
    loading.classList.add("hidden");
    console.error("[ERROR] /run 통신 오류:", err);
  }
}

function renderRunResult(data) {
  const resultBox = document.getElementById("runResultBox");
  resultBox.classList.remove("hidden");

  document.getElementById("metaTool").textContent = data.tool;
  document.getElementById("metaPeriod").textContent = data.reference_period;
  document.getElementById("metaUsed").textContent = `${data.rows_used}행`;
  document.getElementById("metaExcluded").textContent = `${data.rows_excluded}행 (${data.exclusion_reason})`;
  document.getElementById("metaUnit").textContent = data.unit;

  // Render Chart
  renderChart(data);

  // Render summary text / tables
  renderCalcSummary(data);
}

function renderChart(data) {
  const canvas = document.getElementById("analysisChart");
  const ctx = canvas.getContext("2d");

  // Destroy previous chart if exists
  if (currentChartInstance) {
    currentChartInstance.destroy();
  }

  const chartData = data.result_data ? data.result_data.chart_data : null;
  if (!chartData) {
    canvas.style.display = "none";
    return;
  }
  canvas.style.display = "block";

  let chartType = "bar";
  let options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: "top" }
    }
  };

  // Select appropriate chart type based on tool
  if (data.tool === "trend_line") {
    chartType = "line";
  } else if (data.tool === "top_bottom_n") {
    chartType = "bar";
    options.indexAxis = "y"; // Horizontal bar chart
  } else if (data.tool === "correlation_scatter") {
    chartType = "scatter";
    options.scales = {
      x: { title: { display: true, text: data.result_data.x_column } },
      y: { title: { display: true, text: data.result_data.y_column } }
    };
  }

  currentChartInstance = new Chart(ctx, {
    type: chartType,
    data: chartData,
    options: options
  });

  console.log(`[CHART] 차트 렌더 완료 (차트 종류: ${chartType})`);
}

function renderCalcSummary(data) {
  const summaryArea = document.getElementById("calcSummaryArea");
  summaryArea.innerHTML = "";

  const resData = data.result_data || {};

  // If top_n items exist
  if (resData.top_n) {
    let html = `<div style="display:flex; gap:20px; flex-wrap:wrap;">`;
    html += `<div style="flex:1; min-width:240px;"><h4>🥇 상위 ${resData.n}개 순위</h4><ol style="padding-left:20px;">`;
    resData.top_n.forEach(item => {
      html += `<li><strong>${escapeHtml(item.name)}:</strong> ${item.value !== null ? item.value + "%" : "-"}</li>`;
    });
    html += `</ol></div>`;

    if (resData.bottom_n) {
      html += `<div style="flex:1; min-width:240px;"><h4>🔻 하위 ${resData.n}개 순위</h4><ol style="padding-left:20px;">`;
      resData.bottom_n.forEach(item => {
        html += `<li><strong>${escapeHtml(item.name)}:</strong> ${item.value !== null ? item.value + "%" : "-"}</li>`;
      });
      html += `</ol></div>`;
    }
    html += `</div>`;
    summaryArea.innerHTML = html;
  } else if (resData.target_item) {
    // compare_one_vs_all
    summaryArea.innerHTML = `
      <div style="background:#fff; border:1px solid #e2e8f0; padding:16px; border-radius:8px;">
        <h4>📊 ${escapeHtml(resData.target_item)} 분석 요약</h4>
        <p>• 해당 국가 수치: <strong>${resData.target_value}%</strong> (전체 ${resData.total_countries}개국 중 ${resData.rank}위)</p>
        <p>• 전 세계 평균: <strong>${resData.overall_mean}%</strong> (평균 대비 <strong>${resData.diff_from_mean > 0 ? "+" : ""}${resData.diff_from_mean}%p</strong>)</p>
        <p>• 전 세계 중앙값: <strong>${resData.overall_median}%</strong></p>
      </div>
    `;
  }
}

/**
 * 6. Step 4: AI Explain Mode A/B (/explain)
 */
function setupModeButtons() {
  const btnB = document.getElementById("btnModeB");
  const btnA = document.getElementById("btnModeA");

  btnB.addEventListener("click", () => {
    btnB.classList.add("active");
    btnA.classList.remove("active");
    requestExplain("B");
  });

  btnA.addEventListener("click", () => {
    btnA.classList.add("active");
    btnB.classList.remove("active");
    requestExplain("A");
  });
}

async function requestExplain(mode) {
  const step4 = document.getElementById("step4Section");
  const loading = document.getElementById("explainLoading");
  const loadingText = document.getElementById("explainLoadingText");
  const reportContainer = document.getElementById("reportContainer");
  const reportBadge = document.getElementById("reportModeBadge");
  const reportContent = document.getElementById("reportContent");

  step4.classList.remove("hidden");
  loading.classList.remove("hidden");
  reportContainer.classList.add("hidden");

  if (mode === "A") {
    loadingText.textContent = "Gemini에게 계산 결과 없이 '그냥 보고서 써줘'라고 요청 중 (의도적 환각 유도)...";
    reportBadge.className = "badge mode-a";
    reportBadge.textContent = "⚠️ 모드 A: 비교용 보고서 (Pandas 계산 결과 미제공)";
  } else {
    loadingText.textContent = "Gemini가 Pandas의 엄격한 계산 결과만 바탕으로 해석 보고서 작성 중...";
    reportBadge.className = "badge mode-b";
    reportBadge.textContent = "🛡️ 모드 B: 정식 교육용 보고서 (Pandas 계산 기반)";
  }

  console.log(`[EXPLAIN] 해석 요청 시작 (모드: ${mode})`);

  try {
    const res = await fetch("/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: mode,
        run_result: lastRunResult
      })
    });

    const data = await res.json();
    loading.classList.add("hidden");

    if (!res.ok) {
      console.error("[ERROR] 해석 요청 실패:", data.error);
      alert(data.error || "해석 보고서 생성에 실패했습니다.");
      return;
    }

    console.log(`[EXPLAIN] 응답 수신 완료 (모드: ${mode})`);
    reportContainer.classList.remove("hidden");

    // Simple markdown-to-HTML parser for basic headings, bold, bullet points
    reportContent.innerHTML = parseSimpleMarkdown(data.report || "");

    // Clear previous chat messages when a new report is generated
    const chatMessages = document.getElementById("chatMessages");
    if (chatMessages) chatMessages.innerHTML = "";

  } catch (err) {
    loading.classList.add("hidden");
    console.error("[ERROR] /explain 통신 오류:", err);
  }
}

/**
 * 7. Setup Follow-up Q&A Chat Events
 */
function setupChatEvents() {
  const chips = document.querySelectorAll(".question-chips .chip");
  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");

  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      const question = chip.getAttribute("data-q");
      if (question) {
        sendFollowupQuestion(question);
      }
    });
  });

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const question = input.value.trim();
      if (question) {
        sendFollowupQuestion(question);
        input.value = "";
      }
    });
  }
}

async function sendFollowupQuestion(question) {
  const chatMessages = document.getElementById("chatMessages");
  const reportContent = document.getElementById("reportContent");
  const currentReportText = reportContent ? reportContent.innerText : "";

  // Append User Bubble
  const userBubble = document.createElement("div");
  userBubble.className = "chat-bubble user";
  userBubble.textContent = question;
  chatMessages.appendChild(userBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  // Append AI Loading Bubble
  const aiBubble = document.createElement("div");
  aiBubble.className = "chat-bubble ai";
  aiBubble.innerHTML = "<em>답변을 작성하고 있습니다...</em>";
  chatMessages.appendChild(aiBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  console.log(`[EXPLAIN] 후속 질문 전송: "${question}"`);

  try {
    const res = await fetch("/followup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question,
        report: currentReportText
      })
    });

    const data = await res.json();
    if (!res.ok) {
      aiBubble.innerHTML = `⚠️ 오류: ${data.error || "답변을 불러오지 못했습니다."}`;
      return;
    }

    aiBubble.innerHTML = parseSimpleMarkdown(data.answer || "");
    chatMessages.scrollTop = chatMessages.scrollHeight;
    console.log(`[EXPLAIN] 후속 답변 수신 완료`);

  } catch (err) {
    aiBubble.innerHTML = "⚠️ 네트워크 오류로 답변을 받지 못했습니다.";
    console.error("[ERROR] /followup 통신 오류:", err);
  }
}

/**
 * Helper: Simple Markdown Parser for Report Rendering
 */
function parseSimpleMarkdown(md) {
  let html = md
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*)\*/gim, '<em>$1</em>')
    .replace(/^\• (.*$)/gim, '<li>$1</li>')
    .replace(/^\- (.*$)/gim, '<li>$1</li>')
    .replace(/\n\n/gim, '</p><p>')
    .replace(/\n/gim, '<br>');

  return `<p>${html}</p>`;
}

function escapeHtml(text) {
  if (!text) return "";
  const map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}
