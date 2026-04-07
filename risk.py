import feedparser
import datetime
import json
import math

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1004/rss.xml"
]

NUCLEAR_STATES = {
    "us","russia","china","israel",
    "india","pakistan","north korea"
}

EVENT_KEYWORDS = {
    # hard military
    "missile": 4,
    "ballistic": 5,
    "airstrike": 3,
    "strike": 2,
    "attack": 3,
    "bomb": 3,
    "drone": 3,

    # escalation language
    "conflict": 1.5,
    "clash": 1.5,
    "clashes": 1.5,
    "tensions": 2,
    "crisis": 2,
    "threat": 2,

    # military posture
    "deploy": 3,
    "deployment": 3,
    "mobilize": 4,
    "exercise": 2,
    "drills": 2,

    # explicit nuclear
    "nuclear": 8,
    "atomic": 6
}

def fetch_headlines():
    headlines = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:30]:
            headlines.append({
                "title": entry.title.lower(),
                "published": entry.get("published_parsed")
            })
    return headlines

def detect_actors(text):
    actors = set()
    for state in NUCLEAR_STATES.union({"iran","taiwan","gaza","ukraine"}):
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
        multiplier = 2.2
    elif len(actors) == 1:
        multiplier = 1.2

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
    scored_count = 0

    for h in headlines:
        score, actors = score_headline(h["title"])

        if score == 0:
            continue

        age = hours_old(h["published"])
        score = apply_decay(score, age)

        total_score += score
        drivers.append((score, h["title"]))
        scored_count += 1

    probability = 1 / (1 + math.exp(-0.07 * (total_score - 25)))

    drivers = sorted(drivers, reverse=True)[:5]

    data = {
        "last_updated": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "score": round(total_score, 2),
        "probability": round(probability * 100, 2),
        "top_drivers": [d[1] for d in drivers],
        "debug": {
            "headline_count": len(headlines),
            "scored_count": scored_count
        }
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
