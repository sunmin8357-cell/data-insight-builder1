import os
import csv
import logging
import pandas as pd
from flask import Flask, jsonify, render_template, request, send_from_directory
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging (Python standard logging, no print statements)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure Flask app
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", 10)) * 1024 * 1024

# Global in-memory dataset storage (single dataset, cleared on restart)
CURRENT_DATASET = None

@app.route("/")
def index():
    logger.info("[REQUEST] GET /")
    return render_template("index.html")

@app.route("/sw.js")
def service_worker():
    return send_from_directory("static", "sw.js", mimetype="application/javascript")

@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

@app.route("/health", methods=["GET"])
def health():
    logger.info("[REQUEST] GET /health")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    is_api_key_configured = bool(api_key and api_key != "your_gemini_api_key_here")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    response_data = {
        "status": "healthy",
        "api_key_configured": is_api_key_configured,
        "gemini_model": gemini_model
    }
    logger.info(f"[RESPONSE] status=200 api_key_configured={is_api_key_configured}")
    return jsonify(response_data)

@app.route("/inspect", methods=["POST"])
def inspect_file():
    global CURRENT_DATASET
    logger.info("[REQUEST] POST /inspect")
    
    if "file" not in request.files:
        logger.warning("[ERROR] No file part in request")
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
        
    uploaded_file = request.files["file"]
    filename = uploaded_file.filename or ""
    
    if not filename:
        logger.warning("[ERROR] Empty filename")
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
        
    if not filename.lower().endswith(".csv"):
        logger.warning(f"[ERROR] Invalid file extension: {filename}")
        return jsonify({"error": "CSV 파일만 업로드할 수 있습니다 (.csv 허용)."}), 400
        
    # Read file content into memory
    file_bytes = uploaded_file.read()
    file_size = len(file_bytes)
    logger.info(f"[FILE] name={filename} size={file_size} bytes")
    
    if file_size == 0:
        logger.warning("[ERROR] Uploaded file is empty")
        return jsonify({"error": "업로드한 파일이 비어 있습니다."}), 400
        
    # Step 1: Detect Encoding
    encodings_to_try = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]
    decoded_text = None
    successful_encoding = None
    
    for enc in encodings_to_try:
        try:
            decoded_text = file_bytes.decode(enc)
            successful_encoding = enc
            logger.info(f"[ENCODING] {enc} 시도 성공")
            break
        except UnicodeDecodeError:
            logger.info(f"[ENCODING] {enc} 시도 실패 (디코딩 에러)")
            continue
            
    if not successful_encoding or decoded_text is None:
        logger.error("[ERROR] All encodings failed")
        return jsonify({"error": "지원하는 인코딩(utf-8-sig, utf-8, cp949, euc-kr)으로 파일을 읽을 수 없습니다."}), 400

    # Step 2: Detect Header row and skip lines
    raw_lines = decoded_text.splitlines()
    if not any(line.strip() for line in raw_lines):
        return jsonify({"error": "파일에 유효한 데이터 행이 없습니다."}), 400

    skipped_rows = 0
    max_cols = 0
    best_row_idx = 0

    # Scan the first 30 non-empty lines to find the true table header
    # True table headers typically have the maximum number of columns in the document
    for idx, line in enumerate(raw_lines[:30]):
        if not line.strip():
            continue
        try:
            reader = csv.reader([line])
            cols = next(reader)
        except Exception:
            continue
            
        non_empty = [c.strip() for c in cols if c.strip()]
        # Check if line has more columns than previously seen
        if len(cols) > max_cols and len(non_empty) >= 2:
            max_cols = len(cols)
            best_row_idx = idx

    skipped_rows = best_row_idx
    logger.info(f"[HEADER] 헤더 줄 감지 결과 (건너뛴 줄 수): {skipped_rows}줄, 감지된 열 수: {max_cols}")
        
    # Step 3: Parse CSV with Pandas
    try:
        from io import StringIO
        df = pd.read_csv(
            StringIO(decoded_text),
            skiprows=skipped_rows,
            encoding=None  # Already decoded to string
        )
    except Exception as e:
        logger.error(f"[ERROR] Pandas CSV 파싱 실패: {str(e)}", exc_info=True)
        return jsonify({"error": f"CSV 파싱 중 오류가 발생했습니다: {str(e)}"}), 400
        
    logger.info(f"[CSV] parsing 완료 rows={len(df)} columns={len(df.columns)}")
    
    # Save parsed dataframe into global in-memory dataset
    CURRENT_DATASET = {
        "filename": filename,
        "df": df.copy(),
        "encoding": successful_encoding,
        "skipped_rows": skipped_rows
    }
    
    # Step 4: Comprehensive Diagnostics
    warnings = []
    
    # 4.1 Duplicate rows
    duplicate_count = int(df.duplicated().sum())
    if duplicate_count > 0:
        warnings.append(f"전체 중복 행이 {duplicate_count}개 발견되었습니다.")
        
    # 4.2 Unnamed columns / completely empty columns
    unnamed_cols = [str(c) for c in df.columns if str(c).startswith("Unnamed:") or not str(c).strip()]
    empty_cols = [str(c) for c in df.columns if df[c].isna().all()]
    if unnamed_cols:
        warnings.append(f"이름이 없는(Unnamed/빈칸) 열이 {len(unnamed_cols)}개 있습니다: {', '.join(unnamed_cols[:3])}")
    if empty_cols:
        warnings.append(f"데이터가 완전히 비어있는 열이 {len(empty_cols)}개 있습니다.")

    # 4.3 Column data types & Missing values
    column_types = {}
    missing_info = {}
    numeric_columns = []
    string_columns = []
    year_candidate_columns = []
    
    for c in df.columns:
        col_str = str(c).strip()
        dtype_str = str(df[c].dtype)
        column_types[col_str] = dtype_str
        
        # Missing count & ratio
        missing_cnt = int(df[c].isna().sum())
        missing_pct = round((missing_cnt / len(df)) * 100, 2) if len(df) > 0 else 0
        missing_info[col_str] = {
            "count": missing_cnt,
            "percentage": missing_pct
        }
        
        # Column categorization
        if pd.api.types.is_numeric_dtype(df[c]):
            numeric_columns.append(col_str)
        else:
            string_columns.append(col_str)
            
        # Year candidate detection (4-digit year like 1960 ~ 2099)
        if col_str.isdigit() and len(col_str) == 4 and 1900 <= int(col_str) <= 2100:
            year_candidate_columns.append(col_str)

    # Sort year candidate columns
    year_candidate_columns.sort()

    # 4.4 Year coverage and Recommended reference year
    year_coverage = {}
    best_year = None
    
    if year_candidate_columns:
        for y_col in year_candidate_columns:
            filled_cnt = int(df[y_col].notna().sum())
            pct = round((filled_cnt / len(df)) * 100, 2) if len(df) > 0 else 0
            year_coverage[y_col] = {
                "filled_count": filled_cnt,
                "total_count": len(df),
                "percentage": pct
            }

        # Filter candidate years having high coverage (at least 70% of rows filled)
        viable_years = [y for y in year_candidate_columns if year_coverage[y]["percentage"] >= 70.0]
        if viable_years:
            # Pick the latest among viable years (e.g. 2024 instead of older peak)
            best_year = viable_years[-1]
        else:
            # Fallback to year with absolute maximum filled count
            best_year = max(year_candidate_columns, key=lambda y: year_coverage[y]["filled_count"])
                    
        # Check if the absolute latest year is sparsely populated
        latest_year = year_candidate_columns[-1]
        latest_filled = year_coverage[latest_year]["filled_count"]
        best_filled = year_coverage[best_year]["filled_count"]
        if best_year and best_year != latest_year and latest_filled < best_filled * 0.5:
            warnings.append(
                f"최신 연도인 {latest_year}년은 데이터가 {latest_filled}건({year_coverage[latest_year]['percentage']}%)에 불과하여, "
                f"충분한 데이터를 갖춘 가장 최근 연도인 {best_year}년({best_filled}건, {year_coverage[best_year]['percentage']}%)을 기준 시점으로 권장합니다."
            )
            
    # 4.5 Aggregate rows detection (World, regional, income groupings)
    aggregate_keywords = [
        "world", "oecd members", "euro area", "european union",
        "high income", "low income", "middle income", "upper middle income",
        "lower middle income", "sub-saharan africa", "latin america",
        "east asia", "south asia", "arab world", "total", "income", "area", "countries"
    ]
    
    aggregate_rows = []
    # Identify label/name column
    label_candidates = [c for c in ["Country Name", "country", "Name", "name", "Region", "region"] if c in df.columns]
    target_label_col = label_candidates[0] if label_candidates else string_columns[0] if string_columns else None
    
    if target_label_col:
        for idx, val in df[target_label_col].items():
            val_str = str(val).strip().lower()
            if any(kw in val_str for kw in aggregate_keywords):
                aggregate_rows.append({
                    "index": int(idx),
                    "label": str(val)
                })
                
    if aggregate_rows:
        warnings.append(
            f"개별 국가가 아닌 지역/소득 묶음(집계 행 후보)이 {len(aggregate_rows)}건 감지되었습니다 "
            f"(예: {', '.join([r['label'] for r in aggregate_rows[:3]])}). 평균 계산 시 이중 집계에 유의하세요."
        )

    # 4.6 Data preview (first 10 rows, NaN replaced with null for clean JSON)
    preview_df = df.head(10).copy()
    preview_rows = preview_df.replace({float("nan"): None}).to_dict(orient="records")

    logger.info(f"[DIAGNOSE] 진단 완료 warnings={len(warnings)} aggregates={len(aggregate_rows)} best_year={best_year}")

    result = {
        "filename": filename,
        "file_size": file_size,
        "encoding": successful_encoding,
        "skipped_rows": skipped_rows,
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": [str(c) for c in df.columns],
        "column_types": column_types,
        "numeric_columns": numeric_columns,
        "string_columns": string_columns,
        "year_candidate_columns": year_candidate_columns,
        "duplicate_rows": duplicate_count,
        "unnamed_columns": unnamed_cols,
        "empty_columns": empty_cols,
        "missing_info": missing_info,
        "year_coverage": year_coverage,
        "recommended_year": best_year,
        "aggregate_candidates": aggregate_rows,
        "preview_rows": preview_rows,
        "warnings": warnings
    }
    
    return jsonify(result)

