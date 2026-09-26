#!/usr/bin/env python3
"""Build the GitHub Pages site in docs/ from data/attributions.json and data/genres.json.

Python 3, standard library only. From the repo root:

    python3 docs/_build_site.py

Writes docs/index.html (results and burndown), docs/r/<RISM id>.html (one page per anonymous
source with a finding, movements side by side) and docs/concordances.html. Incipits are
rendered in the browser by Verovio from the Plaine & Easie code stored in the data.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPO = "https://github.com/aaymeloglu/rism-attributions"
RISM = "https://rism.online/sources/"
VEROVIO = "https://cdn.jsdelivr.net/npm/verovio@6.3.0/dist/verovio-toolkit-wasm.js"

STYLE = """
:root { --ink:#1f1b16; --muted:#6b6259; --accent:#8a3b12; --rule:#d9d0c3; --bg:#faf6ef; --surface:#fff; --serif:Georgia,'Times New Roman',serif; --mono:ui-monospace,Menlo,Consolas,monospace; --notation:none; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --ink:#e8e1d6; --muted:#a39b90; --accent:#e0956a; --rule:#3b352f; --bg:#171411; --surface:#1f1b17; --notation:invert(.88); } }
:root[data-theme="dark"] { --ink:#e8e1d6; --muted:#a39b90; --accent:#e0956a; --rule:#3b352f; --bg:#171411; --surface:#1f1b17; --notation:invert(.88); }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font-family:var(--serif); font-size:17px; line-height:1.55; }
.wrap { max-width:1200px; margin:0 auto; padding:24px 16px 64px; }
h1 { font-size:34px; font-style:italic; color:var(--accent); margin:8px 0 4px; }
h2 { font-size:24px; color:var(--accent); margin:32px 0 10px; }
h3 { font-size:19px; margin:24px 0 8px; }
p.lede { color:var(--muted); max-width:80ch; margin:0 0 20px; }
a { color:var(--accent); }
.scroll { overflow-x:auto; }
table.idx { width:100%; border-collapse:collapse; background:var(--surface); border:1px solid var(--rule); }
table.idx th, table.idx td { text-align:left; vertical-align:top; padding:10px 12px; border-bottom:1px solid var(--rule); }
table.idx th { font-size:12px; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }
.where { color:var(--muted); font-size:14px; }
.badge { display:inline-block; font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; border:1px solid var(--accent); color:var(--accent); padding:3px 8px; border-radius:3px; white-space:nowrap; }
.badge.probable { opacity:.8; } .badge.unresolved, .badge.rejected, .badge.open, .badge.flag { border-color:var(--muted); color:var(--muted); }
.badges .badge { margin:0 4px 4px 0; }
ul.flags { font-size:14px; color:var(--muted); }
.crumbs { font-size:14px; color:var(--muted); margin-bottom:8px; }
.credit { font-size:13px; color:var(--muted); margin-top:28px; max-width:90ch; }
.mv { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:10px 0 22px; }
.mv > div { background:var(--surface); border:1px solid var(--rule); padding:10px 12px; min-width:0; }
.mv h4 { margin:0 0 4px; font-size:13px; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); font-weight:normal; }
.score { min-height:40px; filter:var(--notation); }
.score svg { max-width:100%; height:auto; }
code.pae { display:block; font-family:var(--mono); font-size:12px; color:var(--muted); word-break:break-all; margin-top:6px; }
.agree { font-size:14px; margin:18px 0 4px; }
details { margin:18px 0; } summary { cursor:pointer; color:var(--accent); }
@media (max-width:700px) { body { font-size:16px; } .mv { grid-template-columns:1fr; } table.idx td { padding:8px; } }
"""

SORT_JS = """<script>
document.querySelectorAll('table.sortable th[data-col]').forEach(function(th){
  th.style.cursor='pointer'; th.title='Sort';
  th.addEventListener('click',function(){
    var t=th.closest('table'), c=+th.dataset.col, rows=Array.from(t.querySelectorAll('tr')).slice(1);
    var asc=!(th.dataset.asc==='1'); th.dataset.asc=asc?'1':'0';
    rows.sort(function(a,b){var x=a.cells[c].dataset.sort||a.cells[c].textContent.trim(), y=b.cells[c].dataset.sort||b.cells[c].textContent.trim(); return (x<y?-1:x>y?1:0)*(asc?1:-1);});
    rows.forEach(function(r){t.appendChild(r);});
  });
});
</script>"""

RENDER_JS = f"""<script src="{VEROVIO}" defer></script>
<script>
document.addEventListener('DOMContentLoaded', function() {{
  verovio.module.onRuntimeInitialized = function() {{
    var tk = new verovio.toolkit();
    tk.setOptions({{inputFrom:'pae', scale:32, pageWidth:1400, adjustPageHeight:true, header:'none', footer:'none', breaks:'none'}});
    document.querySelectorAll('.score[data-pae]').forEach(function(el) {{
      try {{ el.innerHTML = tk.renderData(el.dataset.pae, {{}}); }} catch (e) {{ el.textContent = '(could not render)'; }}
    }});
  }};
}});
</script>"""

LABELS = {"confirmed": "Same music", "probable": "Probably same music", "unresolved": "Unresolved", "rejected": "Rejected"}
ATTRIBUTION = {"secure": "", "disputed": "Composer disputed", "uncertain": "Attribution uncertain",
               "name-only": "Surname only", "modern-copy": "Attribution from a modern copy"}
PRIOR = {"new": "", "anonymous-record": "Already named in the record", "comparator-record": "Already noted by RISM"}
SHOWN = ("confirmed", "probable", "unresolved")


def page(title, body, crumbs="", depth=0):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}</style></head>
<body><div class="wrap">{crumbs.replace('HREF_UP', up)}{body}
<p class="credit">Catalogue data and incipits come from <a href="https://rism.online/">RISM</a> (Répertoire International des Sources Musicales), CC BY 4.0. Incipits are rendered with <a href="https://www.verovio.org/">Verovio</a>. Source and data: <a href="{REPO}">{REPO}</a>.</p>
</div></body></html>
"""


def badge(verdict):
    return f'<span class="badge {verdict}">{LABELS[verdict]}</span>'


def badges(lead):
    out = [badge(lead["verdict"])]
    for text in (ATTRIBUTION.get(lead.get("attribution"), ""), PRIOR.get(lead.get("prior"), "")):
        if text:
            out.append(f'<span class="badge flag">{text}</span>')
    return '<span class="badges">' + "".join(out) + "</span>"


def roman(n):
    out = ""
    for value, sym in ((40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out += sym
            n -= value
    return out


def pae_string(p):
    return f"@clef:{p['clef']}\n@keysig:{p['keysig']}\n@timesig:{p['timesig']}\n@data:{p['data']}"


def score(p):
    return f'<div class="score" data-pae="{html.escape(pae_string(p))}"></div><code class="pae">{html.escape(p["data"])}</code>'


def evidence(lead):
    mv, hit = lead.get("movements", []), lead.get("movements_matched", [])
    return f"{len(hit)} of {len(mv)} encoded movement{'s' if len(mv) != 1 else ''}"


def matched_work(lead):
    ids = [p["match"]["source"] for p in lead.get("incipits", []) if p.get("match") and p["counts"]]
    best = max(sorted(set(ids)), key=ids.count) if ids else None
    for s in lead.get("sources", []):
        if s["id"] == best:
            return s
    return lead["sources"][0] if lead.get("sources") else None


def pair_caption(p):
    m = p.get("match")
    if not m:
        return "no matching incipit among the attributed copies"
    where = ""
    if m["offset"][1]:
        where = f", starting {m['offset'][1]} pitches into the attributed incipit"
    elif m["offset"][0]:
        where = f", the attributed incipit starting {m['offset'][0]} pitches into this one"
    verdict = "" if p["counts"] else " (too short to count)"
    return f"{p['overlap']} of {p['notes']} pitches agree{where}{verdict}"


def record_page(r):
    parts = [f"<h1>{html.escape(r['shelfmark'])}</h1>",
             f'<p class="lede">Catalogued in RISM as “{html.escape(r["label"])}” by Anonymus. '
             f'<a href="{RISM}{r["id"]}">RISM {r["id"]}</a></p>']
    for lead in r["leads"]:
        if lead["verdict"] not in SHOWN:
            continue
        parts.append(f"<h2>{html.escape(lead['composer'])}</h2><p>{badges(lead)}</p><p>{html.escape(lead['note'])}</p>")
        flags = [f"Already noted in RISM {html.escape(d['source'])}" for d in lead["prior_documentation"]]
        flags += [html.escape(f) for f in lead["attribution_flags"]]
        if flags:
            parts.append("<p class='where'>Catalogue flags:</p><ul class='flags'>" + "".join(f"<li>{f}</li>" for f in flags) + "</ul>")
        srcs = "".join(f'<li><a href="{RISM}{s["id"]}">RISM {s["id"]}</a>: {html.escape(s["label"])}</li>' for s in lead["sources"])
        parts.append(f"<p class='where'>Attributed copies compared ({evidence(lead)} match):</p><ul class='where'>{srcs}</ul>")
        for p in lead["incipits"]:
            parts.append(f"<p class='agree'><b>Movement {roman(p['movement'])}</b> · {html.escape(p['incipit'])} "
                         f"<span class='where'>· {pair_caption(p)}</span></p>")
            left = f"<div><h4>Anonymous copy</h4>{score(p['anon'])}</div>"
            if p.get("match"):
                m = p["match"]
                right = (f"<div><h4>{html.escape(lead['composer'].split(' (')[0])} · <a href='{RISM}{m['source']}'>RISM {m['source']}</a> "
                         f"movement {roman(m['movement'])} · {html.escape(m['incipit'])}</h4>{score(m)}</div>")
            else:
                right = "<div><h4>Attributed copies</h4><p class='where'>No encoded incipit matches this movement.</p></div>"
            parts.append(f"<div class='mv'>{left}{right}</div>")
    crumbs = '<div class="crumbs"><a href="HREF_UPindex.html">All results</a></div>'
    return page(f"{r['shelfmark']} · RISM attributions", "".join(parts) + RENDER_JS, crumbs, depth=1)


def build():
    data = json.loads((ROOT / "data" / "attributions.json").read_text())
    genres = json.loads((ROOT / "data" / "genres.json").read_text())
    conc = json.loads((ROOT / "data" / "anonymous_concordances.json").read_text())
    (DOCS / "r").mkdir(parents=True, exist_ok=True)
    for old in (DOCS / "r").glob("*.html"):
        old.unlink()
    rows, other = [], []
    for r in data:
        lead = r["leads"][0]
        if r["verdict"] in SHOWN:
            (DOCS / "r" / f"{r['id']}.html").write_text(record_page(r))
            work = matched_work(lead)
            names = " / ".join(html.escape(x["composer"]) for x in r["leads"] if x["verdict"] == r["verdict"])
            rows.append("<tr>"
                        f'<td><a href="r/{r["id"]}.html"><b>{html.escape(r["shelfmark"])}</b></a><br>'
                        f'<span class="where">{html.escape(r["label"].split(";")[0])} · <a href="{RISM}{r["id"]}">RISM {r["id"]}</a></span></td>'
                        f'<td><b>{names}</b><br><span class="where">{html.escape(work["label"]) if work else ""}</span></td>'
                        f'<td>{evidence(lead)}</td>'
                        f'<td data-sort="{SHOWN.index(r["verdict"])}{lead["attribution"] != "secure":d}{lead["prior"] != "new":d}">{badges(lead)}<br><span class="where">{html.escape(lead["note"])}</span></td></tr>')
        else:
            other.append(f'<tr><td><a href="{RISM}{r["id"]}">{html.escape(r["shelfmark"])}</a></td>'
                         f'<td>{html.escape(lead["composer"])}</td><td>{badge(r["verdict"])}</td><td class="where">{html.escape(lead["note"])}</td></tr>')
    shown = [r for r in data if r["verdict"] in SHOWN]
    count = {v: sum(1 for r in shown if r["verdict"] == v) for v in LABELS}
    same = [r["leads"][0] for r in shown if r["verdict"] == "confirmed"]
    new_secure = sum(1 for x in same if x["attribution"] == "secure" and x["prior"] == "new")
    documented = sum(1 for x in same if x["prior"] != "new")
    multi = sum(1 for x in same if len(x.get("movements_matched", [])) >= 2)
    qualified = sum(1 for x in same if x["prior"] == "new" and x["attribution"] != "secure")
    burn = []
    for g in genres:
        done = [r for r in data if r["genre"] == g["slug"]]
        found = sum(1 for r in done if r["verdict"] in ("confirmed", "probable"))
        status = (f'<span class="badge confirmed">searched</span> <span class="where">{g["run"]}</span>' if g.get("run")
                  else '<span class="badge open">open</span>')
        burn.append(f'<tr><td>{html.escape(g["subject"])}</td><td data-sort="{g["anonymous_with_incipits"]:07d}">{g["anonymous_with_incipits"]:,}</td>'
                    f'<td>{len(done) if g.get("run") else ""}</td><td>{found if g.get("run") else ""}</td><td>{status}</td></tr>')
    body = (
        "<h1>RISM: naming the anonymous</h1>"
        '<p class="lede"><a href="https://rism.online/">RISM</a> catalogues about 1.6 million music manuscripts and prints; '
        'about 297,000 of them are listed under “Anonymus”. Most of those carry an incipit, the opening bars of each movement in '
        'Plaine &amp; Easie code. This project searches every anonymous incipit against the attributed ones, keeps matches that no '
        'other composer shares, and compares every candidate incipit by incipit. '
        f'So far {count["confirmed"]} anonymous copies are the same music as an attributed copy ({multi} on two or more '
        f'movements, {count["confirmed"] - multi} on a single movement). Of those, {new_secure} are not noted '
        f'in RISM and carry a single, unqualified attribution; {qualified} more are new but their composer is disputed, uncertain, '
        f'a bare surname or known only from a modern copy; {documented} turned out to be noted in RISM already. '
        f'{count["probable"]} more are probably the same music (transposed, arranged, or only partly encoded) and {count["unresolved"]} are unresolved. '
        'The automatic score compares pitch contour only, ignoring rhythm; it finds candidates, and the rendered incipits on each '
        'page are the evidence. A match transfers RISM’s attribution of the other copy, so it cannot settle a disputed authorship, '
        'and composers’ printed thematic catalogues may already list some copies. '
        f'Research and incipit comparison by Claude (an LLM); an independent review by Codex (another LLM) led to the current labels. Method in <a href="{REPO}/blob/main/METHOD.md">METHOD.md</a>.</p>'
        "<h2>Results</h2>"
        '<div class="scroll"><table class="idx sortable"><tr><th data-col="0">Anonymous copy</th><th data-col="1">Matches</th>'
        '<th>Movements matching</th><th data-col="3">Verdict</th></tr>' + "".join(rows) + "</table></div>"
        "<h2>Burndown</h2>"
        '<p class="lede">Anonymous RISM sources with incipits, by subject heading. Multi-movement genres go first because '
        'agreement across several movements is the strongest evidence.</p>'
        '<div class="scroll"><table class="idx sortable"><tr><th data-col="0">Subject</th><th data-col="1">Anonymous with incipits</th>'
        '<th>Leads reviewed</th><th>Found</th><th>Status</th></tr>' + "".join(burn) + "</table></div>"
        f'<p class="where">Also: <a href="concordances.html">{len(conc)} anonymous copies matching other anonymous copies</a> '
        'on two or more movements. These group copies of one work without naming its composer.</p>'
        f'<details><summary>{len(other)} anonymous copies whose leads were reviewed and rejected</summary>'
        '<div class="scroll"><table class="idx"><tr><th>Anonymous copy</th><th>Lead</th><th>Verdict</th><th>Reason</th></tr>'
        + "".join(other) + "</table></div></details>" + SORT_JS)
    (DOCS / "index.html").write_text(page("RISM: naming the anonymous", body))
    crows = "".join(
        f'<tr><td><a href="{RISM}{c["a"]}">{html.escape(c["a_label"])}</a></td><td><a href="{RISM}{c["b"]}">{html.escape(c["b_label"])}</a></td>'
        f'<td>{", ".join(f"{roman(m['a'])} = {roman(m['b'])} ({m['pitches']} pitches)" for m in c["movements"])}</td></tr>' for c in conc)
    (DOCS / "concordances.html").write_text(page(
        "Anonymous concordances · RISM attributions",
        "<h1>Anonymous concordances</h1><p class='lede'>Pairs of anonymous RISM sources whose incipits agree on two or more "
        "distinct movements, at least eight pitches each. Each pair is probably two copies of one work; naming either copy's "
        "composer would name both. These are search results checked by pitch agreement, not reviewed by eye.</p>"
        '<div class="scroll"><table class="idx"><tr><th>Anonymous copy</th><th>Matches anonymous copy</th><th>Movements</th></tr>'
        + crows + "</table></div>", '<div class="crumbs"><a href="index.html">All results</a></div>'))
    (DOCS / ".nojekyll").write_text("")


if __name__ == "__main__":
    build()
