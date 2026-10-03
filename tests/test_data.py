"""Checks that keep verdicts, lead evidence, exported data and the built site consistent.

The consistency tests between data/verdicts.csv and the automatic catalogue flags in
runs/*/leads.json exist because each failure mode below reached the published site once:
a copy already cited in another RISM record counted as new, a disputed or surname-only
attribution counted as secure, and a match with a different movement described as a whole work.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import verdict  # noqa: E402  (the vocabularies live in tools/verdict.py)

VERDICTS, ATTRIBUTION, PRIOR = set(verdict.VERDICTS), set(verdict.ATTRIBUTION), set(verdict.PRIOR)
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
        if e["catalogue_number_in_title"]:
            assert r["prior"] != "new", (r["anon_id"], "the anonymous record already carries the catalogue number")
        if e["names_composer"] and r["prior"] == "new":
            reason = prior_resolutions().get((r["anon_id"], r["composer"]), "")
            assert len(reason) >= 40, (r["anon_id"], "the anonymous record mentions the composer; call it anonymous-record or say in "
                                       "data/prior_resolutions.csv why the mention does not document this match")


def test_title_naming_the_work_is_not_new_without_reason():
    """If the anonymous title already names the matched work, the find is new only when the title
    is a libretto several composers set, and the note must say whose setting it is."""
    for r, e in kept():
        if e.get("title_names_work") and r["prior"] == "new":
            assert re.search(r"setting", r["note"], re.I), (r["anon_id"], "title already names the work; say why the match adds a composer")


def _surname(name):
    return name.split(",")[0].split(" (")[0].strip()


def prior_resolutions():
    with open(ROOT / "data" / "prior_resolutions.csv") as f:
        return {(r["anon_id"], r["composer"]): r["reason"] for r in csv.DictReader(f)}


def resolutions():
    with open(ROOT / "data" / "attribution_resolutions.csv") as f:
        return {(r["anon_id"], r["composer"], r["flag"]): r["reason"] for r in csv.DictReader(f)}


def test_attribution_flags_are_resolved_or_reflected():
    """'secure' means one unqualified composer. A qualified attribution (conjectural, alleged,
    doubtful) is never secure; a bare surname is name-only or disputed; every other flag, on the
    attributed copies or in the anonymous record's own authorship notes, needs a written
    resolution in data/attribution_resolutions.csv. Mentioning a flag is not resolving it."""
    res = resolutions()
    for r, e in kept():
        flags = e["attribution_flags"] + [f for f in e.get("anonymous_record_authorship", []) if "(Misattributed)" not in f]
        for flag in flags:
            if "names no identifiable person" in flag:
                assert r["attribution"] in ("name-only", "disputed", "work-only"), (r["anon_id"], flag)
            elif "qualified as" in flag:
                assert r["attribution"] != "secure", (r["anon_id"], flag, "a qualified attribution is not secure")
            elif r["attribution"] == "secure":
                reason = res.get((r["anon_id"], r["composer"], flag), "")
                assert len(reason) >= 40, (r["anon_id"], flag, "resolve in data/attribution_resolutions.csv or change the attribution")

def test_internal_matches_cite_the_incipit():
    """When the anonymous incipit matches an attributed incipit with a different RISM number
    (anonymous 1.1.1 against 1.2.1), the note must cite that incipit by RISM's own identifier and
    describe it from the record, since RISM numbering mixes movements, sections, parts and pieces."""
    for r, e in kept():
        if r["verdict"] not in ("confirmed", "probable"):
            continue
        for im in e["internal_matches"]:
            ident = im.split(" -> ")[1].split(" ")[1]
            assert ident in r["note"], (r["anon_id"], im, "cite the attributed copy's incipit identifier")


def test_no_computed_movement_numbers():
    """Movement numbers computed from incipit positions have been wrong; notes use RISM's labels."""
    for r in verdict_rows():
        assert not re.search(r"\bmovements? [IVXL]+\b", r["note"]), (r["anon_id"], r["note"][:80])

def test_vocal_matches_are_described():
    """A match with an incipit labelled Recitativo, Aria, Kyrie... is not an overture or a symphony
    movement by default; the note must say what vocal number it is."""
    import context
    for r, e in kept():
        for vm in e["vocal_matches"]:
            word = context.vocal_label(vm)
            assert word.lower()[:6] in r["note"].lower(), (r["anon_id"], vm, "say which vocal number matched")


