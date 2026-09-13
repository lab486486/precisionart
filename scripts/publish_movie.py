#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""대기 지시(queue) → DeepSeek HTML → src/content/movies."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

REPO = Path(__file__).resolve().parents[1]
QUEUE_DIR = REPO / "src" / "content" / "queue"
MOVIES_DIR = REPO / "src" / "content" / "movies"

CATEGORIES = {"review", "recommend"}
logger = logging.getLogger("publish_movie")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if value is None:
        return '""'
    text = str(value)
    if text == "":
        return '""'
    if any(ch in text for ch in ":#{}[]&*!|>'\"%@`\n"):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def dump_frontmatter(data: dict, body: str = "") -> str:
    lines = ["---"]
    for key, value in data.items():
        if value is None:
            lines.append(f"{key}:")
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {yaml_scalar(item)}")
            continue
        lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    if body:
        lines.append("")
        lines.append(body.rstrip() + "\n")
    else:
        lines.append("")
    return "\n".join(lines)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    stripped = text.lstrip("\ufeff")
    if not stripped.startswith("---"):
        return {}, stripped
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return {}, stripped
    raw, body = parts[1], parts[2].lstrip("\n")
    data: dict = {}
    current_list: str | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        if current_list and line.startswith("  - "):
            if not isinstance(data.get(current_list), list):
                data[current_list] = []
            data[current_list].append(line[4:].strip().strip('"').strip("'"))
            continue
        current_list = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            data[key] = ""
            current_list = key
            continue
        if value in ("true", "false"):
            data[key] = value == "true"
            continue
        data[key] = value.strip('"').strip("'")
    return data, body


def write_markdown(path: Path, data: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_frontmatter(data, body), encoding="utf-8")


def iter_queue_files() -> list[Path]:
    if not QUEUE_DIR.exists():
        return []
    files = []
    for path in sorted(QUEUE_DIR.glob("*.md")):
        if path.name.startswith("_") or path.name.lower() == "readme.md":
            continue
        files.append(path)
    return files


def file_stem(name: str) -> str:
    cleaned = re.sub(r"[^\w가-힣.-]+", "-", name.strip())
    return cleaned.strip("-") or "movie"


def movie_key(name: str) -> str:
    return re.sub(r"[^\w가-힣]+", "", name.lower()) or "movie"


def existing_slugs() -> set[str]:
    slugs: set[str] = set()
    if not MOVIES_DIR.exists():
        return slugs
    for path in MOVIES_DIR.glob("*.md"):
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        slug = str(meta.get("entrySlug") or "").strip()
        if slug:
            slugs.add(slug)
    return slugs


def unique_slug(preferred: str, used: set[str]) -> str:
    slug = re.sub(r"[^\w가-힣-]+", "-", preferred.strip().lower()).strip("-") or "movie"
    if slug not in used:
        return slug
    index = 2
    while f"{slug}-{index}" in used:
        index += 1
    return f"{slug}-{index}"


def clean_html(html: str) -> str:
    text = (html or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:html|HTML)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.replace("```", "").strip()


