import os
import json
import logging
from dotenv import load_dotenv
from google import genai
from google.genai import errors

load_dotenv()
logger = logging.getLogger(__name__)

class GeminiInsightService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.client = None
        self._init_client()

    def _init_client(self):
        if not self.api_key or self.api_key.startswith("your_"):
            logger.warning("GEMINI_API_KEY가 올바르게 설정되어 있지 않습니다.")
            return
        try:
            self.client = genai.Client(api_key=self.api_key)
            logger.info("Gemini API 클라이언트가 성공적으로 초기화되었습니다.")
        except Exception as e:
            logger.error(f"Gemini 클라이언트 초기화 실패: {e}")

    def generate_worldbank_insight(self, stats_context, selected_countries=None, focus_mode="trend_inequality", user_question=""):
        """세계은행 인터넷 보급률 데이터를 기반으로 심층 AI 인사이트 보고서 생성"""
        if not self.client:
            raise RuntimeError("Gemini API 클라이언트가 설정되지 않았습니다. .env 파일을 확인해 주세요.")

        # 분석 모드별 시스템 프롬프트 및 지시사항
        modes_config = {
            "trend_inequality": {
                "title": "글로벌 인터넷 보급률 트렌드 및 디지털 불평등 분석",
                "role": "세계은행(World Bank) 및 ITU 수석 디지털 경제학자",
                "focus": "1995년부터 2024년까지의 글로벌 인터넷 보급률 추세, 고소득국(91.7%)과 저소득국(23.0%) 간의 심각한 디지털 양극화(Digital Divide), 사하라 이남 아프리카의 인프라 제약 요인을 집중 분석하세요."
            },
            "country_deepdive": {
                "title": "선택 국가 간 비교 분석 및 성장 궤적 벤치마킹",
                "role": "글로벌 IT 정책 및 데이터 분석 수석 컨설턴트",
                "focus": f"사용자가 선택한 국가들({', '.join(selected_countries) if selected_countries else '주요 국가들'})의 시계열 보급률 데이터를 벤치마킹하고, 각국의 성공 요인(정부 주도 브로드밴드 정책 등)과 정체 요인을 비교 대조하세요."
            },
            "digital_divide_policy": {
                "title": "디지털 격차 해소 및 AI 시대의 정책적 제언",
                "role": "국제기구 디지털 전환 및 공공정책 총괄 고문",
                "focus": "단순한 인터넷 접속을 넘어 AI 시대에 필수적인 초고속 통신망 접근 격차를 해소하기 위한 실질적인 정책 솔루션(인프라 투자 모델, 공공 Wi-Fi, 디지털 리터러시 교육 등)을 제안하세요."
            }
        }

        config = modes_config.get(focus_mode, modes_config["trend_inequality"])

        # 데이터 요약 텍스트 구성
        context_str = json.dumps(stats_context, ensure_ascii=False, indent=2)

        prompt = f"""
당신은 {config['role']}입니다.
아래에 제공된 공식 세계은행(World Bank) '국가별 인터넷 보급률(Individuals using the Internet, % of population)' 통계 데이터를 면밀히 검토하고, 전문가 수준의 국문 분석 리포트를 작성해 주세요.

[제공된 데이터 통계 컨텍스트]
{context_str}

[분석 핵심 방향]
- 분석 주제: {config['title']}
- 집중 과제: {config['focus']}
{f'- 사용자 추가 질문/요청: {user_question}' if user_question else ''}

[리포트 작성 요구사항]
1. 문서 구조:
   # 📊 {config['title']}
   
   ## 1. 📌 Executive Summary (핵심 요약)
   - 주요 발견점 3가지를 명확한 불릿 포인트로 제시
   
   ## 2. 📈 데이터 기반 핵심 분석 (Quantitative Findings)
   - 데이터 수치(예: 세계 평균, 소득 그룹별 수치, 최상위/최하위 격차 등)를 직접 인용하여 논리적 설명
   - 최근 10~20년간의 성장 변곡점 및 트렌드 해석
   
   ## 3. 🔍 심층 통찰 (Key Insights & Drivers)
   - 경제적 요인, 인프라 투자, 모바일 통신 도입 등의 원인 분석
   - 인공지능(AI) 시대에서 이러한 디지털 격차가 국가 경쟁력에 미칠 영향
   
   ## 4. 💡 실천적 제언 (Strategic Recommendations)
   - 정부 및 정책 입안자, 국제기구, IT 기업 관점의 전략적 액션 플랜 3가지

2. 톤앤매너: 전문적이고 설득력 있으며 데이터 기반의 객관적인 어조를 유지하세요.
3. 포맷팅: 가독성이 뛰어난 Markdown 문법(소제목, 테이블, 볼드체, 인용구 등)을 적극 활용하세요.
"""

        try:
            logger.info(f"Gemini 인사이트 생성 요청 (모드: {focus_mode}, 모델: {self.model_name})")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except errors.APIError as e:
            logger.error(f"Gemini API 오류 발생: {e}")
            raise
        except Exception as e:
            logger.error(f"Gemini 호출 중 알 수 없는 예외: {e}")
            raise

    def generate_custom_csv_insight(self, summary_data, user_request=""):
        """사용자가 업로드한 커스텀 데이터셋에 대한 자동 AI 통계 분석 및 비즈니스 인사이트 생성"""
        if not self.client:
            raise RuntimeError("Gemini API 클라이언트가 설정되지 않았습니다.")

        summary_json = json.dumps(summary_data, ensure_ascii=False, indent=2)

        prompt = f"""
당신은 최고의 수석 데이터 과학자이자 비즈니스 인텔리전스(BI) 컨설턴트입니다.
사용자가 업로드한 데이터셋의 기초 통계 및 샘플 데이터를 바탕으로, 통찰력 있는 국문 데이터 분석 보고서를 작성해 주세요.

[데이터셋 메타데이터 및 기술 통계]
{summary_json}

{f'[사용자 특별 요청 사항]\n{user_request}\n' if user_request else ''}

[보고서 작성 가이드]
1. **데이터 개요 및 구조 평가**: 데이터의 규모, 주요 컬럼 특성, 데이터 품질 및 결측치 현황
2. **핵심 통계적 발견점 (Key Patterns & Outliers)**: 주요 수치형 변수의 분포, 평균/중앙값 차이, 이상치 및 특징
3. **실무적 인사이트 및 기회 요인**: 이 데이터가 시사하는 비즈니스/운영적 의미
4. **향후 심층 분석 및 개선 추천**: 추가로 수집하거나 교차 분석해볼 만한 방향 제시

깔끔하고 세련된 Markdown 형식으로 작성해 주세요.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"커스텀 CSV 인사이트 생성 실패: {e}")
            raise
