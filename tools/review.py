"""Print leads for hand review: each incipit of the anonymous copy next to its best match.

    python tools/review.py concertos                  # all leads without a verdict yet, in full
    python tools/review.py concertos --brief          # compact: only agreeing incipits, one line of flags
    python tools/review.py concertos --class good     # only one triage class (comma-separated for several)
    python tools/review.py concertos --id 400012345   # one anonymous source
    python tools/review.py concertos --all            # include leads that already have a verdict

For every lead it shows the catalogue flags from tools/context.py (prior documentation,
attribution qualifiers and cross-references, the anonymous record's own authorship notes),
matches with a differently numbered incipit, text and key mismatches, transposition, and other
composers returned by the five-bar re-search. Each incipit line gives RISM's label, the
instrument or voice, key signature, metre, text incipit and Plaine & Easie code; the match line
adds pitches agreeing, the offset if one incipit enters partway into the other, the share of
broken-chord figuration, and the attributed record.
"""
import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import rism  # noqa: E402
from leads import matches  # noqa: E402


def flags(e):
    out = []
    for d in e["prior_documentation"]:
        out.append(f"PRIOR DOCUMENTATION in {d['source']}: ...{d['text'][-120:]}")
    out += [f"ATTRIBUTION: {f}" for f in e["attribution_flags"]]
    out += [f"ANONYMOUS RECORD: {f[:160]}" for f in e.get("anonymous_record_authorship", [])]
    if e.get("internal_matches"):
        out.append("DIFFERENT INCIPIT NUMBER: " + "; ".join(e["internal_matches"]))
    if e.get("title_names_work"):
        out.append("TITLE ALREADY NAMES THE WORK: " + " ".join(e["title_names_work"]))
    if e.get("text_mismatch"):
        out.append("DIFFERENT WORDS: " + "; ".join(e["text_mismatch"]))
    if e.get("vocal_matches"):
        out.append("VOCAL NUMBER: " + "; ".join(e["vocal_matches"]))
    if e.get("transposed"):
        out.append("TRANSPOSED")
    if e.get("key_label_mismatch"):
        out.append("TITLE KEY DISAGREES WITH KEY SIGNATURE")
    if e["competitors"]:
        out.append("OTHER COMPOSERS IN FIVE-BAR SEARCH: " + "; ".join(e["competitors"]))
    return out


def line(tag, inc, width):
    return (f"  {tag} {inc['inc'][:20]:20} [{inc.get('voice', '')[:8]}] {inc['keysig']:5}{inc['timesig']:5}"
            f" “{inc.get('text', '')[:28]}” {inc['data'][:width]}")


def show(e, brief):
    anon = {i["inc"]: i for i in rism.incipits(rism.source(e["anon"]))}
    print(f"=== [{e['class']}] {e['anon']} {e['label'][:70]}")
    print(f"    {e['composer']} | copies {' '.join(e['sources'][:6])} | copy years {e['copy_years']}"
          f" | incipits matched {len(e['incipits_matched'])} of {len(e['incipits'])}")
    fl = flags(e)
    if brief and fl:
        print("    ! " + " | ".join(fl)[:400])
    else:
        for f in fl:
            print(f"    {f}")
    shown = [m for m in e["incipits"] if m["source"] and matches(m)] if brief else e["incipits"]
    if brief and not shown:
        shown = sorted([m for m in e["incipits"] if m["source"]], key=lambda m: -m["overlap"])[:1]
    for m in shown:
        print(line("A", anon[m["inc"]], 64 if brief else 80))
        if m["source"]:
            ci = {x["inc"]: x for x in rism.incipits(rism.source(m["source"]))}[m["source_inc"]]
            print(line("C", ci, 64 if brief else 80)
                  + f" [{m['overlap']}/{m['notes']} from start {m['agree']} offset {m.get('offset')} fig {m.get('figuration')}]")
            print(f"      {m['source']} {rism.label(rism.source(m['source']))[:80]}")
            for w in m.get("witnesses", [])[:3]:
                print(f"      also {w['source']} {w['source_inc'][:30]} ({w['overlap']} pitches)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--class", dest="cls", help="triage class, or several comma-separated")
    ap.add_argument("--id")
    ap.add_argument("--all", action="store_true", help="include leads that already have a verdict")
    ap.add_argument("--brief", action="store_true", help="only agreeing incipits and one line of flags")
    a = ap.parse_args()
    classes = set(a.cls.split(",")) if a.cls else None
    with open(f"runs/{a.slug}/leads.json") as f:
        leads = json.load(f)
    with open("data/verdicts.csv") as f:
        done = {(r["anon_id"], r["composer"]) for r in csv.DictReader(f)}
    for e in leads:
        if classes and e["class"] not in classes or a.id and e["anon"] != a.id:
            continue
        if not a.all and (e["anon"], e["composer"]) in done:
            continue
        show(e, a.brief)


if __name__ == "__main__":
    main()
