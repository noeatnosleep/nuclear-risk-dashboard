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

REGIONS = {
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

def normalize(word):
    return word[:-1] if word.endswith("s") else word

def tokenize(text):
    words = re.findall(r"\b[a-z]+\b", text.lower())
    return [normalize(w) for w in words]

def fetch_headlines():
    headlines = []
    now = datetime.datetime.utcnow()

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:30]:
            published = entry.get("published_parsed")
            if published:
                published_dt = datetime.datetime(*published[:6])
                age_hours = (now - published_dt).total_seconds() / 3600
            else:
                age_hours = 6  # default fallback

            headlines.append((entry.title, age_hours))

    return headlines

def time_weight(hours):
    # decay: fresh news matters more
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

def extract_regions(tokens):
    return sorted({REGIONS[t] for t in tokens if t in REGIONS})

def score_headline(text, age_hours):
    if is_blacklisted(text):
        return 0, [], []

    tokens = tokenize(text)
    matches = [t for t in tokens if t in KEYWORDS]

    if not matches:
        return 0, [], []

    if not has_proximity(tokens):
        return 0, [], []

    base = sum(KEYWORDS[m] for m in matches)
    regions = extract_regions(tokens)

    if not regions:
        return 0, [], []

    # time weighting
    weighted = base * time_weight(age_hours)

    return weighted, matches, regions

def cluster_events(scored):
    clusters = defaultdict(list)

    for score, text, matches, regions in scored:
        key = tuple(regions)
        clusters[key].append(score)

    return clusters

def compute_cluster_score(clusters):
    total = 0

    for region_key, scores in clusters.items():
        cluster_sum = sum(scores)

        # escalation multiplier for repeated signals
        multiplier = 1 + (len(scores) - 1) * 0.3

        total += cluster_sum * multiplier

    return total

def main():
    headlines = fetch_headlines()

    scored = []

    for text, age in headlines:
        score, matches, regions = score_headline(text, age)

        if score > 0:
            scored.append((score, text, matches, regions))

    clusters = cluster_events(scored)

    total_score = compute_cluster_score(clusters)

    region_count = max(len(clusters), 1)
    normalized_score = total_score / region_count

    # LOW RANGE: smooth floor
    if normalized_score < 5:
        probability = 0.01 + (normalized_score / 5) * 0.04

    # MID RANGE
    elif normalized_score < 20:
        probability = 0.05 + (normalized_score - 5) * 0.01

    # HIGH RANGE (logistic)
    else:
        probability = 1 / (1 + math.exp(-0.12 * (normalized_score - 25)))

    probability = min(probability, 0.95)

    top = sorted(scored, reverse=True)[:5]

    data = {
        "last_updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "score": round(total_score, 2),
        "normalized_score": round(normalized_score, 2),
        "probability": round(probability * 100, 2),
        "top_drivers": [
            f"{t[1]} (matches: {t[2]})" for t in top
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
