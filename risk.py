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
# BASELINE (RESEARCH-ALIGNED)
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
# ACTOR REGEX (FIXED)
# ======================

ACTOR_PATTERNS = {
    "us": r"\b(U\.S\.|U\.S|USA|United States|America)\b",
    "russia": r"\bRussia|Russian\b",
    "china": r"\bChina|Chinese\b",
    "india": r"\bIndia|Indian\b",
    "pakistan": r"\bPakistan\b",
    "iran": r"\bIran|Iranian\b",
    "israel": r"\bIsrael|Israeli\b",
    "north korea": r"\bNorth Korea|DPRK\b",
    "korea": r"\bSouth Korea\b",
    "japan": r"\bJapan|Japanese\b",
    "taiwan": r"\bTaiwan\b",
    "ukraine": r"\bUkraine|Ukrainian\b"
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

def extract_actors(text):
    found = set()
    for actor, pattern in ACTOR_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.add(actor)
    return list(found)

def classify(text):
    tokens = re.findall(r"\b[a-z]+\b", text.lower())

    if any(t in STRATEGIC for t in tokens):
        return "strategic"
    if any(t in ACTION for t in tokens):
        return "action"
    if any(t in PREP for t in tokens):
        return "preparation"
    if any(t in INTENT for t in tokens):
        return "intent"
    return None

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

def extract_source(link):
    try:
        return link.split("/")[2]
    except:
        return ""

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
# MAIN
# ======================

def main():
    headlines = fetch()

    state = load_json(STATE_FILE, BASELINE_STATE.copy())

    # decay toward baseline (NOT zero)
    for k in state:
        baseline = BASELINE_STATE[k]
        state[k] = baseline + (state[k] - baseline) * DECAY

    updates = []

    for title, age, link in headlines:
        actors = extract_actors(title)
        if len(actors) < 2:
            continue

        state_key = map_state(actors)
        if not state_key:
            continue

        event_class = classify(title)
        if not event_class:
            continue

        impact = event_impact(event_class, age)

        # damp persistent war noise
        if state_key == "russia_ukraine" and event_class != "strategic":
            impact *= 0.25

        state[state_key] += impact

        updates.append({
            "title": title,
            "actors": actors,
            "class": event_class,
            "impact": round(impact, 3),
            "link": link,
            "source": extract_source(link)
        })

    # clamp
    for k in state:
        state[k] = min(10, state[k])

    # ======================
    # GLOBAL RISK (NORMALIZED TO BASELINE)
    # ======================

    weighted_sum = sum(state[k] * STATE_WEIGHTS[k] for k in state)
    baseline_sum = sum(BASELINE_STATE[k] * STATE_WEIGHTS[k] for k in BASELINE_STATE)

    # ratio vs baseline (this is the key fix)
    normalized = weighted_sum / baseline_sum

    # map to % scale
    risk = min(95, round(normalized * 12, 2))

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
