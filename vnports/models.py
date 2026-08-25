"""Kieu du lieu chuan cho mot luot tau du kien cap cang."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional

from .dates import VN_TZ

_NOISE = re.compile(r"[^A-Z0-9]+")


def normalize_name(name):
    """Chuan hoa ten tau de so sanh: bo dau cach, ky tu dac biet, viet hoa."""
    if not name:
        return ""
    return _NOISE.sub("", str(name).upper())


def valid_imo(imo):
    """Kiem tra so IMO 7 chu so bang thuat toan check-digit cua IMO."""
    if not imo:
        return None
    digits = re.sub(r"\D", "", str(imo))
    if len(digits) != 7:
        return None
    checksum = sum(int(d) * w for d, w in zip(digits[:6], range(7, 1, -1)))
    return digits if checksum % 10 == int(digits[6]) else None


@dataclass
class VesselArrival:
    """Mot ban ghi 'tau du kien den cang', da chuan hoa tu bat ky nguon nao."""

    vessel_name: str = ""
    imo: Optional[str] = None
    mmsi: Optional[str] = None
    call_sign: Optional[str] = None
    flag: Optional[str] = None
    vessel_type: Optional[str] = None
    gross_tonnage: Optional[float] = None
    dwt: Optional[float] = None
    loa: Optional[float] = None
    eta: Optional[datetime] = None
    etd: Optional[datetime] = None
    port_code: Optional[str] = None
    port_name: Optional[str] = None
    berth: Optional[str] = None
    terminal: Optional[str] = None
    from_port: Optional[str] = None
    voyage: Optional[str] = None
    agent: Optional[str] = None
    cargo: Optional[str] = None
    source: str = ""
    source_kind: str = ""  # ais | port_authority | terminal | carrier
    source_url: Optional[str] = None
    fetched_at: Optional[datetime] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.imo = valid_imo(self.imo) or (self.imo or None)
        if self.vessel_name:
            self.vessel_name = " ".join(str(self.vessel_name).split()).upper()

    @property
    def identity(self):
        """Khoa dinh danh tau: uu tien IMO, sau do MMSI, cuoi cung la ten."""
        if valid_imo(self.imo):
            return ("imo", valid_imo(self.imo))
        if self.mmsi and re.fullmatch(r"\d{9}", str(self.mmsi)):
            return ("mmsi", str(self.mmsi))
        return ("name", normalize_name(self.vessel_name))

    def to_row(self):
        d = asdict(self)
        d.pop("raw", None)
        for k in ("eta", "etd", "fetched_at"):
            v = d.get(k)
            if isinstance(v, datetime):
                d[k] = v.astimezone(VN_TZ).isoformat()
        return d
