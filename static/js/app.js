// Data Insight Builder Frontend Application

let timelineChart = null;
let incomeChart = null;
let regionChart = null;

let allCountries = [];
let selectedCountryCodes = ['KOR', 'USA', 'JPN', 'DEU', 'WLD'];
let currentReportMarkdown = '';

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initOverviewAndCharts();
    initCountryDropdown();
    initInsightGenerator();
    initCustomCsvUpload();
});

// ==============================
// 1. 탭 네비게이션
// ==============================
function initTabs() {
    const tabWorldBankBtn = document.getElementById('tab-worldbank-btn');
    const tabCustomBtn = document.getElementById('tab-custom-btn');
    const worldBankView = document.getElementById('worldbank-view');
    const customView = document.getElementById('custom-view');

    tabWorldBankBtn.addEventListener('click', () => {
        tabWorldBankBtn.classList.add('active', 'bg-white', 'text-blue-600', 'shadow-sm');
        tabWorldBankBtn.classList.remove('text-slate-600');
        tabCustomBtn.classList.remove('active', 'bg-white', 'text-blue-600', 'shadow-sm');
        tabCustomBtn.classList.add('text-slate-600');

        worldBankView.classList.remove('hidden');
        customView.classList.add('hidden');
    });

    tabCustomBtn.addEventListener('click', () => {
        tabCustomBtn.classList.add('active', 'bg-white', 'text-blue-600', 'shadow-sm');
        tabCustomBtn.classList.remove('text-slate-600');
        tabWorldBankBtn.classList.remove('active', 'bg-white', 'text-blue-600', 'shadow-sm');
        tabWorldBankBtn.classList.add('text-slate-600');

        customView.classList.remove('hidden');
        worldBankView.classList.add('hidden');
    });
}

// ==============================
// 2. 오버뷰 통계 & 차트 초기화
// ==============================
async function initOverviewAndCharts() {
    try {
        const res = await fetch('/api/overview');
        const json = await res.json();
        if (!json.success) throw new Error(json.error);

        const data = json.data;

        // KPI 카드 업데이트
        document.getElementById('kpi-world-avg').textContent = `${data.world_average}%`;
        document.getElementById('kpi-year-badge').textContent = `${data.latest_year}년 기준`;
        if (data.korea_value) {
            document.getElementById('kpi-korea-val').textContent = `${data.korea_value}%`;
        }

        // 소득그룹 평균 막대 차트
        renderIncomeChart(data.income_group_averages);

        // 지역별 평균 수평 막대 차트
        renderRegionChart(data.region_averages);

        // 메인 시계열 라인 차트 로드
        renderSelectedTags();
        await updateTimelineChart();

    } catch (err) {
        console.error('오버뷰 로드 실패:', err);
        showToast('데이터 로드 실패: ' + err.message, 'error');
    }
}

// 소득 그룹 차트
function renderIncomeChart(incomeDict) {
    const ctx = document.getElementById('incomeChart').getContext('2d');
    const order = ['Low income', 'Lower middle income', 'Upper middle income', 'High income'];
    const labels = ['저소득국', '중저소득국', '중상위소득국', '고소득국'];
    const values = order.map(k => incomeDict[k] || 0);

    incomeChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '평균 보급률 (%)',
                data: values,
                backgroundColor: [
                    'rgba(244, 63, 94, 0.75)',
                    'rgba(245, 158, 11, 0.75)',
                    'rgba(59, 130, 246, 0.75)',
                    'rgba(16, 185, 129, 0.75)'
                ],
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } }
            }
        }
    });
}

// 지역별 차트
function renderRegionChart(regionDict) {
    const ctx = document.getElementById('regionChart').getContext('2d');
    const labels = Object.keys(regionDict);
    const values = Object.values(regionDict);

    regionChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '평균 보급률 (%)',
                data: values,
                backgroundColor: 'rgba(99, 102, 241, 0.75)',
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } }
            }
        }
    });
}