@app.route("/suggest", methods=["POST"])
def suggest_analyses():
    global CURRENT_DATASET
    logger.info("[REQUEST] POST /suggest")

    if not CURRENT_DATASET or "df" not in CURRENT_DATASET:
        logger.warning("[ERROR] No dataset loaded in memory for suggestion")
        return jsonify({"error": "먼저 CSV 파일을 업로드하고 진단을 완료해주세요."}), 400

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        logger.warning("[ERROR] Gemini API Key is missing or default placeholder")
        return jsonify({"error": "Gemini API Key가 설정되지 않았습니다. .env 파일에 키를 등록해주세요."}), 400

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Request body can contain diagnostic summary or we extract from memory
    req_data = request.get_json(silent=True) or {}
    df = CURRENT_DATASET["df"]

    # Year columns detection
    year_cols = [str(c) for c in df.columns if str(c).strip().isdigit() and len(str(c).strip()) == 4]
    year_cols.sort()
    recommended_year = req_data.get("recommended_year") or (year_cols[-2] if len(year_cols) >= 2 else (year_cols[-1] if year_cols else "2024"))

    # Tool Catalog definitions for Gemini Prompt
    catalog_description = """
[허용된 도구 이름 목록 (정확히 아래 영문 이름만 tool 필드에 넣을 수 있습니다)]
1. "top_bottom_n" : 기준연도 상위/하위 N개 국가 순위 비교 (params: {"reference_period": "2024", "n": 10, "exclude_aggregates": true})
2. "compare_one_vs_all" : 한국과 전 세계 평균/중앙값 비교 (params: {"reference_period": "2024", "target_item": "Korea, Rep.", "exclude_aggregates": true})
3. "trend_line" : 주요 국가들의 시계열 변화 추이 (params: {"items": ["Korea, Rep.", "United States", "Japan"]})
4. "change_rate" : 두 시점 사이의 증가폭과 성장률 비교 (params: {"start_period": "2015", "reference_period": "2024", "n": 10, "exclude_aggregates": true})
5. "distribution" : 기준연도 데이터의 구간별 빈도 분포 (params: {"reference_period": "2024", "bins": 5, "exclude_aggregates": true})
6. "correlation_scatter" : 과거와 현재의 피어슨 상관계수 산점도 (params: {"x_column": "2015", "y_column": "2024", "reference_period": "2015 vs 2024", "exclude_aggregates": true})
7. "describe_numeric" : 기준연도 기초 통계 요약 (params: {"reference_period": "2024", "exclude_aggregates": true})
"""

    prompt = f"""
당신은 교육용 데이터 분석 웹앱의 AI 컨설턴트입니다.
사용자가 업로드한 CSV 데이터셋의 진단 결과를 바탕으로, 통찰력 있는 분석 3~4개를 골라 제안해주세요.

{catalog_description}

[데이터셋 진단 요약]
- 파일명: {CURRENT_DATASET.get('filename')}
- 전체 행 수: {len(df)}행, 열 수: {len(df.columns)}열
- 권장 기준연도: {recommended_year} (충실도가 가장 높은 최근 연도)

[절대 규칙 - 위반 금지]
1. 제안하는 "tool" 값은 반드시 위의 허용 목록에 있는 이름("top_bottom_n", "compare_one_vs_all", "trend_line", "change_rate", "distribution", "correlation_scatter", "describe_numeric") 중 하나여야 합니다.
   절대로 다른 이름(예: trend_analysis, distribution_overview 등)을 임의로 지어내지 마십시오.
2. 3~4개의 서로 다른 도구를 골라 제안하십시오.
3. 기준 시점은 반드시 권장 기준연도인 "{recommended_year}"를 사용하십시오.
4. 반드시 순수 JSON 형식으로만 응답하십시오 (Markdown 백틱 기호 포함하지 말 것).

[JSON 응답 포맷]
{{
  "suggestions": [
    {{
      "tool": "top_bottom_n",
      "params": {{"reference_period": "{recommended_year}", "n": 10, "exclude_aggregates": true}},
      "reference_period": "{recommended_year}",
      "why": "초보자가 이해하기 쉬운 이 분석의 필요성",
      "caution": "해석할 때 주의할 점"
    }},
    {{
      "tool": "compare_one_vs_all",
      "params": {{"reference_period": "{recommended_year}", "target_item": "Korea, Rep.", "exclude_aggregates": true}},
      "reference_period": "{recommended_year}",
      "why": "우리나라와 세계 평균의 격차 확인",
      "caution": "전체 평균 산출 시 소규모 극단값의 영향 주의"
    }},
    {{
      "tool": "change_rate",
      "params": {{"start_period": "2015", "reference_period": "{recommended_year}", "n": 10, "exclude_aggregates": true}},
      "reference_period": "{recommended_year}",
      "why": "지난 10년간 가장 극적으로 성장한 국가 탐색",
      "caution": "초기 수치가 매우 낮았던 개도국의 변화율 과장 주의"
    }}
  ]
}}
"""

    logger.info(f"[AI] suggest 요청 시작 (model={model_name})")

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        response_text = response.text.strip()
        logger.info(f"[AI] suggest 응답 수신 (길이={len(response_text)})")
    except Exception as e:
        logger.error(f"[ERROR] Gemini API 호출 실패: {str(e)}", exc_info=True)
        return jsonify({"error": f"Gemini API 호출에 실패했습니다: {str(e)}"}), 500

    # Clean potential markdown wrapping from Gemini response
    cleaned_json_str = response_text
    if cleaned_json_str.startswith("```"):
        lines = cleaned_json_str.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned_json_str = "\n".join(lines).strip()

    import json
    try:
        parsed_result = json.loads(cleaned_json_str)
        suggestions = parsed_result.get("suggestions", [])
        logger.info(f"[AI] JSON 파싱 성공 suggestions={len(suggestions)}")
    except Exception as e:
        logger.error(f"[ERROR] Gemini 응답 JSON 파싱 실패: {str(e)}\n응답 원문: {response_text}")
        return jsonify({
            "error": "Gemini API의 응답을 JSON으로 해석하지 못했습니다.",
            "raw_response": response_text
        }), 500

    # Validate catalog containment
    import tools
    valid_suggestions = []
    for s in suggestions:
        tool_name = s.get("tool")
        if tool_name in tools.TOOL_CATALOG:
            valid_suggestions.append(s)
        else:
            logger.warning(f"[AI] 카탈로그에 없는 도구 무시: {tool_name}")

    return jsonify({"suggestions": valid_suggestions})

