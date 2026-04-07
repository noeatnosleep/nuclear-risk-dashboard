import feedparser
import datetime
import json
import math

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1004/rss.xml",
    "https://www.reutersagency.com/feed/?best-topics=world&post_type=best"
]

NUCLEAR_STATES = {
    "us","russia","china","israel",
    "india","pakistan","north korea"
}

EVENT_KEYWORDS = {
    "missile": 3,
    "ballistic": 4,
    "airstrike": 2,
    "strike": 2,
    "attack": 2,
    "deploy": 3,
    "mobilize": 4,
    "evacuate": 5,
    "nuclear": 8
}

def fetch_headlines():
    headlines = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:20]:
            headlines.append({
                "title": entry.title.lower(),
                "published": entry.get("published_parsed")
            })
    return headlines

def detect_actors(text):
    actors = set()
    for state in NUCLEAR_STATES.union({"iran","taiwan"}):
        if state in text:
            actors.add(state)
    return actors

def score_headline(text):
    base = 0
    for word, weight in EVENT_KEYWORDS.items():
        if word in text:
            base += weight

    if base == 0:
        return 0, set()

    actors = detect_actors(text)

    multiplier = 1.0
    if len(actors) >= 2:
        multiplier = 2.0
    elif len(actors) == 1:
        multiplier = 0.8

    return base * multiplier, actors

def hours_old(published_struct):
    try:
        if not published_struct:
            return 0
        pub = datetime.datetime(*published_struct[:6])
        now = datetime.datetime.utcnow()
        return (now - pub).total_seconds() / 3600
    except:
        return 0

def apply_decay(score, hours):
    return score * (0.5 ** (hours / 24))

def main():
    headlines = fetch_headlines()

    total_score = 0
    drivers = []

    for h in headlines:
        score, actors = score_headline(h["title"])

        if score == 0:
            continue

        age = hours_old(h["published"])
        score = apply_decay(score, age)

        total_score += score
        drivers.append((score, h["title"]))

    probability = 1 / (1 + math.exp(-0.08 * (total_score - 35)))

    drivers = sorted(drivers, reverse=True)[:5]

    data = {
        "last_updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "score": round(total_score, 2),
        "probability": round(probability * 100, 2),
        "top_drivers": [d[1] for d in drivers],
        "debug": {
            "headline_count": len(headlines),
            "scored_count": len(drivers)
        }
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
