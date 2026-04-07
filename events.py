import math
import re

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

MAX_IMPACT_PER_EVENT = 1.5

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

def event_impact(event_class, age):
    base = CLASS_SCORE.get(event_class, 0)
    decay = math.exp(-age / 24)
    return min(MAX_IMPACT_PER_EVENT, base * decay)
