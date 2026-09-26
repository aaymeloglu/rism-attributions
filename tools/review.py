"""Print leads for hand review: each movement of the anonymous copy next to its best match.

    python tools/review.py concertos                 # all leads without a verdict yet
    python tools/review.py concertos --class good    # only one triage class
    python tools/review.py concertos --id 400012345  # one anonymous source
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import rism  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--class", dest="cls")
    ap.add_argument("--id")
    ap.add_argument("--all", action="store_true", help="include leads that already have a verdict")
    a = ap.parse_args()
    with open(f"runs/{a.slug}/leads.json") as f:
        leads = json.load(f)
    with open("data/verdicts.csv") as f:
        done = {(r["anon_id"], r["composer"]) for r in csv.DictReader(f)}
    for e in leads:
        if a.cls and e["class"] != a.cls or a.id and e["anon"] != a.id:
            continue
        if not a.all and (e["anon"], e["composer"]) in done:
            continue
        anon = {i["inc"]: i for i in rism.incipits(rism.source(e["anon"]))}
        print(f"=== [{e['class']}] {e['anon']} {e['label'][:70]}")
        print(f"    {e['composer']} | copies {' '.join(e['sources'][:6])} | copy years {e['copy_years']}")
        print(f"    movements matched {e['movements_matched']} of {e['movements']}"
              + (f" | anonymous->comparator movement {e['movement_mismatch']}" if e["movement_mismatch"] else ""))
        for d in e["prior_documentation"]:
            print(f"    PRIOR DOCUMENTATION in {d['source']}: ...{d['text'][-140:]}")
        for f in e["attribution_flags"]:
            print(f"    ATTRIBUTION: {f}")
        if e["competitors"]:
            print(f"    OTHER COMPOSERS: {'; '.join(e['competitors'])}")
        for m in e["incipits"]:
            i = anon[m["inc"]]
            print(f"  A mv{m['movement']} {m['inc'][:14]:14} {i['keysig']:5}{i['timesig']:4} {i['data'][:80]}")
            if m["source"]:
                ci = {x["inc"]: x for x in rism.incipits(rism.source(m["source"]))}[m["source_inc"]]
                lab = rism.label(rism.source(m["source"]))
                print(f"  C mv{m['source_movement']} {m['overlap']:>2}/{m['notes']:<2} (from start {m['agree']}, offset {m.get('offset')}) "
                      f"{m['source']} {ci['inc'][:16]} {ci['keysig']:5}{ci['timesig']:4} {ci['data'][:70]}")
                print(f"           {lab[:90]}")


if __name__ == "__main__":
    main()
