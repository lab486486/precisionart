# -*- coding: utf-8 -*-
"""
peak_scheduler.py
DeepSeek 피크타임(peak-valley) 요금 회피 스케줄러

공식 피크 (UTC):
  - 01:00–04:00
  - 06:00–10:00

한국(Asia/Seoul, UTC+9) 환산:
  - 10:00–13:00
  - 15:00–19:00

규칙 (스냅 투 밸리):
  피크 구간에 걸리면 '피크 종료 시각'으로 시(hour)만 옮기고,
  분·초는 그대로 유지한다.

  예) KST
    10:30 → 13:30
    11:45 → 13:45
    12:59 → 13:59
    15:30 → 19:30
    17:10 → 19:10
    09:30 → 그대로 (피크 아님)
    14:30 → 그대로 (피크 아님)
    13:00 → 그대로 (피크 종료 시점, 비피크)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9
    from backports.zoneinfo import ZoneInfo  # type: ignore


# DeepSeek 공식 피크 (반개구간: start 포함, end 미포함)
PEAK_WINDOWS_UTC: tuple[tuple[time, time], ...] = (
    (time(1, 0), time(4, 0)),
    (time(6, 0), time(10, 0)),
)

DEFAULT_TZ = "Asia/Seoul"


@dataclass(frozen=True)
class PeakAdjustment:
    original: datetime
    adjusted: datetime
    was_peak: bool
    peak_label: str = ""

    @property
    def changed(self) -> bool:
        return self.original != self.adjusted


def _as_aware(dt: datetime, tz_name: str) -> datetime:
    """naive면 로컬 TZ로 간주, aware면 그대로."""
    tz = ZoneInfo(tz_name)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt


def _utc_time_in_peak(utc_t: time) -> Optional[tuple[time, time]]:
    for start, end in PEAK_WINDOWS_UTC:
        if start <= utc_t < end:
            return start, end
    return None


def is_peak(dt: datetime, tz_name: str = DEFAULT_TZ) -> bool:
    """주어진 시각이 DeepSeek 피크인지 여부."""
    aware = _as_aware(dt, tz_name)
    utc_t = aware.astimezone(timezone.utc).time().replace(microsecond=0)
    return _utc_time_in_peak(utc_t) is not None


def next_valley_datetime(dt: datetime, tz_name: str = DEFAULT_TZ) -> datetime:
    """
    피크면 피크 종료 시각(같은 분·초)으로 스냅.
    비피크면 그대로 반환.
    """
    return adjust_away_from_peak(dt, tz_name=tz_name).adjusted


def adjust_away_from_peak(
    dt: datetime,
    tz_name: str = DEFAULT_TZ,
) -> PeakAdjustment:
    """
    예약 시각이 피크면 피크 종료 + 동일 분·초로 자동 조정.

    오전 피크(KST 10–13) → 13:MM
    오후 피크(KST 15–19) → 19:MM
    """
    aware = _as_aware(dt, tz_name)
    utc_dt = aware.astimezone(timezone.utc)
    window = _utc_time_in_peak(utc_dt.time().replace(microsecond=0))

    if window is None:
        return PeakAdjustment(original=aware, adjusted=aware, was_peak=False)

    _start, end = window
    # 같은 UTC 날짜의 피크 종료 시각 + 원래 분/초
    adjusted_utc = datetime(
        year=utc_dt.year,
        month=utc_dt.month,
        day=utc_dt.day,
        hour=end.hour,
        minute=utc_dt.minute,
        second=utc_dt.second,
        microsecond=utc_dt.microsecond,
        tzinfo=timezone.utc,
    )

    # end가 자정(00:00)인 경우 대비 (현재 스펙에는 없음)
    if end == time(0, 0):
        adjusted_utc += timedelta(days=1)

    adjusted_local = adjusted_utc.astimezone(ZoneInfo(tz_name))
    label = f"UTC { _start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
    return PeakAdjustment(
        original=aware,
        adjusted=adjusted_local,
        was_peak=True,
        peak_label=label,
    )


def seconds_until_valley(dt: Optional[datetime] = None, tz_name: str = DEFAULT_TZ) -> int:
    """지금(또는 dt)이 피크면 밸리까지 남은 초. 아니면 0."""
    now = dt or datetime.now(ZoneInfo(tz_name))
    adj = adjust_away_from_peak(now, tz_name=tz_name)
    if not adj.was_peak:
        return 0
    delta = adj.adjusted - adj.original
    return max(0, int(delta.total_seconds()))


def wait_or_skip_if_peak(
    *,
    tz_name: str = DEFAULT_TZ,
    mode: str = "skip",
    max_wait_seconds: int = 0,
    logger=None,
) -> bool:
    """
    피크일 때 처리 여부 결정.

    Returns
    -------
    bool
        True  → API 호출 진행 가능
        False → 이번 실행은 건너뜀
    """
    now = datetime.now(ZoneInfo(tz_name))
    adj = adjust_away_from_peak(now, tz_name=tz_name)
    if not adj.was_peak:
        return True

    wait_sec = seconds_until_valley(now, tz_name=tz_name)
    msg = (
        f"DeepSeek 피크타임입니다 ({adj.peak_label}). "
        f"현재 {adj.original.strftime('%H:%M:%S')} → "
        f"밸리 {adj.adjusted.strftime('%H:%M:%S')} "
        f"(약 {wait_sec // 60}분 후)"
    )

    if mode == "wait" and wait_sec <= max_wait_seconds:
        if logger:
            logger.info("%s — %s초 대기 후 재개합니다.", msg, wait_sec)
        import time as _time
        _time.sleep(wait_sec)
        return True

    if logger:
        logger.warning("%s — 이번 실행을 건너뜁니다. (mode=%s)", msg, mode)
    return False


def format_wp_datetime(dt: datetime, tz_name: str = DEFAULT_TZ) -> str:
    """워드프레스 REST API용 로컬 datetime 문자열."""
    aware = _as_aware(dt, tz_name).astimezone(ZoneInfo(tz_name))
    return aware.strftime("%Y-%m-%dT%H:%M:%S")


def describe_peaks(tz_name: str = DEFAULT_TZ, on_date: Optional[date] = None) -> str:
    """사람이 읽기 쉬운 피크 안내문."""
    day = on_date or datetime.now(ZoneInfo(tz_name)).date()
    lines = [
        "DeepSeek 피크타임 (2배 요금)",
        f"기준 TZ: {tz_name}",
        "UTC: 01:00–04:00, 06:00–10:00",
    ]
    for start, end in PEAK_WINDOWS_UTC:
        local_start = datetime(
            day.year, day.month, day.day, start.hour, start.minute, tzinfo=timezone.utc
        ).astimezone(ZoneInfo(tz_name))
        local_end = datetime(
            day.year, day.month, day.day, end.hour, end.minute, tzinfo=timezone.utc
        ).astimezone(ZoneInfo(tz_name))
        lines.append(
            f"  {local_start.strftime('%H:%M')}–{local_end.strftime('%H:%M')} "
            f"→ 예약 시 {local_end.strftime('%H')}:MM 으로 스냅"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    tz = DEFAULT_TZ
    print(describe_peaks(tz))
    print()
    samples = [
        "2026-07-14 09:30",
        "2026-07-14 10:30",
        "2026-07-14 11:00",
        "2026-07-14 12:45",
        "2026-07-14 13:00",
        "2026-07-14 14:30",
        "2026-07-14 15:30",
        "2026-07-14 16:30",
        "2026-07-14 18:59",
        "2026-07-14 19:00",
        "2026-07-14 20:15",
    ]
    for s in samples:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
        adj = adjust_away_from_peak(dt, tz)
        mark = "ADJUST" if adj.changed else "ok    "
        print(
            f"{mark}  {adj.original.strftime('%H:%M')} → {adj.adjusted.strftime('%H:%M')}"
            + (f"  ({adj.peak_label})" if adj.was_peak else "")
        )