# Global cache for the last successful run result (to be used in /explain)
LAST_RUN_RESULT = None

@app.route("/run", methods=["POST"])
def run_tool():
    global CURRENT_DATASET, LAST_RUN_RESULT
    logger.info("[REQUEST] POST /run")

    if not CURRENT_DATASET or "df" not in CURRENT_DATASET:
        logger.warning("[ERROR] No dataset loaded in memory for run")
        return jsonify({"error": "먼저 CSV 파일을 업로드하고 진단을 완료해주세요."}), 400

    req_data = request.get_json(silent=True) or {}
    tool_name = req_data.get("tool")
    params = req_data.get("params") or {}

    if not tool_name:
        return jsonify({"error": "실행할 도구(tool)명이 전달되지 않았습니다."}), 400

    import tools
    if tool_name not in tools.TOOL_CATALOG:
        logger.warning(f"[ERROR] Requested tool '{tool_name}' not in catalog")
        return jsonify({"error": f"도구 목록에 존재하지 않는 도구입니다: '{tool_name}'"}), 400

    tool_func = tools.TOOL_CATALOG[tool_name]
    df = CURRENT_DATASET["df"]

    try:
        # Execute tool via Pandas
        result = tool_func(df, params)
    except Exception as e:
        logger.error(f"[ERROR] 도구 실행 중 예외 발생: {str(e)}", exc_info=True)
        return jsonify({"error": f"도구 실행 중 오류가 발생했습니다: {str(e)}"}), 500

    if not result.get("success", False):
        error_msg = result.get("error", "도구 실행에 실패했습니다.")
        logger.warning(f"[ERROR] 도구 실행 실패: {error_msg}")
        return jsonify({"error": error_msg}), 400

    # Log tool execution summary
    logger.info(
        f"[TOOL] {tool_name}, reference_period={result.get('reference_period')}, "
        f"rows_used={result.get('rows_used')}, rows_excluded={result.get('rows_excluded')}"
    )

    # Store in memory for Gemini explain (Prompt Mode B)
    LAST_RUN_RESULT = result

    return jsonify(result)

