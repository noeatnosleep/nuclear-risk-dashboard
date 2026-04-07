import re
import math
from datetime import datetime, timezone

from actors import extract_actors


# -----------------------------
# CONFIG
# -----------------------------

CLASS_WEIGHTS = {
    "rhetoric": 0.3,
    "movement": 0.6,
    "action": 1.0,
    "strategic": 1.4
}

MAX_IMPACT = 1.25
DECAY_HALFLIFE_HOURS = 12


# -----------------------------
# HELPERS
# -----------------------------

def hours_since(published):
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except:
        return 24  # assume old

    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 3600


def time_decay(hours):
    # exponential decay
    return math.exp(-math.log(2) * hours / DECAY_HALFLIFE_HOURS)


def classify_text(title):
    t = title.lower()

    if re.search(r"(launch|strike|attack|bomb|missile|drone)", t):
        return "action"
    if re.search(r"(deploy|movement|exercise|drill|mobilize)", t):
        return "movement"
    if re.search(r"(sanction|policy|nuclear|treaty|doctrine)", t):
        return "strategic"
    return "rhetoric"


# -----------------------------
# MAIN API (REQUIRED BY risk.py)
# -----------------------------

def classify_event(event):
    """
    Expected input:
    {
        "title": str,
        "published": ISO timestamp (optional),
        "link": str,
        "source": str
    }
    """

    title = event.get("title", "")
    if not title:
        return None

    actors = extract_actors(title)

    # need at least 2 actors for a pair
    if len(actors) < 2:
        return None

    # pick first 2 deterministically
    actors = sorted(actors)[:2]

    event_class = classify_text(title)
    weight = CLASS_WEIGHTS[event_class]

    age_hours = hours_since(event.get("published", ""))
    decay = time_decay(age_hours)

    impact = weight * decay
    impact = min(impact, MAX_IMPACT)

    return {
        "actors": actors,
        "class": event_class,
        "impact": impact
    }
