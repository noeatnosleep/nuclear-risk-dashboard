"""Event classification and impact scoring."""

import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from actors import extract_actors, has_conflict_signal
from config import load_config
from states import ACTOR_PAIR_TO_STATE, STATE_WEIGHTS

CONFIG = load_config()
SIGNAL_WEIGHTS = CONFIG["signal_weights"]
MAX_IMPACT = float(CONFIG["max_impact"])
DECAY_HALFLIFE_HOURS = float(CONFIG["decay_halflife_hours"])
MIN_CONFIDENCE_BY_CLASS = CONFIG["min_confidence_by_class"]
FALLBACK_PAIRING_ENABLED = bool(CONFIG.get("fallback_pairing_enabled", False))
AMBIGUITY_PENALTY = float(CONFIG.get("ambiguity_penalty", 0.15))
STRONG_SIGNAL_KEYWORDS = tuple(CONFIG.get("strong_signal_keywords", []))

# Contradiction matrix: if both classes appear in one event text, apply additive penalty.
DEFAULT_CONTRADICTION_MATRIX = {
    "action:deescalation": -0.05,
    "movement:deescalation": -0.04,
    "strategic:deescalation": -0.06,
    "action:movement": -0.03,
}
CONTRADICTION_MATRIX = CONFIG.get("contradiction_matrix", DEFAULT_CONTRADICTION_MATRIX)

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

ACTION_PATTERN = re.compile(r"(strike|attack|bomb|missile|drone|killed|destroyed|raid)", re.IGNORECASE)
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


def event_text(event):
    title = event.get("title", "")
    summary = event.get("summary", "")
    return f"{title} {summary}".strip()


def matrix_penalty(components):
    present = [key for key, value in components.items() if key != "rhetoric" and value != 0]
    if len(present) < 2:
        return 0.0

    penalty = 0.0
    for i in range(len(present)):
        for j in range(i + 1, len(present)):
            a = present[i]
            b = present[j]
            key1 = f"{a}:{b}"
            key2 = f"{b}:{a}"
            penalty += float(CONTRADICTION_MATRIX.get(key1, CONTRADICTION_MATRIX.get(key2, 0.0)))
    return penalty


def score_signals(text):
    components = {
        "deescalation": SIGNAL_WEIGHTS["deescalation"] if DEESCALATION_PATTERN.search(text) else 0.0,
        "action": SIGNAL_WEIGHTS["action"] if ACTION_PATTERN.search(text) else 0.0,
        "movement": SIGNAL_WEIGHTS["movement"] if MOVEMENT_PATTERN.search(text) else 0.0,
        "strategic": SIGNAL_WEIGHTS["strategic"] if STRATEGIC_PATTERN.search(text) else 0.0,
    }

    total = sum(components.values())
    if total == 0:
        components["rhetoric"] = SIGNAL_WEIGHTS["rhetoric"]
        total = SIGNAL_WEIGHTS["rhetoric"]
    else:
        components["rhetoric"] = 0.0

    contradiction_adjustment = matrix_penalty(components)
    if contradiction_adjustment:
        total += contradiction_adjustment
        components["contradiction_adjustment"] = contradiction_adjustment

    dominant_class = max(
        ["deescalation", "action", "movement", "strategic", "rhetoric"],
        key=lambda key: abs(components.get(key, 0.0)),
    )
    return dominant_class, total, components


def build_valid_state_keys(actors):
    keys = []
    for i in range(len(actors)):
        for j in range(i + 1, len(actors)):
            pair = tuple(sorted([actors[i], actors[j]]))
            if pair in ACTOR_PAIR_TO_STATE:
                keys.append(ACTOR_PAIR_TO_STATE[pair])
    return sorted(set(keys))


def select_state_key_deterministically(candidate_state_keys):
    if not candidate_state_keys:
        return None
    return sorted(candidate_state_keys, key=lambda key: (-STATE_WEIGHTS.get(key, 0.0), key))[0]


def choose_state_key_from_actors(actors):
    if len(actors) >= 2:
        keys = build_valid_state_keys(actors)
        return select_state_key_deterministically(keys)

    if len(actors) == 1 and FALLBACK_PAIRING_ENABLED:
        actor = actors[0]
        for candidate in FALLBACK_MAP.get(actor, []):
            pair = tuple(sorted([actor, candidate]))
            if pair in ACTOR_PAIR_TO_STATE:
                return ACTOR_PAIR_TO_STATE[pair]
    return None


def compute_confidence(actors, signal_total, source_weight, text, signal_components):
    actor_score = min(0.55, 0.27 * len(actors))
    signal_score = min(0.25, abs(signal_total) / 5)
    source_score = min(0.12, max(0.0, float(source_weight) / 10.0))

    strong_keyword_bonus = 0.08 if any(keyword in text.lower() for keyword in STRONG_SIGNAL_KEYWORDS) else 0.0

    has_positive_signal = any(signal_components.get(label, 0) > 0 for label in ["action", "movement", "strategic"])
    has_negative_signal = signal_components.get("deescalation", 0) < 0
    ambiguity_penalty = AMBIGUITY_PENALTY if has_positive_signal and has_negative_signal else 0.0

    contradiction_penalty = abs(float(signal_components.get("contradiction_adjustment", 0.0))) * 0.04

    confidence = actor_score + signal_score + source_score + strong_keyword_bonus - ambiguity_penalty - contradiction_penalty
    return max(0.0, min(1.0, confidence))


def classify_event(event):
    title = event.get("title", "")
    if not title:
        return {"ok": False, "reason": "missing_title"}

    text = event_text(event)

    actors = extract_actors(text)
    if not actors:
        return {"ok": False, "reason": "no_actor"}

    if not has_conflict_signal(text):
        return {"ok": False, "reason": "no_signal"}

    state_key = choose_state_key_from_actors(actors)
    if not state_key:
        return {"ok": False, "reason": "invalid_pair"}

    event_class, signal_total, signal_components = score_signals(text)
    source_weight = float(event.get("source_weight", 1.0))
    confidence = compute_confidence(actors, signal_total, source_weight, text, signal_components)

    min_confidence = float(MIN_CONFIDENCE_BY_CLASS.get(event_class, 0.5))
    if confidence < min_confidence:
        return {"ok": False, "reason": "low_confidence"}

    age_hours = hours_since(event.get("published", ""))
    decay = time_decay(age_hours)
    signed_impact = signal_total * decay
    impact = max(-MAX_IMPACT, min(MAX_IMPACT, signed_impact))

    return {
        "ok": True,
        "state_key": state_key,
        "actors": state_key.split("_"),
        "class": event_class,
        "impact": impact,
        "age_hours": round(age_hours, 2),
        "confidence": round(confidence, 3),
        "signal_total": round(signal_total, 3),
        "signal_components": signal_components,
    }