@app.route("/explain", methods=["POST"])
def explain_result():
    global CURRENT_DATASET, LAST_RUN_RESULT
    logger.info("[REQUEST] POST /explain")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        logger.warning("[ERROR] Gemini API Key is missing or default placeholder")
        return jsonify({"error": "Gemini API Key가 설정되지 않았습니다. .env 파일에 키를 등록해주세요."}), 400

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    req_data = request.get_json(silent=True) or {}
    mode = req_data.get("mode", "B").upper() # "A" or "B"
    run_result = req_data.get("run_result") or LAST_RUN_RESULT

    if mode == "B" and not run_result:
        return jsonify({"error": "해석할 분석 계산 결과가 없습니다. 먼저 분석 도구를 실행해주세요."}), 400

    logger.info(f"[AI] explain 요청 시작 (mode={mode}, model={model_name})")

    if mode == "A":
        # Mode A: Comparison mode (deliberately loose, diagnostic summary only, no pandas result)
        filename = CURRENT_DATASET.get("filename") if CURRENT_DATASET else "업로드된 데이터"
        prompt = f"""
당신은 데이터 분석가입니다.
사용자가 '{filename}'라는 CSV 파일을 업로드했습니다.
이 데이터를 분석해서 초보자를 위한 전체적인 분석 보고서를 자세하게 작성해주세요.
"""
    else:
        # Mode B: Rigorous educational mode
        # Strict rules: Only use provided pandas numbers, don't invent anything
        tool_name = run_result.get("tool")
        ref_period = run_result.get("reference_period")
        rows_used = run_result.get("rows_used")
        rows_excluded = run_result.get("rows_excluded")
        exclusion_reason = run_result.get("exclusion_reason")
        caution = run_result.get("caution")
        unit = run_result.get("unit")
        calc_data = run_result.get("result_data", {})

        import json
        calc_data_str = json.dumps(calc_data, ensure_ascii=False, indent=2)

        prompt = f"""
당신은 중학생도 이해할 수 있게 친절하고 정직하게 설명하는 데이터 리터러시 전문 AI 멘토입니다.
아래에 제공된 [Pandas 계산 결과]만을 바탕으로 데이터 해석 보고서를 작성해주세요.

[절대 규칙 - 위반 시 감점]
1. 반드시 아래 제공된 [Pandas 계산 결과]에 명시된 숫자만 사용하십시오. 직접 계산하거나 숫자를 추정/창작하지 마십시오.
2. 데이터에 없는 국가, 연도, 열 이름을 지어내어 언급하지 마십시오.
3. 기준 시점({ref_period})과 계산에 사용된 행 수({rows_used}행), 제외된 행 수({rows_excluded}행) 및 제외 이유({exclusion_reason})를 반드시 본문에 명시하십시오.
4. 상관관계를 인과관계로 표현하지 마십시오 (주의사항: {caution}).
5. 지표의 정의(인터넷 사용자: 최근 3개월 내 사용 경험이 있는 개인)와 출처(World Bank / ITU)를 보고서 앞부분에 표기하십시오.
6. 데이터로 확인할 수 없는 사실은 반드시 "이 데이터로는 확인할 수 없다"라고 솔직하게 쓰십시오.
7. 중학생도 이해할 수 있는 명쾌하고 쉬운 어조를 사용하되, 정확성을 철저히 지키십시오.

[Pandas 계산 결과]
- 실행 도구: {tool_name}
- 기준 시점: {ref_period}
- 계산에 사용한 행 수: {rows_used}
- 제외된 행 수: {rows_excluded} (사유: {exclusion_reason})
- 단위: {unit}
- 주의사항: {caution}
- 상세 계산 수치(JSON):
{calc_data_str}

[출력 형식 - 반드시 아래 마크다운 제목 7개를 그대로 사용할 것]
## 무엇을 봤는가
## 데이터 출처와 정의
## 기준 시점과 제외된 항목
## 계산 결과
## 읽어낼 수 있는 것
## 이 데이터로는 알 수 없는 것
## 다음에 확인해볼 것
"""

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        report_text = response.text.strip()
        logger.info(f"[AI] explain 응답 수신 완료 (길이={len(report_text)})")
    except Exception as e:
        logger.error(f"[ERROR] Gemini API explain 실패: {str(e)}", exc_info=True)
        return jsonify({"error": f"Gemini API 호출에 실패했습니다: {str(e)}"}), 500

    return jsonify({
        "mode": mode,
        "report": report_text
    })

