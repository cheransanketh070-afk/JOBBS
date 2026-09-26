"""
Lightweight in-process background job runner.

Scraping takes several seconds to tens of seconds, so it runs on a
background thread while the browser polls /api/search/status/<job_id>.

This is intentionally simple (no Redis/Celery) so the whole app stays
deployable on a single free-tier web dyno with no paid add-ons. The
trade-off: job state lives in this process's memory, so it only works
correctly with a single worker process. If you later scale to multiple
gunicorn workers or multiple machines, replace this with a real task
queue (e.g. Celery + Redis, or RQ) — the interface below is written so
that swap only touches this one file.
"""
import threading
import time
import uuid
from typing import Callable, Dict, Optional

_jobs_lock = threading.Lock()
_jobs: Dict[str, dict] = {}

JOB_TTL_SECONDS = 60 * 30  # forget finished jobs after 30 minutes


def _cleanup_old_jobs():
    cutoff = time.time() - JOB_TTL_SECONDS
    stale = [jid for jid, j in _jobs.items() if j.get("finished_at") and j["finished_at"] < cutoff]
    for jid in stale:
        _jobs.pop(jid, None)


def start_job(target: Callable, *args, **kwargs) -> str:
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _cleanup_old_jobs()
        _jobs[job_id] = {
            "status": "running",
            "progress": 0,
            "total": kwargs.get("max_results", 0),
            "result": None,
            "error": None,
            "cancel": False,
            "finished_at": None,
        }

    def progress_cb(done, total):
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["progress"] = done
                _jobs[job_id]["total"] = total

    def cancel_check():
        with _jobs_lock:
            return _jobs.get(job_id, {}).get("cancel", False)

    def runner():
        try:
            result = target(*args, progress_cb=progress_cb, cancel_check=cancel_check, **kwargs)
            with _jobs_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = result
                _jobs[job_id]["finished_at"] = time.time()
        except Exception as exc:  # noqa: BLE001
            with _jobs_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["error"] = str(exc)
                _jobs[job_id]["finished_at"] = time.time()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def cancel_job(job_id: str):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["cancel"] = True
