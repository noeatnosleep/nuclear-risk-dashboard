import feedparser
from datetime import datetime


FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "http://rss.cnn.com/rss/edition_world.rss",
    "https://www.aljazeera.com/xml/rss/all.xml"
]


def fetch_events():
    events = []

    for url in FEEDS:
        try:
            feed = feedparser.parse(url)

            for entry in feed.entries[:10]:
                events.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "source": url,
                    "published": entry.get("published", "")
                })

        except Exception as e:
            continue

    return events


if __name__ == "__main__":
    ev = fetch_events()
    print("EVENT COUNT:", len(ev))
    for e in ev[:5]:
        print(e["title"])
