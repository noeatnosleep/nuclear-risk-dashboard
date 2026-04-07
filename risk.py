import datetime
import json
import os

from actors import extract_actors
from events import classify, event_impact
from states import BASELINE_STATE, STATE_WEIGHTS, map_state
from ingest import fetch

STATE_FILE = "state.json"
LOG_FILE = "history_log.json"
MAX_LOG_ENTRIES = 200

DECAY = 0.985
MAX_IMPACT_PER_STATE_PER_CYCLE = 3.0

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

def extract_source(link):
    try:
        return link.split("/")[2]
    except:
        return ""

def main():
    headlines = fetch()

    state = load_json(STATE_FILE, BASELINE_STATE.copy())

    # decay toward baseline
    for k in state:
        baseline = BASELINE_STATE[k]
        state[k] = baseline + (state[k] - baseline) * DECAY

    updates = []
    cycle_impact = {k: 0 for k in state}

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

        if state_key == "russia_ukraine" and event_class != "strategic":
            impact *= 0.25

        remaining = MAX_IMPACT_PER_STATE_PER_CYCLE - cycle_impact[state_key]
        if remaining <= 0:
            continue

        impact = min(impact, remaining)

        state[state_key] += impact
        cycle_impact[state_key] += impact

        updates.append({
            "title": title,
            "actors": actors,
            "class": event_class,
            "impact": round(impact, 3),
            "link": link,
            "source": extract_source(link)
        })

    for k in state:
        state[k] = min(10, state[k])

    weighted_sum = sum(state[k] * STATE_WEIGHTS[k] for k in state)
    baseline_sum = sum(BASELINE_STATE[k] * STATE_WEIGHTS[k] for k in BASELINE_STATE)

    normalized = weighted_sum / baseline_sum
    risk = min(95, round(normalized * 12, 2))

    log = load_json(LOG_FILE, {"data": []})
    now = datetime.datetime.utcnow()

    log["data"].append({"t": now.isoformat(), "p": risk})
    log["data"] = log["data"][-MAX_LOG_ENTRIES:]

    save_json(LOG_FILE, log)
    save_json(STATE_FILE, state)

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
