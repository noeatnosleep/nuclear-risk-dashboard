"""News ingestion with deduplication and source weighting."""

import hashlib
from difflib import SequenceMatcher

import feedparser

from config import load_config

FEEDS = [
    {"url": "http://feeds.bbci.co.uk/news/world/rss.xml", "name": "bbc_world", "default_weight": 1.0},
    {"url": "http://rss.cnn.com/rss/edition_world.rss", "name": "cnn_world", "default_weight": 0.95},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml", "name": "aljazeera_all", "default_weight": 0.95},
    {"url": "https://www.reuters.com/world/rss", "name": "reuters_world", "default_weight": 1.0},
    {"url": "https://www.theguardian.com/world/rss", "name": "guardian_world", "default_weight": 0.9},
    {"url": "https://feeds.npr.org/1004/rss.xml", "name": "npr_world", "default_weight": 0.85},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "name": "nyt_world", "default_weight": 0.95},
    {"url": "https://feeds.washingtonpost.com/rss/world", "name": "wapo_world", "default_weight": 0.9},
    {"url": "https://www.france24.com/en/rss", "name": "france24_world", "default_weight": 0.9},
    {"url": "https://www.dw.com/en/top-stories/s-9097?maca=en-rss-en-top-1022-rdf", "name": "dw_top", "default_weight": 0.9},
    {"url": "https://news.un.org/feed/subscribe/en/news/all/rss.xml", "name": "un_news", "default_weight": 1.05},
    {"url": "https://www.iaea.org/newscenter/rss", "name": "iaea_news", "default_weight": 1.1},
    {"url": "https://www.state.gov/feeds/press-releases.xml", "name": "us_state_press", "default_weight": 1.05},
    {"url": "https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=945&max=20", "name": "us_defense_news", "default_weight": 1.05},
    {"url": "https://www.whitehouse.gov/briefing-room/feed/", "name": "whitehouse_briefing", "default_weight": 1.0},
    {"url": "https://www.nato.int/cps/en/natohq/news.htm?displayMode=rss", "name": "nato_news", "default_weight": 1.0},
    {"url": "https://www.oecd.org/newsroom/index.xml", "name": "oecd_news", "default_weight": 0.85},
    {"url": "https://www.csis.org/analysis/rss.xml", "name": "csis_analysis", "default_weight": 0.8},
    {"url": "https://carnegieendowment.org/rss/all.xml", "name": "carnegie_all", "default_weight": 0.8},
    {"url": "https://www.crisisgroup.org/rss", "name": "crisisgroup", "default_weight": 0.9},
    {"url": "https://www.armscontrol.org/feeds/all", "name": "armscontrol", "default_weight": 0.95},
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
