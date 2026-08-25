"""Xuat ket qua ra CSV / JSON / Markdown."""
from __future__ import annotations

import csv
import json
from pathlib import Path

COLUMNS = [
    "eta", "vessel_name", "imo", "mmsi", "flag", "vessel_type", "port_name",
    "port_code", "berth", "terminal", "from_port", "agent", "voyage",
    "gross_tonnage", "dwt", "loa", "etd", "source", "source_kind", "source_url",
    "call_sign", "cargo", "fetched_at",
]


def to_rows(arrivals):
    return [a.to_row() for a in arrivals]


def write_csv(arrivals, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in to_rows(arrivals):
            writer.writerow(row)
    return path


def write_json(arrivals, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = []
    for arrival, row in zip(arrivals, to_rows(arrivals)):
        row["merged_sources"] = arrival.raw.get("_merged_sources", [])
        payload.append(row)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def to_markdown(arrivals, limit=50):
    cols = ["eta", "vessel_name", "imo", "flag", "port_name", "berth", "source"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in to_rows(arrivals)[:limit]:
        lines.append("| " + " | ".join(str(row.get(c) or "") for c in cols) + " |")
    if len(arrivals) > limit:
        lines.append("| ... | con %d dong | | | | | |" % (len(arrivals) - limit))
    return "\n".join(lines)


def write_markdown(arrivals, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(arrivals, limit=10 ** 6), encoding="utf-8")
    return path
