import math
import pandas as pd

def safe_number(val):
    """Convert float NaN or inf to None for safe JSON serialization."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(float(val), 4)
    return val

# Common keywords for detecting regional/income aggregates
AGGREGATE_KEYWORDS = [
    "world", "oecd members", "euro area", "european union",
    "high income", "low income", "middle income", "upper middle income",
    "lower middle income", "sub-saharan africa", "latin america",
    "east asia", "south asia", "arab world", "total", "income", "area", "countries"
]

def find_label_column(df):
    """Find the best column representing entity names (e.g. Country Name)."""
    candidates = ["Country Name", "country", "Name", "name", "Region", "region"]
    for c in candidates:
        if c in df.columns:
            return c
    # Fallback to first string/object column
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            return c
    return df.columns[0]

# Tool 1: reshape_wide_to_long
def reshape_wide_to_long(df, params=None):
    """
    1. reshape_wide_to_long: 가로로 나열된 연도 열들을 세로 행(Long Format)으로 변환합니다.
    """
    params = params or {}
    id_cols = params.get("id_columns")
    
    # Auto-detect year columns (4-digit columns)
    year_cols = [str(c) for c in df.columns if str(c).strip().isdigit() and len(str(c).strip()) == 4]
    
    if not year_cols:
        return {
            "error": "변환할 4자리 연도 열을 찾지 못했습니다.",
            "success": False
        }
        
    if not id_cols:
        id_cols = [str(c) for c in df.columns if str(c) not in year_cols and not str(c).startswith("Unnamed:")]

    total_rows = len(df)
    
    melted = pd.melt(
        df,
        id_vars=id_cols,
        value_vars=year_cols,
        var_name="Year",
        value_name="Value"
    )
    
    # Exclude null values in long format
    before_drop = len(melted)
    melted = melted.dropna(subset=["Value"])
    dropped_nulls = before_drop - len(melted)

    # Preview 15 rows
    preview = melted.head(15).replace({float("nan"): None}).to_dict(orient="records")

    return {
        "tool": "reshape_wide_to_long",
        "success": True,
        "reference_period": "전체 연도 (1960~2025)",
        "rows_used": total_rows,
        "rows_excluded": 0,
        "exclusion_reason": f"변환 후 결측치 {dropped_nulls}건 제거",
        "used_columns": id_cols + ["Year", "Value"],
        "unit": "행 (변환된 관측치)",
        "caution": "연도별 결측치는 세로 변환 후 제외되었습니다. 행 수가 기존보다 크게 증가합니다.",
        "result_data": {
            "melted_row_count": len(melted),
            "original_row_count": total_rows,
            "year_count": len(year_cols),
            "preview": preview
        }
    }

# Tool 2: quality_report
def quality_report(df, params=None):
    """
    2. quality_report: 결측·중복·데이터 타입·비정상 열 이름을 종합 진단합니다.
    """
    total_rows = len(df)
    total_cols = len(df.columns)
    duplicate_rows = int(df.duplicated().sum())

    unnamed_cols = [str(c) for c in df.columns if str(c).startswith("Unnamed:") or not str(c).strip()]
    empty_cols = [str(c) for c in df.columns if df[c].isna().all()]
    
    col_details = []
    for c in df.columns:
        c_str = str(c)
        missing_cnt = int(df[c].isna().sum())
        missing_pct = round((missing_cnt / total_rows) * 100, 2) if total_rows > 0 else 0
        col_details.append({
            "column": c_str,
            "dtype": str(df[c].dtype),
            "missing_count": missing_cnt,
            "missing_pct": missing_pct
        })

    return {
        "tool": "quality_report",
        "success": True,
        "reference_period": "전체 데이터셋",
        "rows_used": total_rows,
        "rows_excluded": 0,
        "exclusion_reason": "없음 (전체 행 대상 검사)",
        "used_columns": [str(c) for c in df.columns],
        "unit": "개 / %",
        "caution": "결측치가 50% 이상인 열은 단일 시점 분석 시 제외하는 것이 안전합니다.",
        "result_data": {
            "total_rows": total_rows,
            "total_columns": total_cols,
            "duplicate_rows": duplicate_rows,
            "unnamed_columns": unnamed_cols,
            "empty_columns": empty_cols,
            "column_details": col_details
        }
    }

# Tool 3: year_coverage
def year_coverage(df, params=None):
    """
    3. year_coverage: 연도별 데이터 충실도를 계산하고 가장 적합한 권장 기준연도를 제안합니다.
    """
    total_rows = len(df)
    year_cols = [str(c) for c in df.columns if str(c).strip().isdigit() and len(str(c).strip()) == 4]
    year_cols.sort()

    if not year_cols:
        return {
            "error": "데이터셋에서 4자리 연도 열을 찾을 수 없습니다.",
            "success": False
        }

    coverage_list = []
    best_year = None
    
    for y in year_cols:
        filled_cnt = int(df[y].notna().sum())
        pct = round((filled_cnt / total_rows) * 100, 2) if total_rows > 0 else 0
        coverage_list.append({
            "year": y,
            "filled_count": filled_cnt,
            "total_rows": total_rows,
            "percentage": pct
        })

    # Pick latest viable year with coverage >= 70%
    viable = [item for item in coverage_list if item["percentage"] >= 70.0]
    if viable:
        best_year = viable[-1]["year"]
    else:
        best_year = max(coverage_list, key=lambda x: x["filled_count"])["year"]

    # Chart data for Frontend (bar chart of year coverage)
    chart_data = {
        "labels": [item["year"] for item in coverage_list[-15:]], # last 15 years
        "datasets": [{
            "label": "데이터 충실도 (%)",
            "data": [item["percentage"] for item in coverage_list[-15:]]
        }]
    }

    return {
        "tool": "year_coverage",
        "success": True,
        "reference_period": f"{year_cols[0]}~{year_cols[-1]}",
        "rows_used": total_rows,
        "rows_excluded": 0,
        "exclusion_reason": "없음",
        "used_columns": year_cols,
        "unit": "% (충실도)",
        "caution": "최신 연도라도 데이터가 50% 미만으로 집계된 경우 분석에서 왜곡이 발생하므로 권장 기준연도를 사용하세요.",
        "result_data": {
            "recommended_year": best_year,
            "total_year_count": len(year_cols),
            "coverage_list": coverage_list,
            "chart_data": chart_data
        }
    }

# Tool 4: detect_aggregates
def detect_aggregates(df, params=None):
    """
    4. detect_aggregates: 세계/지역/소득분류 등 개별 국가가 아닌 집계 행을 탐지합니다.
    """
    total_rows = len(df)
    label_col = find_label_column(df)
    
    aggregate_list = []
    pure_country_count = 0

    for idx, val in df[label_col].items():
        val_str = str(val).strip().lower()
        if any(kw in val_str for kw in AGGREGATE_KEYWORDS):
            aggregate_list.append({
                "index": int(idx),
                "name": str(val)
            })
        else:
            pure_country_count += 1

    return {
        "tool": "detect_aggregates",
        "success": True,
        "reference_period": "전체 데이터셋",
        "rows_used": total_rows,
        "rows_excluded": 0,
        "exclusion_reason": "없음 (탐지 목적)",
        "used_columns": [label_col],
        "unit": "개 (행)",
        "caution": "이 행들은 여러 국가를 합친 집계치이므로, 국가 간 평균/순위 계산 시 반드시 제외해야 이중 계산을 막을 수 있습니다.",
        "result_data": {
            "label_column": label_col,
            "aggregate_count": len(aggregate_list),
            "pure_country_count": pure_country_count,
            "aggregates": aggregate_list
        }
    }

def filter_data(df, reference_period, value_column=None, exclude_aggregates=True):
    """
    Common helper for tools 7-12:
    - Validates reference_period
    - Filters out missing values at reference_period
    - Optionally excludes aggregate rows (default: True)
    """
    total_original = len(df)
    target_col = value_column or reference_period
    
    if not reference_period:
        return None, {"error": "기준 시점(reference_period)은 필수 파라미터입니다.", "success": False}
        
    if target_col not in df.columns:
        return None, {"error": f"선택한 열/연도 '{target_col}'가 데이터에 없습니다.", "success": False}
        
    # Check numeric
    df_work = df.copy()
    try:
        df_work[target_col] = pd.to_numeric(df_work[target_col], errors="coerce")
    except Exception:
        pass
        
    # 1. Filter out missing values
    valid_mask = df_work[target_col].notna()
    missing_count = int((~valid_mask).sum())
    df_filtered = df_work[valid_mask]
    
    # 2. Exclude aggregates if requested
    excluded_agg_count = 0
    label_col = find_label_column(df_filtered)
    
    if exclude_aggregates:
        agg_mask = df_filtered[label_col].astype(str).str.lower().apply(
            lambda x: any(kw in x for kw in AGGREGATE_KEYWORDS)
        )
        excluded_agg_count = int(agg_mask.sum())
        df_filtered = df_filtered[~agg_mask]
        
    rows_excluded = missing_count + excluded_agg_count
    exclusion_reason = f"결측치 {missing_count}건 제외"
    if exclude_aggregates:
        exclusion_reason += f", 집계 행 {excluded_agg_count}건 제외"

    return df_filtered, {
        "total_original": total_original,
        "rows_used": len(df_filtered),
        "rows_excluded": rows_excluded,
        "missing_count": missing_count,
        "excluded_agg_count": excluded_agg_count,
        "exclusion_reason": exclusion_reason,
        "target_col": target_col,
        "label_col": label_col
    }

# Tool 5: describe_numeric
def describe_numeric(df, params=None):
    """
    5. describe_numeric: 개수·평균·중앙값·최소·최대·표준편차 기초 통계를 계산합니다.
    """
    params = params or {}
    ref_col = params.get("value_column") or params.get("reference_period") or "2024"
    exclude_aggs = params.get("exclude_aggregates", True)

    df_filtered, meta = filter_data(df, ref_col, ref_col, exclude_aggregates=exclude_aggs)
    if df_filtered is None:
        return meta

    series = df_filtered[meta["target_col"]]
    if len(series) == 0:
        return {"error": f"'{ref_col}' 열에 계산할 유효한 숫자가 없습니다.", "success": False}

    stats = {
        "count": int(series.count()),
        "mean": safe_number(series.mean()),
        "median": safe_number(series.median()),
        "std": safe_number(series.std()),
        "min": safe_number(series.min()),
        "max": safe_number(series.max()),
        "q25": safe_number(series.quantile(0.25)),
        "q75": safe_number(series.quantile(0.75))
    }

    return {
        "tool": "describe_numeric",
        "success": True,
        "reference_period": str(ref_col),
        "rows_used": meta["rows_used"],
        "rows_excluded": meta["rows_excluded"],
        "exclusion_reason": meta["exclusion_reason"],
        "used_columns": [meta["target_col"]],
        "unit": "수치 단위 (비율 % 또는 수치)",
        "caution": "평균은 극단값의 영향을 크게 받으므로 왜도가 심한 경우 중앙값을 함께 참고하세요.",
        "result_data": {
            "target_column": meta["target_col"],
            "stats": stats
        }
    }

# Tool 6: trend_line
def trend_line(df, params=None):
    """
    6. trend_line: 선택한 항목들의 연도별 변화 추이를 꺾은선 차트 데이터로 생성합니다.
    """
    params = params or {}
    items = params.get("items", ["Korea, Rep.", "United States", "Japan", "Germany"])
    label_col = params.get("label_column") or find_label_column(df)
    
    # 4-digit year columns
    year_cols = [str(c) for c in df.columns if str(c).strip().isdigit() and len(str(c).strip()) == 4]
    year_cols.sort()
    
    # Filter only years that have at least some data
    valid_years = [y for y in year_cols if df[y].notna().sum() > 0]
    # Limit to reasonable range (e.g. 1995 ~ latest)
    valid_years = [y for y in valid_years if int(y) >= 1995]

    matched_rows = df[df[label_col].astype(str).isin(items)]
    
    datasets = []
    for _, row in matched_rows.iterrows():
        item_name = str(row[label_col])
        values = [safe_number(row.get(y)) for y in valid_years]
        datasets.append({
            "label": item_name,
            "data": values
        })

    chart_data = {
        "labels": valid_years,
        "datasets": datasets
    }

    return {
        "tool": "trend_line",
        "success": True,
        "reference_period": f"{valid_years[0]}~{valid_years[-1]}" if valid_years else "1995~최근",
        "rows_used": len(matched_rows),
        "rows_excluded": len(df) - len(matched_rows),
        "exclusion_reason": f"선택한 {len(items)}개 항목 외 {len(df) - len(matched_rows)}건 제외",
        "used_columns": [label_col] + valid_years,
        "unit": "연도별 수치",
        "caution": "국가마다 최초 통계 집계 시점이 다를 수 있어 초반 연도에 선이 끊길 수 있습니다.",
        "result_data": {
            "selected_items": items,
            "years": valid_years,
            "chart_data": chart_data
        }
    }

# Tool 7: top_bottom_n
def top_bottom_n(df, params=None):
    """
    7. top_bottom_n: 기준연도 기준 상위·하위 N개 항목을 추출하고 수평 막대 차트 데이터를 만듭니다.
       - target_item 파라미터가 주어지면, 해당 항목이 Top N 바깥에 있더라도 비교를 위해 차트와 목록에 함께 포함시킵니다.
    """
    params = params or {}
    ref_col = params.get("reference_period")
    n = int(params.get("n", 10))
    val_col = params.get("value_column") or ref_col
    exclude_aggs = params.get("exclude_aggregates", True)
    target_item = params.get("target_item") or params.get("include_item")

    df_filtered, meta = filter_data(df, ref_col, val_col, exclude_aggregates=exclude_aggs)
    if df_filtered is None:
        return meta

    label_col = meta["label_col"]
    sorted_df = df_filtered.sort_values(by=meta["target_col"], ascending=False).reset_index(drop=True)
    
    top_n = sorted_df.head(n)
    bottom_n = sorted_df.tail(n).iloc[::-1] # worst at bottom

    top_items = []
    for rank_idx, r in top_n.iterrows():
        top_items.append({
            "name": f"{rank_idx+1}위: {str(r[label_col])}",
            "raw_name": str(r[label_col]),
            "value": safe_number(r[meta["target_col"]]),
            "is_target": False
        })

    # If target_item is specified (e.g. Korea, Rep.)
    if target_item:
        found = False
        for item in top_items:
            if str(target_item).lower() in item["raw_name"].lower():
                item["is_target"] = True
                if "(대한민국)" not in item["name"]:
                    item["name"] += " (대한민국)"
                found = True
        if not found:
            match_row = sorted_df[sorted_df[label_col].astype(str).str.lower().str.contains(str(target_item).lower())]
            if not match_row.empty:
                idx = match_row.index[0]
                r = match_row.iloc[0]
                top_items.append({
                    "name": f"{idx+1}위: {str(r[label_col])} (대한민국)",
                    "raw_name": str(r[label_col]),
                    "value": safe_number(r[meta["target_col"]]),
                    "is_target": True
                })

    bottom_items = [{"name": str(r[label_col]), "value": safe_number(r[meta["target_col"]])} for _, r in bottom_n.iterrows()]

    # Set distinct colors: Korea (highlight coral/red), other countries (blue)
    bg_colors = []
    border_colors = []
    for item in top_items:
        if item.get("is_target"):
            bg_colors.append("rgba(239, 68, 68, 0.85)")   # 대한민국 강조 (코랄 레드)
            border_colors.append("#dc2626")
        else:
            bg_colors.append("rgba(59, 130, 246, 0.75)")  # 상위 10위 (블루)
            border_colors.append("#2563eb")

    # Chart data for Top N (plus target item if appended)
    chart_data = {
        "labels": [item["name"] for item in top_items],
        "datasets": [{
            "label": f"{ref_col}년 인터넷 사용률 (%)",
            "data": [item["value"] for item in top_items],
            "backgroundColor": bg_colors,
            "borderColor": border_colors,
            "borderWidth": 1.5
        }]
    }

    return {
        "tool": "top_bottom_n",
        "success": True,
        "reference_period": str(ref_col),
        "rows_used": meta["rows_used"],
        "rows_excluded": meta["rows_excluded"],
        "exclusion_reason": meta["exclusion_reason"],
        "used_columns": [label_col, meta["target_col"]],
        "unit": "수치 (%)",
        "caution": "소규모 도시국가나 특수 표본의 경우 100% 반올림 처리될 수 있으므로 표본 특성을 고려해야 합니다.",
        "result_data": {
            "n": n,
            "top_n": top_items,
            "bottom_n": bottom_items,
            "chart_data": chart_data
        }
    }

# Tool 8: group_summary
def group_summary(df, params=None):
    """
    8. group_summary: 그룹별(대륙/소득군/분류) 평균, 합계, 개수 집계 및 막대 차트 데이터 생성.
    """
    params = params or {}
    ref_col = params.get("reference_period")
    group_col = params.get("group_column") or "Region"
    val_col = params.get("value_column") or ref_col
    exclude_aggs = params.get("exclude_aggregates", True)

    if group_col not in df.columns:
        # Check if we can infer or if missing
        return {"error": f"그룹핑할 열 '{group_col}'가 데이터에 없습니다.", "success": False}

    df_filtered, meta = filter_data(df, ref_col, val_col, exclude_aggregates=exclude_aggs)
    if df_filtered is None:
        return meta

    # Group by
    grouped = df_filtered.groupby(group_col)[meta["target_col"]].agg(["count", "mean", "median"]).reset_index()
    grouped = grouped.sort_values(by="mean", ascending=False)

    summary_list = []
    for _, r in grouped.iterrows():
        summary_list.append({
            "group": str(r[group_col]),
            "count": int(r["count"]),
            "mean": safe_number(r["mean"]),
            "median": safe_number(r["median"])
        })

    chart_data = {
        "labels": [s["group"] for s in summary_list],
        "datasets": [{
            "label": f"{ref_col}년 그룹별 평균",
            "data": [s["mean"] for s in summary_list]
        }]
    }

    return {
        "tool": "group_summary",
        "success": True,
        "reference_period": str(ref_col),
        "rows_used": meta["rows_used"],
        "rows_excluded": meta["rows_excluded"],
        "exclusion_reason": meta["exclusion_reason"],
        "used_columns": [group_col, meta["target_col"]],
        "unit": "그룹별 평균 / 중앙값",
        "caution": "그룹 내 속한 국가 수가 적은 경우 이상치 하나에 그룹 평균이 크게 왜곡될 수 있습니다.",
        "result_data": {
            "group_column": group_col,
            "summary": summary_list,
            "chart_data": chart_data
        }
    }

# Tool 9: change_rate
def change_rate(df, params=None):
    """
    9. change_rate: 두 시점(시작 연도, 종료 연도) 사이의 절대 변화량과 변화율을 계산합니다.
    """
    params = params or {}
    start_period = params.get("start_period") or params.get("start_year") or "2015"
    end_period = params.get("reference_period") or params.get("end_period") or params.get("end_year") or "2024"
    n = int(params.get("n", 10))
    exclude_aggs = params.get("exclude_aggregates", True)

    if not end_period:
        return {"error": "종료 기준 시점(reference_period)은 필수 파라미터입니다.", "success": False}
    if not start_period:
        return {"error": "시작 기준 시점(start_period)은 필수 파라미터입니다.", "success": False}

    if start_period not in df.columns or end_period not in df.columns:
        return {"error": f"비교할 시점 '{start_period}' 또는 '{end_period}'가 데이터에 없습니다.", "success": False}

    label_col = find_label_column(df)
    df_work = df.copy()
    df_work[start_period] = pd.to_numeric(df_work[start_period], errors="coerce")
    df_work[end_period] = pd.to_numeric(df_work[end_period], errors="coerce")

    # Exclude rows missing either start or end
    valid_mask = df_work[start_period].notna() & df_work[end_period].notna()
    missing_count = int((~valid_mask).sum())
    df_filtered = df_work[valid_mask]

    # Exclude aggregates if requested
    excluded_agg_count = 0
    if exclude_aggs:
        agg_mask = df_filtered[label_col].astype(str).str.lower().apply(
            lambda x: any(kw in x for kw in AGGREGATE_KEYWORDS)
        )
        excluded_agg_count = int(agg_mask.sum())
        df_filtered = df_filtered[~agg_mask]

    # Calculate difference and rate
    df_filtered["diff"] = df_filtered[end_period] - df_filtered[start_period]
    # Percentage change (prevent divide by zero)
    df_filtered["pct_change"] = df_filtered.apply(
        lambda r: ((r["diff"] / r[start_period]) * 100) if r[start_period] > 0 else None,
        axis=1
    )

    # Sort by absolute difference
    sorted_df = df_filtered.sort_values(by="diff", ascending=False)
    top_gainers = sorted_df.head(n)

    gainer_items = []
    for _, r in top_gainers.iterrows():
        gainer_items.append({
            "name": str(r[label_col]),
            "start_val": safe_number(r[start_period]),
            "end_val": safe_number(r[end_period]),
            "diff": safe_number(r["diff"]),
            "pct_change": safe_number(r["pct_change"])
        })

    chart_data = {
        "labels": [g["name"] for g in gainer_items],
        "datasets": [{
            "label": f"{start_period}년 대비 {end_period}년 증가폭 (%p)",
            "data": [g["diff"] for g in gainer_items]
        }]
    }

    return {
        "tool": "change_rate",
        "success": True,
        "reference_period": f"{start_period}년 -> {end_period}년",
        "rows_used": len(df_filtered),
        "rows_excluded": missing_count + excluded_agg_count,
        "exclusion_reason": f"두 시점 중 하나라도 결측치인 {missing_count}건 제외" + (f", 집계 행 {excluded_agg_count}건 제외" if exclude_aggs else ""),
        "used_columns": [label_col, start_period, end_period],
        "unit": "증가폭 (%p) / 변화율 (%)",
        "caution": "초기 값이 매우 작았던 국가는 상대 변화율(%)이 비정상적으로 높게 나타날 수 있으므로 절대 증가폭(%p)을 함께 보아야 합니다.",
        "result_data": {
            "start_period": start_period,
            "end_period": end_period,
            "top_gainers": gainer_items,
            "chart_data": chart_data
        }
    }

# Tool 10: distribution
def distribution(df, params=None):
    """
    10. distribution: 특정 기준연도 데이터의 구간별 분포(히스토그램)를 생성합니다.
    """
    params = params or {}
    ref_col = params.get("reference_period")
    val_col = params.get("value_column") or ref_col
    bins_count = int(params.get("bins", 5))
    exclude_aggs = params.get("exclude_aggregates", True)

    df_filtered, meta = filter_data(df, ref_col, val_col, exclude_aggregates=exclude_aggs)
    if df_filtered is None:
        return meta

    series = df_filtered[meta["target_col"]]
    if len(series) == 0:
        return {"error": f"'{ref_col}' 열에 분석할 데이터가 없습니다.", "success": False}

    # Generate custom bins or equal-width bins
    min_val = math.floor(series.min())
    max_val = math.ceil(series.max())
    
    # Custom 10-step or 5-step interval
    step = (max_val - min_val) / bins_count
    intervals = []
    labels = []
    
    for i in range(bins_count):
        low = min_val + (i * step)
        high = min_val + ((i + 1) * step)
        label = f"{round(low, 1)}~{round(high, 1)}"
        if i == bins_count - 1:
            cnt = int(((series >= low) & (series <= high)).sum())
        else:
            cnt = int(((series >= low) & (series < high)).sum())
        intervals.append({
            "range": label,
            "count": cnt,
            "percentage": round((cnt / len(series)) * 100, 2)
        })
        labels.append(label)

    chart_data = {
        "labels": labels,
        "datasets": [{
            "label": f"{ref_col}년 빈도수",
            "data": [item["count"] for item in intervals]
        }]
    }

    return {
        "tool": "distribution",
        "success": True,
        "reference_period": str(ref_col),
        "rows_used": meta["rows_used"],
        "rows_excluded": meta["rows_excluded"],
        "exclusion_reason": meta["exclusion_reason"],
        "used_columns": [meta["target_col"]],
        "unit": "빈도수 (개국) / 비율 (%)",
        "caution": "분포의 양극화(Bimodal)나 극단값에 의해 한쪽 구간으로 쏠리는 현상이 있는지 확인해야 합니다.",
        "result_data": {
            "bins_count": bins_count,
            "intervals": intervals,
            "chart_data": chart_data
        }
    }

# Tool 11: correlation_scatter
def correlation_scatter(df, params=None):
    """
    11. correlation_scatter: 두 숫자 열의 피어슨 상관계수를 계산하고 산점도 데이터를 생성합니다.
    """
    params = params or {}
    x_col = params.get("x_column")
    y_col = params.get("y_column")
    ref_col = params.get("reference_period")
    exclude_aggs = params.get("exclude_aggregates", True)

    # If reference_period is provided and x_col/y_col omitted, default to comparing two years (e.g. 2015 vs 2024)
    if not x_col and not y_col:
        x_col = params.get("start_period", "2015")
        y_col = ref_col or "2024"
    elif not ref_col:
        ref_col = f"{x_col} & {y_col}"

    if not x_col or not y_col:
        return {"error": "비교할 두 개의 열(x_column, y_column) 또는 기준 시점이 필요합니다.", "success": False}

    if x_col not in df.columns or y_col not in df.columns:
        return {"error": f"열 '{x_col}' 또는 '{y_col}'가 데이터에 존재하지 않습니다.", "success": False}

    label_col = find_label_column(df)
    df_work = df.copy()
    df_work[x_col] = pd.to_numeric(df_work[x_col], errors="coerce")
    df_work[y_col] = pd.to_numeric(df_work[y_col], errors="coerce")

    # Filter out missing in either
    valid_mask = df_work[x_col].notna() & df_work[y_col].notna()
    missing_count = int((~valid_mask).sum())
    df_filtered = df_work[valid_mask]

    excluded_agg_count = 0
    if exclude_aggs:
        agg_mask = df_filtered[label_col].astype(str).str.lower().apply(
            lambda x: any(kw in x for kw in AGGREGATE_KEYWORDS)
        )
        excluded_agg_count = int(agg_mask.sum())
        df_filtered = df_filtered[~agg_mask]

    if len(df_filtered) < 2:
        return {"error": "상관계수를 계산하기 위한 유효한 데이터 쌍이 부족합니다.", "success": False}

    corr_value = float(df_filtered[x_col].corr(df_filtered[y_col]))
    
    # Points for scatter chart
    points = []
    for _, r in df_filtered.iterrows():
        points.append({
            "label": str(r[label_col]),
            "x": safe_number(r[x_col]),
            "y": safe_number(r[y_col])
        })

    chart_data = {
        "datasets": [{
            "label": f"{x_col} vs {y_col}",
            "data": points
        }]
    }

    return {
        "tool": "correlation_scatter",
        "success": True,
        "reference_period": str(ref_col),
        "rows_used": len(df_filtered),
        "rows_excluded": missing_count + excluded_agg_count,
        "exclusion_reason": f"두 변수 중 하나라도 결측치인 {missing_count}건 제외" + (f", 집계 행 {excluded_agg_count}건 제외" if exclude_aggs else ""),
        "used_columns": [label_col, x_col, y_col],
        "unit": "피어슨 상관계수 (r)",
        "caution": "★매우 중요: 상관관계는 인과관계가 아닙니다. 두 변수가 같은 방향으로 움직인다고 해서 한쪽이 다른 쪽의 원인임을 의미하지는 않습니다.",
        "result_data": {
            "x_column": x_col,
            "y_column": y_col,
            "correlation_coefficient": safe_number(corr_value),
            "sample_count": len(df_filtered),
            "chart_data": chart_data
        }
    }

# Tool 12: compare_one_vs_all
def compare_one_vs_all(df, params=None):
    """
    12. compare_one_vs_all: 특정 1개 대상(예: 한국)과 전체 평균·중앙값을 강조 막대로 비교합니다.
    """
    params = params or {}
    ref_col = params.get("reference_period")
    target_item = params.get("target_item", "Korea, Rep.")
    val_col = params.get("value_column") or ref_col
    exclude_aggs = params.get("exclude_aggregates", True)

    df_filtered, meta = filter_data(df, ref_col, val_col, exclude_aggregates=exclude_aggs)
    if df_filtered is None:
        return meta

    label_col = meta["label_col"]
    series = df_filtered[meta["target_col"]]
    overall_mean = safe_number(series.mean())
    overall_median = safe_number(series.median())

    # Find the target item
    item_row = df_filtered[df_filtered[label_col].astype(str) == str(target_item)]
    
    # If not found directly, try case-insensitive contains
    if item_row.empty:
        item_row = df_filtered[df_filtered[label_col].astype(str).str.lower().str.contains(str(target_item).lower())]

    if item_row.empty:
        return {
            "error": f"선택한 대상 '{target_item}'을 데이터셋에서 찾을 수 없거나 해당 연도에 결측치입니다.",
            "success": False
        }

    target_name = str(item_row.iloc[0][label_col])
    target_value = safe_number(item_row.iloc[0][meta["target_col"]])

    # Rank calculation
    sorted_df = df_filtered.sort_values(by=meta["target_col"], ascending=False).reset_index(drop=True)
    rank = int(sorted_df[sorted_df[label_col] == target_name].index[0]) + 1
    total_valid = len(sorted_df)

    diff_from_mean = safe_number(target_value - overall_mean) if target_value and overall_mean else None
    diff_from_median = safe_number(target_value - overall_median) if target_value and overall_median else None

    chart_data = {
        "labels": [target_name, f"전체 평균 ({total_valid}개국)", "전체 중앙값"],
        "datasets": [{
            "label": f"{ref_col}년 수치 비교",
            "data": [target_value, overall_mean, overall_median]
        }]
    }

    return {
        "tool": "compare_one_vs_all",
        "success": True,
        "reference_period": str(ref_col),
        "rows_used": meta["rows_used"],
        "rows_excluded": meta["rows_excluded"],
        "exclusion_reason": meta["exclusion_reason"],
        "used_columns": [label_col, meta["target_col"]],
        "unit": "수치 (%)",
        "caution": "특정 국가와 비교할 때 전체 집단에서 이상치(100% 포화 국가나 극빈국)가 평균에 미친 영향을 고려해야 합니다.",
        "result_data": {
            "target_item": target_name,
            "target_value": target_value,
            "overall_mean": overall_mean,
            "overall_median": overall_median,
            "diff_from_mean": diff_from_mean,
            "diff_from_median": diff_from_median,
            "rank": rank,
            "total_countries": total_valid,
            "chart_data": chart_data
        }
    }

# Tool Registry / Catalog
TOOL_CATALOG = {
    "reshape_wide_to_long": reshape_wide_to_long,
    "quality_report": quality_report,
    "year_coverage": year_coverage,
    "detect_aggregates": detect_aggregates,
    "describe_numeric": describe_numeric,
    "trend_line": trend_line,
    "top_bottom_n": top_bottom_n,
    "group_summary": group_summary,
    "change_rate": change_rate,
    "distribution": distribution,
    "correlation_scatter": correlation_scatter,
    "compare_one_vs_all": compare_one_vs_all
}


