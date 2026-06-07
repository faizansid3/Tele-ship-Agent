"""
Memory: user profile (Layer 4).

Thin helpers over db's profile blob so preferences can evolve over time
("add devops", "remove frontend", "I graduate in 2027"). The collector reads
the profile on every post, so changes affect scoring immediately.
"""

from db import get_profile, save_profile


def add_interests(*interests: str) -> dict:
    p = get_profile()
    existing = {i.lower() for i in p.get("interests", [])}
    for it in interests:
        it = it.strip().lower()
        if it and it not in existing:
            p.setdefault("interests", []).append(it)
            existing.add(it)
    save_profile(p)
    return p


def remove_interests(*interests: str) -> dict:
    p = get_profile()
    drop = {i.strip().lower() for i in interests}
    p["interests"] = [i for i in p.get("interests", []) if i.lower() not in drop]
    save_profile(p)
    return p


def add_reject(*terms: str) -> dict:
    p = get_profile()
    existing = {i.lower() for i in p.get("reject", [])}
    for t in terms:
        t = t.strip().lower()
        if t and t not in existing:
            p.setdefault("reject", []).append(t)
            existing.add(t)
    save_profile(p)
    return p


def set_graduation_year(year: int) -> dict:
    p = get_profile()
    p["graduation_year"] = int(year)
    save_profile(p)
    return p
