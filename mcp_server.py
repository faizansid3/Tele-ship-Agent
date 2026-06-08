"""
Internship MCP server (Layer 5 interface to Hermes).

Exposes the internship system as MCP tools. Hermes (qwen3-coder-next) handles
all natural-language understanding on Telegram and calls these tools; our code
only does structured queries and returns clean data. No NL parsing here.

Register with Hermes:
    hermes mcp add internship --command python --args E:\\Hermes\\internship-agent\\mcp_server.py
    hermes tools enable internship
"""

import time

from mcp.server.fastmcp import FastMCP

import db
import profile as profile_mod

mcp = FastMCP("internship")


def _fmt(jobs: list[dict]) -> list[dict]:
    """Trim job rows to the fields worth sending to the agent."""
    return [
        {
            "id": j["id"],
            "score": j["score"],
            "company": j["company"],
            "role": j["role"],
            "location": j["location"],
            "category": j["category"],
            "is_internship": j["is_internship"],
            "summary": j["summary"],
            "link": j["link"],
            "applied": j["applied"],
            "reasons": j["score_reasons"],
        }
        for j in jobs
    ]


@mcp.tool()
def get_today_jobs(min_score: int = 40, limit: int = 3) -> dict:
    """Return jobs collected in the last 24 hours, best matches first.

    Shows the top 3 by default to keep replies concise; pass a larger `limit`
    (e.g. when the user asks to "show more") to return more.
    """
    since = time.time() - 86400
    jobs = db.query_jobs(since_ts=since, min_score=min_score, limit=limit)
    return {"count": len(jobs), "jobs": _fmt(jobs)}


@mcp.tool()
def search_jobs(
    text: str = "",
    category: str = "",
    min_score: int = 0,
    internships_only: bool = False,
    limit: int = 20,
) -> dict:
    """Search stored jobs.

    text: keyword across company/role/full text (e.g. 'nvidia', 'remote').
    category: one of sde, backend, frontend, fullstack, ai-ml, genai, devops, data, other.
    internships_only: restrict to internship roles.
    """
    jobs = db.query_jobs(
        text=text or None,
        category=category or None,
        min_score=min_score,
        is_internship=True if internships_only else None,
        limit=limit,
    )
    return {"count": len(jobs), "jobs": _fmt(jobs)}


@mcp.tool()
def get_job(job_id: int) -> dict:
    """Get the full details (including original text) of one job by id."""
    job = db.get_job(job_id)
    if not job:
        return {"error": f"No job with id {job_id}"}
    return job


@mcp.tool()
def mark_applied(job_id: int) -> dict:
    """Mark a job as applied to."""
    ok = db.set_flag(job_id, "applied", True)
    return {"ok": ok, "job_id": job_id}


@mcp.tool()
def get_profile() -> dict:
    """Get the user's current internship preferences profile."""
    return db.get_profile()


@mcp.tool()
def update_profile(
    add_interests: list[str] = [],
    remove_interests: list[str] = [],
    reject_terms: list[str] = [],
    graduation_year: int = 0,
) -> dict:
    """Update the user's preferences.

    Use to add/remove interest areas (e.g. add 'devops', remove 'frontend'),
    add reject terms, or set the graduation year. Returns the updated profile.
    """
    if add_interests:
        profile_mod.add_interests(*add_interests)
    if remove_interests:
        profile_mod.remove_interests(*remove_interests)
    if reject_terms:
        profile_mod.add_reject(*reject_terms)
    if graduation_year:
        profile_mod.set_graduation_year(graduation_year)
    return db.get_profile()


@mcp.tool()
def list_sources() -> dict:
    """List the Telegram channels currently being monitored."""
    return {"sources": db.list_sources(enabled_only=False)}


@mcp.tool()
def stats() -> dict:
    """Summary counts: total jobs, applied, and last-24h."""
    return db.stats()


if __name__ == "__main__":
    db.init_db()
    mcp.run()
