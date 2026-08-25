"""Quan ly job thu thap chay nen, dung cho web app.

Job chay trong thread rieng, cap nhat tien do sau moi nguon de giao dien co the
hoi (poll) trang thai. Ket qua giu trong bo nho, gioi han so job luu lai.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional

from .aggregate import deduplicate, filter_window, sort_arrivals, summarize
from .dates import now_vn
from .export import to_rows
from .http import Fetcher
from .ports import select_ports
from .sources import FetchContext, get_sources

MAX_JOBS = 20
MAX_LOG_LINES = 400


@dataclass
class Job:
    """Mot lan chay thu thap."""

    id: str
    params: Dict[str, Any]
    status: str = "pending"          # pending | running | done | error | cancelled
    created_at: Any = field(default_factory=now_vn)
    started_at: Any = None
    finished_at: Any = None
    total_sources: int = 0
    done_sources: int = 0
    current_source: str = ""
    logs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    results: List[Any] = field(default_factory=list)
    message: str = ""
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def log(self, text):
        self.logs.append("%s  %s" % (now_vn().strftime("%H:%M:%S"), text))
        del self.logs[:-MAX_LOG_LINES]

    @property
    def progress(self):
        if not self.total_sources:
            return 0.0
        return round(self.done_sources / self.total_sources * 100, 1)

    def summary(self):
        """Trang thai gon de tra ve cho giao dien (khong kem toan bo ket qua)."""
        return {
            "id": self.id,
            "status": self.status,
            "params": self.params,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "total_sources": self.total_sources,
            "done_sources": self.done_sources,
            "current_source": self.current_source,
            "progress": self.progress,
            "result_count": len(self.results),
            "error_count": len(self.errors),
            "stats": self.stats,
            "message": self.message,
        }


class JobStore:
    """Luu job trong bo nho, an toan da luong."""

    def __init__(self, max_jobs=MAX_JOBS):
        self._jobs: Dict[str, Job] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()
        self.max_jobs = max_jobs

    def create(self, params):
        job = Job(id=uuid.uuid4().hex[:12], params=params)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            while len(self._order) > self.max_jobs:   # don job cu nhat
                self._jobs.pop(self._order.pop(0), None)
        return job

    def get(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def list(self):
        with self._lock:
            return [self._jobs[i] for i in reversed(self._order) if i in self._jobs]

    def cancel(self, job_id):
        job = self.get(job_id)
        if job and job.status in ("pending", "running"):
            job._cancel.set()
            return True
        return False


def _make_fetcher(params):
    if params.get("demo"):
        from .demo import DemoFetcher

        return DemoFetcher()
    return Fetcher(timeout=params.get("timeout", 30), retries=params.get("retries", 2),
                   delay=params.get("delay", 0.8))


def run_job(job):
    """Chay mot job: goi lan luot cac nguon, gop trung roi loc theo cua so ETA."""
    params = job.params
    job.status = "running"
    job.started_at = now_vn()
    try:
        ports = select_ports(params.get("ports") or ["all"])
        if not ports:
            raise ValueError("Khong khop cang nao")
        sources = get_sources(params.get("sources") or ["all"], params.get("kinds") or ["all"])
        if not sources:
            raise ValueError("Khong khop nguon nao")

        start = now_vn() + timedelta(days=float(params.get("from_days", 0)))
        end = now_vn() + timedelta(days=float(params.get("days", 30)))
        job.total_sources = len(sources)
        job.log("Cua so ETA %s -> %s | %d cang | %d nguon%s" % (
            start.strftime("%d/%m %H:%M"), end.strftime("%d/%m %H:%M"),
            len(ports), len(sources), " | DEMO" if params.get("demo") else ""))

        ctx = FetchContext(window_start=start, window_end=end, ports=ports,
                           fetcher=_make_fetcher(params))
        raw = []
        for source in sources:
            if job._cancel.is_set():
                job.status = "cancelled"
                job.message = "Da huy theo yeu cau"
                job.log("Da huy")
                return job
            job.current_source = source.name
            ready, why = source.available(ctx)
            if not ready:
                job.log("bo qua %s (%s)" % (source.name, why))
                job.done_sources += 1
                continue
            before_rows, before_errors = len(raw), len(ctx.errors)
            try:
                raw.extend(source.fetch(ctx))
            except Exception as exc:   # mot nguon hong khong duoc lam hong ca job
                ctx.fail(source.name, getattr(source, "url_template", ""), exc)
            added = len(raw) - before_rows
            if added:
                job.log("%s: %d ban ghi" % (source.name, added))
            elif len(ctx.errors) > before_errors:
                job.log("%s: loi - %s" % (source.name, ctx.errors[-1].split(" | ")[-1][:80]))
            else:
                job.log("%s: khong doc duoc bang tau" % source.name)
            job.done_sources += 1

        job.current_source = ""
        merged = deduplicate(raw)
        inside = sort_arrivals(filter_window(
            merged, start, end, require_eta=not params.get("keep_no_eta")))
        job.results = inside
        job.stats = summarize(inside)
        job.stats.update({"raw_count": len(raw), "merged_count": len(merged),
                          "window_start": start.isoformat(), "window_end": end.isoformat()})
        job.errors = list(ctx.errors)
        job.log("Xong: %d tho -> %d sau gop -> %d trong cua so" %
                (len(raw), len(merged), len(inside)))
        job.status = "done"
        job.message = "%d tau trong cua so" % len(inside)
    except Exception as exc:
        job.status = "error"
        job.message = "%s: %s" % (type(exc).__name__, exc)
        job.log("LOI " + job.message)
    finally:
        job.finished_at = now_vn()
    return job


def start_job(store, params):
    """Tao job va chay nen; tra ve job de goi y lay trang thai."""
    job = store.create(params)
    thread = threading.Thread(target=run_job, args=(job,), daemon=True,
                              name="vnports-job-" + job.id)
    thread.start()
    return job


def job_rows(job, limit=None):
    """Ket qua dang bang, kem danh sach nguon da gop cho tung dong."""
    rows = to_rows(job.results if limit is None else job.results[:limit])
    for row, arrival in zip(rows, job.results):
        row["merged_sources"] = arrival.raw.get("_merged_sources", [])
        row["eta_variants"] = arrival.raw.get("_eta_variants", [])
    return rows
