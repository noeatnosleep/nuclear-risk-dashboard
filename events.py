import re
import math
from datetime import datetime, timezone

from actors import extract_actors, STATE_KEYS


# -----------------------------
# CONFIG
# -----------------------------

CLASS_WEIGHTS = {
    "rhetoric": 0.25,
    "movement": 0.6,
    "action": 1.0,
    "strategic": 1.4
}

MAX_IMPACT = 1.25
DECAY_HALFLIFE_HOURS = 12


# fallback pairing when only one actor is present
FALLBACK_MAP = {
    "us": ["china", "russia", "iran"],
    "china": ["us", "taiwan"],
    "russia": ["ukraine", "us"],
    "iran": ["us", "israel"],
    "nk": ["us", "sk"],
    "india": ["pakistan", "china"],
    "pakistan": ["india"],
    "israel": ["iran"],
    "ukraine": ["russia"],
    "taiwan": ["china"]
}


# -----------------------------
# HELPERS
# -----------------------------

def hours_since(published):
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
    except:
        return 24

    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 3600


def time_decay(hours):
    return math.exp(-math.log(2) * hours / DECAY_HALFLIFE_HOURS)


def classify_text(title):
    t = title.lower()

    if re.search(r"(strike|attack|bomb|missile|drone|killed|destroyed)", t):
        return "action"

    if re.search(r"(deploy|exercise|drill|mobilize|movement)", t):
        return "movement"

    if re.search(r"(sanction|policy|nuclear|treaty|doctrine)", t):
        return "strategic"

    return "rhetoric"


def build_valid_pairs(actors):
    pairs = []

    for i in range(len(actors)):
        for j in range(i + 1, len(actors)):
            pair = "_".join(sorted([actors[i], actors[j]]))
            if pair in STATE_KEYS:
                pairs.append(pair)

    return pairs


# -----------------------------
# MAIN
# -----------------------------

def classify_event(event):
    title = event.get("title", "")
    if not title:
        return None

    actors = extract_actors(title)

    # -----------------------------
    # CASE 1: multiple actors
    # -----------------------------
    if len(actors) >= 2:
        pairs = build_valid_pairs(actors)

        if not pairs:
            return None

        pair = pairs[0]
        actors = pair.split("_")

    # -----------------------------
    # CASE 2: single actor → fallback
    # -----------------------------
    elif len(actors) == 1:
        actor = actors[0]

        if actor not in FALLBACK_MAP:
            return None

        for candidate in FALLBACK_MAP[actor]:
            pair = "_".join(sorted([actor, candidate]))
            if pair in STATE_KEYS:
                actors = sorted([actor, candidate])
                break
        else:
            return None

    else:
        return None

    # -----------------------------
    # CLASSIFICATION
    # -----------------------------
    event_class = classify_text(title)
    weight = CLASS_WEIGHTS[event_class]

    age_hours = hours_since(event.get("published", ""))
    decay = time_decay(age_hours)

    impact = min(weight * decay, MAX_IMPACT)

    return {
        "actors": actors,
        "class": event_class,
        "impact": impact
    }
