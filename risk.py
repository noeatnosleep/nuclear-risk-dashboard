import feedparser
import datetime
import json
import math
import re
import os
from urllib.parse import urlparse

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

LOG_FILE = "history_log.json"
MAX_LOG_ENTRIES = 200

DECAY = 0.3

KEYWORDS = {
    "missile":4,"attack":3,"strike":3,"bomb":4,"drone":2,
    "war":2,"conflict":2,"clash":2,"tension":2,
    "crisis":3,"threat":3,"deploy":3,"mobilize":3,
    "military":2,"exercise":1,"nuclear":10
}

ACTORS = {
    "iran":"middle_east","israel":"middle_east","gaza":"middle_east",
    "russia":"europe","ukraine":"europe",
    "china":"asia","taiwan":"asia","north korea":"asia"
}

REGION_BASELINE = {
    "middle_east":2.5,"europe":2.0,"asia":1.5
}

def tokenize(text):
    return re.findall(r"\b[a-z]+\b", text.lower())

def time_weight(h):
    return math.exp(-h/24)

def fetch():
    out=[]
    now=datetime.datetime.utcnow()

    for url in RSS_FEEDS:
        feed=feedparser.parse(url)
        for e in feed.entries[:30]:
            try:
                title=e.title
                link=getattr(e,"link","")
                pub=e.get("published_parsed")
                if pub:
                    dt=datetime.datetime(*pub[:6])
                    age=(now-dt).total_seconds()/3600
                else:
                    age=6
                out.append((title,age,link))
            except:
                continue
    return out

def score(text,age):
    t=tokenize(text)
    matches=[x for x in t if x in KEYWORDS]
    actors=[x for x in t if x in ACTORS]

    if not matches or not actors:
        return 0,[],[],[]

    regions=list({ACTORS[x] for x in actors})
    base=sum(KEYWORDS[x] for x in matches)

    return base*time_weight(age),matches,actors,regions

def load(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}

def save(path,data):
    with open(path,"w") as f:
        json.dump(data,f)

def update_log(prob):
    log=load(LOG_FILE)
    arr=log.get("data",[])

    now=datetime.datetime.utcnow()

    if not arr:
        arr=[]
        for i in range(5):
            t=(now - datetime.timedelta(minutes=(5-i)*6)).isoformat()
            arr.append({"t":t,"p":prob})
    else:
        arr.append({"t":now.isoformat(),"p":prob})

    arr=arr[-MAX_LOG_ENTRIES:]
    save(LOG_FILE,{"data":arr})

def main():
    headlines=fetch()

    clusters={}
    scored=[]

    for t,a,l in headlines:
        s,m,ac,r=score(t,a)
        if s == 0:
            continue

        # cluster key = actors + top keywords
        key = tuple(sorted(set(ac))) + tuple(sorted(set(m)))

        if key not in clusters:
            clusters[key] = []
        clusters[key].append((s,t,m,ac,r,l))

    total=0
    regions=set()

    for key,items in clusters.items():
        # cap cluster impact (prevents spam amplification)
        cluster_score = sum(x[0] for x in items)
        cluster_score = min(cluster_score, max(x[0] for x in items) * 2)

        total += cluster_score

        for x in items:
            regions.update(x[4])
            scored.append(x)

    baseline=sum(REGION_BASELINE.get(x,1) for x in regions)
    total+=baseline

    norm=total/max(len(regions),1)

    if norm<5:
        prob=1+norm
    elif norm<20:
        prob=6+(norm-5)*1.2
    else:
        prob=min(95,20+(norm-20)*1.5)

    prob=round(prob,2)

    update_log(prob)

    top=sorted(scored,reverse=True)[:5]

    out={
        "last_updated":datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "probability":prob,
        "top_drivers":[
            {
                "title":x[1],
                "actors":x[3],
                "matches":x[2],
                "source":urlparse(x[5]).netloc,
                "link":x[5]
            } for x in top
        ]
    }

    with open("risk.json","w") as f:
        json.dump(out,f,indent=2)

if __name__=="__main__":
    main()
