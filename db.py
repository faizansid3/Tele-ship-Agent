"""
Storage layer (Layer 2).

One SQLite database holds everything: collected jobs, the user profile, and
the list of monitored sources. All access goes through the functions here so
the schema stays in one place.

Dedup is by content_hash (sha256 of normalised text), so the same post
forwarded across channels is stored once.
"""

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash  TEXT UNIQUE,
    source        TEXT,
    company       TEXT,
    role          TEXT,
    location      TEXT,
    link          TEXT,
    full_text     TEXT,
    category      TEXT,
    is_internship INTEGER,
    grad_years    TEXT,          -- JSON list e.g. ["2027"]
    skills        TEXT,          -- JSON list
    summary       TEXT,
    score         INTEGER,
    score_reasons TEXT,          -- JSON list of strings
    posted_at     TEXT,
    collected_at  REAL,
    seen          INTEGER DEFAULT 0,
    applied       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS profile (
    id   INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT                 -- JSON blob
);

CREATE TABLE IF NOT EXISTS sources (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id  INTEGER UNIQUE,   -- Telegram channel id
    name     TEXT,
    enabled  INTEGER DEFAULT 1
);
"""

DEFAULT_PROFILE = {
    "graduation_year": 2027,
    "interests": [
        "software engineering",
        "sde internship",
        "backend",
        "full stack",
        "ai",
        "machine learning",
        "genai",
        "agentic ai",
        "startups",
    ],
    "reject": ["experienced", "sales", "data analyst"],
}


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)
        # seed profile row if missing
        row = c.execute("SELECT 1 FROM profile WHERE id = 1").fetchone()
        if not row:
            c.execute(
                "INSERT INTO profile (id, data) VALUES (1, ?)",
                (json.dumps(DEFAULT_PROFILE),),
            )


def hash_text(text: str) -> str:
    norm = " ".join((text or "").lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# ── Jobs ───────────────────────────────────────────────────────────
def job_exists(content_hash: str) -> bool:
    with _conn() as c:
        return (
            c.execute(
                "SELECT 1 FROM jobs WHERE content_hash = ?", (content_hash,)
            ).fetchone()
            is not None
        )


def save_job(job: dict) -> int | None:
    """Insert a job dict. Returns row id, or None if it was a duplicate."""
    with _conn() as c:
        try:
            cur = c.execute(
                """
                INSERT INTO jobs (
                    content_hash, source, company, role, location, link,
                    full_text, category, is_internship, grad_years, skills,
                    summary, score, score_reasons, posted_at, collected_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    job["content_hash"],
                    job.get("source"),
                    job.get("company"),
                    job.get("role"),
                    job.get("location"),
                    job.get("link"),
                    job.get("full_text"),
                    job.get("category"),
                    1 if job.get("is_internship") else 0,
                    json.dumps(job.get("grad_years") or []),
                    json.dumps(job.get("skills") or []),
                    job.get("summary"),
                    int(job.get("score") or 0),
                    json.dumps(job.get("score_reasons") or []),
                    job.get("posted_at"),
                    time.time(),
                ),
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None  # duplicate content_hash


def _row_to_job(row: sqlite3.Row) -> dict:
    d = dict(row)
    for k in ("grad_years", "skills", "score_reasons"):
        try:
            d[k] = json.loads(d[k]) if d[k] else []
        except (TypeError, json.JSONDecodeError):
            d[k] = []
    d["is_internship"] = bool(d["is_internship"])
    d["seen"] = bool(d["seen"])
    d["applied"] = bool(d["applied"])
    return d


def query_jobs(
    since_ts: float | None = None,
    text: str | None = None,
    category: str | None = None,
    min_score: int = 0,
    is_internship: bool | None = None,
    applied: bool | None = None,
    limit: int = 20,
) -> list[dict]:
    sql = "SELECT * FROM jobs WHERE score >= ?"
    args: list = [min_score]
    if since_ts is not None:
        sql += " AND collected_at >= ?"
        args.append(since_ts)
    if category:
        sql += " AND lower(category) = ?"
        args.append(category.lower())
    if is_internship is not None:
        sql += " AND is_internship = ?"
        args.append(1 if is_internship else 0)
    if applied is not None:
        sql += " AND applied = ?"
        args.append(1 if applied else 0)
    if text:
        sql += " AND (lower(full_text) LIKE ? OR lower(company) LIKE ? OR lower(role) LIKE ?)"
        like = f"%{text.lower()}%"
        args += [like, like, like]
    sql += " ORDER BY score DESC, collected_at DESC LIMIT ?"
    args.append(limit)
    with _conn() as c:
        return [_row_to_job(r) for r in c.execute(sql, args).fetchall()]


def get_job(job_id: int) -> dict | None:
    with _conn() as c:
        r = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(r) if r else None


def set_flag(job_id: int, field: str, value: bool) -> bool:
    if field not in ("seen", "applied"):
        raise ValueError(field)
    with _conn() as c:
        cur = c.execute(
            f"UPDATE jobs SET {field} = ? WHERE id = ?",
            (1 if value else 0, job_id),
        )
        return cur.rowcount > 0


def stats() -> dict:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        applied = c.execute("SELECT COUNT(*) FROM jobs WHERE applied = 1").fetchone()[0]
        day_ago = time.time() - 86400
        today = c.execute(
            "SELECT COUNT(*) FROM jobs WHERE collected_at >= ?", (day_ago,)
        ).fetchone()[0]
        return {"total_jobs": total, "applied": applied, "last_24h": today}


# ── Profile ────────────────────────────────────────────────────────
def get_profile() -> dict:
    with _conn() as c:
        row = c.execute("SELECT data FROM profile WHERE id = 1").fetchone()
        return json.loads(row["data"]) if row else dict(DEFAULT_PROFILE)


def save_profile(profile: dict):
    with _conn() as c:
        c.execute(
            "INSERT INTO profile (id, data) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (json.dumps(profile),),
        )


# ── Sources ────────────────────────────────────────────────────────
def add_source(chat_id: int, name: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO sources (chat_id, name, enabled) VALUES (?,?,1) "
            "ON CONFLICT(chat_id) DO UPDATE SET name = excluded.name, enabled = 1",
            (chat_id, name),
        )


def remove_source(chat_id: int):
    with _conn() as c:
        c.execute("UPDATE sources SET enabled = 0 WHERE chat_id = ?", (chat_id,))


def list_sources(enabled_only: bool = True) -> list[dict]:
    sql = "SELECT chat_id, name, enabled FROM sources"
    if enabled_only:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY name"
    with _conn() as c:
        return [dict(r) for r in c.execute(sql).fetchall()]


if __name__ == "__main__":
    init_db()
    print("DB initialised at", DB_PATH)
    print("Profile:", json.dumps(get_profile(), indent=2))
    print("Stats:", stats())
