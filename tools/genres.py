"""Refresh data/genres.json: anonymous RISM sources with incipits per subject heading.

    python tools/genres.py

The subject list is the burndown order. A genre's "run" is the date its search was run
(set by hand when runs/<slug>/ is committed); it is kept across refreshes.
"""
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import rism  # noqa: E402

SUBJECTS = ["Symphonies", "Concertos", "Sonatas", "Overtures", "Operas", "Masses", "Arias (voc.)"]


def count(subject):
    q = urllib.parse.quote(subject)
    url = f"{rism.ANONYMUS}/sources?rows=20&fq=has-incipits:true&fq=subjects:{q}"
    path = os.path.join(rism.CACHE, __import__("hashlib").md5(url.encode()).hexdigest() + ".json")
    if os.path.exists(path):
        os.remove(path)  # counts should be fresh
    return rism.get(url)["totalItems"]


def main():
    try:
        with open("data/genres.json") as f:
            old = {g["subject"]: g for g in json.load(f)}
    except FileNotFoundError:
        old = {}
    out = []
    for s in SUBJECTS:
        g = {"subject": s, "slug": s.lower().split(" (")[0].replace(" ", "-"), "anonymous_with_incipits": count(s)}
        if old.get(s, {}).get("run"):
            g["run"] = old[s]["run"]
        out.append(g)
    with open("data/genres.json", "w") as f:
        json.dump(out, f, indent=1)
    for g in out:
        print(g)


if __name__ == "__main__":
    main()
