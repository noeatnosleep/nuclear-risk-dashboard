"""Build historical risk/diagnostics via policy curve or true article replay.

Default mode is `replay`, which ingests historical articles from GDELT,
classifies them with the existing model, and replays day-by-day state updates.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import load_config
from events import classify_event
from risk import (
    apply_cross_state_coupling,
    apply_event_impacts,
    apply_updates_with_clamp,
    compute_probability,
    decay_toward_baseline,
)
from states import BASELINE_STATE

RISK_FILE = ROOT / "risk.json"
HISTORY_FILE = ROOT / "history_log.json"
DIAGNOSTICS_FILE = ROOT / "diagnostics_log.json"
DEFAULT_POLICY_FILE = ROOT / "data" / "backhistory_policy.json"

QUERY = "(nuclear OR missile OR ceasefire OR strike OR escalation OR deterrence)"


@dataclass(frozen=True)
class Anchor:
    date: datetime
    probability: float


@dataclass(frozen=True)
class VolatilityBand:
    start: datetime
    end: datetime
    amplitude: float


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_utc_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def domain_weight_lookup(config: dict) -> list[tuple[str, float]]:
    import ast
    ingest_path = ROOT / "ingest.py"
    rows = []
    try:
        source = ingest_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        feeds = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "FEEDS":
                        feeds = ast.literal_eval(node.value)
                        break
        for feed in feeds:
            domain = (urlparse(feed.get("url", "")).netloc or "").lower()
            name = feed.get("name", "")
            default = float(feed.get("default_weight", 1.0))
            weight = float(config.get("source_weights", {}).get(name, default))
            if domain:
                rows.append((domain, weight))
    except Exception:
        pass
    return rows


def lookup_source_weight(url: str, domain_weights: list[tuple[str, float]]) -> float:
    domain = (urlparse(url).netloc or "").lower()
    for known, weight in domain_weights:
        if known and known in domain:
            return weight
    return 0.85


def fetch_gdelt_day(day: datetime, max_records: int = 80) -> list[dict]:
    start = day.strftime("%Y%m%d000000")
    end = day.strftime("%Y%m%d235959")
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc?"
        f"query={quote(QUERY)}&mode=ArtList&maxrecords={max_records}&format=json"
        f"&startdatetime={start}&enddatetime={end}"
    )
    req = Request(url, headers={"User-Agent": "nuclear-risk-dashboard-backfill"})
    with urlopen(req, timeout=40) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("articles", []) if isinstance(payload, dict) else []


def replay_from_articles(days: int, config: dict) -> tuple[list[dict], list[dict]]:
    domain_weights = domain_weight_lookup(config)
    state = BASELINE_STATE.copy()
    entries = []
    diagnostics = []

    end_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start_day = end_day - timedelta(days=days - 1)

    for idx in range(days):
        day = start_day + timedelta(days=idx)
        try:
            articles = fetch_gdelt_day(day)
        except Exception:
            articles = []

        events = []
        for article in articles:
            title = article.get("title", "")
            url = article.get("url", "")
            if not title or not url:
                continue
            events.append(
                {
                    "title": title,
                    "summary": article.get("seendate", ""),
                    "link": url,
                    "source": url,
                    "source_name": article.get("domain", "gdelt"),
                    "source_weight": lookup_source_weight(url, domain_weights),
                    "published": article.get("seendate", ""),
                }
            )

        updates, top_drivers, classified_count, paired_count, debug_drops = apply_event_impacts(state, events)
        coupled = apply_cross_state_coupling(updates)
        total_signal = sum(abs(v) for v in coupled.values())

        if total_signal == 0:
            state = decay_toward_baseline(state, BASELINE_STATE, multiplier=2.5)
        else:
            decayed = decay_toward_baseline(state, BASELINE_STATE)
            state = apply_updates_with_clamp(decayed, coupled)

        probability = round(compute_probability(state), 2)
        ts = day.strftime("%Y-%m-%d 00:00:00 UTC")
        entries.append({"ts": ts, "probability": probability})
        diagnostics.append(
            {
                "ts": ts,
                "probability": probability,
                "uncertainty": 18.0 if not top_drivers else 10.0,
                "state": state,
                "drop_reasons": debug_drops,
                "event_count": len(events),
                "classified_count": classified_count,
                "paired_count": paired_count,
            }
        )

    return entries, diagnostics


def load_policy(path: Path, current_probability: float) -> dict:
    if not path.exists():
        end = datetime.now(timezone.utc)
        return {
            "days": 365,
            "floor": 2.0,
            "ceiling": 35.0,
            "anchors": [
                {"date": (end - timedelta(days=364)).strftime("%Y-%m-%d"), "probability": round(current_probability + 4.0, 2)},
                {"date": end.strftime("%Y-%m-%d"), "probability": round(current_probability, 2)},
            ],
            "volatility_bands": [],
        }
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_policy_entries(policy: dict, current_probability: float) -> list[dict]:
    floor = float(policy.get("floor", 2.0))
    ceiling = float(policy.get("ceiling", 35.0))
    days = int(policy.get("days", 365))
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    anchors = [
        Anchor(parse_utc_date(a["date"]), clamp(float(a["probability"]), floor, ceiling)) for a in policy.get("anchors", [])
    ]
    if not anchors:
        anchors = [Anchor(end - timedelta(days=days - 1), clamp(current_probability + 4, floor, ceiling)), Anchor(end, current_probability)]
    anchors = sorted(anchors, key=lambda x: x.date)

    bands = [VolatilityBand(parse_utc_date(b["start_date"]), parse_utc_date(b["end_date"]), float(b.get("amplitude", 0))) for b in policy.get("volatility_bands", [])]

    def interp(day):
        if day <= anchors[0].date:
            return anchors[0].probability
        for i in range(1, len(anchors)):
            l, r = anchors[i - 1], anchors[i]
            if l.date <= day <= r.date:
                span = max((r.date - l.date).days, 1)
                return l.probability + (r.probability - l.probability) * ((day - l.date).days / span)
        return anchors[-1].probability

    rows = []
    start = end - timedelta(days=days - 1)
    for i in range(days):
        day = start + timedelta(days=i)
        amp = max((b.amplitude for b in bands if b.start <= day <= b.end), default=0.0)
        val = clamp(interp(day) + (math.sin(day.toordinal() * 0.42) * amp if amp else 0.0), floor, ceiling)
        rows.append({"ts": day.strftime("%Y-%m-%d 00:00:00 UTC"), "probability": round(val, 2)})
    return rows


def save_outputs(entries: list[dict], diagnostics: list[dict]) -> None:
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump({"entries": entries, "data": [{"t": e["ts"], "p": e["probability"]} for e in entries]}, f, indent=2)
    with DIAGNOSTICS_FILE.open("w", encoding="utf-8") as f:
        json.dump(diagnostics[-400:], f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["replay", "policy"], default="replay")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_FILE))
    args = parser.parse_args()

    with RISK_FILE.open("r", encoding="utf-8") as f:
        risk = json.load(f)
    current_probability = float(risk.get("probability", 12.0))
    config = load_config()

    if args.mode == "replay":
        try:
            entries, diagnostics = replay_from_articles(args.days, config)
            mode_used = "replay"
        except Exception:
            policy = load_policy(Path(args.policy), current_probability)
            entries = build_policy_entries(policy, current_probability)
            diagnostics = [{"ts": e["ts"], "probability": e["probability"], "uncertainty": 18.0, "state": BASELINE_STATE, "drop_reasons": {}, "event_count": 0, "classified_count": 0} for e in entries]
            mode_used = "policy-fallback"
    else:
        policy = load_policy(Path(args.policy), current_probability)
        entries = build_policy_entries(policy, current_probability)
        diagnostics = [{"ts": e["ts"], "probability": e["probability"], "uncertainty": 18.0, "state": BASELINE_STATE, "drop_reasons": {}, "event_count": 0, "classified_count": 0} for e in entries]
        mode_used = "policy"

    save_outputs(entries, diagnostics)
    print(f"Mode: {mode_used}")
    print(f"Wrote {len(entries)} history points")
    print(f"Wrote {min(len(diagnostics),400)} diagnostics points")


if __name__ == "__main__":
    main()
