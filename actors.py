"""Actor extraction and normalization utilities."""

import re

ACTOR_PATTERNS = {
    "us": r"\b(united states|u\.s\.|u\.s|us|america|washington|pentagon|white house)\b",
    "russia": r"\b(russia|russian|kremlin|moscow)\b",
    "china": r"\b(china|chinese|beijing)\b",
    "india": r"\b(india|indian|new delhi)\b",
    "pakistan": r"\b(pakistan|pakistani|islamabad)\b",
    "iran": r"\b(iran|iranian|tehran)\b",
    "israel": r"\b(israel|israeli|jerusalem)\b",
    "nk": r"\b(north korea|dprk|pyongyang)\b",
    "sk": r"\b(south korea|seoul|republic of korea)\b",
    "japan": r"\b(japan|japanese|tokyo)\b",
    "ukraine": r"\b(ukraine|ukrainian|kyiv|kiev)\b",
    "taiwan": r"\b(taiwan|taipei)\b",
}


CONFLICT_SIGNAL_PATTERN = re.compile(
    r"\b("
    r"strike|attack|bomb|missile|drone|killed|destroyed|"
    r"military|troops|forces|exercise|drill|sanction|"
    r"ceasefire|talks|negotiation|truce|nuclear|war"
    r")\b",
    flags=re.IGNORECASE,
)


def has_conflict_signal(text):
    return bool(CONFLICT_SIGNAL_PATTERN.search((text or "").lower()))


def extract_actors(text):
    text = (text or "").lower()
    found = set()

    for actor, pattern in ACTOR_PATTERNS.items():
        if re.search(pattern, text):
            found.add(actor)

    return sorted(found)
