"""Risk computation pipeline for nuclear-risk-dashboard."""

import json
import math
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

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
CLUSTER_CORROBORATION_BONUS = float(CONFIG.get("cluster_corroboration_bonus", 0.08))
MAX_DRIVER_COUNT = int(CONFIG.get("max_driver_count", 256))


def clamp(value, low, high):
    return max(low, min(high, value))


def extract_domain(url):
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def normalize_title(title):
    text = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(title or "").lower())).strip()
    tokens = [tok for tok in text.split() if tok not in {"and", "the", "a", "an", "after", "amid"}]
    return " ".join(tokens)


def cluster_key_for_driver(driver):
    tokens = normalize_title(driver.get("title", "")).split()
    short = " ".join(tokens[:8]) if tokens else "untitled"
    return f"{driver.get('state_key','unknown')}::{short}"


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
    avg_corroboration = sum(driver.get("corroboration_count", 1) for driver in top_drivers) / len(top_drivers)
    confidence_penalty = (1 - avg_confidence) * 16
    corroboration_bonus = min(4.0, (avg_corroboration - 1) * 1.2)
    low_volume_penalty = 10 if event_count < 15 else 5 if event_count < 30 else 2
    return round(clamp(confidence_penalty + low_volume_penalty - corroboration_bonus, 2, 30), 2)


def build_signal_sources(events, top_drivers):
    seen = set()
    rows = []

    for event in events:
        source_name = str(event.get("source_name", "")).strip()
        source_url = str(event.get("source", "")).strip()
        source_domain = extract_domain(source_url)
        if not source_name and not source_url and not source_domain:
            continue
        key = (source_name, source_url, source_domain)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": source_name or source_domain or "unknown", "url": source_url, "domain": source_domain})

    for driver in top_drivers:
        source_url = str(driver.get("source", "")).strip()
        source_domain = str(driver.get("source_domain", "")).strip() or extract_domain(source_url)
        key = (source_domain, source_url, source_domain)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": source_domain or "unknown", "url": source_url, "domain": source_domain})

    rows.sort(key=lambda row: row.get("name", ""))
    return rows


def merge_driver_clusters(top_drivers):
    grouped = {}
    for driver in top_drivers:
        key = cluster_key_for_driver(driver)
        grouped.setdefault(key, []).append(driver)

    merged = []
    for _, rows in grouped.items():
        seed = rows[0].copy()
        domains = sorted(set(r.get("source_domain", "") for r in rows if r.get("source_domain")))
        links = [r.get("link") for r in rows if r.get("link")]
        corroboration_count = len(rows)

        mean_impact = sum(float(r.get("impact", 0.0)) for r in rows) / corroboration_count
        mean_conf = sum(float(r.get("confidence", 0.0)) for r in rows) / corroboration_count
        boost = 1.0 + (corroboration_count - 1) * CLUSTER_CORROBORATION_BONUS

        seed["impact"] = round(clamp(mean_impact * boost, -2.0, 2.0), 3)
        seed["confidence"] = round(clamp(mean_conf + min(0.18, (corroboration_count - 1) * 0.03), 0.0, 1.0), 3)
        seed["corroboration_count"] = corroboration_count
        seed["cluster_sources"] = domains
        seed["cluster_links"] = links[:12]
        merged.append(seed)

    merged.sort(key=lambda row: abs(row.get("impact", 0)), reverse=True)
    return merged


def save_state(probability, state, top_drivers, debug, signal_sources):
    sorted_drivers = sorted(top_drivers, key=lambda row: abs(row.get("impact", 0)), reverse=True)
    uncertainty = compute_uncertainty(sorted_drivers, debug.get("event_count", 0))

    payload = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "probability": round(probability, 2),
        "uncertainty": uncertainty,
        "state": state,
        "top_drivers": sorted_drivers[:MAX_DRIVER_COUNT],
        "signal_sources": signal_sources,
        "driver_sort_default": "chronological",
        "available_driver_sort": ["severity", "chronological", "confidence", "source_weight", "corroboration"],
        "debug": debug,
    }

    with open(STATE_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2)

    history = load_history()
    history.append({"ts": payload["last_updated"], "probability": payload["probability"]})
    save_history(history[-400:])

    save_diagnostics(
        {
            "ts": payload["last_updated"],
            "probability": payload["probability"],
            "uncertainty": payload["uncertainty"],
            "state": state,
            "drop_reasons": debug.get("drop_reasons", {}),
            "event_count": debug.get("event_count", 0),
            "classified_count": debug.get("classified_count", 0),
            "drivers": sorted_drivers[:MAX_DRIVER_COUNT],
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

        source_url = event.get("source", "")

        top_drivers.append(
            {
                "title": event.get("title"),
                "published": event.get("published", ""),
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
                "source": source_url,
                "source_domain": extract_domain(source_url),
            }
        )

    clustered_drivers = merge_driver_clusters(top_drivers)
    return updates, clustered_drivers, classified_count, paired_count, debug_drops


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

    signal_sources = build_signal_sources(events, top_drivers)
    save_state(probability, state, top_drivers, debug, signal_sources)
    return probability, state, top_drivers


if __name__ == "__main__":
    from ingest import fetch_events

    run(fetch_events())
