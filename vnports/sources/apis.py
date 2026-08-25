"""Cac nguon API thuong mai: MarineTraffic, VesselFinder, Datalastic, AISStream.

Deu can API key rieng; khong co key thi nguon tu dong bi bo qua (xem `available`).
Cau truc JSON tra ve co the doi theo goi dich vu, nen phan anh xa truong duoc
viet theo kieu "thu nhieu ten khoa" thay vi gan chet mot ten.
"""
from __future__ import annotations

from datetime import timedelta

from ..dates import now_vn, parse_datetime
from ..http import env_key
from ..models import VesselArrival
from .base import Source

# Cac ten khoa co the gap cho cung mot truong, xet theo thu tu uu tien.
FIELD_ALIASES = {
    "vessel_name": ("SHIPNAME", "shipname", "NAME", "name", "vessel_name", "VESSEL_NAME"),
    "imo": ("IMO", "imo", "IMO_NUMBER", "imo_number"),
    "mmsi": ("MMSI", "mmsi"),
    "call_sign": ("CALLSIGN", "callsign", "CALL_SIGN"),
    "flag": ("FLAG", "flag", "COUNTRY", "country_iso"),
    "vessel_type": ("TYPE_NAME", "SHIPTYPE", "type", "ship_type", "TYPE"),
    "eta": ("ETA", "eta", "ETA_CALC", "eta_calc", "ETA_UTC", "arrival"),
    "gross_tonnage": ("GT", "gross_tonnage", "grt"),
    "dwt": ("DWT", "dwt", "deadweight"),
    "loa": ("LENGTH", "loa", "length"),
    "from_port": ("LAST_PORT", "last_port", "from_port", "departure_port"),
    "port_name": ("PORT_NAME", "port_name", "DESTINATION", "destination"),
}


def pick(record, field):
    for key in FIELD_ALIASES.get(field, ()):  # thu lan luot cac ten khoa
        if isinstance(record, dict) and record.get(key) not in (None, ""):
            return record[key]
    return None


def records_from(payload):
    """Lay danh sach ban ghi tu nhieu kieu bao boc JSON khac nhau."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("data", "results", "vessels", "arrivals", "expectedarrivals", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                return [r for r in value if isinstance(r, dict)]
            if isinstance(value, dict):
                return records_from(value)
    return []


class JsonApiSource(Source):
    """Nguon JSON cau hinh bang URL template + bien moi truong chua key."""

    def __init__(self, name, kind, url_template, requires_key, id_field,
                 homepage="", coverage="", horizon_days=7, docs=""):
        self.name = name
        self.kind = kind
        self.url_template = url_template
        self.requires_key = requires_key
        self.id_field = id_field
        self.homepage = homepage
        self.coverage = coverage
        self.horizon_days = horizon_days
        self.docs = docs

    def fetch(self, ctx):
        key = env_key(self.requires_key)
        results = []
        for port in ctx.ports:
            if self.id_field and not port.get(self.id_field):
                ctx.log("bo qua %s: chua co %s" % (port.get("key"), self.id_field))
                continue
            url = self.url_template.format(
                key=key,
                mt_id=port.get("marinetraffic_id") or "",
                unlocode=port.get("unlocode") or "",
                vf_id=port.get("vesselfinder_id") or "",
                days=max(1, min(self.horizon_days,
                                (ctx.window_end - now_vn()).days or 1)),
            )
            try:
                payload = ctx.fetcher.get_json(url)
            except Exception as exc:
                ctx.fail(self.name, url.replace(key or "", "***"), exc)
                continue
            rows = records_from(payload)
            ctx.log("%s <- %d ban ghi cho %s" % (self.name, len(rows), port.get("key")))
            for row in rows:
                name = pick(row, "vessel_name")
                if not name:
                    continue
                results.append(VesselArrival(
                    vessel_name=str(name),
                    imo=pick(row, "imo"),
                    mmsi=pick(row, "mmsi"),
                    call_sign=pick(row, "call_sign"),
                    flag=pick(row, "flag"),
                    vessel_type=pick(row, "vessel_type"),
                    eta=parse_datetime(pick(row, "eta")),
                    port_code=port.get("unlocode"),
                    port_name=port.get("name"),
                    from_port=pick(row, "from_port"),
                    source=self.name,
                    source_kind=self.kind,
                    source_url=url.replace(key or "", "***"),
                    fetched_at=now_vn(),
                    raw=row,
                ))
        return results


def build_api_sources():
    """Cac API co endpoint 'expected arrivals' duoc cong bo cong khai."""
    return [
        JsonApiSource(
            name="marinetraffic_api",
            kind="ais",
            url_template=("https://services.marinetraffic.com/api/expectedarrivals/"
                          "v:2/{key}/portid:{mt_id}/protocol:jsono"),
            requires_key="MARINETRAFFIC_API_KEY",
            id_field="marinetraffic_id",
            homepage="https://servicedocs.marinetraffic.com/",
            coverage="Tau du kien den mot cang (AIS). Can goi API tra phi cua Kpler/MarineTraffic.",
            horizon_days=7,
            docs="https://servicedocs.marinetraffic.com/tag/Vessels-Expected-in-Port",
        ),
        JsonApiSource(
            name="vesselfinder_api",
            kind="ais",
            url_template=("https://api.vesselfinder.com/expectedarrivals"
                          "?userkey={key}&unlocode={unlocode}&format=json"),
            requires_key="VESSELFINDER_API_KEY",
            id_field="unlocode",
            homepage="https://api.vesselfinder.com/docs/expectedarrivals.html",
            coverage="Phuong thuc ExpectedArrivals: vi tri AIS + voyage cua tau du kien vao cang.",
            horizon_days=7,
            docs="https://api.vesselfinder.com/docs/expectedarrivals.html",
        ),
        JsonApiSource(
            name="datalastic_api",
            kind="ais",
            url_template=("https://api.datalastic.com/api/v0/vessel_inradius"
                          "?api-key={key}&lat={lat}&lon={lon}&radius=50"),
            requires_key="DATALASTIC_API_KEY",
            id_field="__disabled__",
            homepage="https://datalastic.com/",
            coverage=("Chua bat: Datalastic khong co endpoint 'expected arrivals' theo cang, "
                      "phai suy ra tu vessel_inradius + destination. Xem docs/SOURCES.md."),
            horizon_days=5,
            docs="https://datalastic.com/pricing/",
        ),
    ]