def test_text_mismatch_is_described():
    """The same melody under different words is a contrafactum or a coincidence; the note must say so."""
    for r, e in kept():
        if e.get("text_mismatch") and r["verdict"] in ("confirmed", "probable"):
            assert re.search(r"\btext|\bwords|contrafact", r["note"], re.I), (r["anon_id"], e["text_mismatch"], "say the words differ")


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
            if lead["attribution"] == "secure":
                assert not any("qualified as" in f for f in lead["attribution_flags"]), key
        assert rec["verdict"] == min((x["verdict"] for x in rec["leads"]), key=order.index)
    assert seen == set(rows), "attributions.json is stale; re-run tools/export.py"


def test_concordances_are_reviewed():
    """Every automatic candidate needs a verdict, so a rejected pair cannot reappear on regeneration."""
    for c in json.loads((ROOT / "data" / "anonymous_concordances.json").read_text()):
        assert c["verdict"] in ("same", "probable", "rejected"), (c["a"], c["b"], "add to data/concordance_verdicts.csv")
        assert len({m["a"].split(" ")[0].rsplit(".", 1)[0] for m in c["incipits"]}) >= 2, c
        assert all(m["pitches"] >= 8 for m in c["incipits"]), c


def test_pae_parser():
    from pae import anchored, pitches, sim
    a = pitches("''8GGAGE/4C8CC4D8DD/4E8CGGAGE", "n")
    b = pitches("8''G{GAGE}/4C8{CC}4D8{DD}/4E8{CG}{GAGE}/", "n")
    assert a[:5] == [79, 79, 81, 79, 76]
    assert sim(a, b) == 12, "grouping braces must not change pitches"
    assert sim(pitches("''8GGAGE", "n"), pitches("''8AABAxF", "n")) == 4, "comparison is by interval"
    assert pitches("'4B", "bBE") == [70] and pitches("'4nB", "bBE") == [71]
    assert len(pitches("'4ABAG/i/i/", "n")) == len(pitches("'4ABAG/ABAG/ABAG/", "n")) == 12, "measure repeat"
    assert pitches("!{6'B''B}!ff/", "bBE") == [70, 82] * 3, "repeated group: once plus one per f"
    assert pitches("'4Dqq6{EDC}r8E", "xFC") == [62, 64] and pitches("'4Dqq6{EDC}r8E", "xFC", graces=True) == [62, 64, 62, 61, 64]
    assert pitches("'4xFF/F", "n") == [66, 66, 65], "an accidental holds to the end of the measure"
    assert pitches("'4xFF''F", "n") == [66, 66, 77], "only in the same octave"
    assert pitches("'4nBB/B", "bBE") == [71, 71, 70] and pitches("'4xF$bBE F", "n") == [66, 65]
    assert pitches("@3/4 %C-1'4CDE", "n") == [60, 62, 64] and pitches("$bBE'4B", "n") == [70]
    late = pitches("=4/''GF/AG/{6FGFE}{DC'BnA}/4B-/", "bBEA")
    full = pitches("{8.6'B''E8'BB}/B4G8A/B4E8F/{G-E}-/4''GF/AG/{6FGFE}{DC'BnA}/4", "bBEA")
    assert sim(late, full) < 3 and anchored(late, full)[0] >= 12, "a part entering after rests still matches"


def test_best_eligible_witness_wins():
    """A longer agreement that fails the figuration test must not hide a shorter one that passes."""
    from leads import compare, matches
    anon = {"inc": "1.1.1", "voice": "vl 1", "keysig": "n", "timesig": "c", "text": "",
            "data": "''8CECE/CECE/CECE/CECE/DGAB/''C'BAG/FEDC"}
    tremolo = ("1", [{"inc": "1.1.1", "voice": "vl 1", "keysig": "n", "timesig": "c", "text": "",
                      "data": "''8CECE/CECE/CECE/CECE/CECE/CECE/CECE"}])
    melody = ("2", [{"inc": "1.1.1", "voice": "vl 1", "keysig": "n", "timesig": "c", "text": "",
                     "data": "''8E/DGAB/''C'BAG/FEDC/"}])
    best = compare(anon, [tremolo, melody])
    assert best["source"] == "2" and matches(best), best
    assert any(w["source"] == "1" for w in best.get("failed_witnesses", [])), "failing witness stays visible"


