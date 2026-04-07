import json
import math
from datetime import datetime

from states import BASELINE_STATE
from actors import STATE_KEYS
from events import classify_event
from ingest import fetch_events


STATE_FILE = "risk.json"
HISTORY_FILE = "history_log.json"


DECAY_RATE = 0.15
EMPTY_RUN_DECAY_MULTIPLIER = 2.5
MAX_STEP_CHANGE = 1.25


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def load_previous_state():
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return data.get("state", BASELINE_STATE.copy())
    except:
        return BASELINE_STATE.copy()


def load_history():
    try:
        with open(HISTORY_FILE, "r") as f:
            data = json.load(f)

            # CRITICAL FIX
            if isinstance(data, list):
                return data
            else:
                return []

    except:
        return []


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def save_state(probability, state, top_drivers):
    payload = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "probability": round(probability, 2),
        "state": state,
        "top_drivers": top_drivers[:5]
    }

    with open(STATE_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    history = load_history()

    history.append({
        "ts": payload["last_updated"],
        "probability": payload["probability"]
    })

    history = history[-200:]

    save_history(history)


def decay_toward_baseline(current, baseline, multiplier=1.0):
    new_state = {}
    for k in current:
        delta = baseline[k] - current[k]
        new_state[k] = current[k] + (delta * DECAY_RATE * multiplier)
    return new_state


def apply_event_impacts(state, events):
    updates = {k: 0.0 for k in state}
    top_drivers = []

    for e in events:
        try:
            classified = classify_event(e)
        except Exception:
            continue

        if not classified:
            continue

        actors = classified["actors"]
        pair = "_".join(sorted(actors))

        if pair not in updates:
            continue

        impact = classified["impact"]
        updates[pair] += impact

        top_drivers.append({
            "title": e.get("title"),
            "actors": actors,
            "class": classified["class"],
            "impact": round(impact, 3),
            "link": e.get("link"),
            "source": e.get("source")
        })

    return updates, top_drivers


def apply_updates_with_clamp(state, updates):
    new_state = {}

    for k in state:
        step = clamp(updates[k], -MAX_STEP_CHANGE, MAX_STEP_CHANGE)
        new_state[k] = clamp(state[k] + step, 0, 10)

    return new_state


def compute_probability(state):
    avg = sum(state.values()) / len(state)
    prob = 1 / (1 + math.exp(-(avg - 5)))
    return prob * 100


def run(events):

    print("EVENT COUNT:", len(events))

    prev_state = load_previous_state()

    updates, top_drivers = apply_event_impacts(prev_state, events)

    total_signal = sum(abs(v) for v in updates.values())

    if total_signal == 0:
        state = decay_toward_baseline(
            prev_state,
            BASELINE_STATE,
            multiplier=EMPTY_RUN_DECAY_MULTIPLIER
        )
    else:
        decayed = decay_toward_baseline(prev_state, BASELINE_STATE)
        state = apply_updates_with_clamp(decayed, updates)

    probability = compute_probability(state)

    save_state(probability, state, top_drivers)

    return probability, state, top_drivers


if __name__ == "__main__":
    events = fetch_events()
    run(events)
