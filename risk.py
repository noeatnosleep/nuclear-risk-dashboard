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
    return re.findall(r"\b[a-z]+\b", text.lower())

def fetch_headlines():
    headlines = []
    now = datetime.datetime.utcnow()

    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"Feed parse failed: {url} -> {e}")
            continue

        for entry in getattr(feed, "entries", [])[:30]:
            try:
                title = entry.title
            except:
                continue

            try:
                published = entry.get("published_parsed")
                if published:
                    published_dt = datetime.datetime(*published[:6])
                    age_hours = (now - published_dt).total_seconds() / 3600
                else:
                    age_hours = 6
            except:
                age_hours = 6

            headlines.append((title, age_hours))

    return headlines

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

    if not matches:
        return 0, [], [], None

    if not has_proximity(tokens):
        return 0, [], [], None

    actors = extract_actors(tokens)
    if not actors:
        return 0, [], [], None

    regions = sorted({ACTORS[a] for a in actors})

    base = sum(KEYWORDS[m] for m in matches)
    weighted = base * time_weight(age_hours) * action_multiplier(matches)

    return weighted, matches, actors, regions

def main():
    try:
        headlines = fetch_headlines()
        print(f"Fetched {len(headlines)} headlines")

        scored = []

        for text, age in headlines:
            try:
                score, matches, actors, regions = score_headline(text, age)
                if score > 0:
                    scored.append((score, text, matches, actors, regions))
            except Exception as e:
                print(f"Scoring failed: {text} -> {e}")

        print(f"Scored: {len(scored)}")

        clusters = defaultdict(list)
        for score, text, matches, actors, regions in scored:
            clusters[tuple(regions)].append((score, actors))

        total_score = sum(s for s, _, _, _, _ in scored)

        probability = min(0.01 + total_score * 0.01, 0.95)

        top = sorted(scored, reverse=True)[:5]

        data = {
            "last_updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "score": round(total_score, 2),
            "probability": round(probability * 100, 2),
            "top_drivers": [
                f"{t[1]} (actors: {t[3]}, matches: {t[2]})" for t in top
            ],
            "debug": {
                "headline_count": len(headlines),
                "scored_count": len(scored),
                "unique_regions": len(clusters)
            }
        }

        with open("risk.json", "w") as f:
            json.dump(data, f, indent=2)

        print("risk.json written successfully")

    except Exception as e:
        print("FATAL ERROR:", e)
        raise

if __name__ == "__main__":
    main()
