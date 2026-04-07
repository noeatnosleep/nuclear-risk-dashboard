import feedparser
import datetime
import json
import math
import re
import os

# ======================
# CONFIG
# ======================

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1004/rss.xml",
    "https://rss.cnn.com/rss/edition_world.rss",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.dw.com/xml/rss-en-all",
    "https://www.theguardian.com/world/rss"
]

STATE_FILE = "state.json"
LOG_FILE = "history_log.json"
MAX_LOG_ENTRIES = 200

DECAY = 0.985

# ======================
# BASELINE (RESEARCH-DRIVEN)
# ======================

BASELINE_STATE = {
    "us_russia": 6.5,
    "us_china": 5.5,
    "china_taiwan": 6.5,

    "india_pakistan": 7.5,
    "china_india": 4.5,

    "iran_us": 6.0,
    "iran_israel": 7.0,

    "nk_us": 6.5,
    "nk_sk": 6.0,
    "nk_japan": 5.5,

    "russia_ukraine": 8.0
}

STATE_WEIGHTS = {
    "us_russia": 0.25,
    "us_china": 0.20,
    "china_taiwan": 0.15,

    "india_pakistan": 0.15,
    "china_india": 0.08,

    "iran_us": 0.07,
    "iran_israel": 0.05,

    "nk_us": 0.03,
    "nk_sk": 0.015,
    "nk_japan": 0.015,

    "russia_ukraine": 0.07
}

# ======================
# ACTORS + MAPPING
# ======================

ACTORS = {
    "us","america","united states",
    "russia","china",
    "india","pakistan",
    "iran","israel",
    "north korea","korea","japan",
    "taiwan","ukraine"
}

STATE_KEYS = {
    ("us","russia"): "us_russia",
    ("us","china"): "us_china",
    ("china","taiwan"): "china_taiwan",

    ("india","pakistan"): "india_pakistan",
    ("china","india"): "china_india",

    ("iran","us"): "iran_us",
    ("iran","israel"): "iran_israel",

    ("north korea","us"): "nk_us",
    ("north korea","korea"): "nk_sk",
    ("north korea","japan"): "nk_japan",

    ("russia","ukraine"): "russia_ukraine"
}

# ======================
# EVENT CLASSIFICATION
# ======================

INTENT = {"threat","warn","vow","rhetoric"}
PREP = {"deploy","mobilize","exercise"}
ACTION = {"attack","strike","bomb","raid"}
STRATEGIC = {"nuclear","icbm","warhead"}

CLASS_SCORE = {
    "intent": 0.2,
    "preparation": 0.5,
    "action": 0.9,
    "strategic": 1.5
}

# ======================
# UTILS
# ======================

def tokenize(text):
    return re.findall(r"\b[a-z]+\b", text.lower())

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ======================
# FETCH
# ======================

def fetch():
    out = []
    now = datetime.datetime.utcnow()

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries[:30]:
            try:
                title = e.title
                link = getattr(e, "link", "")
                pub = e.get("published_parsed")

                if pub:
                    dt = datetime.datetime(*pub[:6])
                    age = (now - dt).total_seconds() / 3600
                else:
                    age = 6

                out.append((title, age, link))
            except:
                continue

    return out

# ======================
# CLASSIFICATION
# ======================

def classify(tokens):
    if any(t in STRATEGIC for t in tokens):
        return "strategic"
    if any(t in ACTION for t in tokens):
        return "action"
    if any(t in PREP for t in tokens):
        return "preparation"
    if any(t in INTENT for t in tokens):
        return "intent"
    return None

def extract_actors(tokens):
    return list(set([t for t in tokens if t in ACTORS]))

def map_state(actors):
    actors = set(actors)

    for pair, key in STATE_KEYS.items():
        if set(pair).issubset(actors):
            return key

    return None

def event_impact(event_class, age):
    base = CLASS_SCORE.get(event_class, 0)
    decay = math.exp(-age / 24)
    return base * decay

# ======================
# MAIN
# ======================

def main():
    headlines = fetch()

    # initialize or load state
    state = load_json(STATE_FILE, BASELINE_STATE.copy())

    # decay toward baseline (critical)
    for k in state:
        baseline = BASELINE_STATE[k]
        state[k] = baseline + (state[k] - baseline) * DECAY

    updates = []

    for title, age, link in headlines:
        tokens = tokenize(title)

        actors = extract_actors(tokens)
        if not actors:
            continue

        state_key = map_state(actors)
        if not state_key:
            continue

        event_class = classify(tokens)
        if not event_class:
            continue

        impact = event_impact(event_class, age)

        # persistent conflict dampening
        if state_key == "russia_ukraine" and event_class != "strategic":
            impact *= 0.25

        state[state_key] += impact

        updates.append({
            "title": title,
            "actors": actors,
            "class": event_class,
            "impact": round(impact, 3),
            "link": link
        })

    # clamp state
    for k in state:
        state[k] = min(10, state[k])

    # ======================
    # GLOBAL RISK
    # ======================

    risk = 0
    for k, v in state.items():
        risk += v * STATE_WEIGHTS[k]

    risk = min(95, round(risk * 10, 2))

    # ======================
    # LOGGING
    # ======================

    log = load_json(LOG_FILE, {"data": []})
    now = datetime.datetime.utcnow()

    log["data"].append({
        "t": now.isoformat(),
        "p": risk
    })

    log["data"] = log["data"][-MAX_LOG_ENTRIES:]
    save_json(LOG_FILE, log)

    save_json(STATE_FILE, state)

    # ======================
    # OUTPUT
    # ======================

    top = sorted(updates, key=lambda x: x["impact"], reverse=True)[:5]

    output = {
        "last_updated": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "probability": risk,
        "state": state,
        "top_drivers": top
    }

    save_json("risk.json", output)


if __name__ == "__main__":
    main()
