import feedparser
import datetime
import json
import math
import re
import os
from collections import defaultdict
from urllib.parse import urlparse

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1004/rss.xml"
]

SOURCE_WEIGHTS = {
    "bbc.co.uk": 1.0,
    "bbc.com": 1.0,
    "npr.org": 0.9,
    "reuters.com": 1.1,
    "apnews.com": 1.1
}

DEFAULT_SOURCE_WEIGHT = 0.75

KEYWORDS = {
    "missile": 4,
    "attack": 3,
    "strike": 3,
    "bomb": 4,
    "drone": 2,
    "war": 2,
    "conflict": 2,
    "clash": 2,
    "tension": 2,
    "crisis": 3,
    "threat": 3,
    "deploy": 3,
    "military": 2,
    "exercise": 1,
    "nuclear": 10
}

ACTION_WORDS = {
    "launch","strike","attack","deploy","threat",
    "warn","escalate","mobilize","bomb"
}

BLACKLIST = {
    "war crime","charged","court","trial",
    "alleged","history","affected by war"
}

ACTORS = {
    "iran": "middle_east",
    "israel": "middle_east",
    "gaza": "middle_east",
    "lebanon": "middle_east",
    "us": "global",
    "russia": "europe",
    "ukraine": "europe",
    "china": "asia",
    "taiwan": "asia",
    "india": "asia",
    "pakistan": "asia",
    "north korea": "asia"
}

REGION_BASELINE = {
    "middle_east": 2.5,
    "europe": 2.0,
    "asia": 1.5,
    "global": 1.0
}

HISTORY_FILE = "history.json"
DECAY = 0.85

def get_source(link):
    try:
        return urlparse(link).netloc.replace("www.", "")
    except:
        return "unknown"

def get_source_weight(link):
    try:
        domain = urlparse(link).netloc.lower()
        for k in SOURCE_WEIGHTS:
            if k in domain:
                return SOURCE_WEIGHTS[k]
    except:
        pass
    return DEFAULT_SOURCE_WEIGHT

def normalize(word):
    return word[:-1] if word.endswith("s") else word

def tokenize(text):
    return [normalize(w) for w in re.findall(r"\b[a-z]+\b", text.lower())]

def important_tokens(tokens):
    return {t for t in tokens if t in KEYWORDS or t in ACTORS}

def is_duplicate(a, b):
    return len(important_tokens(tokenize(a)) & important_tokens(tokenize(b))) >= 2

def dedupe(headlines):
    unique = []
    for h, age, link in headlines:
        if not any(is_duplicate(h, u[0]) for u in unique):
            unique.append((h, age, link))
    return unique

def fetch_headlines():
    headlines = []
    now = datetime.datetime.utcnow()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except:
            continue

        for entry in getattr(feed, "entries", [])[:30]:
            try:
                title = entry.title
                link = getattr(entry, "link", None)
            except:
                continue

            try:
                published = entry.get("published_parsed")
                if published:
                    dt = datetime.datetime(*published[:6])
                    age_hours = (now - dt).total_seconds() / 3600
                else:
                    age_hours = 6
            except:
                age_hours = 6

            headlines.append((title, age_hours, link))

    return dedupe(headlines)

def time_weight(hours):
    return math.exp(-hours / 24)

def is_blacklisted(text):
    return any(b in text.lower() for b in BLACKLIST)

def has_proximity(tokens):
    for i, t in enumerate(tokens):
        if t in KEYWORDS:
            window = tokens[max(0, i-3):i+4]
            if any(w in ACTION_WORDS for w in window):
                return True
    return False

def extract_actors(tokens):
    return sorted({t for t in tokens if t in ACTORS})

def action_multiplier(matches):
    if "nuclear" in matches:
        return 2.5
    if any(m in ["missile","strike","bomb","attack"] for m in matches):
        return 1.6
    if any(m in ["deploy","mobilize"] for m in matches):
        return 1.2
    if any(m in ["threat","warn"] for m in matches):
        return 0.4
    return 1.0

def score_headline(text, age_hours, link):
    if is_blacklisted(text):
        return 0, [], [], None

    tokens = tokenize(text)
    matches = [t for t in tokens if t in KEYWORDS]

    if not matches or not has_proximity(tokens):
        return 0, [], [], None

    actors = extract_actors(tokens)
    if not actors:
        return 0, [], [], None

    regions = sorted({ACTORS[a] for a in actors})

    base = sum(KEYWORDS[m] for m in matches)
    weighted = base * time_weight(age_hours) * action_multiplier(matches)

    return weighted * get_source_weight(link), matches, actors, regions

def group_events(scored):
    groups = defaultdict(list)
    for score, text, matches, actors, regions, link, source in scored:
        key = tuple(sorted(set(matches + actors)))
        groups[key].append((score, source))
    return groups

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_history(data):
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f)

def apply_persistence(groups, history):
    new_history = {}
    total = 0

    for key, entries in groups.items():
        scores = [e[0] for e in entries]
        sources = set(e[1] for e in entries)

        base = sum(scores)
        confirmation = 1 + (len(sources) - 1) * 0.5
        current = base * confirmation

        prev = history.get(str(key), 0)
        combined = current + prev * DECAY

        new_history[str(key)] = combined
        total += combined

    return total, new_history

def compute_regions(scored):
    regions = set()
    for _, _, _, _, r, _, _ in scored:
        for x in r:
            regions.add(x)
    return regions

def main():
    headlines = fetch_headlines()
    scored = []

    for text, age, link in headlines:
        score, matches, actors, regions = score_headline(text, age, link)
        if score > 0:
            source = get_source(link)
            scored.append((score, text, matches, actors, regions, link, source))

    history = load_history()
    groups = group_events(scored)
    total_score, new_history = apply_persistence(groups, history)
    save_history(new_history)

    regions = compute_regions(scored)
    baseline = sum(REGION_BASELINE.get(r, 1.0) for r in regions)
    total_score += baseline

    region_count = max(len(regions), 1)
    normalized = total_score / region_count

    if normalized < 5:
        prob = 0.01 + (normalized / 5) * 0.05
    elif normalized < 20:
        prob = 0.06 + (normalized - 5) * 0.012
    else:
        prob = 1 / (1 + math.exp(-0.12 * (normalized - 25)))

    prob = min(prob, 0.95)

    top = sorted(scored, reverse=True)[:5]

    data = {
        "last_updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "score": round(total_score, 2),
        "normalized_score": round(normalized, 2),
        "probability": round(prob * 100, 2),
        "top_drivers": [
            {
                "title": t[1],
                "actors": t[3],
                "matches": t[2],
                "source": t[6],
                "link": t[5]
            } for t in top
        ],
        "debug": {
            "headline_count": len(headlines),
            "scored_count": len(scored),
            "unique_regions": len(regions)
        }
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
