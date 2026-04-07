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

HARD = {
    "missile":5,"attack":4,"strike":4,"bomb":5,
    "deploy":4,"mobilize":4,"nuclear":10
}

SOFT = {
    "war":2,"conflict":2,"clash":2,"tension":2,
    "crisis":2,"threat":2,"military":1,"exercise":1,
    "rhetoric":1
}

ACTORS = {
    "iran":"middle_east","israel":"middle_east","gaza":"middle_east","lebanon":"middle_east",
    "russia":"europe","ukraine":"europe",
    "china":"asia","taiwan":"asia","north korea":"asia",
    "us":"global","america":"global","united states":"global"
}

REGION_BASELINE = {
    "middle_east":2.5,"europe":2.0,"asia":1.5,"global":2.0
}

RELATIONSHIP_WEIGHT = {
    ("iran","us"):2.5,
    ("iran","israel"):2.2,
    ("us","china"):2.0,
    ("russia","ukraine"):1.0,  # reduced heavily
    ("israel","gaza"):1.0,
    ("global","middle_east"):2.0
}

PERSISTENT_THEATERS = [
    {"russia","ukraine"},
    {"israel","gaza"}
]

ESCALATION_KEYWORDS = {
    "nuclear","nato","tactical","icbm","chemical","retaliation",
    "direct conflict","alliance","world war"
}

INTENT_WORDS = {"threat","warn","vow","rhetoric"}
PREPARATION_WORDS = {"deploy","mobilize","exercise"}
ACTION_WORDS = {"attack","strike","bomb"}
STRATEGIC_WORDS = {"nuclear","icbm"}

EVENT_MULTIPLIER = {
    "intent":0.3,
    "preparation":0.7,
    "action":1.2,
    "strategic":2.0
}

def tokenize(text):
    return re.findall(r"\b[a-z]+\b", text.lower())

def time_weight(h):
    return math.exp(-h/24)

def relationship_multiplier(actors):
    actors=list(set(actors))
    max_w=1.0

    for i in range(len(actors)):
        for j in range(i+1,len(actors)):
            pair=tuple(sorted((actors[i],actors[j])))
            max_w=max(max_w,RELATIONSHIP_WEIGHT.get(pair,1.0))

    return max_w

def is_persistent_theater(actors):
    a=set(actors)
    return any(t.issubset(a) for t in PERSISTENT_THEATERS)

def has_escalation(tokens):
    return any(t in ESCALATION_KEYWORDS for t in tokens)

def classify_event(tokens):
    if any(t in STRATEGIC_WORDS for t in tokens):
        return "strategic"
    if any(t in ACTION_WORDS for t in tokens):
        return "action"
    if any(t in PREPARATION_WORDS for t in tokens):
        return "preparation"
    if any(t in INTENT_WORDS for t in tokens):
        return "intent"
    return None

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
    tokens=tokenize(text)

    hard=[x for x in tokens if x in HARD]
    soft=[x for x in tokens if x in SOFT]
    actors=[x for x in tokens if x in ACTORS]

    if not actors:
        return 0,None,actors,[],False

    regions=list({ACTORS[x] for x in actors})

    if hard:
        base=max(HARD[x] for x in hard)
        is_hard=True
    elif soft:
        base=max(SOFT[x] for x in soft)*0.25
        is_hard=False
    else:
        return 0,None,actors,regions,False

    event_class=classify_event(tokens)
    event_mult=EVENT_MULTIPLIER.get(event_class,1.0)

    rel_mult=relationship_multiplier(actors)

    # THEATER SUPPRESSION (critical fix)
    if is_persistent_theater(actors) and not has_escalation(tokens):
        rel_mult *= 0.35  # aggressive suppression

    final=base * event_mult * rel_mult * time_weight(age)

    return final,"",actors,regions,is_hard

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

    total=0
    regions=set()
    hard_present=False

    for t,a,l in headlines:
        s,_,_,r,is_hard=score(t,a)

        if s==0:
            continue

        total+=s
        regions.update(r)

        if is_hard:
            hard_present=True

    baseline=sum(REGION_BASELINE.get(x,1) for x in regions)
    total+=baseline

    norm=total/max(len(regions),1)

    if norm<5:
        prob=1+norm
    elif norm<20:
        prob=6+(norm-5)*1.2
    else:
        prob=min(95,20+(norm-20)*1.5)

    if not hard_present:
        prob=min(prob,12)

    prob=round(prob,2)

    update_log(prob)

    with open("risk.json","w") as f:
        json.dump({
            "last_updated":datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "probability":prob
        },f,indent=2)

if __name__=="__main__":
    main()
