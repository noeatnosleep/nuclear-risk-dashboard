import feedparser
import datetime
import json
import math
import re

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1004/rss.xml"
]

KEYWORDS = {
    "missile": 5,
    "attack": 4,
    "strike": 3,
    "bomb": 4,
    "drone": 3,
    "war": 2,
    "conflict": 2,
    "clash": 2,
    "tension": 2,
    "crisis": 2,
    "threat": 3,
    "deploy": 4,
    "military": 3,
    "exercise": 2,
    "nuclear": 10
}

# must indicate active or forward-looking event
ACTION_WORDS = {
    "launch","launched","strike","strikes","attack","attacks",
    "deploy","deploys","threat","threatens","warn","warns",
    "escalate","escalation","mobilize","mobilization"
}

ACTORS = {
    "us","russia","china","israel","iran",
    "india","pakistan","north korea","taiwan"
}

def normalize(word):
    if word.endswith("s"):
        return word[:-1]
    return word

def tokenize(text):
    words = re.findall(r"\b[a-z]+\b", text.lower())
    return [normalize(w) for w in words]

def fetch_headlines():
    headlines = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:30]:
            headlines.append(entry.title)
    return headlines

def is_actionable(tokens):
    return any(t in ACTION_WORDS for t in tokens)

def extract_cluster(tokens):
    return tuple(sorted(set(t for t in tokens if t in ACTORS)))

def score_headline(text):
    tokens = tokenize(text)

    matches = [t for t in tokens if t in KEYWORDS]

    if not matches:
        return 0, [], ()

    # FILTER: must be actionable
    if not is_actionable(tokens):
        return 0, [], ()

    base = sum(KEYWORDS[m] for m in matches)
    actors = extract_cluster(tokens)

    multiplier = 1.0
    if len(actors) >= 2:
        multiplier = 2.5
    elif len(actors) == 1:
        multiplier = 1.3

    return base * multiplier, matches, actors

def main():
    headlines = fetch_headlines()

    total_score = 0
    drivers = []
    seen_clusters = set()
    scored_count = 0

    for h in headlines:
        score, matches, cluster = score_headline(h)

        if score == 0:
            continue

        if cluster in seen_clusters and len(cluster) > 0:
            continue

        seen_clusters.add(cluster)

        total_score += score
        drivers.append((score, h, matches))
        scored_count += 1

    probability = 1 / (1 + math.exp(-0.05 * (total_score - 35)))

    drivers = sorted(drivers, reverse=True)[:5]

    data = {
        "last_updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "score": round(total_score, 2),
        "probability": round(probability * 100, 2),
        "top_drivers": [f"{d[1]} (matches: {d[2]})" for d in drivers],
        "debug": {
            "headline_count": len(headlines),
            "scored_count": scored_count,
            "unique_clusters": len(seen_clusters)
        }
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
