import feedparser
import datetime
import json
import math
import re
from collections import defaultdict

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1004/rss.xml"
]

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

def normalize(word):
    return word[:-1] if word.endswith("s") else word

def tokenize(text):
    return [normalize(w) for w in re.findall(r"\b[a-z]+\b", text.lower())]

def important_tokens(tokens):
    return {t for t in tokens if t in KEYWORDS or t in ACTORS}

def is_duplicate(a, b):
    ta = tokenize(a)
    tb = tokenize(b)
    return len(important_tokens(ta) & important_tokens(tb)) >= 2

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
        return 2.0
    if any(m in ["missile","strike","bomb","attack"] for m in matches):
        return 1.4
    if any(m in ["deploy","mobilize"] for m in matches):
        return 1.1
    if any(m in ["threat","warn"] for m in matches):
        return 0.7
    return 1.0

def score_headline(text, age_hours):
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

    return weighted, matches, actors, regions

def cluster_events(scored):
    clusters = defaultdict(list)
    for score, text, matches, actors, regions, link in scored:
        clusters[tuple(regions)].append((score, actors))
    return clusters

def compute_cluster_score(clusters):
    total = 0
    for region_key, entries in clusters.items():
        scores = [e[0] for e in entries]
        actors = set(a for e in entries for a in e[1])

        cluster_sum = sum(scores)
        repetition_multiplier = 1 + (len(scores) - 1) * 0.18
        actor_multiplier = 1 + (len(actors) - 1) * 0.25
        damping = 1 / (1 + (len(scores) - 1) * 0.4)

        total += cluster_sum * repetition_multiplier * actor_multiplier * damping

    return total

def compute_baseline(clusters):
    baseline = 0
    for region_key in clusters.keys():
        for r in region_key:
            baseline += REGION_BASELINE.get(r, 1.0)
    return baseline

def compute_cross_region_bonus(clusters):
    return (len(clusters) - 1) * 2.5 if len(clusters) > 1 else 0

def main():
    headlines = fetch_headlines()
    scored = []

    for text, age, link in headlines:
        score, matches, actors, regions = score_headline(text, age)
        if score > 0:
            scored.append((score, text, matches, actors, regions, link))

    clusters = cluster_events(scored)

    total_score = (
        compute_cluster_score(clusters)
        + compute_baseline(clusters)
        + compute_cross_region_bonus(clusters)
    )

    region_count = max(len(clusters), 1)
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
                "link": t[5]
            } for t in top
        ],
        "debug": {
            "headline_count": len(headlines),
            "scored_count": len(scored),
            "unique_regions": len(clusters)
        }
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
