"""Phan tich chuoi ngay/gio tu cac trang tieng Viet va tieng Anh ve thanh datetime."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:  # pragma: no cover - he thong khong co tzdata
    VN_TZ = timezone(timedelta(hours=7))

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# 25/08/2026 14:30 - 25-08-2026 14h30 - 25.08.2026
_DMY = re.compile(
    r"(?P<d>\d{1,2})[/\-.](?P<m>\d{1,2})(?:[/\-.](?P<y>\d{2,4}))?"
    r"(?:[\sTt,]+(?P<H>\d{1,2})[:hH](?P<M>\d{2}))?"
)
# 2026-08-25 14:30 - 2026/08/25T14:30:00
_YMD = re.compile(
    r"(?P<y>\d{4})[/\-.](?P<m>\d{1,2})[/\-.](?P<d>\d{1,2})"
    r"(?:[\sTt,]+(?P<H>\d{1,2}):(?P<M>\d{2}))?"
)
# Aug 25, 2026 14:30  /  25 Aug 2026 14:30  /  Aug 25 14:30
_MON_NAME = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?", re.I)
_TIME = re.compile(r"\b(?P<H>\d{1,2})[:hH](?P<M>\d{2})\b")
_YEAR = re.compile(r"\b(?P<y>(?:19|20)\d{2})\b")
_DAY = re.compile(r"\b(?P<d>\d{1,2})\b")


def _build(y, m, d, H, M, ref):
    """Ghep cac thanh phan thanh datetime co timezone Viet Nam."""
    if y is None:
        # Thieu nam: chon nam sao cho ngay gan `ref` nhat (truoc/sau khong qua ~6 thang).
        best = None
        for cand in (ref.year - 1, ref.year, ref.year + 1):
            try:
                dt = datetime(cand, m, d, H, M, tzinfo=VN_TZ)
            except ValueError:
                continue
            if best is None or abs(dt - ref) < abs(best - ref):
                best = dt
        return best
    if y < 100:
        y += 2000
    try:
        return datetime(y, m, d, H, M, tzinfo=VN_TZ)
    except ValueError:
        return None


def parse_datetime(text, ref=None):
    """Doc mot chuoi bat ky va tra ve datetime (tz Asia/Ho_Chi_Minh) hoac None.

    `ref` la moc thoi gian dung de suy ra nam khi chuoi khong co nam.
    """
    if text is None:
        return None
    if isinstance(text, datetime):
        return text if text.tzinfo else text.replace(tzinfo=VN_TZ)
    s = str(text).strip()
    if not s or s.lower() in {"-", "--", "n/a", "na", "none", "null", "unknown"}:
        return None
    ref = ref or datetime.now(VN_TZ)

    m = _YMD.search(s)
    if m:
        g = m.groupdict()
        return _build(int(g["y"]), int(g["m"]), int(g["d"]),
                      int(g["H"] or 0), int(g["M"] or 0), ref)

    m = _DMY.search(s)
    if m:
        g = m.groupdict()
        day, mon = int(g["d"]), int(g["m"])
        if mon > 12 and day <= 12:  # chuoi kieu MM/DD
            day, mon = mon, day
        if mon > 12:
            return None
        return _build(int(g["y"]) if g["y"] else None, mon, day,
                      int(g["H"] or 0), int(g["M"] or 0), ref)

    m = _MON_NAME.search(s)
    if m:
        mon = _MONTHS[m.group(1)[:3].lower()]
        rest = s[: m.start()] + " " + s[m.end() :]
        tm = _TIME.search(rest)
        if tm:
            rest = rest[: tm.start()] + " " + rest[tm.end() :]
        ym = _YEAR.search(rest)
        if ym:
            rest = rest[: ym.start()] + " " + rest[ym.end() :]
        dm = _DAY.search(rest)
        if dm:
            return _build(int(ym.group("y")) if ym else None, mon, int(dm.group("d")),
                          int(tm.group("H")) if tm else 0,
                          int(tm.group("M")) if tm else 0, ref)
    return None


def now_vn():
    return datetime.now(VN_TZ)
