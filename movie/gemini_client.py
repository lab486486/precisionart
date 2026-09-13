# -*- coding: utf-8 -*-
"""Gemini REST API 기반 영화 콘텐츠 생성 모듈 (디테일 지침 강화 및 자의적 해석 방지)."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

from instruction_parser import MovieInstruction

logger = logging.getLogger(__name__)


@dataclass
class GeneratedMoviePost:
    title: str
    slug: str
    excerpt: str
    tags: list[str]
    html_content: str


class GeminiMovieGenerator:
    """Gemini API로 디테일이 살아있는 영화 리뷰를 생성합니다."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3-flash-preview",
        fallback_models: list[str] | None = None,
        timeout_seconds: int = 180,
        max_retries: int = 4,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.fallback_models = fallback_models or [model_name, "gemini-2.5-flash", "gemini-flash-latest"]
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def generate(self, instruction: MovieInstruction) -> GeneratedMoviePost:
        prompt = self._build_prompt(instruction)
        last_error: Exception | None = None

        for model in self.fallback_models:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info("Gemini 호출 중: model=%s, attempt=%s/%s", model, attempt, self.max_retries)
                    raw_text = self._call_gemini(model, prompt)
                    data = self._parse_json(raw_text)
                    generated = self._validate_generated(data)
                    return generated
                except Exception as exc:
                    last_error = exc
                    wait_seconds = self._retry_wait_seconds(exc, attempt)
                    logger.warning("Gemini 호출 실패: %s", exc)
                    if attempt < self.max_retries:
                        time.sleep(wait_seconds)
        raise RuntimeError(f"Gemini 콘텐츠 생성 실패: {last_error}")

    def _call_gemini(self, model: str, prompt: str) -> str:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.75,
                "responseMimeType": "application/json",
            },
        }
        response = requests.post(endpoint, params={"key": self.api_key}, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    def _parse_json(self, raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    def _validate_generated(self, data: dict[str, Any]) -> GeneratedMoviePost:
        return GeneratedMoviePost(
            title=str(data.get("title", "")).strip(),
            slug=str(data.get("slug", "")).strip(),
            excerpt=str(data.get("excerpt", "")).strip(),
            tags=data.get("tags", []),
            html_content=str(data.get("html_content", "")).strip(),
        )

    def _retry_wait_seconds(self, exc: Exception, attempt: int) -> float:
        return min((2 ** attempt) * 5, 60)

    def _build_prompt(self, instruction: MovieInstruction) -> str:
        payload = instruction.to_prompt_payload()
        return f"""
당신은 영화 전문 에디터이자 SEO 전문가입니다. 아래 지침을 100% 준수하여 고퀄리티 영화 포스팅을 작성하세요.

### 1. 제목 및 URL 규칙
- 제목: "영화제목 좌표, 검색자의 니즈를 반영한 매력적인 문장" 형식으로 작성하세요 (대괄호 `[]` 절대 금지)
- 제목에 반드시 '좌표' 키워드를 포함하고, 예술적이고 영화적인 관점에서 궁금증을 유발하는 문장을 만드세요.
- 슬러그(URL): `영화제목-좌표-주연배우1-주연배우2` (한글 사용)

### 2. 레이아웃 및 상세 정보 (모바일 대응 반응형 Flexbox 구조)
- 출력되는 포스팅의 최상위 부모 태그(`<div>`)에 반드시 `style="text-align: left !important; word-break: keep-all !important; line-height: 1.8; color: #333;"` 속성을 단 하나만 부여하여 내부의 모든 글자들이 단어 단위로 깔끔하게 떨어지도록 강제하세요.
- 상단 영화 정보 섹션 (모바일 반응형 최적화): 
  - PC와 모바일 모두에서 레이아웃이 깨지지 않도록 아래 구조를 정확히 지켜 생성하세요. (화면이 좁아지면 자동으로 세로 정렬됩니다)
  ```html
  <div style="display: flex; flex-wrap: wrap; gap: 24px; max-width: 800px; margin: 0 auto 40px auto; padding: 20px; border-bottom: 1px solid #eee;">
    <div style="flex: 0 0 auto; width: 100%; max-width: 250px; margin: 0 auto;">
      <img class="wp-post-image" src="[여기에 입력데이터의 대표이미지 주소 주입]" alt="영화제목 포스터" style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); display: block;" />
    </div>
    <div style="flex: 1 1 300px;">
      <h2 style="margin-top: 0; color: #111; font-size: 24px; font-weight: normal;">[영화제목]</h2>
      <ul style="list-style: none; padding: 0; margin: 0; font-size: 15px;">
        <li style="margin-bottom: 8px;">장르: ...</li>
        <li style="margin-bottom: 8px;">감독: ...</li>
        <li style="margin-bottom: 8px;">출연: ...</li>
        <li style="margin-bottom: 8px;">제작사: ...</li>
        <li style="margin-bottom: 8px;">상영등급: ...</li>
        <li style="margin-bottom: 8px;">에디터 평점: ...</li>
      </ul>
    </div>
  </div>

- 에디터 평점 부여 규칙: 
  - 5점 만점 기준이며, 별점 아이콘(⭐)을 사용하여 시각화하세요. (예: ⭐⭐⭐⭐☆ 4.0/5.0)
  - 최소 2.5점에서 최대 5.0점 사이에서 영화의 작품성과 대중성을 고려하여 자동으로 부여하세요.
- HTML 안정성: 모든 태그를 반드시 닫고, 전체를 하나의 `<div>`로 감싸 워드프레스 레이아웃 깨짐을 방지하세요.
- 출력되는 포스팅의 최상위 부모 태그(`<div>`)에 반드시 `style="text-align: left !important; word-break: keep-all !important; line-height: 1.8; color: #333;"` 속성을 단 하나만 부여하여 내부의 모든 문단, 리스트, 카드 섹션 글자들이 단어 단위로 깔끔하게 떨어지도록 강제하세요. 개별 요소가 중앙 정렬되거나 단어가 중간에 잘리는 현상을 완전히 방지해야 합니다.

### 3. 콘텐츠 구성 지침
- ★ 섹션 소제목(h2) 필수 스타일 (최상단 영화제목 h2 제외, 본문 섹션 제목에 전부 적용):
  - 반드시 아래 인라인 스타일을 그대로 사용하세요. (빨간 왼쪽 바 누락 금지)
  - `<h2 style="font-size: clamp(1.25em, 4vw, 1.5em); color: #111; font-weight: 800; margin: 28px 0 16px; line-height: 1.35; word-break: keep-all; border-left: 5px solid #c62828; padding-left: 12px;">소제목</h2>`
  - 적용 대상 예: `이 영화의 줄거리`, `[영화제목] 명장면 타임라인 좌표`, `비슷한 분위기의 한국 영화 추천`, `에디터의 종합 평가`

- 이 영화의 줄거리(h2 태그 사용, 위 소제목 스타일 필수): 
  - 줄거리는 상세하고 풍성하게 작성하되, 가독성을 위해 반드시 문단을 나누어야 합니다.
  - 1문단은 2~3개의 문장으로 구성하며, 전체적으로 2~3개의 문단이 되도록 <p> 태그를 구분하여 작성하세요. 가독성에 중점을 두세요.
  
- [영화제목] 명장면 타임라인 좌표(h2 태그 사용, 위 소제목 스타일 필수): 
     - `<details style="border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 12px; padding: 12px; background-color: #fff;">` 태그를 사용하세요.
     - **summary 규칙**: `<summary>` 태그에는 절대로 '시간(예: 54:04:00)'을 노출하지 마세요. 요약 영역에는 오직 호기심을 자극하는 [장면 제목]만 노출해야 합니다. (예: `<summary style="font-weight: bold; cursor: pointer; color: #c62828;">▶ ▶ 관사에서의 비밀스러운 시간</summary>`)
     - summary 텍스트 색상은 반드시 `#c62828` 이고, 앞에 `▶ ▶` 를 붙이세요.
     - **내부 콘텐츠 규칙**: 이 글의 핵심 정답인 **정확한 타임라인 시간(좌표)**과 관련된 상세 묘사 글, 그리고 이미지는 반드시 사용자가 클릭해서 열어야만 볼 수 있도록 **`<details>` 태그 내부에 배치**하세요. 사용자가 터치하여 아코디언을 열었을 때 비로소 정확한 시간 좌표가 가장 먼저 눈에 띄도록 강조하여 작성하세요.
  
- 비슷한 분위기의 한국 영화 추천(h2 태그 사용, 위 소제목 스타일 필수, 모바일 반응형 카드 섹션):
  - 추천 영화 섹션 전체를 감싸는 부모 태그는 반드시 다음 스타일을 사용하세요: display: flex; flex-wrap: wrap; gap: 16px; width: 100%; margin-bottom: 30px;
  - 추천 영화 카드는 총 3개로 구성하며, 각 카드의 스타일은 다음을 기준으로 삼아 모바일에서 1줄에 1개씩 떨어지도록 하세요: flex: 1 1 240px; box-sizing: border-box; padding: 16px; border-radius: 8px;
  - 당신(AI)이 3개의 추천 영화 중 하나를 무작위로 선정하여 해당 카드에만 아래의 강조 스타일과 배지를 HTML 생성 시점에 직접 적용하세요.
  - 강력 추천 카드용 강조 스타일: border: 3px solid #c62828 !important; box-shadow: 0 0 15px rgba(198, 40, 40, 0.5) !important; position: relative; background-color: #ffebee; (선택된 단 하나의 카드만 배경을 연한 빨간색 계열로 지정하고 나머지 두 카드는 흰색이나 일반 배경을 유지하세요)
  - 강력 추천 카드 내부 최상단 배치 태그: <span style="position: absolute; top: -12px; left: 50%; transform: translateX(-50%); background: #c62828; color: #fff; padding: 2px 10px; border-radius: 10px; font-size: 11px; z-index: 10;">강력 추천</span>
  - 각 카드 콘텐츠 구성: 영화 제목(내부 링크 포함), 주연 배우 정보, 한 줄 핵심 요약 설명, 보러가기 버튼을 포함하세요.
    - 보러가기 버튼 링크 규칙:각 카드 내부에 포함되는 '보러가기' 버튼의 링크(href)에는 해당 추천 영화의 정보를 바탕으로 1번 규칙에서 정의한 슬러그 형태의 상대 경로를 자동으로 생성하여 삽입하세요.
      (예시) <a href="/상류사회-좌표-박해일-수애" style="display: inline-block; padding: 8px 16px; background-color: #c62828; color: #fff; text-decoration: none; border-radius: 4px; font-size: 13px;">보러가기</a>

예시 구조: href="/추천영화제목-좌표-추천주연배우1-추천주연배우2" (반드시 한글 슬러그 규칙을 그대로 적용할 것)
  - 3개 중 강력 추천하는 '단 하나'의 영화에만 카드섹션 배경색을 빨간색으로 지정하고, 나머지 2개 영화의 카드섹션은 기본 배경색을 유지하여 서로 다르게 시각화하세요.
  
- 에디터의 종합 평가(h2 태그 사용, 위 소제목 스타일 필수): 
  - 평가 카드 섹션: 좋았던 점과 아쉬운 점을 감싸는 부모 태그에 display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 24px;를 부여하세요. 개별 카드는 flex: 1 1 340px; padding: 16px; border: 1px solid #e0e0e0; border-radius: 8px; 스타일을 적용하여 모바일 화면에서 자동으로 세로 정렬되게 하세요.
  - 좋았던 점/아쉬운 점 카드 섹션 아래에 일반 본문  태그를 사용하여 전반적인 이 영화에 대한 평가, 현재 대중들의 인식과 평가, 출연 배우들의 성장 및 발전 과정 등을 자연스럽게 풀어내세요.
  - 이 본문 평가는 2~3개의 문장으로 이루어진 문단을 3~4개 정도로 나누어 풍성하게 서술해야 합니다.
  - 이때 연관검색어로 페이지가 잘 노출될수 있도록 다음 키워드 2~3개를 글 작성시 활용합니다. "여자주연배우 이름, 엑기스, 하이라이트, 몇분, 감독판, 시간대, 베드신"
  - 작성 규칙: 단어를 강조할 때는 별표 기호를 절대 사용하지 말고, 반드시 HTML의 strong 태그를 사용할 것.

<!-- 종합 평가 본문이 끝난 직후 -->
<p style="margin-top: 30px; border-top: 1px dashed #eee; padding-top: 20px;">
  오늘 소개해 드린 영화의 숨은 매력과 좌표 정보가 작품을 한층 더 깊이 있게 즐기는 데 도움이 되었기를 바랍니다. 영화 속 한 장면이 주는 여운은 생각보다 길게 남아서, 평범한 일상을 특별하게 바꾸어 주기도 합니다. 더 많은 영화 정보와 흥미로운 비하인드 스토리가 궁금하시다면 블로그 내 다른 포스팅도 함께 확인해 보세요.
</p>

### 4. 출력 형식 (JSON)
- 모든 스타일은 인라인 CSS를 사용하세요. (랜덤 스크립트 대상 클래스 제외)
반드시 아래 JSON 구조로 응답하세요.
{{
  "title": "...",
  "slug": "...",
  "excerpt": "...",
  "tags": [...],
  "html_content": "..."
}}

입력 데이터:
{payload}
""".strip()