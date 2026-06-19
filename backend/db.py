"""
db.py — SQLite persistence layer for MediaWire.

Single-file database (data/mediawire.db). No ORM on purpose: this is a small,
auditable schema and raw SQL keeps the Flask layer thin.
"""
import sqlite3
import json
import os
import threading
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "mediawire.db")
_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            outlet TEXT NOT NULL,
            title TEXT DEFAULT '',
            profile_url TEXT DEFAULT '',
            email TEXT DEFAULT '',
            twitter TEXT DEFAULT '',
            linkedin TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            profile_image TEXT DEFAULT '',
            total_articles INTEGER DEFAULT 1,
            beat TEXT DEFAULT '',
            relevance_score INTEGER DEFAULT NULL,
            relevance_rationale TEXT DEFAULT '',
            ai_summary TEXT DEFAULT '',
            scraped_at TEXT DEFAULT '',
            UNIQUE(name, outlet)
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site TEXT NOT NULL,
            category_url TEXT NOT NULL,
            status TEXT DEFAULT 'queued',
            progress INTEGER DEFAULT 0,
            found_count INTEGER DEFAULT 0,
            log TEXT DEFAULT '[]',
            created_at TEXT DEFAULT '',
            finished_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS email_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            campaign_context TEXT DEFAULT '',
            subject TEXT DEFAULT '',
            body TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            FOREIGN KEY(author_id) REFERENCES authors(id)
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT ''
        );
        """
    )
    conn.commit()
    conn.close()


def now():
    return datetime.utcnow().isoformat()


# ---------------- AUTHORS ----------------

def upsert_authors(rows):
    """rows: list of dicts with keys matching scraper normalized output."""
    if not rows:
        return 0
    conn = get_conn()
    inserted = 0
    with _lock:
        for r in rows:
            try:
                conn.execute(
                    """
                    INSERT INTO authors (name, outlet, title, profile_url, email, twitter,
                        linkedin, bio, profile_image, total_articles, beat, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name, outlet) DO UPDATE SET
                        title=excluded.title,
                        profile_url=CASE WHEN excluded.profile_url != '' THEN excluded.profile_url ELSE authors.profile_url END,
                        email=CASE WHEN excluded.email != '' THEN excluded.email ELSE authors.email END,
                        twitter=CASE WHEN excluded.twitter != '' THEN excluded.twitter ELSE authors.twitter END,
                        linkedin=CASE WHEN excluded.linkedin != '' THEN excluded.linkedin ELSE authors.linkedin END,
                        bio=CASE WHEN excluded.bio != '' THEN excluded.bio ELSE authors.bio END,
                        profile_image=CASE WHEN excluded.profile_image != '' THEN excluded.profile_image ELSE authors.profile_image END,
                        total_articles=authors.total_articles + excluded.total_articles
                    """,
                    (
                        r.get("name", "Unknown"),
                        r.get("outlet", ""),
                        r.get("title", ""),
                        r.get("profile_url", ""),
                        r.get("email", ""),
                        r.get("twitter", ""),
                        r.get("linkedin", ""),
                        r.get("bio", ""),
                        r.get("profile_image", ""),
                        r.get("total_articles", 1),
                        r.get("beat", ""),
                        now(),
                    ),
                )
                inserted += 1
            except Exception:
                continue
        conn.commit()
    conn.close()
    return inserted


def list_authors(search="", outlet="", has_email=None, sort="scraped_at", direction="desc",
                  limit=200, offset=0):
    conn = get_conn()
    q = "SELECT * FROM authors WHERE 1=1"
    params = []
    if search:
        q += " AND (name LIKE ? OR bio LIKE ? OR beat LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    if outlet:
        q += " AND outlet = ?"
        params.append(outlet)
    if has_email is not None:
        if has_email:
            q += " AND email != ''"
        else:
            q += " AND email = ''"
    allowed_sort = {"scraped_at", "name", "outlet", "total_articles", "relevance_score"}
    if sort not in allowed_sort:
        sort = "scraped_at"
    direction = "ASC" if str(direction).lower() == "asc" else "DESC"
    q += f" ORDER BY {sort} {direction} LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_authors(search="", outlet="", has_email=None):
    conn = get_conn()
    q = "SELECT COUNT(*) as c FROM authors WHERE 1=1"
    params = []
    if search:
        q += " AND (name LIKE ? OR bio LIKE ? OR beat LIKE ?)"
        like = f"%{search}%"
        params += [like, like, like]
    if outlet:
        q += " AND outlet = ?"
        params.append(outlet)
    if has_email is not None:
        if has_email:
            q += " AND email != ''"
        else:
            q += " AND email = ''"
    row = conn.execute(q, params).fetchone()
    conn.close()
    return row["c"]


def get_author(author_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM authors WHERE id=?", (author_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_author_fields(author_id, fields: dict):
    if not fields:
        return
    conn = get_conn()
    cols = ", ".join(f"{k}=?" for k in fields)
    params = list(fields.values()) + [author_id]
    with _lock:
        conn.execute(f"UPDATE authors SET {cols} WHERE id=?", params)
        conn.commit()
    conn.close()


def stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM authors").fetchone()["c"]
    with_email = conn.execute("SELECT COUNT(*) c FROM authors WHERE email != ''").fetchone()["c"]
    with_social = conn.execute(
        "SELECT COUNT(*) c FROM authors WHERE twitter != '' OR linkedin != ''"
    ).fetchone()["c"]
    by_outlet = conn.execute(
        "SELECT outlet, COUNT(*) c FROM authors GROUP BY outlet ORDER BY c DESC"
    ).fetchall()
    by_beat = conn.execute(
        "SELECT beat, COUNT(*) c FROM authors WHERE beat != '' GROUP BY beat ORDER BY c DESC LIMIT 8"
    ).fetchall()
    scored = conn.execute(
        "SELECT relevance_score, COUNT(*) c FROM authors WHERE relevance_score IS NOT NULL GROUP BY relevance_score"
    ).fetchall()
    recent = conn.execute(
        "SELECT name, outlet, scraped_at FROM authors ORDER BY scraped_at DESC LIMIT 8"
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "with_email": with_email,
        "with_social": with_social,
        "by_outlet": [dict(r) for r in by_outlet],
        "by_beat": [dict(r) for r in by_beat],
        "scored": [dict(r) for r in scored],
        "recent": [dict(r) for r in recent],
    }


# ---------------- JOBS ----------------

def create_job(site, category_url):
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO jobs (site, category_url, status, created_at, log) VALUES (?, ?, 'queued', ?, '[]')",
        (site, category_url, now()),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def update_job(job_id, **fields):
    if not fields:
        return
    conn = get_conn()
    cols = ", ".join(f"{k}=?" for k in fields)
    params = list(fields.values()) + [job_id]
    with _lock:
        conn.execute(f"UPDATE jobs SET {cols} WHERE id=?", params)
        conn.commit()
    conn.close()


def append_job_log(job_id, message, level="info"):
    conn = get_conn()
    row = conn.execute("SELECT log FROM jobs WHERE id=?", (job_id,)).fetchone()
    log = json.loads(row["log"]) if row and row["log"] else []
    log.append({"t": now(), "level": level, "msg": message})
    log = log[-300:]
    with _lock:
        conn.execute("UPDATE jobs SET log=? WHERE id=?", (json.dumps(log), job_id))
        conn.commit()
    conn.close()


def get_job(job_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["log"] = json.loads(d["log"]) if d["log"] else []
    return d


def list_jobs(limit=30):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, site, category_url, status, progress, found_count, created_at, finished_at "
        "FROM jobs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- CHAT ----------------

def add_chat_message(session_id, role, content):
    conn = get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now()),
        )
        conn.commit()
    conn.close()


def get_chat_history(session_id, limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows][::-1]


# ---------------- EMAIL DRAFTS ----------------

def save_draft(author_id, campaign_context, subject, body):
    conn = get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO email_drafts (author_id, campaign_context, subject, body, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (author_id, campaign_context, subject, body, now()),
        )
        conn.commit()
    draft_id = cur.lastrowid
    conn.close()
    return draft_id


def list_drafts_for_author(author_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM email_drafts WHERE author_id=? ORDER BY id DESC", (author_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
