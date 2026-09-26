"""Step 3: join hand verdicts with lead evidence into data/attributions.json (what the site shows).

    python tools/export.py

One entry per anonymous source with at least one lead. Each lead carries the hand verdict,
attribution status, prior documentation and note from data/verdicts.csv, the automatic
catalogue flags from tools/leads.py, and every encoded incipit of the anonymous copy paired
with its best-matching incipit among the composer's copies (with the Plaine & Easie code of
both, so the site can render them side by side). Also writes data/anonymous_concordances.json.
Reads RISM through the local cache; needs the network only for records not yet cached.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import context  # noqa: E402
import rism  # noqa: E402
from leads import matches  # noqa: E402
from pae import anchored, movement_ordinals, pitches  # noqa: E402

VERDICTS = ["confirmed", "probable", "unresolved", "rejected"]
SHOWN = {"confirmed", "probable", "unresolved"}


def pae(inc):
    return {k: inc[k] for k in ("clef", "keysig", "timesig", "data")}


def lead_detail(anon_src, lead):
    anon = {i["inc"]: i for i in rism.incipits(anon_src)}
    pairs = []
    for m in lead["incipits"]:
        pair = {"incipit": m["inc"], "movement": m["movement"], "anon": pae(anon[m["inc"]]), "notes": m["notes"],
                "overlap": m["overlap"], "from_start": m["agree"], "counts": bool(m["source"] and matches(m))}
        if m["source"] and m["overlap"] >= 5:
            ci = {x["inc"]: x for x in rism.incipits(rism.source(m["source"]))}[m["source_inc"]]
            pair["match"] = {"source": m["source"], "incipit": m["source_inc"], "movement": m["source_movement"],
                             "offset": m["offset"], **pae(ci)}
        pairs.append(pair)
    return {"incipits": pairs, "movements": lead["movements"], "movements_matched": lead["movements_matched"],
            "sources": [{"id": cid, "label": rism.label(rism.source(cid))} for cid in lead["sources"][:12]]}


def concordances():
    """Anonymous sources whose incipits agree with another anonymous source's on two or more
    movements: at least eight agreeing pitches each, distinct movements on both sides (counted by
    pae.movement_ordinals), and Anonymus as the main creator of both records."""
    pairs = {}
    for slug in sorted(os.listdir("runs")):
        path = f"runs/{slug}/results.json"
        if not os.path.exists(path):
            continue
        with open(path) as f:
            results = json.load(f)
        for r in results:
            for c in r["candidates"]:
                if c["composer"] != "Anonymus":
                    continue
                key = tuple(sorted((r["id"], c["id"])))
                if key in pairs:
                    continue
                a, b = rism.source(r["id"]), rism.source(c["id"])
                if not (context.anonymous_creator(a) and context.anonymous_creator(b)):
                    continue
                ai, bi = rism.incipits(a), rism.incipits(b)
                aord = movement_ordinals([i["inc"] for i in ai])
                bord = movement_ordinals([i["inc"] for i in bi])
                agree = {}
                for x in ai:
                    for y in bi:
                        p, q = pitches(x["data"], x["keysig"]), pitches(y["data"], y["keysig"])
                        n, _, _ = anchored(p, q)
                        if n >= 8:
                            agree[aord[x["inc"]]] = max(agree.get(aord[x["inc"]], (0, 0)), (n, bord[y["inc"]]))
                if len(agree) >= 2 and len({v[1] for v in agree.values()}) >= 2:
                    first, second = (r["id"], c["id"])
                    pairs[key] = {"a": first, "a_label": rism.label(a), "b": second, "b_label": rism.label(b),
                                  "movements": [{"a": mv, "b": agree[mv][1], "pitches": agree[mv][0]} for mv in sorted(agree)]}
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
            entry = {"composer": lead["composer"], "verdict": v["verdict"], "attribution": v["attribution"],
                     "prior": v["prior"], "note": v["note"], "class": lead["class"],
                     "prior_documentation": lead["prior_documentation"], "attribution_flags": lead["attribution_flags"],
                     "movement_mismatch": lead["movement_mismatch"]}
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
