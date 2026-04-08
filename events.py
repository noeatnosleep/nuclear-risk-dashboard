"""Event classification and impact scoring."""

import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from actors import extract_actors, has_conflict_signal
from states import VALID_STATE_KEYS

CLASS_WEIGHTS = {
    "deescalation": -0.8,
    "rhetoric": 0.25,
    "movement": 0.6,
    "action": 1.0,
    "strategic": 1.4,
}

MAX_IMPACT = 1.25
DECAY_HALFLIFE_HOURS = 12

FALLBACK_MAP = {
    "us": ["china", "russia", "iran"],
    "china": ["us", "taiwan", "india"],
    "russia": ["ukraine", "us"],
    "iran": ["us", "israel"],
    "nk": ["us", "sk", "japan"],
    "india": ["pakistan", "china"],
    "pakistan": ["india"],
    "israel": ["iran"],
    "ukraine": ["russia"],
    "taiwan": ["china"],
}

ACTION_PATTERN = re.compile(r"(strike|attack|bomb|missile|drone|killed|destroyed)", re.IGNORECASE)
MOVEMENT_PATTERN = re.compile(r"(deploy|exercise|drill|mobilize|movement|troops|warship)", re.IGNORECASE)
STRATEGIC_PATTERN = re.compile(r"(sanction|policy|nuclear|treaty|doctrine|deterrence)", re.IGNORECASE)
DEESCALATION_PATTERN = re.compile(
    r"(ceasefire|truce|peace talks|negotiation|diplomatic talks|de-escalat|withdraw|withdrawal)",
    re.IGNORECASE,
)


def parse_published_datetime(published):
    if not published:
        return None

    raw = str(published).strip()
    if not raw:
        return None

    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        dt = parsedate_to_datetime(raw)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def hours_since(published):
    dt = parse_published_datetime(published)
    if dt is None:
        return 24

    now = datetime.now(timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600)


def time_decay(hours):
    return math.exp(-math.log(2) * hours / DECAY_HALFLIFE_HOURS)


def classify_text(title):
    t = title or ""

    if DEESCALATION_PATTERN.search(t):
        return "deescalation"
    if ACTION_PATTERN.search(t):
        return "action"
    if MOVEMENT_PATTERN.search(t):
        return "movement"
    if STRATEGIC_PATTERN.search(t):
        return "strategic"
    return "rhetoric"


def build_valid_pairs(actors):
    pairs = []
    for i in range(len(actors)):
        for j in range(i + 1, len(actors)):
            pair = "_".join(sorted([actors[i], actors[j]]))
            if pair in VALID_STATE_KEYS:
                pairs.append(pair)
    return pairs


def classify_event(event):
    title = event.get("title", "")
    if not title:
        return None

    actors = extract_actors(title)

    # Lower false positives: require conflict signal when actors detected.
    if actors and not has_conflict_signal(title):
        return None

    if len(actors) >= 2:
        pairs = build_valid_pairs(actors)
        if not pairs:
            return None
        pair = pairs[0]
        actors = pair.split("_")
    elif len(actors) == 1:
        actor = actors[0]
        if actor not in FALLBACK_MAP:
            return None
        selected_pair = None
        for candidate in FALLBACK_MAP[actor]:
            pair = "_".join(sorted([actor, candidate]))
            if pair in VALID_STATE_KEYS:
                selected_pair = pair
                break
        if not selected_pair:
            return None
        actors = selected_pair.split("_")
    else:
        return None

    event_class = classify_text(title)
    weight = CLASS_WEIGHTS[event_class]

    age_hours = hours_since(event.get("published", ""))
    decay = time_decay(age_hours)

    signed_impact = weight * decay
    impact = max(-MAX_IMPACT, min(MAX_IMPACT, signed_impact))

    return {
        "actors": actors,
        "class": event_class,
        "impact": impact,
        "age_hours": round(age_hours, 2),
    }
