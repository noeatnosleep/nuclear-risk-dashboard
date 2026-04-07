import re

ACTOR_PATTERNS = {
    "us": r"\b(united states|u\.s\.|u\.s|america|washington)\b",
    "russia": r"\brussia|russian\b",
    "china": r"\bchina|chinese\b",
    "india": r"\bindia|indian\b",
    "pakistan": r"\bpakistan\b",
    "iran": r"\biran|iranian\b",
    "israel": r"\bisrael|israeli\b",
    "nk": r"\b(north korea|dprk)\b",
    "sk": r"\b(south korea)\b",
    "japan": r"\bjapan|japanese\b",
    "ukraine": r"\bukraine|ukrainian\b",
    "taiwan": r"\btaiwan\b"
}


STATE_KEYS = [
    "us_russia",
    "us_china",
    "china_taiwan",
    "india_pakistan",
    "china_india",
    "iran_us",
    "iran_israel",
    "nk_us",
    "nk_sk",
    "nk_japan",
    "russia_ukraine"
]


def extract_actors(text):
    text = text.lower()
    found = set()

    for actor, pattern in ACTOR_PATTERNS.items():
        if re.search(pattern, text):
            found.add(actor)

    return list(found)
