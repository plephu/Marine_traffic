"""Khung chung cho moi nguon du lieu."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from ..dates import now_vn, parse_datetime
from ..http import Fetcher
from ..models import VesselArrival
from ..tables import best_table


@dataclass
class FetchContext:
    """Tham so cho mot lan thu thap."""

    window_start: datetime
    window_end: datetime
    ports: List[Dict[str, Any]]
    fetcher: Fetcher
    verbose: bool = False
    errors: List[str] = field(default_factory=list)

    def log(self, message):
        if self.verbose:
            print("  " + message, flush=True)

    def fail(self, source_name, url, exc):
        msg = "%s | %s | %s: %s" % (source_name, url, type(exc).__name__, exc)
        self.errors.append(msg)
        self.log("LOI " + msg)


class Source:
    """Giao dien chung: moi nguon tra ve danh sach VesselArrival da chuan hoa."""

    name = "base"
    kind = "unknown"          # ais | port_authority | terminal | carrier
    horizon_days = 0          # tam nhin ETA thuc te cua nguon (ngay)
    requires_key = None       # ten bien moi truong chua API key, neu can
    homepage = ""
    coverage = ""

    def available(self, ctx):
        """Nguon co du dieu kien chay khong (vd. da co API key chua)."""
        from ..http import env_key

        if self.requires_key and not env_key(self.requires_key):
            return False, "thieu bien moi truong %s" % self.requires_key
        return True, ""

    def fetch(self, ctx):  # pragma: no cover - lop con cai dat
        raise NotImplementedError

    def describe(self):
        return {
            "name": self.name,
            "kind": self.kind,
            "horizon_days": self.horizon_days,
            "requires_key": self.requires_key,
            "homepage": self.homepage,
            "coverage": self.coverage,
        }


@dataclass
class HtmlTableSource(Source):
    """Nguon HTML: tai mot hoac nhieu URL roi doc bang bang bo trich xuat chung.

    `url_template` co the chua {vf_id}, {mst_id}, {mt_id}, {unlocode}, {key},
    {d} (do lech ngay) va {date} (dd/mm/yyyy).
    """

    name: str = "html"
    kind: str = "unknown"
    url_template: str = ""
    homepage: str = ""
    coverage: str = ""
    horizon_days: int = 3
    id_field: Optional[str] = None      # truong trong danh muc cang phai co gia tri
    day_offsets: Optional[List[int]] = None   # lap {d} qua cac gia tri nay
    global_source: bool = False         # URL khong phu thuoc cang (chay 1 lan)
    port_key: Optional[str] = None      # gan cung cho nguon global
    requires_key: Optional[str] = None
    postprocess: Optional[Callable] = None

    def _urls_for_port(self, port, ctx):
        offsets = self.day_offsets or [0]
        for offset in offsets:
            if offset > (self.horizon_days or 0):
                continue
            day = now_vn().date() + timedelta(days=offset)
            yield self.url_template.format(
                vf_id=port.get("vesselfinder_id") or "",
                mst_id=port.get("myshiptracking_id") or "",
                mt_id=port.get("marinetraffic_id") or "",
                unlocode=port.get("unlocode") or "",
                key=port.get("key") or "",
                d=offset,
                date=day.strftime("%d/%m/%Y"),
                date_iso=day.strftime("%Y-%m-%d"),
            ), offset

    def fetch(self, ctx):
        results = []
        targets = [None] if self.global_source else list(ctx.ports)
        for port in targets:
            if port is not None and self.id_field and not port.get(self.id_field):
                ctx.log("bo qua %s: chua co %s" % (port.get("key"), self.id_field))
                continue
            port = port or _lookup_port(self.port_key)
            for url, offset in self._urls_for_port(port, ctx):
                try:
                    html = ctx.fetcher.get_text(url)
                except Exception as exc:
                    ctx.fail(self.name, url, exc)
                    continue
                rows = best_table(html)
                ctx.log("%s <- %d hang tu %s" % (self.name, len(rows), url))
                ref = now_vn() + timedelta(days=offset)
                for row in rows:
                    arrival = row_to_arrival(row, port, self, url, ref=ref)
                    if arrival:
                        results.append(arrival)
        if self.postprocess:
            results = self.postprocess(results)
        return results


def _lookup_port(port_key):
    """Tra ten/UNLOCODE that cua cang tu danh muc cho nguon gan cung mot cang."""
    from ..ports import load_ports

    for port in load_ports():
        if port.get("key") == port_key:
            return port
    return {"key": port_key, "name": port_key, "unlocode": None}


def _num(value):
    import re

    if value is None:
        return None
    match = re.search(r"\d[\d.,]*", str(value).replace(" ", ""))
    if not match:
        return None
    text = match.group(0).replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def row_to_arrival(row, port, source, url, ref=None):
    """Chuyen mot hang bang da chuan hoa thanh VesselArrival."""
    name = (row.get("vessel_name") or "").strip()
    if not name or len(name) < 2:
        return None
    if name.lower() in {"vessel", "ten tau", "tên tàu", "ship", "tau", "tàu"}:
        return None
    eta = parse_datetime(row.get("eta"), ref=ref)
    return VesselArrival(
        vessel_name=name,
        imo=row.get("imo"),
        mmsi=row.get("mmsi"),
        call_sign=row.get("call_sign"),
        flag=row.get("flag"),
        vessel_type=row.get("vessel_type"),
        gross_tonnage=_num(row.get("gross_tonnage")),
        dwt=_num(row.get("dwt")),
        loa=_num(row.get("loa")),
        eta=eta,
        etd=parse_datetime(row.get("etd"), ref=ref),
        port_code=port.get("unlocode"),
        port_name=port.get("name") or port.get("key"),
        berth=row.get("berth"),
        terminal=row.get("terminal"),
        from_port=row.get("from_port"),
        voyage=row.get("voyage"),
        agent=row.get("agent"),
        cargo=row.get("cargo"),
        source=source.name,
        source_kind=source.kind,
        source_url=url,
        fetched_at=now_vn(),
        raw={k: v for k, v in row.items() if not k.startswith("_")},
    )
