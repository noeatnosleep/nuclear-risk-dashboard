import json
import math
from datetime import datetime

from states import BASELINE_STATE
from actors import STATE_KEYS
from events import classify_event

STATE_FILE = "risk.json"
HISTORY_FILE = "history_log.json"


# -----------------------------
# CONFIG
# -----------------------------

DECAY_RATE = 0.15                 # pull toward baseline every run
EMPTY_RUN_DECAY_MULTIPLIER = 2.5  # stronger decay when no events
MAX_STEP_CHANGE = 1.25            # per-run clamp per pair


# -----------------------------
# UTIL
# -----------------------------

def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def load_previous_state():
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return data.get("state", BASELINE_STATE.copy())
    except:
        return BASELINE_STATE.copy()


def save_state(probability, state, top_drivers):
    payload = {
        "last_updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "probability": round(probability, 2),
        "state": state,
        "top_drivers": top_drivers[:5]
    }

    with open(STATE_FILE, "w") as f:
        json.dump(payload, f, indent=2)

    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except:
        history = []

    history.append({
        "ts": payload["last_updated"],
        "probability": payload["probability"]
    })

    history = history[-200:]

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# -----------------------------
# CORE
# -----------------------------

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
        classified = classify_event(e)
        if not classified:
            continue

        actors = classified["actors"]
        pair = "_".join(sorted(actors))

        if pair not in updates:
            continue

        impact = classified["impact"]

        updates[pair] += impact

        top_drivers.append({
            "title": e["title"],
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
    # weighted average (simple for now)
    vals = list(state.values())
    avg = sum(vals) / len(vals)

    # sigmoid normalize into %
    prob = 1 / (1 + math.exp(-(avg - 5)))

    return prob * 100


# -----------------------------
# MAIN ENTRY
# -----------------------------

def run(events):

    prev_state = load_previous_state()

    # 1. classify + extract impacts
    updates, top_drivers = apply_event_impacts(prev_state, events)

    total_signal = sum(abs(v) for v in updates.values())

    # -----------------------------
    # CRITICAL FIX: NO-EVENT HANDLING
    # -----------------------------
    if total_signal == 0:
        # no valid events → DO NOT accumulate
        state = decay_toward_baseline(
            prev_state,
            BASELINE_STATE,
            multiplier=EMPTY_RUN_DECAY_MULTIPLIER
        )
    else:
        # normal flow
        decayed = decay_toward_baseline(prev_state, BASELINE_STATE)
        state = apply_updates_with_clamp(decayed, updates)

    # -----------------------------
    # probability
    # -----------------------------
    probability = compute_probability(state)

    # -----------------------------
    # save
    # -----------------------------
    save_state(probability, state, top_drivers)

    return probability, state, top_drivers