class DeepSeekMovieGenerator:
    def __init__(
        self,
        api_key: str,
        model_name: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        timeout: int = 180,
        max_tokens: int = 8000,
    ) -> None:
        if not api_key or api_key in ("YOUR_DEEPSEEK_API_KEY_HERE",):
            raise ValueError("DEEPSEEK_API_KEY 를 설정해 주세요.")
        self.model_name = model_name.strip() or "deepseek-v4-flash"
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout,
        )
        self.max_tokens = max_tokens

    def generate(self, name: str, year: str, timeline: str, note: str, thumbnail: str) -> dict:
        poster = thumbnail or "[여기에 입력데이터의 대표이미지 주소 주입]"
        prompt = f"""프리시전아트(precisionart.net) 영화 명장면 좌표 안내 글을 한국어로 작성하세요.
영상은 호스팅하지 않고, 몇 분 몇 초 타임라인만 안내하는 정보 사이트입니다.

영화 제목: {name}
개봉연도: {year or "미기재"}
대표 이미지: {poster}
타임라인:
{timeline or "없음"}
작성 메모: {note or "없음"}

JSON만 출력하세요.
{{
  "title": "영화제목 좌표, 검색자의 니즈를 반영한 매력적인 문장. 대괄호 금지",
  "slug": "영화제목-좌표-주연배우1-주연배우2",
  "excerpt": "120자 안팎의 한 줄 소개",
  "genre": "장르",
  "director": "감독",
  "cast": "출연",
  "studio": "제작사",
  "rating": "⭐⭐⭐⭐☆ 4.0/5.0",
  "tags": ["태그1", "태그2"],
  "html_content": "HTML 본문"
}}

본문 규칙:
- 순수 HTML만 사용. 코드펜스 금지. 영상 임베드·불법 스트리밍 주소 금지.
- 최상위 div에 style="text-align: left !important; word-break: keep-all !important; line-height: 1.8; color: #333;" 만 부여.
- 상단에 포스터와 장르/감독/출연/제작사/상영등급/에디터 평점 정보 박스를 넣으세요. 포스터 src는 {poster} 를 그대로 쓰세요.
- 섹션 h2는 이 스타일: font-size: clamp(1.25em, 4vw, 1.5em); color: #111; font-weight: 800; margin: 28px 0 16px; line-height: 1.35; word-break: keep-all; border-left: 5px solid #c62828; padding-left: 12px;
- 필수 섹션: 이 영화의 줄거리 / [영화제목] 명장면 타임라인 좌표 / 비슷한 분위기의 한국 영화 추천 / 에디터의 종합 평가
- 타임라인은 details 아코디언. summary에는 시간을 넣지 말고 장면 제목만, 앞에 ▶ ▶, 색상 #c62828. 정확한 좌표 시간은 details 안에 넣으세요.
- 추천 영화는 카드 3개. 보러가기 href는 /추천영화제목-좌표-배우1-배우2 상대경로.
- 본문은 1200자 이상.
"""
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                logger.info("DeepSeek 호출 %s/3 (%s)", attempt, self.model_name)
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 한국어 영화 좌표 안내 에디터입니다. JSON만 출력합니다.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=self.max_tokens,
                    temperature=0.6,
                    response_format={"type": "json_object"},
                )
                raw = (response.choices[0].message.content or "").strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                data = json.loads(raw)
                title = str(data.get("title") or "").strip()
                html = clean_html(str(data.get("html_content") or ""))
                excerpt = str(data.get("excerpt") or "").strip()
                slug = str(data.get("slug") or "").strip()
                if not title:
                    raise ValueError("제목이 비어 있습니다.")
                if "<div" not in html.lower():
                    raise ValueError("html_content 에 <div> 가 없습니다.")
                if len(re.sub(r"\s+", "", html)) < 800:
                    raise ValueError(f"본문이 너무 짧습니다 ({len(html)}자).")
                tags = [str(tag).strip() for tag in (data.get("tags") or []) if str(tag).strip()][:8]
                return {
                    "title": title[:80],
                    "slug": slug,
                    "excerpt": excerpt[:180] or f"{name} 명장면 타임라인 좌표 안내.",
                    "genre": str(data.get("genre") or "").strip(),
                    "director": str(data.get("director") or "").strip(),
                    "cast": str(data.get("cast") or "").strip(),
                    "studio": str(data.get("studio") or "").strip(),
                    "rating": str(data.get("rating") or "").strip(),
                    "tags": tags,
                    "html": html,
                }
            except Exception as exc:
                last_error = exc
                logger.warning("DeepSeek 실패: %s", exc)
                if attempt < 3:
                    time.sleep(4)
        raise RuntimeError(f"DeepSeek 콘텐츠 생성 실패: {last_error}")