// ==============================
// 3. 국가 목록 & 시계열 차트 인터랙션
// ==============================
async function initCountryDropdown() {
    try {
        const res = await fetch('/api/countries');
        const json = await res.json();
        if (!json.success) return;

        allCountries = json.countries;
        const select = document.getElementById('country-select');

        allCountries.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c.code;
            opt.textContent = `${c.name} (${c.code}) - ${c.region}`;
            select.appendChild(opt);
        });

        // 추가 버튼
        document.getElementById('add-country-btn').addEventListener('click', () => {
            const code = select.value;
            if (!code) return;
            if (selectedCountryCodes.includes(code)) {
                showToast('이미 추가된 국가입니다.');
                return;
            }
            if (selectedCountryCodes.length >= 8) {
                showToast('차트 가독성을 위해 최대 8개국까지 비교 가능합니다.');
                return;
            }
            selectedCountryCodes.push(code);
            renderSelectedTags();
            updateTimelineChart();
            select.value = '';
        });

        // 차트 갱신 버튼
        document.getElementById('refresh-chart-btn').addEventListener('click', () => {
            updateTimelineChart();
        });

    } catch (err) {
        console.error('국가 목록 로드 오류:', err);
    }
}

function renderSelectedTags() {
    const container = document.getElementById('selected-tags-container');
    container.innerHTML = '';

    selectedCountryCodes.forEach(code => {
        const country = allCountries.find(c => c.code === code) || { name: code, code: code };
        const tag = document.createElement('span');
        tag.className = 'country-tag';
        tag.innerHTML = `
            <span>${country.name} (${country.code})</span>
            <button type="button" onclick="removeCountry('${code}')">
                <i data-lucide="x" class="w-3 h-3"></i>
            </button>
        `;
        container.appendChild(tag);
    });
    lucide.createIcons();
}

window.removeCountry = function(code) {
    if (selectedCountryCodes.length <= 1) {
        showToast('최소 1개 이상의 국가가 선택되어야 합니다.');
        return;
    }
    selectedCountryCodes = selectedCountryCodes.filter(c => c !== code);
    renderSelectedTags();
    updateTimelineChart();
};

window.applyPreset = function(codes) {
    selectedCountryCodes = [...codes];
    renderSelectedTags();
    updateTimelineChart();
    showToast('비교 국가 프리셋이 적용되었습니다.');
};

async function updateTimelineChart() {
    try {
        const res = await fetch('/api/timeline', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                country_codes: selectedCountryCodes,
                start_year: 1995,
                end_year: 2024
            })
        });
        const json = await res.json();
        if (!json.success) throw new Error(json.error);

        const timeline = json.timeline;
        const ctx = document.getElementById('timelineChart').getContext('2d');

        if (timelineChart) {
            timelineChart.destroy();
        }

        timelineChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timeline.years,
                datasets: timeline.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ` ${context.dataset.label}: ${context.parsed.y !== null ? context.parsed.y + '%' : 'N/A'}`;
                            }
                        }
                    },
                    legend: {
                        position: 'top',
                        labels: { boxWidth: 12, font: { size: 11 } }
                    }
                },
                scales: {
                    x: { grid: { display: false } },
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { callback: v => v + '%' }
                    }
                }
            }
        });

    } catch (err) {
        console.error('시계열 차트 갱신 오류:', err);
    }
}

// ==============================
// 4. Gemini AI 인사이트 생성기
// ==============================
function initInsightGenerator() {
    const btn = document.getElementById('generate-insight-btn');
    const loading = document.getElementById('insight-loading');
    const bodyContainer = document.getElementById('insight-markdown-body');
    const copyBtn = document.getElementById('copy-report-btn');
    const downloadBtn = document.getElementById('download-report-btn');

    btn.addEventListener('click', async () => {
        const mode = document.getElementById('insight-mode').value;
        const userQuestion = document.getElementById('insight-custom-question').value;

        btn.disabled = true;
        btn.classList.add('opacity-60', 'cursor-not-allowed');
        loading.classList.remove('hidden');

        try {
            const res = await fetch('/api/insights/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    focus_mode: mode,
                    selected_countries: selectedCountryCodes,
                    user_question: userQuestion
                })
            });

            const json = await res.json();
            if (!json.success) throw new Error(json.error);

            currentReportMarkdown = json.insight;
            bodyContainer.innerHTML = marked.parse(currentReportMarkdown);
            showToast('AI 인사이트 리포트가 성공적으로 생성되었습니다!');

        } catch (err) {
            console.error('인사이트 생성 오류:', err);
            bodyContainer.innerHTML = `<div class="p-4 bg-rose-50 text-rose-700 rounded-lg">생성 중 오류 발생: ${err.message}</div>`;
            showToast('리포트 생성 실패: ' + err.message, 'error');
        } finally {
            btn.disabled = false;
            btn.classList.remove('opacity-60', 'cursor-not-allowed');
            loading.classList.add('hidden');
        }
    });

    // 클립보드 복사
    copyBtn.addEventListener('click', async () => {
        if (!currentReportMarkdown) {
            showToast('복사할 리포트가 없습니다.');
            return;
        }
        await navigator.clipboard.writeText(currentReportMarkdown);
        showToast('보고서 원문(Markdown)이 클립보드에 복사되었습니다.');
    });

    // 파일 다운로드
    downloadBtn.addEventListener('click', () => {
        if (!currentReportMarkdown) {
            showToast('다운로드할 리포트가 없습니다.');
            return;
        }
        const blob = new Blob([currentReportMarkdown], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Data_Insight_Report_${new Date().toISOString().slice(0, 10)}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('보고서 파일(.md)이 다운로드되었습니다.');
    });
}

