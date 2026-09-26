"""Small cached client for the RISM Online JSON-LD API (https://rism.online)."""
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

BASE = "https://rism.online"
ANONYMUS = "https://rism.online/people/30004985"
HEADERS = {"Accept": "application/ld+json", "User-Agent": "rism-attributions (github.com/aaymeloglu/rism-attributions)"}
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "rism")


def get(url):
    """GET a RISM Online URL as JSON, cached on disk by URL."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, hashlib.md5(url.encode()).hexdigest() + ".json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    data = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            data = json.load(urllib.request.urlopen(req, timeout=90))
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def source(rism_id):
    return get(f"{BASE}/sources/{rism_id}")


def label(obj):
    lab = (obj or {}).get("label", {})
    return (lab.get("en") or lab.get("none") or [""])[0]


def creator(src):
    return label(((src.get("creator") or {}).get("relatedTo")) or {})


def rid(url):
    return url.rstrip("/").split("/")[-1]


def incipits(src):
    """Encoded incipits of a source: [{inc, clef, keysig, timesig, data}]."""
    out = []
    for it in (src.get("incipits") or {}).get("items", []):
        enc = it.get("encodings")
        if not enc:
            continue
        d = enc[0]["data"]
        text = voice = ""
        for x in it.get("summary", []):
            lab = (x.get("label") or {}).get("en", [""])[0]
            val = (x.get("value") or {}).get("none", [""])
            if lab == "Text incipit":
                text = val[0] if val else ""
            elif lab == "Voice/instrument":
                voice = val[0] if val else ""
        out.append({"inc": it["label"]["none"][0], "clef": d.get("clef", ""), "keysig": d.get("keysig", ""),
                    "timesig": d.get("timesig", ""), "data": d.get("data", ""), "text": text, "voice": voice})
    return out


def years(src):
    text = json.dumps(src.get("materialGroups", ""), ensure_ascii=False)
    return [int(y) for y in re.findall(r"\b(1[5-9]\d\d)\b", text)]


def anonymous_sources(subject):
    """All sources by 'Anonymus' with encoded incipits for a RISM subject heading."""
    ids, page = [], 1
    q = urllib.parse.quote(subject)
    while True:
        d = get(f"{ANONYMUS}/sources?rows=100&page={page}&fq=has-incipits:true&fq=subjects:{q}")
        ids += [i["id"] for i in d["items"]]
        if page >= d["view"].get("totalPages", 1):
            return ids
        page += 1


def search_incipit(pae, keysig="", timesig="", rows=100):
    q = {"mode": "incipits", "rows": str(rows), "n": pae}
    if keysig:
        q["ik"] = keysig
    if timesig:
        q["it"] = timesig
    return get(f"{BASE}/search?" + urllib.parse.urlencode(q))
