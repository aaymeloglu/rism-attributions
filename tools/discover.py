"""Step 1: for every anonymous source in a RISM subject, search each movement's incipit.

    python tools/discover.py Symphonies

Writes runs/<slug>/results.json: per anonymous source, its movements (with hit counts) and
the other sources whose incipits matched the first three bars with the same key and metre.
Movements matching more than MAXHITS records are treated as stock figures and skipped.
"""
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
import rism  # noqa: E402

MAXHITS = 40


def fragment(pae, bars):
    return "/".join([m for m in pae.split("/") if m.strip()][:bars])


def search_source(sid):
    s = rism.get(sid)
    out = {"id": rism.rid(sid), "label": rism.label(s), "movements": [], "candidates": {}}
    for inc in rism.incipits(s):
        frag = fragment(inc["data"], 3)
        if len(frag.replace("/", "")) < 12:
            frag = fragment(inc["data"], 4)
        try:
            r = rism.search_incipit(frag, inc["keysig"], inc["timesig"])
        except Exception as ex:
            out["movements"].append({"inc": inc["inc"], "error": str(ex)})
            continue
        total = r.get("totalItems", 0)
        out["movements"].append({"inc": inc["inc"], "fragment": frag, "total": total})
        if total == 0 or total > MAXHITS:
            continue
        for item in r.get("items", []):
            src = item["id"].split("/incipits")[0]
            if src != sid:
                out["candidates"].setdefault(src, set()).add(inc["inc"])
    cands = []
    for src, movs in out["candidates"].items():
        try:
            cs = rism.get(src)
        except Exception:
            continue
        cands.append({"id": rism.rid(src), "composer": rism.creator(cs), "label": rism.label(cs), "movements": sorted(movs)})
    out["candidates"] = sorted(cands, key=lambda c: c["id"])
    return out


def main(subject):
    slug = subject.lower().replace(" ", "-")
    ids = rism.anonymous_sources(subject)
    print(f"{subject}: {len(ids)} anonymous sources with incipits", flush=True)
    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(search_source, ids))
    os.makedirs(f"runs/{slug}", exist_ok=True)
    with open(f"runs/{slug}/results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(f"wrote runs/{slug}/results.json")


if __name__ == "__main__":
    main(sys.argv[1])
