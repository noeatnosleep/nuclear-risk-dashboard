"""News ingestion with deduplication and source weighting."""

import hashlib

import feedparser

FEEDS = [
    {
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "name": "bbc_world",
        "weight": 1.0,
    },
    {
        "url": "http://rss.cnn.com/rss/edition_world.rss",
        "name": "cnn_world",
        "weight": 0.95,
    },
    {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "name": "aljazeera_all",
        "weight": 0.95,
    },
]

MAX_ENTRIES_PER_FEED = 20


def normalize_title(title):
    return " ".join((title or "").lower().split())


def dedupe_key(title, link):
    raw = f"{normalize_title(title)}|{(link or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def fetch_events():
    config = load_config()

    events = []
    seen = set()

    for feed_info in FEEDS:
        url = feed_info["url"]
        source_name = feed_info["name"]
        source_weight = float(feed_info["weight"])

        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")

            key = dedupe_key(title, link)
            if key in seen:
                continue
            seen.add(key)

            events.append({
                "title": title,
                "link": link,
                "source": url,
                "source_name": source_name,
                "source_weight": source_weight,
                "published": published,
                "dedupe_key": key,
            })

    return events


if __name__ == "__main__":
    ev = fetch_events()
    print("EVENT COUNT:", len(ev))
    for event in ev[:5]:
        print(event["title"])