@app.route("/followup", methods=["POST"])
def followup_chat():
    global LAST_RUN_RESULT
    logger.info("[REQUEST] POST /followup")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        return jsonify({"error": "Gemini API Key가 설정되지 않았습니다."}), 400

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    req_data = request.get_json(silent=True) or {}
    user_question = req_data.get("question", "").strip()
    current_report = req_data.get("report", "").strip()

    if not user_question:
        return jsonify({"error": "질문 내용이 없습니다."}), 400

    import json
    calc_str = json.dumps(LAST_RUN_RESULT, ensure_ascii=False, indent=2) if LAST_RUN_RESULT else "계산 결과 없음"

    prompt = f"""
당신은 친절한 데이터 리터러시 전문 AI 튜터입니다.
사용자가 기존에 생성된 데이터 분석 보고서에 대해 후속 질문을 했습니다.

[기존 분석 보고서]
{current_report}

[Pandas 실제 계산 결과]
{calc_str}

[사용자의 질문]
{user_question}

[답변 원칙]
1. 사용자가 "쉽게 설명해줘" 또는 "중학생도 이해할 수 있게"를 요구하면, 어려운 통계 용어 대신 일상 속 쉬운 비유와 예시를 들어 친절하게 설명하세요.
2. 제공된 Pandas 계산 결과에 없는 숫자를 지어내지 마세요.
3. 데이터로 알 수 없는 부분은 솔직하게 "이 데이터로는 알 수 없습니다"라고 말하세요.
4. 핵심을 명확하고 읽기 편하게 답변하세요.
"""

    logger.info(f"[AI] followup 질의 요청 (질문={user_question[:30]}...)")

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        answer_text = response.text.strip()
    except Exception as e:
        logger.error(f"[ERROR] Gemini API followup 실패: {str(e)}", exc_info=True)
        return jsonify({"error": f"답변 생성 실패: {str(e)}"}), 500

    return jsonify({"answer": answer_text})

