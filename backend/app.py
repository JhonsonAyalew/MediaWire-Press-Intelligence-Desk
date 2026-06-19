"""
app.py — MediaWire Flask API.

Run:
    pip install -r requirements.txt
    cp .env.example .env   # add your ANTHROPIC_API_KEY
    python app.py

Serves on http://localhost:5050
"""
import os
import csv
import io
import glob

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

import db
from scrapers import SITES
from services import job_manager, ai_service

db.init_db()

app = Flask(__name__)
CORS(app)


def ok(data=None, **extra):
    payload = {"success": True}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return jsonify(payload)


def err(message, status=400):
    return jsonify({"success": False, "error": message}), status


# ---------------- SITES / SCRAPER ----------------

@app.route("/api/sites")
def api_sites():
    return ok([{"key": k, "label": v["label"], "default_url": v["default_url"]} for k, v in SITES.items()])


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    body = request.get_json(force=True) or {}
    site = body.get("site")
    category_url = body.get("category_url") or SITES.get(site, {}).get("default_url")
    max_pages = int(body.get("max_pages", 1))
    max_threads = int(body.get("max_threads", 8))

    if site not in SITES:
        return err(f"Unknown site '{site}'. Valid: {list(SITES.keys())}")

    try:
        job_id = job_manager.start_job(site, category_url, max_pages, max_threads)
    except Exception as e:
        return err(str(e), 500)

    return ok({"job_id": job_id})


@app.route("/api/jobs")
def api_jobs():
    return ok(db.list_jobs(limit=int(request.args.get("limit", 30))))


@app.route("/api/jobs/<int:job_id>")
def api_job_detail(job_id):
    job = db.get_job(job_id)
    if not job:
        return err("Job not found", 404)
    return ok(job)


# ---------------- AUTHORS ----------------

@app.route("/api/authors")
def api_authors():
    search = request.args.get("search", "")
    outlet = request.args.get("outlet", "")
    has_email_raw = request.args.get("has_email")
    has_email = None
    if has_email_raw in ("true", "1"):
        has_email = True
    elif has_email_raw in ("false", "0"):
        has_email = False
    sort = request.args.get("sort", "scraped_at")
    direction = request.args.get("direction", "desc")
    limit = int(request.args.get("limit", 200))
    offset = int(request.args.get("offset", 0))

    rows = db.list_authors(search, outlet, has_email, sort, direction, limit, offset)
    total = db.count_authors(search, outlet, has_email)
    return ok(rows, total=total)


@app.route("/api/authors/<int:author_id>")
def api_author_detail(author_id):
    author = db.get_author(author_id)
    if not author:
        return err("Author not found", 404)
    author["drafts"] = db.list_drafts_for_author(author_id)
    return ok(author)


@app.route("/api/authors/export")
def api_authors_export():
    rows = db.list_authors(
        search=request.args.get("search", ""),
        outlet=request.args.get("outlet", ""),
        limit=100000,
    )
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    mem = io.BytesIO(buf.getvalue().encode("utf-8"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="mediawire_authors.csv")


@app.route("/api/import-existing", methods=["POST"])
def api_import_existing():
    """Convenience endpoint: import any enhanced_authors_*.csv files already
    produced by the original desktop scrapers, if present on disk."""
    body = request.get_json(force=True) or {}
    search_dir = body.get("dir", "")
    pattern = os.path.join(search_dir, "**", "enhanced_authors_*.csv")
    files = glob.glob(pattern, recursive=True)
    imported = 0
    for path in files:
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = []
                for row in reader:
                    rows.append({
                        "name": row.get("Author Name") or row.get("Author") or "Unknown",
                        "outlet": row.get("Publication Name") or "Unknown",
                        "title": row.get("Title") or "",
                        "profile_url": row.get("Profile URL") or "",
                        "email": row.get("Email") or "",
                        "twitter": row.get("Twitter") or row.get("Twitter Handle") or "",
                        "linkedin": row.get("LinkedIn") or row.get("LinkedIn URL") or "",
                        "bio": row.get("Biography") or row.get("Role / Bio") or "",
                        "profile_image": row.get("Profile Image") or "",
                        "total_articles": int(row.get("Total Articles", 1) or 1),
                    })
                imported += db.upsert_authors(rows)
        except Exception:
            continue
    return ok({"files_found": len(files), "authors_imported": imported})


# ---------------- DASHBOARD ----------------

@app.route("/api/stats")
def api_stats():
    return ok(db.stats())


# ---------------- AI ----------------

@app.route("/api/ai/draft-email", methods=["POST"])
def api_ai_draft_email():
    body = request.get_json(force=True) or {}
    author_id = body.get("author_id")
    campaign_context = body.get("campaign_context", "")
    sender_name = body.get("sender_name", "")
    sender_org = body.get("sender_org", "")

    author = db.get_author(author_id)
    if not author:
        return err("Author not found", 404)

    try:
        draft = ai_service.draft_email(author, campaign_context, sender_name, sender_org)
    except RuntimeError as e:
        return err(str(e), 400)
    except Exception as e:
        return err(f"AI error: {e}", 500)

    db.save_draft(author_id, campaign_context, draft.get("subject", ""), draft.get("body", ""))
    return ok(draft)


@app.route("/api/ai/score", methods=["POST"])
def api_ai_score():
    body = request.get_json(force=True) or {}
    author_id = body.get("author_id")
    campaign_context = body.get("campaign_context", "")

    author = db.get_author(author_id)
    if not author:
        return err("Author not found", 404)

    try:
        result = ai_service.score_author(author, campaign_context)
    except RuntimeError as e:
        return err(str(e), 400)
    except Exception as e:
        return err(f"AI error: {e}", 500)

    db.update_author_fields(author_id, {
        "relevance_score": result.get("score"),
        "relevance_rationale": result.get("rationale", ""),
        "beat": result.get("beat", author.get("beat", "")),
        "ai_summary": result.get("summary", ""),
    })
    return ok(result)


@app.route("/api/ai/score-bulk", methods=["POST"])
def api_ai_score_bulk():
    body = request.get_json(force=True) or {}
    author_ids = body.get("author_ids", [])
    campaign_context = body.get("campaign_context", "")
    results = {}
    for author_id in author_ids:
        author = db.get_author(author_id)
        if not author:
            continue
        try:
            result = ai_service.score_author(author, campaign_context)
            db.update_author_fields(author_id, {
                "relevance_score": result.get("score"),
                "relevance_rationale": result.get("rationale", ""),
                "beat": result.get("beat", author.get("beat", "")),
                "ai_summary": result.get("summary", ""),
            })
            results[author_id] = result
        except Exception as e:
            results[author_id] = {"error": str(e)}
    return ok(results)


@app.route("/api/ai/chat", methods=["POST"])
def api_ai_chat():
    body = request.get_json(force=True) or {}
    session_id = body.get("session_id", "default")
    message = body.get("message", "")
    if not message.strip():
        return err("Message is required")
    try:
        reply = ai_service.chat(session_id, message)
    except RuntimeError as e:
        return err(str(e), 400)
    except Exception as e:
        return err(f"AI error: {e}", 500)
    return ok({"reply": reply})


@app.route("/api/health")
def api_health():
    return ok({
        "status": "ok",
        "ai_configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
