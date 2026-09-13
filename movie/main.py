# -*- coding: utf-8 -*-
"""영화 자동 포스팅 시스템 메인 실행 스크립트 (DeepSeek V4 / Gemini)."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import config
from deepseek_client import DeepSeekMovieGenerator
from gemini_client import GeminiMovieGenerator
from instruction_parser import parse_instruction_post
from peak_scheduler import describe_peaks, wait_or_skip_if_peak
from wordpress_client import WordPressClient

logger = logging.getLogger(__name__)


def setup_logging(log_level: str, log_file: str | None) -> None:
    level = getattr(logging, (log_level or "INFO").upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


def build_generator(args: argparse.Namespace):
    if config.LLM_PROVIDER == "gemini":
        return GeminiMovieGenerator(
            api_key=config.GEMINI_API_KEY,
            model_name=args.model or config.GEMINI_MODEL,
            fallback_models=config.GEMINI_FALLBACK_MODELS,
            timeout_seconds=config.GEMINI_TIMEOUT_SECONDS,
            max_retries=config.GEMINI_MAX_RETRIES,
        )
    return DeepSeekMovieGenerator(
        api_key=config.DEEPSEEK_API_KEY,
        model_name=args.model or config.DEEPSEEK_MODEL,
        base_url=config.DEEPSEEK_BASE_URL,
        thinking=config.DEEPSEEK_THINKING,
        timeout_seconds=config.DEEPSEEK_TIMEOUT_SECONDS,
        max_retries=config.DEEPSEEK_MAX_RETRIES,
        max_tokens=config.DEEPSEEK_MAX_TOKENS,
        fallback_models=config.DEEPSEEK_FALLBACK_MODELS,
    )


def process_single_post(
    post: dict,
    wp_client: WordPressClient,
    generator,
    dry_run: bool,
    publish_status: str,
    instruction_action: str,
) -> bool:
    post_id = int(post.get("id"))
    logger.info("━━━ 영화 지시글 처리 시작: ID=%s ━━━", post_id)

    try:
        instruction = parse_instruction_post(post)
        logger.info(
            "파싱 결과: 영화='%s', 연도='%s', 이미지='%s'",
            instruction.movie_title,
            instruction.release_year,
            instruction.main_image_url or "없음",
        )
        validation_errors = instruction.validate()
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        generated = generator.generate(instruction)
        html_content = generated.html_content

        featured_media_id = None
        if instruction.main_image_url:
            logger.info("메인 포스터 이미지 업로드 검증 중: %s", instruction.main_image_url)

            try:
                img_response = wp_client.session.get(instruction.main_image_url, timeout=30)
                img_response.raise_for_status()

                safe_filename = f"poster_{post_id}_{int(time.time())}.webp"
                headers = {
                    "Content-Disposition": f'attachment; filename="{safe_filename}"',
                    "Content-Type": "image/webp",
                }

                old_headers = wp_client.session.headers.copy()
                wp_client.session.headers.update(headers)

                logger.info("안전한 영문 헤더로 워드프레스 미디어 라이브러리 직접 주입 시도")
                res = wp_client._request("POST", "/media", data=img_response.content)

                wp_client.session.headers = old_headers

                media_data = res.json()
                featured_media_id = int(media_data["id"])

                wp_client._request("POST", f"/media/{featured_media_id}", json={
                    "title": f"{instruction.movie_title} 공식 대표 포스터",
                    "alt_text": f"{instruction.movie_title} 포스터 이미지",
                })
                logger.info("대표 썸네일용 미디어 강제 고정 성공: ID=%s", featured_media_id)

            except Exception as upload_err:
                if "old_headers" in locals():
                    wp_client.session.headers = old_headers
                logger.warning("미디어 강제 주입 실패, 안전 예외 모드로 기존 매핑 전환 시도: %s", upload_err)
                featured_media_id = wp_client.upload_media_from_url(
                    instruction.main_image_url,
                    title=f"{instruction.movie_title} 포스터",
                )

        if featured_media_id:
            media_info = wp_client._request("GET", f"/media/{featured_media_id}").json()
            full_image_url = media_info.get("source_url")

            if "[여기에 입력데이터의 대표이미지 주소 주입]" in html_content:
                html_content = html_content.replace(
                    "[여기에 입력데이터의 대표이미지 주소 주입]",
                    full_image_url,
                )
            elif 'id="featured-thumbnail" src=""' in html_content:
                html_content = html_content.replace(
                    'id="featured-thumbnail" src=""',
                    f'id="featured-thumbnail" src="{full_image_url}"',
                )
            elif 'src=""' in html_content:
                html_content = html_content.replace('src=""', f'src="{full_image_url}"', 1)

        logger.info("본문 훼손 방지 필터 적용 완료. 원본 전체 텍스트 구조 보존.")

        tags = list(
            dict.fromkeys(
                generated.tags
                + [
                    instruction.movie_title,
                    f"{instruction.movie_title} 리뷰",
                    f"{instruction.release_year} 영화",
                ]
            )
        )[:10]

        if dry_run:
            logger.info("[DRY-RUN] 발행 생략")
            logger.info("[DRY-RUN] 제목: %s", generated.title)
            logger.info("[DRY-RUN] 슬러그: %s", generated.slug)
            logger.info("[DRY-RUN] 태그: %s", tags)
            logger.info("[DRY-RUN] 본문 길이: %s자", len(html_content))
            return True

        new_post = wp_client.publish_post(
            title=generated.title,
            html_content=html_content,
            category_name=config.OUTPUT_CATEGORY,
            tags=tags,
            status=publish_status,
            excerpt=generated.excerpt,
            slug=generated.slug or None,
            featured_media_id=featured_media_id,
        )
        logger.info("발행 성공: %s", new_post.get("link", "URL 없음"))
        wp_client.mark_instruction_done(
            post_id,
            done_tag=config.DONE_TAG,
            action=instruction_action,
        )
        logger.info("━━━ 영화 지시글 처리 완료: ID=%s ━━━", post_id)
        return True

    except Exception as exc:
        err_msg = str(exc)
        logger.exception("지시글 처리 실패: ID=%s, error=%s", post_id, err_msg)
        if not dry_run:
            try:
                wp_client.mark_instruction_failed(
                    post_id,
                    failed_tag=config.FAILED_TAG,
                    reason=err_msg,
                )
            except Exception as mark_err:
                logger.error("실패 마킹 중 추가 오류 (세션 리셋 후 재시도): %s", mark_err)
                wp_client.session.headers = {
                    "Accept": "application/json",
                    "User-Agent": "movie-auto-post/1.0",
                }
                wp_client.mark_instruction_failed(
                    post_id,
                    failed_tag=config.FAILED_TAG,
                    reason=err_msg,
                )
        return False


def main(args: argparse.Namespace) -> None:
    setup_logging(args.log_level or config.LOG_LEVEL, None if args.no_log_file else config.LOG_FILE)
    logger.info("=" * 70)
    logger.info("영화 자동 포스팅 시스템 시작: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("LLM provider=%s", config.LLM_PROVIDER)
    if args.dry_run:
        logger.info("DRY-RUN 모드: 실제 발행 및 원본 완료 처리를 하지 않습니다.")
    logger.info("=" * 70)

    peak_relevant = config.LLM_PROVIDER == "deepseek" and config.PEAK_AVOIDANCE_ENABLED
    if peak_relevant:
        logger.info("\n%s", describe_peaks(config.PEAK_AVOIDANCE_TZ))
        if not args.force_peak:
            can_run = wait_or_skip_if_peak(
                tz_name=config.PEAK_AVOIDANCE_TZ,
                mode=config.PEAK_AVOIDANCE_MODE,
                max_wait_seconds=config.PEAK_AVOIDANCE_MAX_WAIT_SECONDS,
                logger=logger,
            )
            if not can_run:
                logger.info("피크타임이라 종료합니다. 밸리 시간에 cron이 다시 돌면 처리됩니다.")
                return
        else:
            logger.warning("※ --force-peak: 피크타임이어도 API 호출을 강제 진행합니다.")

    wp_client = WordPressClient(
        site_url=config.WP_SITE_URL,
        username=config.WP_USERNAME,
        app_password=config.WP_APP_PASSWORD,
    )
    if not args.skip_connection_test and not wp_client.test_connection():
        raise SystemExit(1)

    generator = build_generator(args)

    posts = wp_client.get_instruction_posts(
        category_name=args.instruction_category or config.INSTRUCTION_CATEGORY,
        exclude_tag=config.DONE_TAG,
        per_page=args.max_posts or config.MAX_POSTS_PER_RUN,
    )

    if not posts:
        logger.info("처리할 영화 지시글이 없습니다.")
        return

    success_count = 0
    fail_count = 0
    for index, post in enumerate(posts, start=1):
        logger.info("[%s/%s] 처리 중", index, len(posts))
        success = process_single_post(
            post=post,
            wp_client=wp_client,
            generator=generator,
            dry_run=args.dry_run,
            publish_status=args.status or config.PUBLISH_STATUS,
            instruction_action=args.action or config.INSTRUCTION_POST_ACTION,
        )
        if success:
            success_count += 1
        else:
            fail_count += 1
        if index < len(posts):
            time.sleep(config.API_CALL_DELAY)

    logger.info("=" * 70)
    logger.info("처리 완료: 총 %s개, 성공 %s개, 실패 %s개", len(posts), success_count, fail_count)
    logger.info("=" * 70)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WordPress + DeepSeek/Gemini 영화 자동 포스팅")
    parser.add_argument("--dry-run", action="store_true", help="실제 발행 없이 테스트만 수행")
    parser.add_argument("--max-posts", type=int, default=None, help="이번 실행에서 처리할 최대 글 수")
    parser.add_argument("--status", choices=["publish", "draft", "pending", "private"], default=None, help="새 글 발행 상태")
    parser.add_argument("--action", choices=["tag", "tag_draft", "trash", "delete"], default=None, help="원본 지시글 처리 방식")
    parser.add_argument("--model", type=str, default=None, help="모델명 (deepseek-v4-pro / gemini-...)")
    parser.add_argument("--force-peak", action="store_true", help="DeepSeek 피크타임이어도 API 강제 호출")
    parser.add_argument("--instruction-category", type=str, default=None, help="처리할 워드프레스 지시 카테고리명")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default=None, help="로그 레벨")
    parser.add_argument("--no-log-file", action="store_true", help="로그 파일 저장 비활성화")
    parser.add_argument("--skip-connection-test", action="store_true", help="워드프레스 연결 테스트 생략")
    return parser.parse_args()


if __name__ == "__main__":
    main(parse_args())
