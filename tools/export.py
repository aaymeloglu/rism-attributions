"""Step 3: join hand verdicts with RISM data into data/attributions.json (what the site shows).

    python tools/export.py

One entry per anonymous source that has at least one lead. For each lead: the composer, the
verdict and note from data/verdicts.csv, and every movement paired with its best-matching
incipit among the composer's copies, with the Plaine & Easie code of both so the site can
render them side by side. Reads RISM through the local cache; needs the network only for
records not yet cached.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import rism  # noqa: E402
from pae import dedup, pitches, sim  # noqa: E402

VERDICTS = ["confirmed", "conflicting", "probable", "unresolved", "known", "rejected"]
SHOWN = {"confirmed", "conflicting", "probable", "unresolved"}


def pae(inc):
    return {k: inc[k] for k in ("clef", "keysig", "timesig", "data")}


def lead_detail(anon_src, lead):
    cands = [(cid, rism.source(cid)) for cid in lead["sources"][:12]]
    movements = []
    for inc in rism.incipits(anon_src):
        p = pitches(inc["data"], inc["keysig"])
        best = (0, None, None)
        for cid, cs in cands:
            for ci in rism.incipits(cs):
                v = sim(p, pitches(ci["data"], ci["keysig"]))
                if v > best[0]:
                    best = (v, cid, ci)
        m = {"movement": inc["inc"], "anon": pae(inc), "notes": len(dedup(p)), "agree": best[0]}
        if best[0] >= 5:
            m["match"] = {"source": best[1], "movement": best[2]["inc"], **pae(best[2])}
        movements.append(m)
    return {"composer": lead["composer"], "movements": movements,
            "sources": [{"id": cid, "label": rism.label(cs)} for cid, cs in cands]}


def concordances():
    """Anonymous sources matching another anonymous source on two or more movements."""
    pairs = {}
    for slug in sorted(os.listdir("runs")):
        path = f"runs/{slug}/results.json"
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for r in json.load(f):
                for c in r["candidates"]:
                    if c["composer"] == "Anonymus" and len(c["movements"]) >= 2:
                        key = tuple(sorted((r["id"], c["id"])))
                        if key not in pairs:
                            a, b = (rism.source(k) for k in key)
                            pairs[key] = {"a": key[0], "a_label": rism.label(a), "b": key[1], "b_label": rism.label(b),
                                          "movements": c["movements"]}
    return [pairs[k] for k in sorted(pairs)]


def main():
    with open("data/verdicts.csv") as f:
        verdicts = {(r["anon_id"], r["composer"]): r for r in csv.DictReader(f)}
    records = {}
    for slug in sorted(os.listdir("runs")):
        path = f"runs/{slug}/leads.json"
        if not os.path.exists(path):
            continue
        with open(path) as f:
            leads = json.load(f)
        for lead in leads:
            v = verdicts.get((lead["anon"], lead["composer"]))
            if v is None:
                sys.exit(f"no verdict for {lead['anon']} / {lead['composer']} in data/verdicts.csv")
            src = rism.source(lead["anon"])
            rec = records.setdefault(lead["anon"], {
                "id": lead["anon"], "genre": slug, "label": rism.label(src),
                "shelfmark": rism.label(src).split(";")[-1].strip(), "leads": []})
            entry = {"composer": lead["composer"], "verdict": v["verdict"], "note": v["note"], "class": lead["class"]}
            if v["verdict"] in SHOWN:
                entry.update(lead_detail(src, lead))
            rec["leads"].append(entry)
    for rec in records.values():
        rec["leads"].sort(key=lambda e: VERDICTS.index(e["verdict"]))
        rec["verdict"] = rec["leads"][0]["verdict"]
    out = sorted(records.values(), key=lambda r: (VERDICTS.index(r["verdict"]), r["leads"][0]["composer"], r["id"]))
    with open("data/attributions.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open("data/anonymous_concordances.json", "w") as f:
        json.dump(concordances(), f, ensure_ascii=False, indent=1)
    counts = {v: sum(1 for r in out if r["verdict"] == v) for v in VERDICTS}
    print(len(out), "records", counts)


if __name__ == "__main__":
    main()
