"""Web app: chay job thu thap va hien thi ket qua tren trinh duyet.

Chay:  python -m webapp.server            (mac dinh cong 8000)
       python -m webapp.server --demo     (du lieu mau, khong goi mang)
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vnports.export import COLUMNS
from vnports.jobs import JobStore, job_rows, start_job
from vnports.ports import load_ports
from vnports.sources import get_sources

STATIC_DIR = Path(__file__).parent / "static"
DEMO_MODE = os.environ.get("VNPORTS_DEMO", "") == "1"

app = FastAPI(title="vnports", description="Tau du kien cap cang Viet Nam")
store = JobStore()


class JobRequest(BaseModel):
    """Tham so mot lan chay, khop voi cac tuy chon cua CLI."""

    ports: list[str] = Field(default_factory=lambda: ["all"])
    sources: list[str] = Field(default_factory=lambda: ["all"])
    kinds: list[str] = Field(default_factory=lambda: ["all"])
    days: float = 30
    from_days: float = 0
    keep_no_eta: bool = False
    demo: bool | None = None


@app.get("/api/config")
def get_config():
    """Danh muc cang + nguon de giao dien dung dung form loc."""
    return {
        "demo_default": DEMO_MODE,
        "ports": load_ports(),
        "sources": [dict(source.describe(),
                         ready=source.available(None)[0],
                         reason=source.available(None)[1])
                    for source in get_sources()],
    }


@app.post("/api/jobs")
def create_job(request: JobRequest):
    params = request.model_dump()
    if params.get("demo") is None:
        params["demo"] = DEMO_MODE
    if params["days"] <= params["from_days"]:
        raise HTTPException(400, "Gioi han tren phai lon hon gioi han duoi")
    if not 0 <= params["days"] <= 365:
        raise HTTPException(400, "So ngay phai trong khoang 0-365")
    job = start_job(store, params)
    return job.summary()


@app.get("/api/jobs")
def list_jobs():
    return [job.summary() for job in store.list()]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, logs: int = Query(40, ge=0, le=400)):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Khong tim thay job")
    payload = job.summary()
    payload["logs"] = job.logs[-logs:] if logs else []
    payload["errors"] = job.errors[:20]
    return payload


@app.get("/api/jobs/{job_id}/results")
def get_results(job_id: str, limit: int = Query(2000, ge=1, le=20000)):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Khong tim thay job")
    return {"count": len(job.results), "rows": job_rows(job, limit=limit)}


@app.get("/api/jobs/{job_id}/results.csv")
def download_csv(job_id: str):
    job = store.get(job_id)
    if not job:
        raise HTTPException(404, "Khong tim thay job")
    buffer = io.StringIO()
    buffer.write("﻿")  # BOM de Excel doc dung tieng Viet
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in job_rows(job):
        writer.writerow(row)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tau-cap-cang-%s.csv"' % job_id})


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    if not store.get(job_id):
        raise HTTPException(404, "Khong tim thay job")
    return {"cancelled": store.cancel(job_id)}


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/health")
def health():
    return JSONResponse({"status": "ok", "demo_default": DEMO_MODE})


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Web app vnports")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--demo", action="store_true",
                        help="Dung du lieu mau, khong goi mang (de thu giao dien)")
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)
    if args.demo:
        os.environ["VNPORTS_DEMO"] = "1"
        global DEMO_MODE
        DEMO_MODE = True
    import uvicorn

    print("Mo http://%s:%d%s" % (args.host, args.port, "  (CHE DO DEMO)" if args.demo else ""))
    uvicorn.run("webapp.server:app" if args.reload else app,
                host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
