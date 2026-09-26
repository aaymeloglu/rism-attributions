"""Step 2: turn search hits into graded leads with the evidence a reviewer needs.

    python tools/leads.py symphonies

A lead is one (anonymous source, attributed composer) pair. It is kept when that composer's
copies match two or more movements, or one movement where no other named composer matches
and either two or more of the composer's copies match or the search returned at most two hits.
Records whose main creator is not Anonymus (RISM also lists records that only cross-reference
Anonymus, e.g. for an interpolated movement) are excluded.

For each incipit (identified by RISM's label and instrument; see compare()) the evidence records the best
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
from pae import anchored, dedup, figuration, pitches, sim  # noqa: E402

CATNO = re.compile(r"\b(Hob|RV|MH|KV|WoO|BWV|LaRue|ZakP|MurR|SmWV|LeeB|GraunWV|CSWV)\b")


MAX_FIGURATION = 0.5


def matches(m):
    """Does one incipit comparison count as the same music? Eight agreeing pitches, or six covering
    nearly all of a short incipit, and the agreeing stretch must not be mostly broken-chord
    or tremolo figuration (see pae.figuration)."""
    n = m["overlap"]
    if m.get("figuration", 0) > MAX_FIGURATION:
        return False
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


def _pair(p, q):
    n, i, j = anchored(p, q)
    return n, i, j, sim(p, q)


def compare(inc, cands):
    """Every attributed incipit agreeing with one anonymous incipit, best first.

    Each pair is compared with grace notes dropped and kept, on both sides, and the better
    reading counts. Among equally long agreements a same-key, same-instrument witness ranks
    first, so the explanation does not rest on whichever copy happened to score a pitch higher.
    Incipits are identified by RISM's own labels ("1.2.1 Largo") and instrument, never by a
    computed movement number: RISM's numbering mixes movements, sections, parts and separate
    pieces, and only a reader of the record can tell which.
    """
    readings = [pitches(inc["data"], inc["keysig"]), pitches(inc["data"], inc["keysig"], graces=True)]
    witnesses = []
    for cid, cincs in cands:
        for k, ci in enumerate(cincs):
            best = None
            for p in readings:
                for q in (pitches(ci["data"], ci["keysig"]), pitches(ci["data"], ci["keysig"], graces=True)):
                    n, i, j, agree = _pair(p, q)
                    cand = (n, agree, i, j, p, q)
                    if best is None or cand[:2] > best[:2]:
                        best = cand
            n, agree, i, j, p, q = best
            if n < 5:
                continue
            witnesses.append({"source": cid, "source_inc": ci["inc"], "source_voice": ci["voice"],
                              "source_first": k == 0, "source_keysig": ci["keysig"], "source_text": ci["text"],
                              "overlap": n, "agree": agree, "offset": [i, j],
                              "figuration": round(figuration(p, i, n), 2), "notes": len(dedup(p)),
                              "comparator_notes": len(dedup(q)),
                              "same_key": ci["keysig"] == inc["keysig"], "same_voice": bool(ci["voice"]) and ci["voice"] == inc["voice"]})
    witnesses.sort(key=lambda w: (-w["overlap"], -w["same_key"], -w["same_voice"], -w["agree"], w["source"], w["source_inc"]))
    base = {"inc": inc["inc"], "voice": inc["voice"], "keysig": inc["keysig"], "text": inc["text"],
            "notes": len(dedup(readings[0])), "agree": 0, "overlap": 0, "source": None}
    if witnesses:
        base.update({k: v for k, v in witnesses[0].items()})
        base["witnesses"] = [{k: w[k] for k in ("source", "source_inc", "source_voice", "overlap", "same_key", "same_voice")}
                             for w in witnesses[1:] if matches(w)][:8]
    return base


def evidence(lead):
    a = rism.source(lead["anon"])
    cand_srcs = [(cid, rism.source(cid)) for cid in lead["sources"][:12]]
    cands = [(cid, rism.incipits(s)) for cid, s in cand_srcs]
    ainc = rism.incipits(a)
    incs = [compare(inc, cands) for inc in ainc]
    counted = [m for m in incs if m["source"] and matches(m)]
    for m in incs:
        if m["source"]:
            m["text_agreement"] = context.text_agreement(m["text"], m["source_text"])
    yrs = rism.years(a)
    return {**lead, "incipits": incs,
            "incipits_matched": [m["inc"] for m in counted],
            "distinct_numbers_matched": sorted({re.match(r"[\d.]+", m["inc"]).group(0).rsplit(".", 1)[0] for m in counted
                                                if re.match(r"\d+\.\d+", m["inc"])}),
            "internal_matches": sorted({f"{m['inc']} -> {m['source']} {m['source_inc']}" for m in counted
                                        if m["inc"].split(" ")[0] != m["source_inc"].split(" ")[0]}),
            "vocal_matches": sorted({f"{m['source']} {m['source_inc']}" for m in counted if context.vocal_label(m["source_inc"])}),
            "text_mismatch": sorted({f"{m['inc']} / {m['source']} {m['source_inc']}" for m in counted if m.get("text_agreement") == "different"}),
            "transposed": any(context.keysig_fifths(m["keysig"]) != context.keysig_fifths(m["source_keysig"]) for m in counted),
            "key_label_mismatch": context.key_label_mismatch(lead["label"], ainc[0]["keysig"] if ainc else None),
            "life": [int(x) for x in re.findall(r"(\d{4})", lead["composer"])],
            "copy_years": [min(yrs), max(yrs)] if yrs else None,
            "names_composer": lead["composer"].split(",")[0].split(" (")[0] in json.dumps(a, ensure_ascii=False),
            "catalogue_number_in_title": bool(CATNO.search(lead["label"])),
            "prior_documentation": [{"source": c, "text": t} for c, t in context.prior_documentation(lead["anon"], a, cand_srcs)],
            "attribution_flags": context.attribution_flags(lead["composer"], cand_srcs),
            "anonymous_record_authorship": context.authorship_notes(a, lead["composer"]),
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
    n = len(e["incipits_matched"])
    if len(e["distinct_numbers_matched"]) >= 2:
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
