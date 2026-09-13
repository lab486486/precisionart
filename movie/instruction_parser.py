# -*- coding: utf-8 -*-
"""워드프레스 지시글 파서 (멀티 타임라인 및 이미지 대응)."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup


@dataclass
class TimelineItem:
    time: str
    description: str
    image_url: str | None = None


@dataclass
class MovieInstruction:
    post_id: int
    source_title: str
    movie_title: str
    release_year: str
    main_image_url: str | None = None
    timelines: list[TimelineItem] = field(default_factory=list)
    notes: str = ""
    raw_text: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.movie_title or self.movie_title == "미상":
            errors.append("영화제목을 찾지 못했습니다.")
        if not re.fullmatch(r"(18|19|20)\d{2}", str(self.release_year or "")):
            errors.append("개봉연도는 4자리 숫자로 입력해야 합니다.")
        return errors

    def to_prompt_payload(self) -> str:
        timeline_str = "\n".join(
            [f"- [{item.time}] {item.description} (이미지: {item.image_url or '없음'})" for item in self.timelines]
        )
        return "\n".join(
            [
                f"영화 제목: {self.movie_title}",
                f"개봉연도: {self.release_year}",
                f"대표 포스터 URL: {self.main_image_url or '없음'}",
                "",
                "명장면 타임라인 및 설명:",
                timeline_str or "없음",
                "",
                "추가 메모/요청사항:",
                self.notes.strip() or "없음",
            ]
        )


def _html_to_text_and_images(html_content: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(html_content or "", "html.parser")
    image_urls: list[str] = []
    for image in soup.find_all("img"):
        src = image.get("src")
        if src:
            image_urls.append(src.strip())
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4"]):
        block.append("\n")
    text = soup.get_text("\n")
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip(), image_urls


def _find_field(text: str, names: list[str]) -> str | None:
    joined = "|".join(re.escape(name) for name in names)
    pattern = rf"(?:^|\n)\s*(?:{joined})\s*[:：=]\s*(.+?)(?=\n\s*[가-힣A-Za-z ]{{1,20}}\s*[:：=]|\Z)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def _parse_timelines(text: str, image_urls: list[str]) -> list[TimelineItem]:
    """
    타임라인 형식 파싱:
    00:12:34 설명글
    또는
    타임라인1: 00:12:34 설명글
    """
    items = []
    # 타임라인 섹션 찾기
    section = _find_field(text, ["타임라인", "timeline", "명장면", "좌표"])
    search_text = section if section else text

    # 시간 패턴: 00:00, 00:00:00, 12분 30초 등
    pattern = r"((?:\d{1,2}:)?\d{1,2}:\d{1,2})\s*(.+)"
    matches = re.findall(pattern, search_text)

    # 이미지 매칭 (순서대로 매칭하거나 텍스트 내 URL 찾기)
    img_idx = 0
    # 대표 이미지는 제외하고 매칭하기 위해 1번부터 시작할지 고민 필요
    # 여기서는 텍스트 내에 URL이 있으면 우선 사용

    for time_str, desc in matches:
        desc_clean = desc.split("\n")[0].strip()
        img_url = None
        # 설명글 안에 URL이 있는지 확인
        url_match = re.search(r"https?://[^\s)\]>'\"]+", desc)
        if url_match:
            img_url = url_match.group(0)
            desc_clean = desc_clean.replace(img_url, "").strip()
        elif img_idx < len(image_urls):
            # 본문에 첨부된 이미지 순서대로 할당 (대표 이미지 제외 로직은 호출부에서 처리)
            img_url = image_urls[img_idx]
            img_idx += 1

        items.append(TimelineItem(time=time_str, description=desc_clean, image_url=img_url))
    return items


def parse_instruction_post(post: dict[str, Any]) -> MovieInstruction:
    post_id = int(post.get("id"))
    source_title = post.get("title", {}).get("rendered") or post.get("title", {}).get("raw") or ""
    content_html = post.get("content", {}).get("rendered") or post.get("content", {}).get("raw") or ""
    text, image_urls = _html_to_text_and_images(content_html)

    # 영화 제목 및 연도 추출 (이전 로직 활용)
    from instruction_parser_v1 import _guess_movie_title, _guess_release_year, _guess_image_url
    movie_title = _guess_movie_title(source_title, text)
    release_year = _guess_release_year(source_title, text)
    
    # 대표 이미지 (첫 번째 이미지 또는 명시된 URL)
    main_image_url = _guess_image_url(text, image_urls)
    
    # 타임라인 파싱 시 대표 이미지 제외
    remaining_images = [url for url in image_urls if url != main_image_url]
    timelines = _parse_timelines(text, remaining_images)

    notes = _find_field(text, ["메모", "참고", "요청사항", "추가", "notes"]) or ""

    return MovieInstruction(
        post_id=post_id,
        source_title=re.sub(r"<[^>]+>", "", source_title).strip(),
        movie_title=movie_title,
        release_year=release_year,
        main_image_url=main_image_url,
        timelines=timelines,
        notes=notes,
        raw_text=text,
    )
