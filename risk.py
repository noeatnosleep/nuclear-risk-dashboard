import feedparser
import datetime
import json
import math
import re
import os
from collections import defaultdict
from urllib.parse import urlparse

RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.npr.org/1004/rss.xml"
]

HISTORY_FILE = "history.json"
LOG_FILE = "history_log.json"

DECAY = 0.6
MAX_LOG_ENTRIES = 200

KEYWORDS = {
    "missile":4,"attack":3,"strike":3,"bomb":4,"drone":2,
    "war":2,"conflict":2,"clash":2,"tension":2,
    "crisis":3,"threat":3,"deploy":3,"mobilize":3,
    "military":2,"exercise":1,"nuclear":10
}

SEQUENCE_STAGES = {
    "threat":1,"deploy":2,"mobilize":2,
    "strike":3,"attack":3,"missile":3,"bomb":3
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
    m=[x for x in t if x in KEYWORDS]
    a=[x for x in t if x in ACTORS]

    if not m or not a:
        return 0,[],[],[],0

    r=list({ACTORS[x] for x in a})
    base=sum(KEYWORDS[x] for x in m)
    stage=max([SEQUENCE_STAGES.get(x,0) for x in m],default=0)
    mult=[1,0.6,1.1,1.5][stage] if stage<=3 else 1.5

    return base*time_weight(age)*mult,m,a,r,stage

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
        # seed with time-separated points (fixes invisible chart)
        arr=[]
        for i in range(5):
            t = (now - datetime.timedelta(minutes=(5-i)*6)).isoformat()
            arr.append({"t":t,"p":prob})
    else:
        arr.append({"t":now.isoformat(),"p":prob})

    arr=arr[-MAX_LOG_ENTRIES:]
    save(LOG_FILE,{"data":arr})

def main():
    headlines=fetch()
    history=load(HISTORY_FILE)

    grouped=defaultdict(float)
    regions=set()
    scored=[]

    for t,a,l in headlines:
        s,m,ac,r,stage=score(t,a)
        if s>0:
            key=tuple(sorted(set(m+ac)))
            grouped[str(key)]+=s
            regions.update(r)
            scored.append((s,t,m,ac,r,l))

    total=0
    new_hist={}

    for k,v in grouped.items():
        prev=history.get(k,0)
        combined=v+prev*DECAY
        new_hist[k]=combined
        total+=combined

    save(HISTORY_FILE,new_hist)

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
