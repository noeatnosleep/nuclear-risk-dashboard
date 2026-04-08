"""News ingestion with deduplication and source weighting."""

import hashlib
from difflib import SequenceMatcher

import feedparser

from config import load_config

FEEDS = [
    {
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "name": "bbc_world",
        "default_weight": 1.0,
    },
    {
        "url": "http://rss.cnn.com/rss/edition_world.rss",
        "name": "cnn_world",
        "default_weight": 0.95,
    },
    {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "name": "aljazeera_all",
        "default_weight": 0.95,
    },
]

MAX_ENTRIES_PER_FEED = 20
SIMILARITY_DROP_THRESHOLD = 0.94


def normalize_text(text):
    return " ".join((text or "").lower().split())


def dedupe_key(title, link):
    raw = f"{normalize_text(title)}|{(link or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_near_duplicate(normalized_title, seen_titles):
    for prior in seen_titles:
        if SequenceMatcher(a=normalized_title, b=prior).ratio() >= SIMILARITY_DROP_THRESHOLD:
            return True
    return False


def get_source_weight(feed_name, default_weight, config):
    return float(config.get("source_weights", {}).get(feed_name, default_weight))


def fetch_events():
    config = load_config()

    events = []
    seen = set()
    seen_titles = []

    for feed_info in FEEDS:
        url = feed_info["url"]
        source_name = feed_info["name"]
        source_weight = get_source_weight(source_name, feed_info["default_weight"], config)

        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")
            summary = entry.get("summary", "") or entry.get("description", "")

            key = dedupe_key(title, link)
            if key in seen:
                continue

            normalized_title = normalize_text(title)
            if is_near_duplicate(normalized_title, seen_titles):
                continue

            seen.add(key)
            seen_titles.append(normalized_title)

            events.append(
                {
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "source": url,
                    "source_name": source_name,
                    "source_weight": source_weight,
                    "published": published,
                    "dedupe_key": key,
                }
            )

    return events


if __name__ == "__main__":
    fetched = fetch_events()
    print("EVENT COUNT:", len(fetched))
    for event in fetched[:5]:
        print(event["title"])
