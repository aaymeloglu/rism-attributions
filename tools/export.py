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
from pae import anchored, pitches  # noqa: E402

VERDICTS = ["confirmed", "probable", "unresolved", "rejected"]
SHOWN = {"confirmed", "probable", "unresolved"}


def pae(inc):
    return {k: inc[k] for k in ("clef", "keysig", "timesig", "data")}


def lead_detail(anon_src, lead):
    anon = {i["inc"]: i for i in rism.incipits(anon_src)}
    pairs = []
    for m in lead["incipits"]:
        a = anon[m["inc"]]
        pair = {"incipit": m["inc"], "voice": a["voice"], "text": a["text"], "anon": pae(a), "notes": m["notes"],
                "overlap": m["overlap"], "from_start": m["agree"], "counts": bool(m["source"] and matches(m))}
        if m["source"] and m["overlap"] >= 5:
            ci = {x["inc"]: x for x in rism.incipits(rism.source(m["source"]))}[m["source_inc"]]
            pair["match"] = {"source": m["source"], "incipit": m["source_inc"], "voice": ci["voice"], "text": ci["text"],
                             "offset": m["offset"], "first": m["source_first"], **pae(ci)}
            pair["witnesses"] = m.get("witnesses", [])
        pairs.append(pair)
    return {"incipits": pairs, "incipits_matched": lead["incipits_matched"],
            "sources": [{"id": cid, "label": rism.label(rism.source(cid))} for cid in lead["sources"][:12]]}


def concordance_candidates():
    """Anonymous sources whose incipits agree with another anonymous source's on two or more
    incipits with different RISM numbers (at least eight agreeing pitches each, both matched from
    the start) and Anonymus as the main creator of both records. These are candidates: each needs
    a verdict in data/concordance_verdicts.csv before the site presents it as a concordance."""
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
                a, b = rism.source(key[0]), rism.source(key[1])
                if not (context.anonymous_creator(a) and context.anonymous_creator(b)):
                    continue
                agree = []
                for x in rism.incipits(a):
                    for y in rism.incipits(b):
                        n, i, j = anchored(pitches(x["data"], x["keysig"]), pitches(y["data"], y["keysig"]))
                        if n >= 8 and i == 0 and j == 0:
                            agree.append({"a": x["inc"], "b": y["inc"], "pitches": n})
                nums_a = {m["a"].split(" ")[0].rsplit(".", 1)[0] for m in agree}
                nums_b = {m["b"].split(" ")[0].rsplit(".", 1)[0] for m in agree}
                if len(nums_a) >= 2 and len(nums_b) >= 2:
                    documented = [t for _, t in context.prior_documentation(key[0], a, [(key[1], b)])]
                    documented += [t for _, t in context.prior_documentation(key[1], b, [(key[0], a)])]
                    pairs[key] = {"a": key[0], "a_label": rism.label(a), "b": key[1], "b_label": rism.label(b),
                                  "incipits": agree, "already_documented": bool(documented)}
    return [pairs[k] for k in sorted(pairs)]


def main():
    with open("data/verdicts.csv") as f:
        verdicts = {(r["anon_id"], r["composer"]): r for r in csv.DictReader(f)}
    records = {}
    # A source with leads in several genres keeps the genre of the earliest run (same-day runs by
    # name), and each (source, composer) lead appears once.
    with open("data/genres.json") as f:
        run = {g["slug"]: g.get("run", "9999") for g in json.load(f)}
    slugs = sorted(os.listdir("runs"), key=lambda s: (run.get(s, "9999"), s))
    for slug in slugs:
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
            if any(e["composer"] == lead["composer"] for e in rec["leads"]):
                continue
            entry = {"composer": lead["composer"], "identity": v.get("identity", ""), "verdict": v["verdict"], "attribution": v["attribution"],
                     "prior": v["prior"], "note": v["note"], "class": lead["class"],
                     "prior_documentation": lead["prior_documentation"], "attribution_flags": lead["attribution_flags"],
                     "internal_matches": lead["internal_matches"],
                     "anonymous_record_authorship": lead["anonymous_record_authorship"]}
            if v["verdict"] in SHOWN:
                entry.update(lead_detail(src, lead))
            rec["leads"].append(entry)
    for rec in records.values():
        rec["leads"].sort(key=lambda e: VERDICTS.index(e["verdict"]))
        rec["verdict"] = rec["leads"][0]["verdict"]
    out = sorted(records.values(), key=lambda r: (VERDICTS.index(r["verdict"]), r["leads"][0]["composer"], r["id"]))
    with open("data/attributions.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open("data/concordance_verdicts.csv") as f:
        cv = {(r["a"], r["b"]): r for r in csv.DictReader(f)}
    conc = []
    for c in concordance_candidates():
        v = cv.get((c["a"], c["b"]))
        conc.append({**c, "verdict": v["verdict"] if v else "unreviewed", "note": v["note"] if v else ""})
    # A pair RISM already links is a verified concordance, not a new one; the site says which.
    with open("data/anonymous_concordances.json", "w") as f:
        json.dump(conc, f, ensure_ascii=False, indent=1)
    counts = {v: sum(1 for r in out if r["verdict"] == v) for v in VERDICTS}
    print(len(out), "records", counts)


if __name__ == "__main__":
    main()
