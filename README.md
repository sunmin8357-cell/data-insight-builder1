# 📊 Data Insight Builder

**Data Insight Builder**는 세계은행(World Bank)의 글로벌 통계 데이터셋을 **Pandas**로 가공·분석하고, **Google Gemini API**(`gemini-3.5-flash-lite`)를 활용하여 전문적인 데이터 인사이트 및 정책/비즈니스 분석 리포트를 자동으로 생성해 주는 **Flask 기반 풀스택 데이터 인텔리전스 웹 애플리케이션**입니다.

---

## 📌 주요 특징 및 기능

1. **글로벌 인터넷 보급률 시계열 분석 (World Bank Dataset)**
   - 1960년부터 2025년까지 전 세계 180+ 개국의 인터넷 보급률 통계 자동 파싱
   - **글로벌 핵심 지표 (KPI)** 실시간 산출 (세계 평균, 한국 보급률, 소득 그룹별 격차, 취약 지역 지표)
   - **Chart.js 기반 인터랙티브 시계열 차트**:
     - 국가 다중 선택 및 비교 (선진국, 아시아 주요국, 최상위/최하위 프리셋 제공)
     - 소득 수준별(High, Upper-middle, Lower-middle, Low) 및 대륙/지역별 평균 보급률 비교 막대 차트

2. **🧠 Google Gemini AI 데이터 인사이트 리포트 생성기**
   - **모드 1: 글로벌 트렌드 & 디지털 불평등 분석**: 고소득국과 저소득국 간의 양극화 및 원인 분석
   - **모드 2: 선택 국가 간 성장 궤적 심층 비교**: 선택된 국가들의 10~20년간 보급률 추이 및 정책 효과 비교
   - **모드 3: 디지털 격차 해소 및 AI 시대 정책 제언**: 인프라 투자 모델, 공공 통신망, AI 시대 격차 완화 솔루션 제시
   - **사용자 맞춤 질의 연동**: 원하는 추가 분석 요구사항을 자연어로 입력하여 반영

3. **📁 사용자 커스텀 CSV 데이터 업로드 & AI 자동 분석**
   - 드래그 앤 드롭 파일 업로드 지원 (UTF-8 / CP949 자동 감지)
   - 행/열 크기, 수치형 변수 기초 기술 통계(평균, 표준편차, 중앙값, Min/Max) 자동 요약
   - 업로드된 데이터에 대한 Gemini AI 데이터 과학자 분석 보고서 생성

4. **결과 활용성**
   - **Marked.js** 기반 실시간 마크다운 서식 렌더링
   - **원클릭 클립보드 복사** 및 **Markdown (.md) 파일 자동 다운로드**

---

## 📂 프로젝트 구조

```text
data-insight-builder/
├── app.py                  # Flask 웹 백엔드 및 REST API 엔드포인트
├── analyzer.py             # Pandas 기반 World Bank 및 커스텀 CSV 데이터 분석 엔진
├── gemini_service.py       # Google Gemini API 연동 및 프롬프트 엔지니어링 모듈
├── requirements.txt        # 파이썬 의존성 패키지 목록
├── .env                    # Gemini API Key 및 서버 환경설정
├── .env.example            # 환경변수 설정 가이드
├── .gitignore              # Git 무시 파일 설정
├── README.md               # 프로젝트 매뉴얼
├── data/                   # 세계은행 인터넷 보급률 통계 CSV 및 메타데이터
│   └── API_IT.NET.USER.ZS_DS2_en_csv_v2_468465/
├── templates/
│   └── index.html          # 대시보드 및 업로드 UI 템플릿
└── static/
    ├── css/
    │   └── style.css       # 커스텀 스타일시트
    └── js/
        └── app.js          # 차트 시각화 및 비동기 API 통신 스크립트
```

---

## 🛠️ 기술 스택 (Tech Stack)

- **Backend**: Python 3.8+, Flask, Pandas, NumPy, python-dotenv
- **AI Model**: Google Gemini API (`gemini-3.5-flash-lite`, `google-genai` SDK)
- **Frontend**: HTML5, Tailwind CSS (CDN), Chart.js, Marked.js, Lucide Icons
- **Dataset**: World Bank World Development Indicators (`IT.NET.USER.ZS`)

---

## 🚀 빠른 시작 가이드 (Quick Start)

Windows PowerShell 기준:

### 1. 가상환경 활성화
```powershell
.\venv\Scripts\Activate.ps1
```

### 2. 패키지 설치 확인 (이미 설치된 경우 생략 가능)
```powershell
pip install -r requirements.txt
```

### 3. 환경변수(.env) 설정
`.env` 파일에 Gemini API 키가 올바르게 설정되어 있는지 확인합니다:
```env
GEMINI_API_KEY=your_actual_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
PORT=5050
FLASK_DEBUG=true
```

### 4. 웹 서버 실행
```powershell
python app.py
```

### 5. 브라우저 접속
웹 브라우저를 열고 다음 로컬 주소로 접속합니다:
👉 **[http://127.0.0.1:5050](http://127.0.0.1:5050)**

---

## 💡 주요 API 엔드포인트

| Method | Endpoint | 설명 |
|---|---|---|
| `GET` | `/` | 메인 대시보드 웹 화면 |
| `GET` | `/api/overview` | 글로벌 평균, 최신 연도, 소득/지역별 평균 요약 통계 |
| `GET` | `/api/countries` | 비교 선택 가능한 국가/지역 전체 목록 |
| `POST` | `/api/timeline` | 선택된 국가들의 1995~2024년 시계열 Chart.js 데이터셋 |
| `POST` | `/api/insights/generate` | 선택한 조건에 대한 Gemini AI 국문 심층 분석 리포트 생성 |
| `POST` | `/api/upload` | 사용자 커스텀 CSV 파일 업로드 및 기술 통계/AI 분석 |
| `GET` | `/api/health` | 서버 헬스체크 |
