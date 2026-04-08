"""Canonical state configuration for the risk model."""

STATE_CONFIG = [
    {"key": "us_russia", "actors": ("us", "russia"), "baseline": 3.2, "weight": 0.25},
    {"key": "us_china", "actors": ("us", "china"), "baseline": 3.0, "weight": 0.20},
    {"key": "china_taiwan", "actors": ("china", "taiwan"), "baseline": 4.0, "weight": 0.15},
    {"key": "india_pakistan", "actors": ("india", "pakistan"), "baseline": 4.5, "weight": 0.15},
    {"key": "china_india", "actors": ("china", "india"), "baseline": 2.8, "weight": 0.08},
    {"key": "iran_us", "actors": ("iran", "us"), "baseline": 3.5, "weight": 0.07},
    {"key": "iran_israel", "actors": ("iran", "israel"), "baseline": 4.5, "weight": 0.05},
    {"key": "nk_us", "actors": ("nk", "us"), "baseline": 3.0, "weight": 0.03},
    {"key": "nk_sk", "actors": ("nk", "sk"), "baseline": 2.8, "weight": 0.015},
    {"key": "nk_japan", "actors": ("nk", "japan"), "baseline": 2.6, "weight": 0.015},
    {"key": "russia_ukraine", "actors": ("russia", "ukraine"), "baseline": 5.0, "weight": 0.07},
]

BASELINE_STATE = {entry["key"]: entry["baseline"] for entry in STATE_CONFIG}
STATE_WEIGHTS = {entry["key"]: entry["weight"] for entry in STATE_CONFIG}
VALID_STATE_KEYS = [entry["key"] for entry in STATE_CONFIG]
ACTOR_PAIR_TO_STATE = {tuple(sorted(entry["actors"])): entry["key"] for entry in STATE_CONFIG}


def map_state_from_actors(actors):
    actor_set = set(actors)
    for actor_pair, state_key in ACTOR_PAIR_TO_STATE.items():
        if set(actor_pair).issubset(actor_set):
            return state_key
    return None
