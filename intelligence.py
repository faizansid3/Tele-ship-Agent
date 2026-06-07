"""
Intelligence layer (Layer 3).

Turns a raw Telegram post into structured, scored job data using Hermes
(route B). One call does extraction AND relevance scoring, so scoring always
reflects the user's current profile (passed into the prompt).

If the model decides the post is not a job at all, it returns is_job=false and
the collector skips it -- this replaces the old hardcoded keyword filter.
"""

import json

from hermes_llm import HermesError, complete_json

_PROMPT = """You are the intelligence core of a personal internship-hunting agent.
Analyse ONE message from a Telegram job channel and decide if it is a relevant
opportunity for this user, then return structured JSON.

USER PROFILE:
{profile}

Scoring guidance (0-100):
- Strong match (90-100): internship/fresher SDE, backend, full-stack, AI/ML,
  GenAI, or agentic-AI role open to the user's graduation year.
- Medium (50-89): software role that fits interests but is a partial match
  (e.g. eligibility unclear, slightly off-domain).
- Low (1-49): tangentially related (e.g. data analyst, unrelated tech).
- 0: not a job post, or explicitly excludes the user (experienced-only,
  wrong graduation year, sales, etc.).

Return ONLY a JSON object, no prose, with EXACTLY these keys:
{{
  "is_job": true/false,
  "company": "string or null",
  "role": "string or null",
  "location": "string or null (use 'Remote' if remote)",
  "link": "application URL or null",
  "is_internship": true/false,
  "grad_years": ["2027", ...],          // years eligible, [] if unknown
  "skills": ["python", ...],
  "category": "one of: sde, backend, frontend, fullstack, ai-ml, genai, devops, data, other",
  "summary": "one concise sentence",
  "score": 0-100,
  "reasons": ["short reason", ...]      // why this score, 1-3 items
}}

MESSAGE:
\"\"\"
{post}
\"\"\"
"""


def analyse(post: str, profile: dict) -> dict:
    """Return structured job data for a post. Raises HermesError on failure."""
    prompt = _PROMPT.format(
        profile=json.dumps(profile, indent=2),
        post=post.strip()[:4000],
    )
    data = complete_json(prompt)

    # Normalise / harden the model output.
    return {
        "is_job": bool(data.get("is_job")),
        "company": _clean(data.get("company")),
        "role": _clean(data.get("role")),
        "location": _clean(data.get("location")),
        "link": _clean(data.get("link")),
        "is_internship": bool(data.get("is_internship")),
        "grad_years": [str(y) for y in (data.get("grad_years") or [])],
        "skills": [str(s) for s in (data.get("skills") or [])],
        "category": (data.get("category") or "other").lower(),
        "summary": _clean(data.get("summary")) or "",
        "score": _int(data.get("score")),
        "reasons": [str(r) for r in (data.get("reasons") or [])],
    }


def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() not in ("null", "none", "n/a", "") else None


def _int(v) -> int:
    try:
        return max(0, min(100, int(float(v))))
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    from db import get_profile, init_db

    init_db()
    sample = (
        "🚀 Atlassian is hiring SDE Interns!\n"
        "Batch: 2027 | Location: Bangalore (Hybrid)\n"
        "Skills: Java, Data Structures, Spring Boot\n"
        "Apply: https://atlassian.com/careers/12345"
    )
    print("Analysing sample post via Hermes...\n")
    try:
        result = analyse(sample, get_profile())
        print(json.dumps(result, indent=2))
    except HermesError as e:
        print("FAILED:", e)