def process_item(
    path: Path,
    llm: DeepSeekMovieGenerator,
    dry_run: bool,
    used_slugs: set[str],
) -> bool:
    raw = path.read_text(encoding="utf-8")
    meta, _body = parse_frontmatter(raw)
    status = str(meta.get("status") or "").strip().lower()
    if status != "pending":
        logger.info("건너뜀 (%s): status=%s", path.name, status or "없음")
        return False

    name = str(meta.get("name") or "").strip()
    category = str(meta.get("category") or "").strip()
    year = str(meta.get("year") or "").strip()
    if not name:
        raise ValueError("영화 제목이 없습니다.")
    if category not in CATEGORIES:
        raise ValueError(f"카테고리가 올바르지 않습니다: {category}")
    if category == "instruction":
        raise ValueError("영화지시 글은 공개 사이트에 발행하지 않습니다.")

    thumbnail = str(meta.get("thumbnail") or "").strip()
    generated = llm.generate(
        name,
        year,
        str(meta.get("timeline") or ""),
        str(meta.get("note") or ""),
        thumbnail,
    )
    slug = unique_slug(generated["slug"] or f"{name}-좌표", used_slugs)
    dest = MOVIES_DIR / f"{file_stem(name)}.md"
    if dest.exists():
        raise FileExistsError(f"이미 발행된 글이 있습니다: {dest.name}")

    html = generated["html"]
    if thumbnail and "[여기에 입력데이터의 대표이미지 주소 주입]" in html:
        html = html.replace("[여기에 입력데이터의 대표이미지 주소 주입]", thumbnail)

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    post_meta = {
        "title": generated["title"],
        "name": name,
        "category": category,
        "year": year,
        "genre": generated["genre"],
        "director": generated["director"],
        "cast": generated["cast"],
        "studio": generated["studio"],
        "rating": generated["rating"],
        "thumbnail": thumbnail,
        "excerpt": generated["excerpt"],
        "featured": bool(meta.get("featured")),
        "date": now,
        "updated": now,
        "tags": generated["tags"],
        "entrySlug": slug,
        "legacyPath": f"/{slug}/",
        "movieKey": movie_key(name),
        "hiddenFromList": False,
    }

    if dry_run:
        logger.info("[DRY-RUN] 발행 건너뜀: %s (%s자)", generated["title"], len(html))
        return True

    write_markdown(dest, post_meta, html)
    meta["status"] = "done"
    meta["note"] = f"발행됨: /{slug}/"
    write_markdown(path, meta, "")
    used_slugs.add(slug)
    logger.info("발행 완료: %s → %s", generated["title"], dest.relative_to(REPO))
    return True


def mark_error(path: Path, message: str, dry_run: bool) -> None:
    if dry_run:
        logger.error("[DRY-RUN] %s 오류: %s", path.name, message)
        return
    raw = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(raw)
    meta["status"] = "error"
    meta["note"] = message
    write_markdown(path, meta, body)
    logger.error("%s 오류로 표시: %s", path.name, message)


def main() -> int:
    parser = argparse.ArgumentParser(description="영화 글 지시를 HTML 마크다운으로 발행합니다.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-posts", type=int, default=1)
    parser.add_argument("--model", type=str, default=None)
    args = parser.parse_args()

    load_dotenv(REPO / ".env")
    load_dotenv(REPO / "movie" / ".env")
    setup_logging()
    logger.info("프리시전아트 Git 발행기 시작")

    pending = []
    for path in iter_queue_files():
        meta, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if str(meta.get("status") or "").strip().lower() == "pending":
            pending.append(path)

    if not pending:
        logger.info("대기 중인 지시가 없습니다.")
        return 0

    try:
        llm = DeepSeekMovieGenerator(
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            model_name=args.model or os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
    except ValueError as exc:
        logger.error("DeepSeek 초기화 실패: %s", exc)
        return 1

    selected = pending[: max(1, args.max_posts)]
    logger.info("대기 %s건 중 %s건 처리", len(pending), len(selected))
    used_slugs = existing_slugs()

    ok = 0
    fail = 0
    for path in selected:
        try:
            if process_item(path, llm, dry_run=args.dry_run, used_slugs=used_slugs):
                ok += 1
        except Exception:
            fail += 1
            logger.exception("처리 실패: %s", path.name)
            mark_error(path, str(sys.exc_info()[1]), dry_run=args.dry_run)
        if path != selected[-1]:
            time.sleep(3)

    logger.info("완료: 성공 %s / 실패 %s", ok, fail)
    return 1 if fail and not ok else 0


if __name__ == "__main__":
    sys.exit(main())
