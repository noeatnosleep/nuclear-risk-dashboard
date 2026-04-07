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

def map_state(actors):
    actors = set(actors)
    for pair, key in STATE_KEYS.items():
        if set(pair).issubset(actors):
            return key
    return None
