# -*- coding: utf-8 -*-
"""WordPress REST API 클라이언트."""

from __future__ import annotations

import logging
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class WordPressClient:
    """WordPress REST API를 통해 지시글 조회, 글 발행, 태그/카테고리 관리를 수행합니다."""

    def __init__(self, site_url: str, username: str, app_password: str, timeout: int = 60):
        if not site_url or not username or not app_password:
            raise ValueError("WP_SITE_URL, WP_USERNAME, WP_APP_PASSWORD 설정이 필요합니다.")

        self.base_url = site_url.rstrip("/")
        self.api_url = f"{self.base_url}/wp-json/wp/v2"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, app_password.replace(" ", ""))
        self.session.headers.update({"Accept": "application/json", "User-Agent": "movie-auto-post/1.0"})

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.request(method, f"{self.api_url}{path}", **kwargs)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                logger.error("WordPress API 400 Error 상세: %s", response.text)
            raise e
        return response

    def test_connection(self) -> bool:
        """인증 상태를 확인합니다."""
        try:
            user = self._request("GET", "/users/me").json()
            logger.info("워드프레스 연결 성공: %s", user.get("name", "Unknown"))
            return True
        except Exception as exc:
            logger.error("워드프레스 연결 또는 인증 실패: %s", exc)
            return False

    def get_category_id(self, category_name: str, create_if_missing: bool = True) -> Optional[int]:
        response = self._request("GET", "/categories", params={"search": category_name, "per_page": 100})
        for category in response.json():
            if category.get("name") == category_name:
                return int(category["id"])

        if not create_if_missing:
            return None

        created = self._request("POST", "/categories", json={"name": category_name}).json()
        logger.info("카테고리 생성: %s(ID=%s)", category_name, created.get("id"))
        return int(created["id"])

    def get_tag_id(self, tag_name: str, create_if_missing: bool = True) -> Optional[int]:
        response = self._request("GET", "/tags", params={"search": tag_name, "per_page": 100})
        for tag in response.json():
            if tag.get("name") == tag_name:
                return int(tag["id"])

        if not create_if_missing:
            return None

        created = self._request("POST", "/tags", json={"name": tag_name}).json()
        logger.info("태그 생성: %s(ID=%s)", tag_name, created.get("id"))
        return int(created["id"])

    def get_instruction_posts(self, category_name: str, exclude_tag: str, per_page: int = 3) -> list[dict]:
        """지시 카테고리에서 처리 완료 태그가 없는 글을 오래된 순서로 가져옵니다."""
        category_id = self.get_category_id(category_name, create_if_missing=True)
        exclude_tag_id = self.get_tag_id(exclude_tag, create_if_missing=False)

        params: dict[str, object] = {
            "categories": category_id,
            "per_page": per_page,
            "orderby": "date",
            "order": "asc",
            "status": "publish,draft,pending,private",
            "context": "edit",
        }
        if exclude_tag_id:
            params["tags_exclude"] = exclude_tag_id

        posts = self._request("GET", "/posts", params=params).json()
        logger.info("'%s' 카테고리에서 처리 대상 %s개 조회", category_name, len(posts))
        return posts

    def publish_post(
        self,
        title: str,
        html_content: str,
        category_name: str,
        tags: list[str] | None = None,
        status: str = "draft",
        excerpt: str = "",
        slug: str | None = None,
        featured_media_id: int | None = None,
        meta: dict | None = None,
    ) -> dict:
        category_id = self.get_category_id(category_name, create_if_missing=True)
        tag_ids = []
        for tag_name in tags or []:
            tag_id = self.get_tag_id(tag_name, create_if_missing=True)
            if tag_id:
                tag_ids.append(tag_id)

        payload: dict[str, object] = {
            "title": title,
            "content": html_content,
            "status": status,
            "categories": [category_id],
            "tags": tag_ids,
            "excerpt": excerpt,
            "comment_status": "open",
            "ping_status": "open",
        }
        if slug:
            payload["slug"] = slug
        if featured_media_id:
            payload["featured_media"] = featured_media_id
        if meta:
            payload["meta"] = meta

        post = self._request("POST", "/posts", json=payload).json()
        logger.info("새 영화 글 발행 완료: %s (ID=%s)", title, post.get("id"))
        return post

    def mark_instruction_done(self, post_id: int, done_tag: str, action: str = "tag_draft") -> None:
        """원본 지시글을 처리 완료 상태로 변경합니다."""
        if action == "delete":
            self._request("DELETE", f"/posts/{post_id}", params={"force": True})
            logger.info("원본 지시글 영구 삭제 완료: ID=%s", post_id)
            return

        if action == "trash":
            self._request("DELETE", f"/posts/{post_id}")
            logger.info("원본 지시글 휴지통 이동 완료: ID=%s", post_id)
            return

        post = self._request("GET", f"/posts/{post_id}", params={"context": "edit"}).json()
        existing_tags = list(post.get("tags", []))
        done_tag_id = self.get_tag_id(done_tag, create_if_missing=True)
        if done_tag_id not in existing_tags:
            existing_tags.append(done_tag_id)

        payload: dict[str, object] = {"tags": existing_tags}
        if action == "tag_draft":
            payload["status"] = "draft"

        self._request("POST", f"/posts/{post_id}", json=payload)
        logger.info("원본 지시글 처리 완료 표시: ID=%s, action=%s", post_id, action)

    def mark_instruction_failed(self, post_id: int, failed_tag: str, reason: str) -> None:
        """처리 실패 태그를 추가하고 원본 글에 실패 사유를 남깁니다."""
        try:
            post = self._request("GET", f"/posts/{post_id}", params={"context": "edit"}).json()
            existing_tags = list(post.get("tags", []))
            failed_tag_id = self.get_tag_id(failed_tag, create_if_missing=True)
            if failed_tag_id not in existing_tags:
                existing_tags.append(failed_tag_id)
            current_excerpt = post.get("excerpt", {}).get("raw") or post.get("excerpt", {}).get("rendered", "")
            excerpt = f"자동 처리 실패: {reason[:180]}"
            if current_excerpt and "자동 처리 실패" not in current_excerpt:
                excerpt = f"{excerpt}\n\n{current_excerpt}"
            self._request("POST", f"/posts/{post_id}", json={"tags": existing_tags, "excerpt": excerpt})
            logger.info("원본 지시글 실패 표시 완료: ID=%s", post_id)
        except Exception as exc:
            logger.warning("실패 태그 추가 중 오류: %s", exc)

    def upload_media_from_url(self, image_url: str | None, title: str = "") -> Optional[int]:
        """외부 이미지 URL을 다운로드하여 워드프레스 미디어 라이브러리에 업로드하고 ID를 반환합니다."""
        if not image_url:
            return None

        # 1. 이미 존재하는지 먼저 확인
        existing_id = self.get_media_id_by_url(image_url)
        if existing_id:
            return existing_id

        try:
            # 2. 이미지 다운로드
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()
            
            # 파일명 추출
            filename = image_url.split("/")[-1].split("?")[0]
            if not filename or "." not in filename:
                filename = f"movie_image_{int(time.time())}.jpg"
            
            content_type = img_response.headers.get("Content-Type", "image/jpeg")

            # 3. 워드프레스에 업로드
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": content_type
            }
            
            # 세션 헤더 임시 업데이트 (업로드용)
            old_headers = self.session.headers.copy()
            self.session.headers.update(headers)
            
            response = self._request("POST", "/media", data=img_response.content)
            
            # 헤더 복구
            self.session.headers = old_headers
            
            media_data = response.json()
            media_id = int(media_data["id"])
            
            # 제목 업데이트 (선택 사항)
            if title:
                self._request("POST", f"/media/{media_id}", json={"title": title, "alt_text": title})
                
            logger.info("이미지 업로드 성공: ID=%s, URL=%s", media_id, image_url)
            return media_id
            
        except Exception as exc:
            logger.warning("이미지 업로드 실패: %s (URL: %s)", exc, image_url)
            return None

    def get_media_id_by_url(self, image_url: str | None) -> Optional[int]:
        """이미지 URL이 WordPress 미디어 라이브러리에 있으면 해당 ID를 반환합니다."""
        if not image_url:
            return None
        
        # 파일명 기반 검색
        filename = image_url.rstrip("/").split("/")[-1].split(".")[0].split("?")[0]
        if not filename:
            return None
            
        try:
            # 전체 미디어에서 검색하는 대신 파일명으로 검색
            media_items = self._request("GET", "/media", params={"search": filename, "per_page": 10}).json()
            for media in media_items:
                source_url = media.get("source_url", "")
                # 원본 URL이 포함되어 있거나 파일명이 일치하는지 확인
                if image_url in source_url or filename in source_url:
                    return int(media["id"])
        except Exception as exc:
            logger.warning("이미지 미디어 ID 조회 실패: %s", exc)
        return None
