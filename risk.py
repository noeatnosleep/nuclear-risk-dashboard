import json
import math
from datetime import datetime

from states import BASELINE_STATE, STATE_WEIGHTS
from events import classify_event


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

            # list format: [{"ts": "...", "probability": 12.3}, ...]
            if isinstance(data, list):
                return data
            # legacy object format: {"data": [{"t":"...", "p":12.3}, ...]}
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                normalized = []
                for point in data["data"]:
                    normalized.append({
                        "ts": point.get("t", ""),
                        "probability": point.get("p", 0)
                    })
                return normalized
            return []

    except:
        return []


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        # Write both shapes so old and new front-ends can render:
        # - legacy: {"data":[{"t","p"}]}
        # - modern: {"entries":[{"ts","probability"}]}
        payload = {
            "data": [{"t": x.get("ts", ""), "p": x.get("probability", 0)} for x in history],
            "entries": history
        }
        json.dump(payload, f, indent=2)


def save_state(probability, state, top_drivers, debug):
    sorted_drivers = sorted(top_drivers, key=lambda x: x.get("impact", 0), reverse=True)
    payload = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "probability": round(probability, 2),
        "state": state,
        "top_drivers": sorted_drivers[:8],
        "debug": debug
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
    classified_count = 0
    paired_count = 0

    for e in events:
        try:
            classified = classify_event(e)
        except Exception:
            continue

        if not classified:
            continue

        classified_count += 1
        actors = classified["actors"]
        pair = "_".join(sorted(actors))

        if pair not in updates:
            continue

        paired_count += 1
        impact = classified["impact"]
        updates[pair] += impact

        top_drivers.append({
            "title": e.get("title"),
            "actors": actors,
            "class": classified["class"],
            "impact": round(impact, 3),
            "matches": [classified["class"]],
            "link": e.get("link"),
            "source": e.get("source")
        })

    return updates, top_drivers, classified_count, paired_count


COUPLING_RULES = {
    "us_china": [("china_taiwan", 0.35)],
    "iran_us": [("iran_israel", 0.30)],
    "russia_ukraine": [("us_russia", 0.20)]
}


def apply_cross_state_coupling(updates):
    coupled = updates.copy()

    for src_pair, targets in COUPLING_RULES.items():
        src_signal = updates.get(src_pair, 0.0)
        if src_signal == 0:
            continue
        for target_pair, strength in targets:
            coupled[target_pair] += src_signal * strength

    return coupled


def apply_updates_with_clamp(state, updates):
    new_state = {}

    for k in state:
        step = clamp(updates[k], -MAX_STEP_CHANGE, MAX_STEP_CHANGE)
        new_state[k] = clamp(state[k] + step, 0, 10)

    return new_state


def compute_probability(state):
    total_weight = sum(STATE_WEIGHTS.values())
    weighted = sum(state[k] * STATE_WEIGHTS.get(k, 0.0) for k in state)
    avg = weighted / total_weight if total_weight else (sum(state.values()) / len(state))
    prob = 1 / (1 + math.exp(-(avg - 5)))
    return prob * 100


def run(events):

    print("EVENT COUNT:", len(events))

    prev_state = load_previous_state()

    updates, top_drivers, classified_count, paired_count = apply_event_impacts(prev_state, events)
    coupled_updates = apply_cross_state_coupling(updates)

    total_signal = sum(abs(v) for v in coupled_updates.values())
    non_zero_updates = sum(1 for v in coupled_updates.values() if abs(v) > 1e-9)

    if total_signal == 0:
        state = decay_toward_baseline(
            prev_state,
            BASELINE_STATE,
            multiplier=EMPTY_RUN_DECAY_MULTIPLIER
        )
    else:
        decayed = decay_toward_baseline(prev_state, BASELINE_STATE)
        state = apply_updates_with_clamp(decayed, coupled_updates)

    probability = compute_probability(state)

    debug = {
        "event_count": len(events),
        "classified_count": classified_count,
        "paired_count": paired_count,
        "valid_pair_updates": non_zero_updates,
        "top_driver_count": len(top_drivers),
        "total_signal": round(total_signal, 4)
    }

    save_state(probability, state, top_drivers, debug)

    return probability, state, top_drivers


if __name__ == "__main__":
    from ingest import fetch_events
    events = fetch_events()
    run(events)
