import feedparser
import datetime
from difflib import SequenceMatcher

SIM_THRESHOLD = 0.82

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1004/rss.xml",
    "https://rss.cnn.com/rss/edition_world.rss",
    "https://feeds.reuters.com/Reuters/worldNews",
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.dw.com/xml/rss-en-all",
    "https://www.theguardian.com/world/rss"
]

def is_similar(a, b):
    return SequenceMatcher(None, a, b).ratio() > SIM_THRESHOLD

def dedupe(headlines):
    unique = []
    for h in headlines:
        if not any(is_similar(h[0], u[0]) for u in unique):
            unique.append(h)
    return unique

def fetch():
    out = []
    now = datetime.datetime.utcnow()

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries[:30]:
            try:
                title = e.title
                link = getattr(e, "link", "")
                pub = e.get("published_parsed")

                if pub:
                    dt = datetime.datetime(*pub[:6])
                    age = (now - dt).total_seconds() / 3600
                else:
                    age = 6

                out.append((title, age, link))
            except:
                continue

    return dedupe(out)
