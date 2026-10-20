import os
import glob
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class DataAnalyzer:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.main_df = None
        self.meta_df = None
        self.merged_df = None
        self.year_columns = []
        self._load_datasets()

    def _load_datasets(self):
        try:
            # 1. 메인 CSV 파일 탐색 (skiprows=4 World Bank 포맷)
            main_pattern = os.path.join(self.data_dir, "API_IT.NET.USER.ZS*", "API_IT.NET.USER.ZS*.csv")
            matches = glob.glob(main_pattern)
            if not matches:
                # data 디렉터리 직하에서도 탐색
                matches = glob.glob(os.path.join(self.data_dir, "**", "API*.csv"), recursive=True)

            if matches:
                main_file = matches[0]
                self.main_df = pd.read_csv(main_file, skiprows=4)
                # 연도 컬럼 추출 (숫자로만 된 컬럼들)
                self.year_columns = [c for c in self.main_df.columns if str(c).isdigit()]
                logger.info(f"메인 데이터셋 로드 완료: {main_file} (총 {len(self.main_df)}개 행, 연도: {self.year_columns[0]}~{self.year_columns[-1]})")

            # 2. 메타데이터 CSV 파일 탐색 (Region, IncomeGroup)
            meta_pattern = os.path.join(self.data_dir, "**", "Metadata_Country*.csv")
            meta_matches = glob.glob(meta_pattern, recursive=True)
            if meta_matches:
                self.meta_df = pd.read_csv(meta_matches[0])
                logger.info(f"메타데이터 로드 완료: {meta_matches[0]}")

            # 3. 데이터 병합
            if self.main_df is not None and self.meta_df is not None:
                self.merged_df = pd.merge(
                    self.main_df,
                    self.meta_df[['Country Code', 'Region', 'IncomeGroup']],
                    on='Country Code',
                    how='left'
                )
                # Region이 존재하는 행은 개별 국가, 없는 행은 전세계/지역별 집계
                self.merged_df['IsCountry'] = self.merged_df['Region'].notna() & (self.merged_df['Region'] != '')
            elif self.main_df is not None:
                self.merged_df = self.main_df.copy()
                self.merged_df['IsCountry'] = True
                self.merged_df['Region'] = 'Unknown'
                self.merged_df['IncomeGroup'] = 'Unknown'

        except Exception as e:
            logger.error(f"데이터셋 로드 중 오류 발생: {e}", exc_info=True)

    def get_latest_valid_year(self, min_coverage=100):
        """충분한 데이터가 채워진 최근 연도 반환 (기본값: 최소 100개국 이상 데이터)"""
        if not self.year_columns:
            return "2023"
        for y in reversed(self.year_columns):
            if y in self.merged_df.columns:
                valid_count = self.merged_df[y].dropna().count()
                if valid_count >= min_coverage:
                    return y
        return self.year_columns[-1]

    def get_overview_stats(self):
        """대시보드 상단 요약 지표 및 탑/바텀 국가 정보"""
        if self.merged_df is None:
            return {}

        latest_year = self.get_latest_valid_year()
        countries_only = self.merged_df[self.merged_df['IsCountry']].copy()

        # 최신 연도 기준 통계 (결측치 제외)
        latest_series = countries_only[['Country Name', 'Country Code', 'Region', 'IncomeGroup', latest_year]].dropna(subset=[latest_year])
        
        # 세계 평균 (World Bank 집계 또는 국가 평균)
        world_row = self.merged_df[self.merged_df['Country Code'] == 'WLD']
        if not world_row.empty and not pd.isna(world_row[latest_year].values[0]):
            world_avg = round(float(world_row[latest_year].values[0]), 1)
        else:
            world_avg = round(float(latest_series[latest_year].mean()), 1)

        # 상위 5개국
        top5 = latest_series.sort_values(by=latest_year, ascending=False).head(5)
        top5_list = [
            {"name": row['Country Name'], "code": row['Country Code'], "value": round(float(row[latest_year]), 1), "region": row['Region']}
            for _, row in top5.iterrows()
        ]

        # 하위 5개국
        bottom5 = latest_series.sort_values(by=latest_year, ascending=True).head(5)
        bottom5_list = [
            {"name": row['Country Name'], "code": row['Country Code'], "value": round(float(row[latest_year]), 1), "region": row['Region']}
            for _, row in bottom5.iterrows()
        ]

        # 소득 수준별 평균
        income_avg = countries_only.groupby('IncomeGroup')[latest_year].mean().dropna().round(1).to_dict()

        # 지역별 평균
        region_avg = countries_only.groupby('Region')[latest_year].mean().dropna().round(1).to_dict()

        # 한국 데이터 확인
        kor_row = self.merged_df[self.merged_df['Country Code'] == 'KOR']
        kor_val = None
        if not kor_row.empty and not pd.isna(kor_row[latest_year].values[0]):
            kor_val = round(float(kor_row[latest_year].values[0]), 1)

        return {
            "latest_year": latest_year,
            "world_average": world_avg,
            "tracked_countries_count": len(latest_series),
            "korea_value": kor_val,
            "top5": top5_list,
            "bottom5": bottom5_list,
            "income_group_averages": income_avg,
            "region_averages": region_avg
        }

    def get_country_list(self):
        """드롭다운용 국가/지역 목록"""
        if self.merged_df is None:
            return []
        
        # 국가 우선 정렬, 집계 지역 분리
        countries = []
        for _, row in self.merged_df.iterrows():
            countries.append({
                "name": row['Country Name'],
                "code": row['Country Code'],
                "region": str(row.get('Region', '')) if pd.notna(row.get('Region')) else 'Global / Regional Group',
                "income_group": str(row.get('IncomeGroup', '')) if pd.notna(row.get('IncomeGroup')) else '',
                "is_country": bool(row['IsCountry'])
            })
        
        # 이름 순 정렬 (한국, 미국 등을 찾기 쉽도록)
        countries.sort(key=lambda x: (not x['is_country'], x['name']))
        return countries

    def get_timeline(self, country_codes=None, start_year=1995, end_year=None):
        """Chart.js에 바로 바인딩 가능한 시계열 데이터셋 반환"""
        if self.merged_df is None:
            return {"years": [], "datasets": []}

        if not country_codes:
            # 기본 프리셋: 한국, 미국, 일본, 독일, 세계 평균
            country_codes = ['KOR', 'USA', 'JPN', 'DEU', 'WLD']

        if end_year is None:
            end_year = int(self.get_latest_valid_year())
        start_year = int(start_year)

        # 연도 레이블 필터링
        years = [y for y in self.year_columns if start_year <= int(y) <= end_year]

        # 색상 팔레트
        palette = [
            {"border": "#2563eb", "bg": "rgba(37, 99, 235, 0.1)"},    # Blue
            {"border": "#ea580c", "bg": "rgba(234, 88, 12, 0.1)"},    # Orange
            {"border": "#10b981", "bg": "rgba(16, 185, 129, 0.1)"},   # Emerald
            {"border": "#8b5cf6", "bg": "rgba(139, 92, 246, 0.1)"},   # Violet
            {"border": "#ef4444", "bg": "rgba(239, 68, 68, 0.1)"},    # Red
            {"border": "#06b6d4", "bg": "rgba(6, 182, 212, 0.1)"},    # Cyan
            {"border": "#f59e0b", "bg": "rgba(245, 158, 11, 0.1)"},   # Amber
            {"border": "#64748b", "bg": "rgba(100, 116, 139, 0.1)"}   # Slate
        ]

        datasets = []
        for i, code in enumerate(country_codes):
            row = self.merged_df[self.merged_df['Country Code'] == code]
            if row.empty:
                continue
            row = row.iloc[0]
            name = row['Country Name']
            
            # 각 연도별 수치 (NaN은 None으로 변환)
            data_points = []
            for y in years:
                val = row[y]
                if pd.isna(val):
                    data_points.append(None)
                else:
                    data_points.append(round(float(val), 2))

            color = palette[i % len(palette)]
            is_world = (code == 'WLD')
            datasets.append({
                "label": f"{name} ({code})",
                "code": code,
                "data": data_points,
                "borderColor": "#475569" if is_world else color["border"],
                "backgroundColor": color["bg"],
                "borderWidth": 3 if code in ['KOR', 'WLD'] else 2,
                "borderDash": [5, 5] if is_world else [],
                "tension": 0.25,
                "fill": False
            })

        return {
            "years": years,
            "datasets": datasets
        }

    def get_growth_leaders(self, start_year="2014", end_year="2024", limit=10):
        """최근 10년간 가장 가파르게 성장한 국가 목록"""
        if self.merged_df is None or start_year not in self.merged_df.columns or end_year not in self.merged_df.columns:
            return []

        countries_only = self.merged_df[self.merged_df['IsCountry']].copy()
        valid = countries_only.dropna(subset=[start_year, end_year]).copy()
        
        valid['growth_point'] = valid[end_year] - valid[start_year]
        valid['growth_rate'] = ((valid[end_year] - valid[start_year]) / valid[start_year].replace(0, np.nan)) * 100

        leaders = valid.sort_values(by='growth_point', ascending=False).head(limit)
        result = []
        for _, row in leaders.iterrows():
            result.append({
                "name": row['Country Name'],
                "code": row['Country Code'],
                "region": row['Region'],
                "start_val": round(float(row[start_year]), 1),
                "end_val": round(float(row[end_year]), 1),
                "growth_point": round(float(row['growth_point']), 1)
            })
        return result

    def analyze_custom_dataframe(self, df):
        """사용자가 업로드한 커스텀 CSV 데이터의 기초 통계 및 요약"""
        summary = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "columns": list(df.columns),
            "sample_rows": df.head(5).to_dict(orient="records"),
            "numeric_columns": [],
            "statistics": {}
        }

        numeric_df = df.select_dtypes(include=[np.number])
        summary["numeric_columns"] = list(numeric_df.columns)

        if not numeric_df.empty:
            desc = numeric_df.describe().round(2).to_dict()
            summary["statistics"] = desc

        return summary
