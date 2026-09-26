"""Checks that keep verdicts, lead evidence, exported data and the built site consistent.

The consistency tests between data/verdicts.csv and the automatic catalogue flags in
runs/*/leads.json exist because each failure mode below reached the published site once:
a copy already cited in another RISM record counted as new, a disputed or surname-only
attribution counted as secure, and a match with a different movement described as a whole work.
"""
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

VERDICTS = {"confirmed", "probable", "unresolved", "rejected"}
ATTRIBUTION = {"secure", "disputed", "uncertain", "name-only", "modern-copy"}
PRIOR = {"new", "anonymous-record", "comparator-record"}
SHOWN = {"confirmed", "probable", "unresolved"}


def verdict_rows():
    with open(ROOT / "data" / "verdicts.csv") as f:
        return list(csv.DictReader(f))


def leads():
    out = {}
    for p in sorted((ROOT / "runs").glob("*/leads.json")):
        for e in json.loads(p.read_text()):
            out[(e["anon"], e["composer"])] = e
    return out


def kept():
    """(verdict row, lead) for every lead not rejected."""
    L = leads()
    return [(r, L[(r["anon_id"], r["composer"])]) for r in verdict_rows() if r["verdict"] != "rejected"]


def test_vocabulary():
    rows = verdict_rows()
    keys = [(r["anon_id"], r["composer"]) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate verdict rows"
    for r in rows:
        assert r["verdict"] in VERDICTS, r
        assert re.fullmatch(r"\d+", r["anon_id"]), r
        assert r["note"], (r["anon_id"], r["composer"], "every verdict needs a note")
        if r["verdict"] == "rejected":
            assert r["attribution"] == r["prior"] == "", r
        else:
            assert r["attribution"] in ATTRIBUTION and r["prior"] in PRIOR, r


def test_every_lead_has_exactly_one_verdict():
    L, rows = set(leads()), {(r["anon_id"], r["composer"]) for r in verdict_rows()}
    assert L == rows, {"leads without verdict": sorted(L - rows)[:5], "verdicts without lead": sorted(rows - L)[:5]}


def test_prior_documentation_is_not_called_new():
    for r, e in kept():
        if e["prior_documentation"]:
            assert r["prior"] == "comparator-record", (r["anon_id"], "an attributed copy's record already cites this copy")
        if e["names_composer"] or e["catalogue_number_in_title"]:
            assert r["prior"] != "new", (r["anon_id"], "the anonymous record already names the composer or catalogue number")


def _surname(name):
    return name.split(",")[0].split(" (")[0].strip()


def test_attribution_flags_are_reflected():
    """A flagged attribution is not 'secure' unless the note names what was flagged."""
    for r, e in kept():
        for flag in e["attribution_flags"]:
            if "names no identifiable person" in flag:
                assert r["attribution"] in ("name-only", "disputed"), (r["anon_id"], flag)
                continue
            if r["attribution"] != "secure":
                continue
            if "cross-reference to" in flag:
                name = flag.split("cross-reference to ", 1)[1].split(" (")[0]
                assert _surname(name) in r["note"], (r["anon_id"], flag, "note must mention the cross-referenced composer")
            elif "copied or edited by" in flag:
                name = flag.split("copied or edited by ", 1)[1].split(";")[0]
                assert _surname(name) in r["note"], (r["anon_id"], flag, "note must mention the modern copy")
            elif "qualified as" in flag:
                q = flag.rsplit(" ", 1)[1].lower()
                assert q in r["note"].lower(), (r["anon_id"], flag, "a qualified attribution is not secure")


def test_movement_mismatch_is_described():
    """When the anonymous movement matches a different movement of the attributed copy, the note
    must name that movement (as a roman or arabic number), not describe the match as the work."""
    from pae import roman
    for r, e in kept():
        if r["verdict"] not in ("confirmed", "probable"):
            continue
        for mm in e["movement_mismatch"]:
            b = int(mm.split("->")[1])
            assert re.search(rf"\b({roman(b)}|{b})\b", r["note"]), (r["anon_id"], mm, "name the attributed copy's movement")


def test_vocal_matches_are_described():
    """A match with an incipit labelled Recitativo, Aria, Kyrie... is not an overture or a symphony
    movement by default; the note must say what vocal number it is."""
    import context
    for r, e in kept():
        for vm in e["vocal_matches"]:
            word = context.vocal_label(vm)
            assert word.lower()[:6] in r["note"].lower(), (r["anon_id"], vm, "say which vocal number matched")


def test_transposition_claims_match_the_evidence():
    for r, e in kept():
        claims = re.search(r"\btranspos", r["note"], re.I)
        if claims and not re.search(r"\bnot\b[^.;]*transpos|transpos[^.;]*\bnot\b|no transposition", r["note"], re.I):
            assert e["transposed"], (r["anon_id"], "note says transposed, but every matching incipit is in the same key")


def test_key_label_mismatch_is_noted():
    for r, e in kept():
        if e["key_label_mismatch"]:
            assert re.search(r"titl|label|key", r["note"], re.I), (r["anon_id"], "RISM's title key disagrees with the encoded key signature")


def test_attributions_match_verdicts():
    rows = {(r["anon_id"], r["composer"]): r for r in verdict_rows()}
    data = json.loads((ROOT / "data" / "attributions.json").read_text())
    seen = set()
    order = ["confirmed", "probable", "unresolved", "rejected"]
    for rec in data:
        for lead in rec["leads"]:
            key = (rec["id"], lead["composer"])
            seen.add(key)
            for f in ("verdict", "attribution", "prior", "note"):
                assert lead[f] == rows[key][f], (key, f, "re-run tools/export.py")
            if lead["verdict"] == "confirmed":
                assert any(p["counts"] for p in lead["incipits"]), (key, "confirmed needs at least one agreeing incipit")
        assert rec["verdict"] == min((x["verdict"] for x in rec["leads"]), key=order.index)
    assert seen == set(rows), "attributions.json is stale; re-run tools/export.py"


def test_concordances_are_multi_movement():
    for c in json.loads((ROOT / "data" / "anonymous_concordances.json").read_text()):
        assert len({m["a"] for m in c["movements"]}) >= 2 and len({m["b"] for m in c["movements"]}) >= 2, c
        assert all(m["pitches"] >= 8 for m in c["movements"]), c


def test_pae_parser():
    from pae import anchored, movement_ordinals, pitches, sim
    a = pitches("''8GGAGE/4C8CC4D8DD/4E8CGGAGE", "n")
    b = pitches("8''G{GAGE}/4C8{CC}4D8{DD}/4E8{CG}{GAGE}/", "n")
    assert a[:5] == [79, 79, 81, 79, 76]
    assert sim(a, b) == 12, "grouping braces must not change pitches"
    assert sim(pitches("''8GGAGE", "n"), pitches("''8AABAxF", "n")) == 4, "comparison is by interval"
    assert pitches("'4B", "bBE") == [70] and pitches("'4nB", "bBE") == [71]
    assert len(pitches("'4ABAG/i/i/", "n")) == len(pitches("'4ABAG/ABAG/ABAG/", "n")) == 12, "measure repeat"
    assert pitches("!{6'B''B}!ff/", "bBE") == [70, 82] * 3, "repeated group: once plus one per f"
    assert pitches("'4Dqq6{EDC}r8E", "xFC") == [62, 64] and pitches("'4Dqq6{EDC}r8E", "xFC", graces=True) == [62, 64, 62, 61, 64]
    assert pitches("@3/4 %C-1'4CDE", "n") == [60, 62, 64] and pitches("$bBE'4B", "n") == [70]
    late = pitches("=4/''GF/AG/{6FGFE}{DC'BnA}/4B-/", "bBEA")
    full = pitches("{8.6'B''E8'BB}/B4G8A/B4E8F/{G-E}-/4''GF/AG/{6FGFE}{DC'BnA}/4", "bBEA")
    assert sim(late, full) < 3 and anchored(late, full)[0] >= 12, "a part entering after rests still matches"
    assert movement_ordinals(["1.1.1 Allegro", "1.1.2 Andante", "1.1.3 Menuetto"]) == {"1.1.1 Allegro": 1, "1.1.2 Andante": 2, "1.1.3 Menuetto": 3}
    assert movement_ordinals(["1.3.1 Menuetto.", "1.3.2", "1.4.1 Trio.", "1.4.2"]) == {"1.3.1 Menuetto.": 1, "1.3.2": 1, "1.4.1 Trio.": 2, "1.4.2": 2}


def test_no_local_paths_or_secrets():
    bad = re.compile(r"/Users/|/private/tmp|AIza[0-9A-Za-z_-]{20,}")
    for p in [*ROOT.glob("*.md"), *(ROOT / "tools").glob("*.py"), *(ROOT / "data").glob("*"), *(ROOT / "docs").rglob("*.html")]:
        assert not bad.search(p.read_text()), p


def test_site_is_up_to_date():
    """docs/ must equal a fresh build. Builds into a temp copy so the check is the same locally and in CI."""
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "repo"
        shutil.copytree(ROOT, dst, ignore=shutil.ignore_patterns(".git", ".venv", ".cache", "__pycache__"))
        subprocess.run([sys.executable, "docs/_build_site.py"], cwd=dst, check=True)
        for built in (dst / "docs").rglob("*.html"):
            rel = built.relative_to(dst)
            assert (ROOT / rel).read_text() == built.read_text(), f"{rel} is stale; run python3 docs/_build_site.py"
        assert {p.relative_to(dst) for p in (dst / "docs").rglob("*.html")} == {p.relative_to(ROOT) for p in (ROOT / "docs").rglob("*.html")}
