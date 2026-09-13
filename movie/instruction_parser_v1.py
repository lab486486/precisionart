# -*- coding: utf-8 -*-
"""지시글에서 영화제목/개봉연도/이미지를 추정하는 보조 파서."""

import re


def _guess_movie_title(source_title, text):
    explicit = re.search(r"영화제목\s*[:：=]\s*(.+)", text)
    if explicit:
        return explicit.group(1).strip().split("\n")[0].strip()
    return source_title.replace("영화리뷰 요청 - ", "").strip()


def _guess_release_year(source_title, text):
    match = re.search(r"개봉연도\s*[:：=]\s*(\d{4})", text)
    if match:
        return match.group(1)
    match = re.search(r"\b((?:19|20)\d{2})\b", f"{source_title} {text}")
    return match.group(1) if match else ""


def _guess_image_url(text, image_urls):
    explicit = re.search(r"이미지\s*[:：=]\s*(https?://[^\s]+)", text)
    if explicit:
        return explicit.group(1).strip()
    return image_urls[0] if image_urls else None
