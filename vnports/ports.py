"""Danh muc cang bien Viet Nam va anh xa sang ID cua tung nguon du lieu."""
from __future__ import annotations

import json
from pathlib import Path

_DATA = Path(__file__).with_name("data_ports.json")


def load_ports():
    """Doc danh muc cang tu data_ports.json (nguoi dung co the sua truc tiep)."""
    data = json.loads(_DATA.read_text(encoding="utf-8"))
    return data["ports"]


def select_ports(selectors=None):
    """Loc cang theo key / UN/LOCODE / ten (khong phan biet hoa thuong).

    `selectors` rong hoac chua 'all' -> tra ve toan bo danh muc.
    """
    ports = load_ports()
    if not selectors or "all" in [s.lower() for s in selectors]:
        return ports
    wanted = {s.strip().lower() for s in selectors}
    out = []
    for port in ports:
        candidates = {
            str(port.get("key", "")).lower(),
            str(port.get("unlocode") or "").lower(),
            str(port.get("name", "")).lower(),
        }
        if candidates & wanted or any(w in str(port.get("name", "")).lower() for w in wanted):
            out.append(port)
    return out
