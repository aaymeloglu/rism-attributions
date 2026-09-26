"""Step 2: turn search hits into graded leads with the evidence a reviewer needs.

    python tools/leads.py symphonies

A lead is one (anonymous source, attributed composer) pair. It is kept when the composer's
copies match two or more movements, or one movement where no other named composer matches
and either two or more of the composer's copies match or the search returned at most two hits.

For each lead this records how many notes of each movement agree with the composer's best
matching incipit (transposition-invariant, repeated notes collapsed), whether the composer's
dates are possible for the copy, whether the record already names the composer or a thematic
catalogue number, and which composers a five-bar re-search returns.
Writes runs/<slug>/leads.json. Classes are triage only; verdicts are made by hand in
data/verdicts.csv.
"""
import collections
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
import rism  # noqa: E402
from pae import dedup, pitches, sim  # noqa: E402

CATNO = re.compile(r"\b(Hob|RV|MH|KV|WoO|BWV|LaRue|ZakP|MurR|SmWV|LeeB|GraunWV|CSWV)\b")


def build_leads(results):
    leads = []
    for r in results:
        moves = [m for m in r["movements"] if "error" not in m]
        total = {m["inc"]: m["total"] for m in moves}
        by = collections.defaultdict(lambda: {"movs": set(), "srcs": set()})
        for c in r["candidates"]:
            if c["composer"] in ("Anonymus", ""):
                continue
            by[c["composer"]]["movs"] |= set(c["movements"])
            by[c["composer"]]["srcs"].add(c["id"])
        for comp, v in by.items():
            if len(v["movs"]) == 1:
                mv = next(iter(v["movs"]))
                if any(mv in w["movs"] for c, w in by.items() if c != comp):
                    continue
                if len(v["srcs"]) < 2 and total.get(mv, 99) > 2:
                    continue
            leads.append({"anon": r["id"], "label": r["label"], "composer": comp,
                          "matched": sorted(v["movs"]), "sources": sorted(v["srcs"])})
    return leads


def evidence(lead):
    a = rism.source(lead["anon"])
    text = json.dumps(a, ensure_ascii=False)
    life = [int(x) for x in re.findall(r"(\d{4})", lead["composer"])]
    cands = [(cid, rism.incipits(rism.source(cid))) for cid in lead["sources"][:12]]
    movements = []
    for inc in rism.incipits(a):
        p = pitches(inc["data"], inc["keysig"])
        best = (0, None, None)
        for cid, cincs in cands:
            for ci in cincs:
                v = sim(p, pitches(ci["data"], ci["keysig"]))
                if v > best[0]:
                    best = (v, cid, ci["inc"])
        movements.append({"inc": inc["inc"], "notes": len(dedup(p)), "agree": best[0], "source": best[1], "source_inc": best[2]})
    yrs = rism.years(a)
    surname = lead["composer"].split(",")[0].split(" (")[0]
    return {**lead, "movements": movements, "life": life, "copy_years": [min(yrs), max(yrs)] if yrs else None,
            "names_composer": surname in text, "catalogue_number_in_title": bool(CATNO.search(lead["label"])),
            "competitors": specificity(a, lead)}


def specificity(a, lead):
    """Composers other than the lead's returned by a five-bar search of each matched movement."""
    other = set()
    for inc in rism.incipits(a):
        if inc["inc"] not in lead["matched"]:
            continue
        frag = "/".join([m for m in inc["data"].split("/") if m.strip()][:5])
        try:
            r = rism.search_incipit(frag, inc["keysig"], inc["timesig"])
        except Exception:
            continue
        for item in r.get("items", []):
            src = item["id"].split("/incipits")[0]
            if rism.rid(src) == lead["anon"]:
                continue
            c = rism.creator(rism.get(src))
            if c not in ("Anonymus", "") and c.split(" (")[0] != lead["composer"].split(" (")[0]:
                other.add(c)
    return sorted(other)


def classify(e):
    if e["names_composer"] or e["catalogue_number_in_title"]:
        return "known"
    if e["life"] and e["copy_years"]:
        if e["copy_years"][1] < e["life"][0] + 12:
            return "date-impossible"
    if len(e["life"]) > 1 and e["life"][1] < 1690:
        return "date-impossible"
    full = [m for m in e["movements"] if m["agree"] >= 6 and m["agree"] >= min(m["notes"], 10)]
    if len(full) >= 2:
        return "strong"
    if full and len(e["sources"]) >= 2:
        return "good"
    if full:
        return "plausible"
    return "weak"


def main(slug):
    with open(f"runs/{slug}/results.json") as f:
        results = json.load(f)
    leads = build_leads(results)
    with ThreadPoolExecutor(6) as ex:
        out = list(ex.map(evidence, leads))
    for e in out:
        e["class"] = classify(e)
    out.sort(key=lambda e: (e["anon"], e["composer"]))
    with open(f"runs/{slug}/leads.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(len(out), "leads", dict(collections.Counter(e["class"] for e in out)))


if __name__ == "__main__":
    main(sys.argv[1])
