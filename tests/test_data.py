"""Checks that keep verdicts, runs, exported data and the built site consistent."""
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

VERDICTS = {"confirmed", "conflicting", "probable", "unresolved", "known", "rejected"}
SHOWN = {"confirmed", "conflicting", "probable", "unresolved"}


def load_verdicts():
    with open(ROOT / "data" / "verdicts.csv") as f:
        return list(csv.DictReader(f))


def load_leads():
    out = []
    for p in sorted((ROOT / "runs").glob("*/leads.json")):
        out += json.loads(p.read_text())
    return out


def test_verdict_vocabulary_and_uniqueness():
    rows = load_verdicts()
    keys = [(r["anon_id"], r["composer"]) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate verdict rows"
    for r in rows:
        assert r["verdict"] in VERDICTS, r
        assert re.fullmatch(r"\d+", r["anon_id"]), r
        if r["verdict"] in {"probable", "unresolved", "conflicting", "rejected", "known"}:
            assert r["note"], (r["anon_id"], "this verdict needs a note saying why")


def test_every_lead_has_exactly_one_verdict():
    leads = {(e["anon"], e["composer"]) for e in load_leads()}
    rows = {(r["anon_id"], r["composer"]) for r in load_verdicts()}
    assert leads == rows, {"leads without verdict": sorted(leads - rows)[:5], "verdicts without lead": sorted(rows - leads)[:5]}


def test_attributions_match_verdicts():
    rows = {(r["anon_id"], r["composer"]): r for r in load_verdicts()}
    data = json.loads((ROOT / "data" / "attributions.json").read_text())
    seen = set()
    for rec in data:
        for lead in rec["leads"]:
            key = (rec["id"], lead["composer"])
            seen.add(key)
            assert lead["verdict"] == rows[key]["verdict"], key
            assert lead["note"] == rows[key]["note"], (key, "re-run tools/export.py")
            if lead["verdict"] in SHOWN:
                assert lead["movements"] and lead["sources"], key
                for m in lead["movements"]:
                    assert m["anon"]["data"], key
        assert rec["verdict"] == min((lead["verdict"] for lead in rec["leads"]), key=list(
            ["confirmed", "conflicting", "probable", "unresolved", "known", "rejected"]).index)
    assert seen == set(rows), "attributions.json is stale; re-run tools/export.py"


def test_confirmed_leads_show_agreeing_music():
    data = json.loads((ROOT / "data" / "attributions.json").read_text())
    for rec in data:
        for lead in rec["leads"]:
            if lead["verdict"] == "confirmed":
                assert any(m.get("match") and m["agree"] >= 6 for m in lead["movements"]), (rec["id"], lead["composer"])


def test_pae_pitch_parser():
    from pae import pitches, sim
    a = pitches("''8GGAGE/4C8CC4D8DD/4E8CGGAGE", "n")
    b = pitches("8''G{GAGE}/4C8{CC}4D8{DD}/4E8{CG}{GAGE}/", "n")
    assert a[:5] == [79, 79, 81, 79, 76]
    assert sim(a, b) == 12, "grouping braces must not change pitches"
    up = pitches("''8AABAxF", "n")
    assert sim(pitches("''8GGAGE", "n"), up) == 4, "comparison is by interval, so a transposed copy matches"
    assert pitches("'4B", "bBE") == [70] and pitches("'4nB", "bBE") == [71]


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
