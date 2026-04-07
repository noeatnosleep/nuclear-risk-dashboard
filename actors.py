import re

ACTOR_PATTERNS = {
    "us": r"\b(U\.S\.|U\.S|USA|United States|America)\b",
    "russia": r"\bRussia|Russian\b",
    "china": r"\bChina|Chinese\b",
    "india": r"\bIndia|Indian\b",
    "pakistan": r"\bPakistan\b",
    "iran": r"\bIran|Iranian\b",
    "israel": r"\bIsrael|Israeli\b",
    "north korea": r"\bNorth Korea|DPRK\b",
    "korea": r"\bSouth Korea\b",
    "japan": r"\bJapan|Japanese\b",
    "taiwan": r"\bTaiwan\b",
    "ukraine": r"\bUkraine|Ukrainian\b"
}

def extract_actors(text):
    found = set()
    for actor, pattern in ACTOR_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.add(actor)
    return list(found)
