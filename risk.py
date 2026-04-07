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
    "missile","ballistic","airstrike","strike","attack","bomb","drone",
    "conflict","clash","tension","crisis","threat",
    "deploy","deployment","mobilize","exercise","drill",
    "military","war","nuclear","atomic"
}

def normalize(word):
    # crude plural normalization
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

def score_headline(text):
    tokens = tokenize(text)
    matches = [w for w in tokens if w in KEYWORDS]
    score = len(matches)
    return score, matches

def main():
    headlines = fetch_headlines()

    total_score = 0
    drivers = []
    scored_count = 0

    for h in headlines:
        score, matches = score_headline(h)

        if score == 0:
            continue

        total_score += score
        drivers.append((score, h, matches))
        scored_count += 1

    probability = min(100, total_score * 1.2)

    drivers = sorted(drivers, reverse=True)[:5]

    data = {
        "last_updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "score": total_score,
        "probability": round(probability, 2),
        "top_drivers": [f"{d[1]} (matches: {d[2]})" for d in drivers],
        "debug": {
            "headline_count": len(headlines),
            "scored_count": scored_count
        }
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