def test_verdict_helper_instances_do_not_clobber(tmp_path):
    """Two Verdicts instances saving in turn must keep both sets of edits."""
    import shutil
    from verdict import Verdicts
    path = tmp_path / "v.csv"
    shutil.copy(ROOT / "data" / "verdicts.csv", path)
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        a, b = Verdicts("symphonies", str(path)), Verdicts("concertos", str(path))
        ka, kb = next(iter(a.rows)), next(k for k, r in b.rows.items() if r["genre"] == "concertos")
        a.set(ka[0], ka[1], "rejected", "edit A")
        b.set(kb[0], kb[1], "rejected", "edit B")
        a.save()
        b.save()
        with open(path) as f:
            notes = {(r["anon_id"], r["composer"]): r["note"] for r in csv.DictReader(f)}
        assert notes[ka] == "edit A" and notes[kb] == "edit B"
    finally:
        os.chdir(cwd)


def test_identity_corrections_are_explained():
    for r in verdict_rows():
        if r["identity"]:
            assert r["identity"] != r["composer"], r["anon_id"]
            assert re.search(r"heading", r["note"], re.I), (r["anon_id"], "say that RISM's heading is wrong and why")


def test_title_naming_a_work_set_by_several_composers():
    """'title-names-work' means the title names a work with one known composer. If the dataset
    itself matches that title to two composers, the category cannot apply to it. Leads marked
    'shared' (a joint work, e.g. by two brothers) are not competing settings and are left out."""
    import context
    L = leads()
    by_title = {}
    for r, e in kept():
        if e.get("title_names_work") and r["attribution"] != "shared":
            by_title.setdefault(context._core(e["label"].split(";")[0]), set()).add(r["identity"] or r["composer"])
    for r, e in kept():
        if e.get("title_names_work") and r["prior"] == "title-names-work":
            composers = by_title.get(context._core(e["label"].split(";")[0]), set())
            assert len(composers) <= 1, (r["anon_id"], composers, "several composers set this title")


def test_documented_concordances_say_so():
    for c in json.loads((ROOT / "data" / "anonymous_concordances.json").read_text()):
        if c.get("already_documented") and c["verdict"] != "rejected":
            assert re.search(r"already|cross-referenc", c["note"], re.I), (c["a"], c["b"], "the records already point at each other")

    shown = [c for c in json.loads((ROOT / "data/anonymous_concordances.json").read_text())
             if c["verdict"] in ("same", "probable")]
    count = re.search(r"RISM already documents (\d+) of", (ROOT / "README.md").read_text())
    assert count and int(count[1]) == sum(c["already_documented"] for c in shown), "README concordance total is stale"


def test_local_shelfmark_concordances():
    """Real RISM notes omit D-Dl/PL-Wu when citing copies in the same library."""
    import context
    sources = json.loads((ROOT / "tests/fixtures/local_concordances.json").read_text())
    exported = {(c["a"], c["b"]): c for c in json.loads((ROOT / "data/anonymous_concordances.json").read_text())}
    for a, b in [("212003416", "212003586"), ("212003585", "212003586"),
                 ("212003540", "212003541"), ("300511197", "300511198")]:
        hits = context.prior_documentation(a, sources[a], [(b, sources[b])])
        hits += context.prior_documentation(b, sources[b], [(a, sources[a])])
        assert hits, (a, b, "an explicit local citation was missed")
        assert exported[a, b]["already_documented"], (a, b, "regenerate concordances")
    # A former shelfmark suggests a relationship but does not establish a concordance.
    a, b = "1001012602", "1001012610"
    assert not context.prior_documentation(a, sources[a], [(b, sources[b])])
    assert not context.prior_documentation(b, sources[b], [(a, sources[a])])


def test_shelfmark_references_need_library_and_boundaries():
    import context
    def source(siglum, callno, note=""):
        return {"label": {"en": [f"Concertos; Manuscript copy; {siglum} {callno}"]},
                "notes": {"summary": [{"label": {"en": ["General note"]}, "value": {"none": [note]}}]}}
    anon = source("D-Dl", "Mus.2-O-14")
    assert context.prior_documentation("123456", anon, [("9", source("D-Dl", "Mus.2-O-15", "Partitur unter Mus.2-O-14."))])
    for other in [source("PL-Wu", "Mus.2-O-15", "Partitur unter Mus.2-O-14."),
                  source("D-Dl", "Mus.2-O-14a"),
                  source("D-Dl", "Mus.2-O-15", "Partitur unter D-Dl Mus.2-O-14a."),
                  source("D-Dl", "Mus.2-O-15", "Partitur unter D-Dl Mus.2-O-14,2."),
                  source("D-Dl", "Mus.2-O-15", "See RISM 1234567.")]:
        assert not context.prior_documentation("123456", anon, [("9", other)]), other


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
