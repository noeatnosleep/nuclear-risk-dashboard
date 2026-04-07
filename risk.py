import feedparser
import datetime
import json
import math
import re
from collections import Counter

# --- CONFIG ---

RSS_FEEDS = [
    "https://www.reuters.com/rssFeed/worldNews",
    "https://apnews.com/rss/apf-topnews"
]

NUCLEAR_STATES = {
    "united states","us","russia","china","israel",
    "india","pakistan","north korea"
}

# High-risk nuclear pairings
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
    "threat": 2,
    "nuclear": 8
}

# --- FETCH ---

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

# --- CLEAN ---

def dedupe(headlines):
    seen = set()
    unique = []
    for h in headlines:
        key = h["title"][:80]
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique

# --- ACTOR DETECTION ---

def detect_actors(text):
    actors = set()
    for state in NUCLEAR_STATES.union({"iran","taiwan"}):
        if state in text:
            actors.add(state)
    return actors

# --- PAIR RISK ---

def pair_multiplier(actors):
    if len(actors) < 2:
        return 0.3  # low relevance

    for pair in HIGH_RISK_PAIRS:
        if pair.issubset(actors):
            return 3.0

    for pair in MEDIUM_RISK_PAIRS:
        if pair.issubset(actors):
            return 1.8

    if len(actors.intersection(NUCLEAR_STATES)) >= 2:
        return 2.2

    return 1.0

# --- SCORING ---

def score_headline(text):
    base = 0

    for word, weight in EVENT_KEYWORDS.items():
        if word in text:
            base += weight

    actors = detect_actors(text)

    multiplier = pair_multiplier(actors)

    return base * multiplier, actors

# --- TIME DECAY ---

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

# --- KEYWORD DISCOVERY (CONTROLLED) ---

def extract_new_terms(headlines):
    words = []
    for h in headlines:
        tokens = re.findall(r'\b[a-z]{5,}\b', h["title"])
        words.extend(tokens)

    counts = Counter(words)

    new_terms = {}
    for word, count in counts.items():
        if count >= 3 and word not in EVENT_KEYWORDS:
            new_terms[word] = min(3, count)

    return new_terms

# --- MAIN ---

def main():
    headlines = fetch_headlines()
    headlines = dedupe(headlines)

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

    # normalize
    probability = 1 / (1 + math.exp(-0.08 * (total_score - 20)))

    # top drivers
    drivers = sorted(drivers, reverse=True)[:5]

    new_terms = extract_new_terms(headlines)

    data = {
        "date": str(datetime.date.today()),
        "score": round(total_score, 2),
        "probability": round(probability * 100, 2),
        "top_drivers": [d[1] for d in drivers],
        "new_terms_detected": list(new_terms.keys())[:5]
    }

    with open("risk.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    main()
