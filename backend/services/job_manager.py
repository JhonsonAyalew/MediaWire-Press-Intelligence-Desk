"""
services/job_manager.py — runs scrape jobs on background threads and
streams progress/log lines into the jobs table so the frontend can poll them.
"""
import threading
import traceback

import db
from scrapers import SITES


def start_job(site_key, category_url, max_pages=1, max_threads=8):
    if site_key not in SITES:
        raise ValueError(f"Unknown site: {site_key}")

    job_id = db.create_job(site_key, category_url)

    thread = threading.Thread(
        target=_run_job, args=(job_id, site_key, category_url, max_pages, max_threads),
        daemon=True,
    )
    thread.start()
    return job_id


def _run_job(job_id, site_key, category_url, max_pages, max_threads):
    site = SITES[site_key]
    db.update_job(job_id, status="running")
    db.append_job_log(job_id, f"Starting {site['label']} scrape job", "info")

    def log_callback(msg, level="info"):
        db.append_job_log(job_id, msg, level)

    try:
        results = site["module"].run(
            category_url, max_pages=max_pages, max_threads=max_threads,
            log_callback=log_callback,
        )
        for r in results:
            r["outlet"] = site["label"]
        inserted = db.upsert_authors(results)
        db.update_job(
            job_id, status="completed", progress=100, found_count=inserted,
            finished_at=db.now(),
        )
        db.append_job_log(job_id, f"Done — {inserted} authors saved", "success")
    except Exception as e:
        db.append_job_log(job_id, f"Job failed: {e}", "error")
        db.append_job_log(job_id, traceback.format_exc()[-800:], "debug")
        db.update_job(job_id, status="failed", finished_at=db.now())