@app.route("/ask-nl", methods=["POST"])
def ask_natural_language():
    global CURRENT_DATASET
    logger.info("[REQUEST] POST /ask-nl")

    if not CURRENT_DATASET or "df" not in CURRENT_DATASET:
        return jsonify({"error": "먼저 CSV 파일을 업로드하고 진단을 완료해주세요."}), 400

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        return jsonify({"error": "Gemini API Key가 설정되지 않았습니다."}), 400

    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    req_data = request.get_json(silent=True) or {}
    user_query = req_data.get("query", "").strip()

    if not user_query:
        return jsonify({"error": "질문 내용이 없습니다."}), 400

    df = CURRENT_DATASET["df"]
    
    # 4-digit year columns
    year_cols = [str(c) for c in df.columns if str(c).strip().isdigit() and len(str(c).strip()) == 4]
    year_cols.sort()
    
    # We provide metadata summary and catalog for Gemini
    catalog_overview = """
사용 가능한 도구 및 파라미터 규격:
1. "top_bottom_n": {"reference_period": "연도", "n": 10, "target_item": "Korea, Rep.", "exclude_aggregates": true}
2. "compare_one_vs_all": {"reference_period": "연도", "target_item": "국가명(예: Korea, Rep.)", "exclude_aggregates": true}
3. "trend_line": {"items": ["Korea, Rep.", "United States", "Japan"]}
4. "change_rate": {"start_period": "시작연도", "reference_period": "종료연도", "n": 10, "exclude_aggregates": true}
5. "distribution": {"reference_period": "연도", "bins": 5, "exclude_aggregates": true}
6. "correlation_scatter": {"x_column": "연도1", "y_column": "연도2", "reference_period": "연도1 vs 연도2", "exclude_aggregates": true}
7. "describe_numeric": {"reference_period": "연도", "exclude_aggregates": true}
"""

    prompt = f"""
당신은 데이터 분석 AI 비서입니다.
사용자가 데이터에 대해 자연어로 다음과 같이 질문했습니다:
"{user_query}"

[데이터셋 정보]
- 파일명: {CURRENT_DATASET.get('filename')}
- 감지된 연도 열: {', '.join(year_cols[-10:])} (최근 10개)
- 기본 권장 기준연도: 2024년

{catalog_overview}

[작업 지시]
1. 사용자의 자연어 질문을 분석하여, 이 질문에 답하기 위해 가장 적절한 분석 도구(tool)와 파라미터(params)를 선정하십시오.
   - 예 1: "1~10등까지 대한민국 포함해서 비교해줘" 또는 "1~10위 대한민국 포함"
     -> tool: "top_bottom_n", params: {{"reference_period": "2024", "n": 10, "target_item": "Korea, Rep.", "exclude_aggregates": true}}
   - 예 2: "상위 10개국 순위와 한국 비교"
     -> tool: "top_bottom_n", params: {{"reference_period": "2024", "n": 10, "target_item": "Korea, Rep.", "exclude_aggregates": true}}
2. 사용자 질문에 대한 친절하고 핵심적인 사전 자연어 안내 답변(answer)을 작성하십시오.
   - 대한민국(13위, 97.90%)이 1~10위 국가들과 얼마나 근소한 차이(10위 아이슬란드와 불과 0.31%p 차)인지 핵심 수치 언급
   - 아래 시각화 그래프 버튼을 클릭하면 1~10위와 대한민국이 함께 포함된 차트가 렌더링된다는 점 안내
3. 반드시 아래 JSON 형식으로만 응답하십시오 (Markdown 백틱 기호 제외).

[JSON 응답 포맷]
{{
  "answer": "사용자의 질문에 대한 자연어 설명 및 분석 방향 안내",
  "chart_button": {{
    "title": "시각화 버튼에 표시할 문구 (예: 2024년 세계 1~10위 + 대한민국 비교 그래프 보기)",
    "tool": "top_bottom_n",
    "params": {{
      "reference_period": "2024",
      "n": 10,
      "target_item": "Korea, Rep.",
      "exclude_aggregates": true
    }}
  }}
}}
"""

    logger.info(f"[AI] ask-nl 요청 시작 (query={user_query[:30]}...)")

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        resp_text = response.text.strip()
    except Exception as e:
        logger.error(f"[ERROR] ask-nl 실패: {str(e)}", exc_info=True)
        return jsonify({"error": f"AI 분석 구성 실패: {str(e)}"}), 500

    # Clean markdown
    cleaned = resp_text
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"): lines = lines[1:]
        if lines and lines[-1].startswith("```"): lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    import json
    try:
        parsed = json.loads(cleaned)
    except Exception as e:
        logger.error(f"[ERROR] ask-nl JSON 파싱 실패: {str(e)}\n원문: {resp_text}")
        return jsonify({
            "answer": resp_text,
            "chart_button": None
        })

    return jsonify(parsed)

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    logger.info(f"Starting AI Data Insight Builder on http://127.0.0.1:5000 (debug={debug_mode})")
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)






