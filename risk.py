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
    "missile": 3,
    "attack": 2,
    "strike": 2,
    "bomb": 2,
    "drone": 2,
    "war": 1,
    "conflict": 1,
    "clash": 1,
    "tension": 1,
    "crisis": 1,
    "threat": 2,
    "deploy": 2,
    "military": 1,
    "exercise": 1,
    "nuclear": 8
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
    "us": "global",
    "russia": "europe",
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
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:30]:
            headlines.append(entry.title)
    return headlines

def is_blacklisted(text):
    return any(b in text.lower() for b in BLACKLIST)

def has_proximity(tokens):
    for i, t in enumerate(tokens):
        if t in KEYWORDS:
            window = tokens[max(0, i-3):i+4]
            if any(w in ACTION_WORDS for w in window):
                return True
    return False

def extract_region(tokens):
    return tuple(sorted({REGIONS[t] for t in tokens if t in REGIONS}))

def score_headline(text):
    if is_blacklisted(text):
        return 0, [], ()

    tokens = tokenize(text)

    matches = [t for t in tokens if t in KEYWORDS]
    if not matches:
        return 0, [], ()

    if not has_proximity(tokens):
        return 0, [], ()

    base = sum(KEYWORDS[m] for m in matches)
    region = extract_region(tokens)

    multiplier = 1.0
    if len(region) >= 2:
        multiplier = 1.5
    elif len(region) == 1:
        multiplier = 1.1

    return base * multiplier, matches, region

def main():
    headlines = fetch_headlines()

    total_score = 0
    drivers = []
    seen_regions = set()
    scored_count = 0

    for h in headlines:
        score, matches, region = score_headline(h)

        if score == 0:
            continue

        if region in seen_regions and region:
            continue

        seen_regions.add(region)

        total_score += score
        drivers.append((score, h, matches))
        scored_count += 1

    # ---- NORMALIZATION ----
    region_count = max(len(seen_regions), 1)
    normalized_score = total_score / region_count

    # ---- HARD FLOOR (critical fix) ----
    if normalized_score < 5:
        probability = 0.03  # force baseline (3%)
    else:
        probability = 1 / (1 + math.exp(-0.15 * (normalized_score - 12)))

    drivers = sorted(drivers, reverse=True)[:5]

    data = {
        "last_updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "score": round(total_score, 2),
        "normalized_score": round(normalized_score, 2),
        "probability": round(probability * 100, 2),
        "top_drivers": [f"{d[1]} (matches: {d[2]})" for d in drivers],
        "debug": {
            "headline_count": len(headlines),
            "scored_count": scored_count,
            "unique_regions": len(seen_regions)
        }
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
