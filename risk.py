"""Risk computation pipeline for nuclear-risk-dashboard."""

import json
import math
from datetime import datetime, timezone

from config import load_config
from events import classify_event
from states import BASELINE_STATE, STATE_WEIGHTS

STATE_FILE = "risk.json"
HISTORY_FILE = "history_log.json"
DIAGNOSTICS_FILE = "diagnostics_log.json"

DECAY_RATE = 0.15
EMPTY_RUN_DECAY_MULTIPLIER = 2.5
MAX_STEP_CHANGE = 1.0

CONFIG = load_config()
PROBABILITY_CENTER = float(CONFIG.get("probability_center", 4.8))
PROBABILITY_STEEPNESS = float(CONFIG.get("probability_steepness", 0.9))


def clamp(value, low, high):
    return max(low, min(high, value))


def load_previous_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
            state = data.get("state", {})
            if not state:
                return BASELINE_STATE.copy()
            return {key: float(state.get(key, BASELINE_STATE[key])) for key in BASELINE_STATE}
    except Exception:
        return BASELINE_STATE.copy()


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except Exception:
        return None


def load_history():
    data = load_json(HISTORY_FILE)
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return [{"ts": row.get("t", ""), "probability": row.get("p", 0)} for row in data["data"]]
    if isinstance(data, list):
        return data
    return []


def save_history(history):
    payload = {
        "entries": history,
        "data": [{"t": row.get("ts", ""), "p": row.get("probability", 0)} for row in history],
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2)


def load_diagnostics():
    data = load_json(DIAGNOSTICS_FILE)
    if isinstance(data, list):
        return data
    return []


def save_diagnostics(entry):
    diagnostics = load_diagnostics()
    diagnostics.append(entry)
    diagnostics = diagnostics[-400:]
    with open(DIAGNOSTICS_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(diagnostics, file_obj, indent=2)


def compute_uncertainty(top_drivers, event_count):
    if not top_drivers:
        return 18.0
    avg_confidence = sum(driver.get("confidence", 0) for driver in top_drivers) / len(top_drivers)
    confidence_penalty = (1 - avg_confidence) * 16
    low_volume_penalty = 10 if event_count < 15 else 5 if event_count < 30 else 2
    return round(clamp(confidence_penalty + low_volume_penalty, 2, 30), 2)


def save_state(probability, state, top_drivers, debug):
    sorted_drivers = sorted(top_drivers, key=lambda row: abs(row.get("impact", 0)), reverse=True)
    uncertainty = compute_uncertainty(sorted_drivers, debug.get("event_count", 0))

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "probability": round(probability, 2),
        "uncertainty": uncertainty,
        "state": state,
        "top_drivers": sorted_drivers[:8],
        "debug": debug,
    }

    with open(STATE_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2)

    history = load_history()
    history.append({"ts": payload["last_updated"], "probability": payload["probability"]})
    save_history(history[-200:])

    save_diagnostics(
        {
            "ts": payload["last_updated"],
            "probability": payload["probability"],
            "uncertainty": payload["uncertainty"],
            "drop_reasons": debug.get("drop_reasons", {}),
            "event_count": debug.get("event_count", 0),
            "classified_count": debug.get("classified_count", 0),
        }
    )


def decay_toward_baseline(current, baseline, multiplier=1.0):
    output = {}
    for key in current:
        delta = baseline[key] - current[key]
        output[key] = current[key] + (delta * DECAY_RATE * multiplier)
    return output


def apply_event_impacts(state, events):
    updates = {key: 0.0 for key in state}
    top_drivers = []
    debug_drops = {
        "missing_title": 0,
        "no_actor": 0,
        "no_signal": 0,
        "invalid_pair": 0,
        "low_confidence": 0,
        "classifier_error": 0,
    }

    classified_count = 0
    paired_count = 0

    for event in events:
        try:
            classified = classify_event(event)
        except Exception:
            debug_drops["classifier_error"] += 1
            continue

        if not classified.get("ok"):
            reason = classified.get("reason", "classifier_error")
            debug_drops[reason] = debug_drops.get(reason, 0) + 1
            continue

        classified_count += 1
        state_key = classified["state_key"]

        if state_key not in updates:
            debug_drops["invalid_pair"] += 1
            continue

        paired_count += 1
        source_weight = float(event.get("source_weight", 1.0))
        impact = classified["impact"] * source_weight
        updates[state_key] += impact

        top_drivers.append(
            {
                "title": event.get("title"),
                "actors": classified["actors"],
                "state_key": state_key,
                "class": classified["class"],
                "impact": round(impact, 3),
                "raw_impact": round(classified["impact"], 3),
                "source_weight": source_weight,
                "age_hours": classified.get("age_hours"),
                "confidence": classified.get("confidence"),
                "signal_total": classified.get("signal_total"),
                "signal_components": classified.get("signal_components"),
                "link": event.get("link"),
                "source": event.get("source"),
            }
        )

    return updates, top_drivers, classified_count, paired_count, debug_drops


COUPLING_RULES = {
    "us_china": [("china_taiwan", 0.2)],
    "iran_us": [("iran_israel", 0.2)],
    "russia_ukraine": [("us_russia", 0.1)],
}


def apply_cross_state_coupling(updates):
    coupled = updates.copy()
    for source_pair, targets in COUPLING_RULES.items():
        source_signal = updates.get(source_pair, 0.0)
        if source_signal == 0:
            continue
        for target_pair, strength in targets:
            coupled[target_pair] += source_signal * strength
    return coupled


def apply_updates_with_clamp(state, updates):
    output = {}
    for key in state:
        step = clamp(updates[key], -MAX_STEP_CHANGE, MAX_STEP_CHANGE)
        output[key] = clamp(state[key] + step, 0, 10)
    return output


def compute_probability(state):
    total_weight = sum(STATE_WEIGHTS.values())
    weighted_sum = sum(state[key] * STATE_WEIGHTS.get(key, 0.0) for key in state)
    average = weighted_sum / total_weight if total_weight else (sum(state.values()) / len(state))
    z = (average - PROBABILITY_CENTER) * PROBABILITY_STEEPNESS
    probability = 1 / (1 + math.exp(-z))
    return probability * 100


def run(events):
    previous_state = load_previous_state()
    updates, top_drivers, classified_count, paired_count, debug_drops = apply_event_impacts(previous_state, events)
    coupled_updates = apply_cross_state_coupling(updates)

    total_signal = sum(abs(value) for value in coupled_updates.values())
    non_zero_updates = sum(1 for value in coupled_updates.values() if abs(value) > 1e-9)

    if total_signal == 0:
        state = decay_toward_baseline(previous_state, BASELINE_STATE, multiplier=EMPTY_RUN_DECAY_MULTIPLIER)
    else:
        decayed = decay_toward_baseline(previous_state, BASELINE_STATE)
        state = apply_updates_with_clamp(decayed, coupled_updates)

    probability = compute_probability(state)

    debug = {
        "event_count": len(events),
        "classified_count": classified_count,
        "paired_count": paired_count,
        "valid_pair_updates": non_zero_updates,
        "top_driver_count": len(top_drivers),
        "total_signal": round(total_signal, 4),
        "drop_reasons": debug_drops,
    }

    save_state(probability, state, top_drivers, debug)
    return probability, state, top_drivers


if __name__ == "__main__":
    from ingest import fetch_events
    run(fetch_events())
