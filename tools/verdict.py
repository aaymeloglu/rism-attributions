"""Record hand verdicts in data/verdicts.csv, from the command line or from a review script.

    python tools/verdict.py todo concertos
    python tools/verdict.py set concertos 1001083393 Woelfl confirmed --note "The first incipit matches ..."
    python tools/verdict.py set operas 115893 Duni confirmed --prior title-names-work --note "..."
    python tools/verdict.py reject operas 704003764 Palestrina --note "Only a common figure agrees"
    python tools/verdict.py reject-rest operas --note "Only figuration or a short fragment agrees"

The composer argument is a prefix of RISM's heading ("Mozart, Wolfgang" or just "Woelfl"); it
must match at least one lead for that anonymous source. From Python, for a batch of verdicts:

    from verdict import Verdicts
    v = Verdicts("operas")
    v.set("115893", "Duni", "confirmed", "...", prior="title-names-work")
    v.reject("704003764", "Palestrina", "...")
    v.save()

Rows are kept sorted by genre, anonymous id and composer, so diffs stay readable. The
vocabularies are the ones tests/test_data.py enforces; see METHOD.md for what each value means.
"""
import argparse
import csv
import json
import os

VERDICTS = ("confirmed", "probable", "unresolved", "rejected")
ATTRIBUTION = ("secure", "disputed", "uncertain", "name-only", "modern-copy", "work-only", "shared")
PRIOR = ("new", "anonymous-record", "comparator-record", "title-names-work")
FIELDS = ["genre", "anon_id", "composer", "identity", "verdict", "attribution", "prior", "note"]
GENRE_ORDER = ["symphonies", "concertos", "operas", "sonatas", "overtures", "masses", "arias"]


class Verdicts:
    def __init__(self, slug, path="data/verdicts.csv"):
        self.slug, self.path = slug, path
        with open(f"runs/{slug}/leads.json") as f:
            self.leads = json.load(f)
        self.rows, self.dirty = {}, set()
        if os.path.exists(path):
            with open(path) as f:
                self.rows = {(r["anon_id"], r["composer"]): {k: r.get(k, "") for k in FIELDS} for r in csv.DictReader(f)}

    def _leads(self, anon, composer):
        hit = [e for e in self.leads if e["anon"] == anon and e["composer"].startswith(composer)]
        if not hit:
            raise SystemExit(f"no {self.slug} lead for {anon} / {composer}")
        return hit

    def set(self, anon, composer, verdict, note, attribution="secure", prior="new", identity=""):
        """identity: the reviewed composer when RISM's heading on the attributed copy is wrong (e.g.
        father for son); the heading stays in `composer`, which is how the lead is keyed."""
        if verdict not in VERDICTS:
            raise SystemExit(f"verdict must be one of {VERDICTS}")
        if verdict != "rejected" and (attribution not in ATTRIBUTION or prior not in PRIOR):
            raise SystemExit(f"attribution must be one of {ATTRIBUTION}; prior one of {PRIOR}")
        if not note:
            raise SystemExit("every verdict needs a note")
        for e in self._leads(anon, composer):
            self.dirty.add((anon, e["composer"]))
            self.rows[(anon, e["composer"])] = {
                "genre": self.slug, "anon_id": anon, "composer": e["composer"], "identity": identity, "verdict": verdict,
                "attribution": "" if verdict == "rejected" else attribution,
                "prior": "" if verdict == "rejected" else prior, "note": note}

    def reject(self, anon, composer, note):
        self.set(anon, composer, "rejected", note)

    def todo(self):
        return [e for e in self.leads if (e["anon"], e["composer"]) not in self.rows]

    def reject_rest(self, note):
        for e in self.todo():
            self.reject(e["anon"], e["composer"], note)

    def save(self):
        """Write back only the rows this instance changed, on top of a fresh read of the file, so two
        instances (say, one per genre) cannot overwrite each other's edits."""
        current = {}
        if os.path.exists(self.path):
            with open(self.path) as f:
                current = {(r["anon_id"], r["composer"]): {k: r.get(k, "") for k in FIELDS} for r in csv.DictReader(f)}
        for key in self.dirty:
            current[key] = self.rows[key]
        self.rows, self.dirty = current, set()
        order = {g: i for i, g in enumerate(GENRE_ORDER)}
        out = sorted(self.rows.values(), key=lambda r: (order.get(r["genre"], 99), r["genre"], r["anon_id"], r["composer"]))
        with open(self.path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(out)
        print(f"{self.slug}: {len(self.todo())} leads without a verdict")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("todo")
    t.add_argument("slug")
    s = sub.add_parser("set")
    for arg in ("slug", "anon", "composer", "verdict"):
        s.add_argument(arg)
    s.add_argument("--attribution", default="secure")
    s.add_argument("--prior", default="new")
    s.add_argument("--identity", default="", help="reviewed composer when RISM's heading is wrong")
    s.add_argument("--note", required=True)
    r = sub.add_parser("reject")
    for arg in ("slug", "anon", "composer"):
        r.add_argument(arg)
    r.add_argument("--note", required=True)
    rr = sub.add_parser("reject-rest")
    rr.add_argument("slug")
    rr.add_argument("--note", required=True)
    a = ap.parse_args()
    v = Verdicts(a.slug)
    if a.cmd == "todo":
        for e in v.todo():
            print(e["anon"], e["class"], e["composer"])
        print(len(v.todo()), "without a verdict")
        return
    if a.cmd == "set":
        v.set(a.anon, a.composer, a.verdict, a.note, a.attribution, a.prior, a.identity)
    elif a.cmd == "reject":
        v.reject(a.anon, a.composer, a.note)
    elif a.cmd == "reject-rest":
        v.reject_rest(a.note)
    v.save()


if __name__ == "__main__":
    main()
