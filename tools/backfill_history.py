"""Build historical risk/diagnostics via true article replay only.

This tool intentionally does not generate synthetic baseline/policy history.
If replay fails, it exits non-zero so callers can detect missing real data.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import load_config
from risk import (
    apply_cross_state_coupling,
    apply_event_impacts,
    apply_updates_with_clamp,
    compute_probability,
    decay_toward_baseline,
)
from states import BASELINE_STATE

HISTORY_FILE = ROOT / "history_log.json"
DIAGNOSTICS_FILE = ROOT / "diagnostics_log.json"
POLICY_FILE = ROOT / "data" / "backhistory_policy.json"

QUERY = "(nuclear OR missile OR ceasefire OR strike OR escalation OR deterrence OR war OR military OR sanctions OR conflict)"


def domain_weight_lookup(config: dict) -> list[tuple[str, float]]:
    import ast

    ingest_path = ROOT / "ingest.py"
    rows = []
    source = ingest_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    feeds = []
    for node in tree.body:
        if getattr(node, "targets", None):
            for target in node.targets:
                if getattr(target, "id", "") == "FEEDS":
                    feeds = ast.literal_eval(node.value)
                    break
    for feed in feeds:
        domain = (urlparse(feed.get("url", "")).netloc or "").lower()
        name = feed.get("name", "")
        default = float(feed.get("default_weight", 1.0))
        weight = float(config.get("source_weights", {}).get(name, default))
        if domain:
            rows.append((domain, weight))
    return rows


def lookup_source_weight(url: str, domain_weights: list[tuple[str, float]]) -> float:
    domain = (urlparse(url).netloc or "").lower()
    for known, weight in domain_weights:
        if known and known in domain:
            return weight
    return 0.85


def fetch_gdelt_day(day: datetime, max_records: int = 220) -> list[dict]:
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
    if not isinstance(payload, dict):
        return []
    return payload.get("articles", [])


def replay_from_articles(days: int, config: dict) -> tuple[list[dict], list[dict]]:
    domain_weights = domain_weight_lookup(config)
    state = BASELINE_STATE.copy()
    entries = []
    diagnostics = []

    end_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start_day = end_day - timedelta(days=days - 1)

    for idx in range(days):
        day = start_day + timedelta(days=idx)
        articles = fetch_gdelt_day(day)

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
                "drivers": sorted(top_drivers, key=lambda row: abs(row.get("impact", 0)), reverse=True)[:256],
                "history_source": "gdelt_replay",
            }
        )

    return entries, diagnostics


def save_outputs(entries: list[dict], diagnostics: list[dict]) -> None:
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump({"entries": entries, "data": [{"t": e["ts"], "p": e["probability"]} for e in entries]}, f, indent=2)
    with DIAGNOSTICS_FILE.open("w", encoding="utf-8") as f:
        json.dump(diagnostics[-400:], f, indent=2)


def write_policy_metadata(days: int) -> None:
    payload = {
        "mode": "replay",
        "days": days,
        "note": "Synthetic/policy history disabled. This file is metadata only.",
    }
    with POLICY_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()

    config = load_config()
    entries, diagnostics = replay_from_articles(args.days, config)
    save_outputs(entries, diagnostics)
    write_policy_metadata(args.days)

    print("Mode: replay")
    print(f"Wrote {len(entries)} history points")
    print(f"Wrote {min(len(diagnostics), 400)} diagnostics points")


if __name__ == "__main__":
    main()
