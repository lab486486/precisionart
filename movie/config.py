# -*- coding: utf-8 -*-
"""영화 자동 포스팅 시스템 설정 모듈."""

from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def _get_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)).strip())

def _get_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)).strip())

def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")

# WordPress REST API
WP_SITE_URL = os.getenv("WP_SITE_URL", "https://precisionart.net").rstrip("/")
WP_USERNAME = os.getenv("WP_USERNAME", "admin")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")

# LLM provider: deepseek | gemini
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()

# DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_THINKING = _get_bool("DEEPSEEK_THINKING", False)
DEEPSEEK_MAX_TOKENS = _get_int("DEEPSEEK_MAX_TOKENS", 16000)
DEEPSEEK_TIMEOUT_SECONDS = _get_int("DEEPSEEK_TIMEOUT_SECONDS", 240)
DEEPSEEK_MAX_RETRIES = _get_int("DEEPSEEK_MAX_RETRIES", 4)
DEEPSEEK_FALLBACK_MODELS = [
    item.strip()
    for item in os.getenv(
        "DEEPSEEK_FALLBACK_MODELS",
        "deepseek-v4-pro,deepseek-v4-flash",
    ).split(",")
    if item.strip()
]

# Peak avoidance
PEAK_AVOIDANCE_ENABLED = _get_bool("PEAK_AVOIDANCE_ENABLED", True)
PEAK_AVOIDANCE_TZ = os.getenv("PEAK_AVOIDANCE_TZ", "Asia/Seoul")
PEAK_AVOIDANCE_MODE = os.getenv("PEAK_AVOIDANCE_MODE", "skip").strip().lower()
PEAK_AVOIDANCE_MAX_WAIT_SECONDS = _get_int("PEAK_AVOIDANCE_MAX_WAIT_SECONDS", 0)

# Gemini API (rollback)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
GEMINI_FALLBACK_MODELS = [
    item.strip() for item in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3-flash-preview,gemini-2.5-flash,gemini-flash-latest",
    ).split(",") if item.strip()
]
GEMINI_MAX_RETRIES = _get_int("GEMINI_MAX_RETRIES", 4)
GEMINI_TIMEOUT_SECONDS = _get_int("GEMINI_TIMEOUT_SECONDS", 180)

# WordPress behavior
INSTRUCTION_CATEGORY = os.getenv("INSTRUCTION_CATEGORY", "영화지시")
OUTPUT_CATEGORY = os.getenv("OUTPUT_CATEGORY", "영화리뷰")
DONE_TAG = os.getenv("DONE_TAG", "처리완료")
FAILED_TAG = os.getenv("FAILED_TAG", "처리실패")
INSTRUCTION_POST_ACTION = os.getenv("INSTRUCTION_POST_ACTION", "tag_draft")
PUBLISH_STATUS = os.getenv("PUBLISH_STATUS", "draft")

MAX_POSTS_PER_RUN = _get_int("MAX_POSTS_PER_RUN", 3)
API_CALL_DELAY = _get_float("API_CALL_DELAY", 5.0)

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = str(BASE_DIR / "movie_auto_post.log")