// ==============================
// 5. 커스텀 CSV 파일 업로드 & 분석
// ==============================
function initCustomCsvUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('custom-file-input');
    const fileNameDisplay = document.getElementById('selected-file-name');
    const uploadBtn = document.getElementById('upload-analyze-btn');
    const resultsArea = document.getElementById('custom-results-area');
    let selectedFile = null;

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-blue-500', 'bg-blue-50');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-blue-500', 'bg-blue-50');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-blue-500', 'bg-blue-50');
        if (e.dataTransfer.files.length > 0) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files[0]);
        }
    });

    function handleFileSelect(file) {
        if (!file.name.endsWith('.csv')) {
            showToast('CSV 파일만 업로드할 수 있습니다.', 'error');
            return;
        }
        selectedFile = file;
        fileNameDisplay.textContent = `선택된 파일: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    }

    uploadBtn.addEventListener('click', async () => {
        if (!selectedFile) {
            showToast('먼저 분석할 CSV 파일을 선택해 주세요.', 'error');
            return;
        }

        const promptInput = document.getElementById('custom-prompt-input').value;
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('generate_ai', 'true');
        formData.append('user_request', promptInput);

        uploadBtn.disabled = true;
        uploadBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i> 분석 중...`;
        lucide.createIcons();

        try {
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            const json = await res.json();
            if (!json.success) throw new Error(json.error);

            resultsArea.classList.remove('hidden');

            // 1. 배지 렌더링
            const badges = document.getElementById('custom-badges');
            badges.innerHTML = `
                <span class="px-3 py-1 bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold">총 ${json.summary.row_count}개 행</span>
                <span class="px-3 py-1 bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold">총 ${json.summary.column_count}개 컬럼</span>
                <span class="px-3 py-1 bg-blue-50 text-blue-700 rounded-lg text-xs font-semibold">수치형 변수: ${json.summary.numeric_columns.length}개</span>
            `;

            // 2. 통계 테이블 렌더링
            const statsTable = document.getElementById('custom-stats-table');
            const stats = json.summary.statistics;
            if (stats && Object.keys(stats).length > 0) {
                const metrics = ['mean', 'std', 'min', '50%', 'max'];
                const cols = Object.keys(stats);

                let thead = `<thead class="bg-slate-50"><tr><th class="p-2.5">통계 지표</th>`;
                cols.forEach(c => thead += `<th class="p-2.5">${c}</th>`);
                thead += `</tr></thead>`;

                let tbody = `<tbody class="divide-y divide-slate-100">`;
                metrics.forEach(m => {
                    const label = m === '50%' ? '중앙값 (median)' : m;
                    tbody += `<tr><td class="p-2.5 font-semibold bg-slate-50">${label}</td>`;
                    cols.forEach(c => {
                        const val = stats[c][m] !== undefined ? stats[c][m] : '-';
                        tbody += `<td class="p-2.5">${val}</td>`;
                    });
                    tbody += `</tr>`;
                });
                tbody += `</tbody>`;
                statsTable.innerHTML = thead + tbody;
            }

            // 3. AI 인사이트 마크다운 출력
            if (json.insight) {
                document.getElementById('custom-ai-output').innerHTML = marked.parse(json.insight);
            }

            showToast('커스텀 데이터 분석 및 AI 리포트 생성이 완료되었습니다!');

        } catch (err) {
            console.error('커스텀 업로드 오류:', err);
            showToast('업로드 분석 오류: ' + err.message, 'error');
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = `<i data-lucide="sparkles" class="w-4 h-4"></i> 업로드 & AI 분석 실행`;
            lucide.createIcons();
        }
    });
}

// ==============================
// 유틸리티: Toast 알림
// ==============================
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastMsg = document.getElementById('toast-message');
    toastMsg.textContent = message;

    toast.classList.remove('translate-y-20', 'opacity-0');
    setTimeout(() => {
        toast.classList.add('translate-y-20', 'opacity-0');
    }, 3500);
}
