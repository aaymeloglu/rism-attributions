"""Step 2: turn search hits into graded leads with the evidence a reviewer needs.

    python tools/leads.py symphonies

A lead is one (anonymous source, attributed composer) pair. It is kept when that composer's
copies match two or more movements, or one movement where no other named composer matches
and either two or more of the composer's copies match or the search returned at most two hits.
Records whose main creator is not Anonymus (RISM also lists records that only cross-reference
Anonymus, e.g. for an interpolated movement) are excluded.

For each movement (see pae.movement_ordinals: not every incipit is a movement) the evidence records the best
pitch agreement with the composer's incipits, both from the start and with one incipit
starting partway into the other (so a part entering after rests still matches), and which of the comparator's movements it matched.
Each lead also carries catalogue context from tools/context.py: whether an attributed copy
already cites the anonymous copy, and whether the attribution is qualified, cross-referenced
to other composers, or a bare surname. Writes runs/<slug>/leads.json. Classes only order the
review; verdicts are made by hand in data/verdicts.csv.
"""
import collections
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
import context  # noqa: E402
import rism  # noqa: E402
from pae import anchored, dedup, movement_ordinals, pitches, sim  # noqa: E402

CATNO = re.compile(r"\b(Hob|RV|MH|KV|WoO|BWV|LaRue|ZakP|MurR|SmWV|LeeB|GraunWV|CSWV)\b")


def matches(m):
    """Does one incipit comparison count as the same music? Eight agreeing pitches, or six covering
    nearly all of a short incipit."""
    n = m["overlap"]
    return n >= 8 or (n >= 6 and n >= 0.8 * min(m["notes"], m["comparator_notes"]))


def build_leads(results):
    leads = []
    for r in results:
        if not context.anonymous_creator(rism.source(r["id"])):
            continue
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
                if any(v["movs"] & w["movs"] for c, w in by.items() if c != comp):
                    continue
                if len(v["srcs"]) < 2 and min(total.get(x, 99) for x in v["movs"]) > 2:
                    continue
            leads.append({"anon": r["id"], "label": r["label"], "composer": comp,
                          "matched": sorted(v["movs"]), "sources": sorted(v["srcs"])})
    return leads


def compare(inc, ordinal, cands):
    p = pitches(inc["data"], inc["keysig"])
    best = {"inc": inc["inc"], "movement": ordinal, "notes": len(dedup(p)),
            "agree": 0, "overlap": 0, "source": None}
    for cid, cincs in cands:
        cord = movement_ordinals([ci["inc"] for ci in cincs])
        for ci in cincs:
            q = pitches(ci["data"], ci["keysig"])
            n, i, j = anchored(p, q)
            key = (n, sim(p, q))
            if key > (best["overlap"], best["agree"]):
                best.update(agree=key[1], overlap=n, offset=[i, j], source=cid, source_inc=ci["inc"],
                            source_movement=cord[ci["inc"]], comparator_notes=len(dedup(q)))
    return best


def evidence(lead):
    a = rism.source(lead["anon"])
    cand_srcs = [(cid, rism.source(cid)) for cid in lead["sources"][:12]]
    cands = [(cid, rism.incipits(s)) for cid, s in cand_srcs]
    ainc = rism.incipits(a)
    aord = movement_ordinals([i["inc"] for i in ainc])
    incs = [compare(inc, aord[inc["inc"]], cands) for inc in ainc]
    movements = {}
    for m in incs:
        movements.setdefault(m["movement"], []).append(m)
    matched = sorted(mv for mv, ms in movements.items() if any(x["source"] and matches(x) for x in ms))
    internal = sorted({f"{x['movement']}->{x['source_movement']}" for x in incs
                       if x["source"] and matches(x) and x["source_movement"] != x["movement"]})
    for m in incs:
        if m["source"]:
            m["source_label"] = rism.label(rism.source(m["source"]))
            m["source_keysig"] = next(ci["keysig"] for cid, cincs in cands if cid == m["source"] for ci in cincs if ci["inc"] == m["source_inc"])
            m["keysig"] = next(i["keysig"] for i in ainc if i["inc"] == m["inc"])
    counted = [m for m in incs if m["source"] and matches(m)]
    yrs = rism.years(a)
    return {**lead, "incipits": incs,
            "vocal_matches": sorted({f"{m['source']} {m['source_inc']}" for m in counted if context.vocal_label(m["source_inc"])}),
            "transposed": any(context.keysig_fifths(m["keysig"]) != context.keysig_fifths(m["source_keysig"]) for m in counted),
            "key_label_mismatch": context.key_label_mismatch(lead["label"], ainc[0]["keysig"] if ainc else None), "movements": sorted(movements), "movements_matched": matched,
            "movement_mismatch": internal,
            "life": [int(x) for x in re.findall(r"(\d{4})", lead["composer"])],
            "copy_years": [min(yrs), max(yrs)] if yrs else None,
            "names_composer": lead["composer"].split(",")[0].split(" (")[0] in json.dumps(a, ensure_ascii=False),
            "catalogue_number_in_title": bool(CATNO.search(lead["label"])),
            "prior_documentation": [{"source": c, "text": t} for c, t in context.prior_documentation(lead["anon"], a, cand_srcs)],
            "attribution_flags": context.attribution_flags(lead["composer"], cand_srcs),
            "competitors": specificity(a, lead)}


def specificity(a, lead):
    """Composers other than the lead's returned by a five-bar search of each matched incipit."""
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
    if e["names_composer"] or e["catalogue_number_in_title"] or e["prior_documentation"]:
        return "known"
    if e["life"] and e["copy_years"] and e["copy_years"][1] < e["life"][0] + 12:
        return "date-impossible"
    if len(e["life"]) > 1 and e["life"][1] < 1690:
        return "date-early"  # possible (an older sinfonia, a later arrangement); review, do not reject
    n = len(e["movements_matched"])
    if n >= 2:
        return "strong"
    if n and len(e["sources"]) >= 2:
        return "good"
    if n:
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
