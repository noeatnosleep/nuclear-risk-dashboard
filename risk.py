import feedparser
import datetime
import json
import math

RSS_FEEDS = [
    "https://www.reuters.com/rssFeed/worldNews",
    "https://apnews.com/rss/apf-topnews"
]

NUCLEAR_STATES = {
    "us","russia","china","israel",
    "india","pakistan","north korea"
}

HIGH_RISK_PAIRS = [
    {"us","china"},
    {"us","russia"},
    {"india","pakistan"}
]

MEDIUM_RISK_PAIRS = [
    {"israel","iran"},
    {"us","iran"},
    {"china","taiwan"}
]

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
        for entry in feed.entries[:30]:
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

def pair_multiplier(actors):
    if len(actors) < 2:
        return 0  # HARD FILTER — ignore weak signals

    for pair in HIGH_RISK_PAIRS:
        if pair.issubset(actors):
            return 3.0

    for pair in MEDIUM_RISK_PAIRS:
        if pair.issubset(actors):
            return 1.8

    if len(actors.intersection(NUCLEAR_STATES)) >= 2:
        return 2.2

    return 0  # ignore irrelevant multi-actor noise

def score_headline(text):
    base = 0
    for word, weight in EVENT_KEYWORDS.items():
        if word in text:
            base += weight

    if base == 0:
        return 0, set()

    actors = detect_actors(text)
    multiplier = pair_multiplier(actors)

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

        if score < 1:
            continue  # remove weak residual noise

        total_score += score
        drivers.append((score, h["title"]))

    probability = 1 / (1 + math.exp(-0.1 * (total_score - 15)))

    drivers = sorted(drivers, reverse=True)[:5]

    data = {
        "date": str(datetime.date.today()),
        "score": round(total_score, 2),
        "probability": round(probability * 100, 2),
        "top_drivers": [d[1] for d in drivers]
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
