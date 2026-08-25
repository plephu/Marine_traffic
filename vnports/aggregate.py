"""Loc theo cua so ETA va hop nhat ban ghi trung nhau giua cac nguon."""
from __future__ import annotations

from datetime import timedelta

from .models import VesselArrival, normalize_name
from .sources.catalog import SOURCE_PRIORITY

# Hai ban ghi cung tau, cung cang, ETA lech khong qua nguong nay -> coi la mot.
ETA_TOLERANCE = timedelta(hours=18)

_MERGE_FIELDS = [
    "imo", "mmsi", "call_sign", "flag", "vessel_type", "gross_tonnage", "dwt",
    "loa", "etd", "berth", "terminal", "from_port", "voyage", "agent", "cargo",
    "port_code", "port_name",
]


def in_window(arrival, start, end, require_eta=True):
    """Ban ghi co ETA nam trong [start, end] khong."""
    if arrival.eta is None:
        return not require_eta
    return start <= arrival.eta <= end


def filter_window(arrivals, start, end, require_eta=True):
    return [a for a in arrivals if in_window(a, start, end, require_eta)]


def _eta_key(arrival):
    """Khoa sap xep theo ETA, an toan voi ban ghi thieu ETA (day xuong cuoi)."""
    return arrival.eta.timestamp() if arrival.eta else float("inf")


def _priority(arrival):
    return SOURCE_PRIORITY.get(arrival.source_kind, 0)


def _merge_pair(primary, other):
    """Bo sung truong con thieu cua `primary` tu `other`; ghi lai nguon da gop."""
    for field in _MERGE_FIELDS:
        if getattr(primary, field, None) in (None, "") and getattr(other, field, None) not in (None, ""):
            setattr(primary, field, getattr(other, field))
    if primary.eta is None and other.eta is not None:
        primary.eta = other.eta
    merged = primary.raw.setdefault("_merged_sources", [])
    for name in [other.source] + list(other.raw.get("_merged_sources", [])):
        if name and name not in merged and name != primary.source:
            merged.append(name)
    if other.eta and primary.eta and other.eta != primary.eta:
        primary.raw.setdefault("_eta_variants", []).append(
            {"source": other.source, "eta": other.eta.isoformat()}
        )
    return primary


def deduplicate(arrivals):
    """Gop cac ban ghi cung tau + cung cang + ETA gan nhau thanh mot dong.

    Ban ghi tu nguon uu tien cao hon (cang vu > terminal > AIS > hang tau)
    duoc giu lam ban chinh; cac nguon khac chi bo sung truong con thieu.
    """
    ordered = sorted(arrivals, key=lambda a: (-_priority(a), _eta_key(a)))
    groups = {}
    order = []
    for arrival in ordered:
        kind, value = arrival.identity
        port = (arrival.port_code or arrival.port_name or "").lower()
        matched = None
        for key in order:
            candidate = groups[key]
            c_kind, c_value = candidate.identity
            same_ship = (kind == c_kind and value == c_value) or (
                kind == "name" and c_kind != "name"
                and normalize_name(arrival.vessel_name) == normalize_name(candidate.vessel_name)
            ) or (
                c_kind == "name" and kind != "name"
                and normalize_name(arrival.vessel_name) == normalize_name(candidate.vessel_name)
            )
            if not same_ship:
                continue
            c_port = (candidate.port_code or candidate.port_name or "").lower()
            if port and c_port and port != c_port:
                continue
            if arrival.eta and candidate.eta and abs(arrival.eta - candidate.eta) > ETA_TOLERANCE:
                continue
            matched = key
            break
        if matched is None:
            key = (kind, value, port, arrival.eta.isoformat() if arrival.eta else "")
            groups[key] = arrival
            order.append(key)
        else:
            _merge_pair(groups[matched], arrival)
    return [groups[k] for k in order]


def sort_arrivals(arrivals):
    """Sap xep theo ETA tang dan; ban ghi khong co ETA xep cuoi."""
    return sorted(arrivals, key=lambda a: (_eta_key(a), a.vessel_name))


def summarize(arrivals):
    """Thong ke nhanh: so ban ghi theo nguon va theo cang."""
    by_source, by_port, by_kind = {}, {}, {}
    for arrival in arrivals:
        by_source[arrival.source] = by_source.get(arrival.source, 0) + 1
        port = arrival.port_name or arrival.port_code or "?"
        by_port[port] = by_port.get(port, 0) + 1
        by_kind[arrival.source_kind] = by_kind.get(arrival.source_kind, 0) + 1
    return {"total": len(arrivals), "by_source": by_source,
            "by_port": by_port, "by_kind": by_kind}
