# actors.py

# Canonical nuclear-relevant actor names
ACTORS = {
    "us": ["united states", "u.s.", "u.s", "america", "american"],
    "russia": ["russia", "russian"],
    "china": ["china", "chinese"],
    "india": ["india", "indian"],
    "pakistan": ["pakistan"],
    "iran": ["iran", "iranian"],
    "israel": ["israel", "israeli"],
    "nk": ["north korea", "dprk"],
    "sk": ["south korea"],
    "japan": ["japan", "japanese"],
    "ukraine": ["ukraine", "ukrainian"],
    "taiwan": ["taiwan"]
}


# All valid state pairs (must match states.py keys)
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

    for actor, keywords in ACTORS.items():
        for k in keywords:
            if k in text:
                found.add(actor)

    return list(found)
