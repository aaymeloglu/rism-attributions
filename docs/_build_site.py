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

LABELS = {"confirmed": "Same music", "probable": "Probable", "unresolved": "Unresolved", "rejected": "Rejected"}
ATTRIBUTION = {"secure": "", "shared": "Work by several composers", "disputed": "Composer disputed", "uncertain": "Attribution uncertain",
               "name-only": "Surname only", "modern-copy": "Attribution from a modern copy", "work-only": "Work identified only"}
PRIOR = {"new": "", "anonymous-record": "Already named in the record", "comparator-record": "Already noted by RISM",
         "title-names-work": "Title already names the work"}
SHOWN = ("confirmed", "probable", "unresolved")
AUTHOR_FILTERS = {"secure": "Unqualified", "disputed": "Disputed", "uncertain": "Uncertain",
                  "name-only": "Surname only", "modern-copy": "Modern copy", "work-only": "Work only",
                  "shared": "Shared", "": "Not assessed"}
PRIOR_FILTERS = {"new": "Not noted", "anonymous-record": "Names composer", "comparator-record": "Cites copy",
                 "title-names-work": "Names work", "": "Not assessed"}


def page(title, body, crumbs="", depth=0, results=False):
    up = "../" * depth
    extra = '<link rel="stylesheet" href="results.css"><script src="results.js" defer></script>' if results else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{STYLE}</style>{extra}</head>
<body{' class="results-page"' if results else ''}><div class="wrap">{crumbs.replace('HREF_UP', up)}{body}
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


def pae_string(p):
    return f"@clef:{p['clef']}\n@keysig:{p['keysig']}\n@timesig:{p['timesig']}\n@data:{p['data']}"


def score(p):
    return f'<div class="score" data-pae="{html.escape(pae_string(p))}"></div><code class="pae">{html.escape(p["data"])}</code>'


def evidence(lead, compact=False):
    inc, hit = lead.get("incipits", []), lead.get("incipits_matched", [])
    if compact:
        return f"{len(hit)} of {len(inc)}" if "incipits" in lead else "Not scored"
    return f"{len(hit)} of {len(inc)} encoded incipit{'s' if len(inc) != 1 else ''}"


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
        heading = html.escape(lead.get("identity") or lead["composer"])
        if lead.get("identity"):
            heading += f" <span class='where'>(RISM heading: {html.escape(lead['composer'])})</span>"
        parts.append(f"<h2>{heading}</h2><p>{badges(lead)}</p><p>{html.escape(lead['note'])}</p>")
        flags = [f"Already noted in RISM {html.escape(d['source'])}" for d in lead["prior_documentation"]]
        flags += [html.escape(f) for f in lead["attribution_flags"]]
        flags += [f"Anonymous record: {html.escape(f)}" for f in lead.get("anonymous_record_authorship", [])]
        if flags:
            parts.append("<p class='where'>Catalogue flags:</p><ul class='flags'>" + "".join(f"<li>{f}</li>" for f in flags) + "</ul>")
        srcs = "".join(f'<li><a href="{RISM}{s["id"]}">RISM {s["id"]}</a>: {html.escape(s["label"])}</li>' for s in lead["sources"])
        parts.append(f"<p class='where'>Attributed copies compared ({evidence(lead)} match):</p><ul class='where'>{srcs}</ul>")
        for p in lead["incipits"]:
            voice = f" · {html.escape(p['voice'])}" if p.get("voice") else ""
            text = f" · “{html.escape(p['text'])}”" if p.get("text") else ""
            parts.append(f"<p class='agree'><b>{html.escape(p['incipit'])}</b>{voice}{text} "
                         f"<span class='where'>· {pair_caption(p)}</span></p>")
            left = f"<div><h4>Anonymous copy</h4>{score(p['anon'])}</div>"
            if p.get("match"):
                m = p["match"]
                mvoice = f" · {html.escape(m['voice'])}" if m.get("voice") else ""
                others = "".join(f"<br>also <a href='{RISM}{w['source']}'>RISM {w['source']}</a> {html.escape(w['source_inc'])}"
                                 for w in p.get("witnesses", [])[:4])
                right = (f"<div><h4>{html.escape(lead['composer'].split(' (')[0])} · <a href='{RISM}{m['source']}'>RISM {m['source']}</a> "
                         f"{html.escape(m['incipit'])}{mvoice}</h4>{score(m)}<p class='where'>{others[4:] if others else ''}</p></div>")
            else:
                right = "<div><h4>Attributed copies</h4><p class='where'>No encoded incipit matches this one.</p></div>"
            parts.append(f"<div class='mv'>{left}{right}</div>")
    crumbs = '<div class="crumbs"><a href="HREF_UPindex.html">All results</a></div>'
    return page(f"{r['shelfmark']} · RISM attributions", "".join(parts) + RENDER_JS, crumbs, depth=1)


def primary_leads(record):
    return [lead for lead in record["leads"] if lead["verdict"] == record["verdict"]]


def filter_group(key, title, options, data, selected=None):
    buttons = []
    for value, label in options.items():
        if key in ("verdict", "genre"):
            count = sum(r[key] == value for r in data)
        else:
            count = sum(any(lead[key] == value for lead in primary_leads(r)) for r in data)
        active = selected is None or value in selected
        buttons.append(f'<button type="button" class="chip {value}" data-value="{value}" '
                       f'aria-pressed="{str(active).lower()}">{html.escape(label)} <span class="chip-count">{count}</span></button>')
    return (f'<fieldset data-filter="{key}"><legend>{title}</legend><div class="filter-options">'
            + "".join(buttons) + '<button type="button" class="filter-all">All</button></div></fieldset>')


def results_row(r, genre_labels):
    leads = primary_leads(r)
    # Keep one row per anonymous copy. Multiple equally ranked leads retain their own
    # explanations and qualifications; filters must match both fields on the same lead.
    displayed = leads[:1] if r["verdict"] == "rejected" else leads
    composers, statuses, notes, counts = [], [], [], []
    for lead in displayed:
        name = lead.get("identity") or lead["composer"]
        short_name = name.split(" (")[0]
        work = matched_work(lead)
        composers.append(f'<div class="lead-block"><strong title="{html.escape(name)}">{html.escape(short_name)}</strong>'
                         + (f'<span class="work-title">{html.escape(work["label"].split(";")[0])}</span>' if work else "") + '</div>')
        flags = [text for text in (ATTRIBUTION.get(lead["attribution"]), PRIOR.get(lead["prior"])) if text]
        prefix = f'<b>{html.escape(short_name.split(",")[0])}:</b> ' if len(displayed) > 1 else ""
        statuses.append('<div class="lead-block">' + (f'<span class="qualification">{prefix}</span>' if prefix and flags else "")
                        + ''.join(f'<span class="qualification">{html.escape(text)}</span>' for text in flags) + '</div>')
        notes.append(f'<div class="lead-block">{prefix}{html.escape(lead["note"])}</div>')
        counts.append(f'<div class="lead-block">' + (f'<span class="qualification">{prefix}</span>' if prefix else "")
                      + f'{evidence(lead, compact=True)}</div>')
    if len(leads) > len(displayed):
        composers.append(f'<span class="where">+ {len(leads) - 1} other rejected candidates</span>')
        notes.append(f'<details><summary>Other rejected candidates ({len(leads) - 1})</summary><ul>'
                     + ''.join(f'<li><b>{html.escape(x.get("identity") or x["composer"])}</b>: {html.escape(x["note"])}</li>' for x in leads[1:]) + '</ul></details>')
    lead_filters = html.escape(json.dumps([{key: lead[key] for key in ("attribution", "prior")} for lead in leads]))
    local = f'r/{r["id"]}.html' if r["verdict"] in SHOWN else RISM + r["id"]
    return (f'<tr data-verdict="{r["verdict"]}" data-genre="{r["genre"]}" data-leads="{lead_filters}">'
            f'<td class="rism-id" data-sort="{r["id"]}"><a href="{RISM}{r["id"]}">{r["id"]}</a></td>'
            f'<td><a class="copy-link" href="{local}">{html.escape(r["shelfmark"])}</a>'
            f'<span class="work-title">{html.escape(r["label"].split(";")[0])}</span></td>'
            f'<td class="genre">{html.escape(genre_labels[r["genre"]])}</td>'
            f'<td>{"".join(composers)}</td>'
            f'<td class="incipit-count">{"".join(counts)}</td>'
            f'<td data-sort="{list(LABELS).index(r["verdict"])}">{badge(r["verdict"])}{"".join(statuses)}</td>'
            f'<td class="explanation">{"".join(notes)}</td></tr>')


def build():
    data = json.loads((ROOT / "data" / "attributions.json").read_text())
    genres = json.loads((ROOT / "data" / "genres.json").read_text())
    conc = json.loads((ROOT / "data" / "anonymous_concordances.json").read_text())
    (DOCS / "r").mkdir(parents=True, exist_ok=True)
    for old in (DOCS / "r").glob("*.html"):
        old.unlink()
    genre_labels = {g["slug"]: g["subject"] for g in genres}
    rows = []
    for r in data:
        if r["verdict"] in SHOWN:
            (DOCS / "r" / f"{r['id']}.html").write_text(record_page(r))
        rows.append(results_row(r, genre_labels))
    shown = [r for r in data if r["verdict"] in SHOWN]
    count = {v: sum(1 for r in data if r["verdict"] == v) for v in LABELS}
    same = [r["leads"][0] for r in shown if r["verdict"] == "confirmed"]
    new_secure = sum(1 for x in same if x["attribution"] == "secure" and x["prior"] == "new")
    documented = sum(1 for x in same if x["prior"] != "new")
    multi = sum(1 for x in same if len({i.split(" ")[0].rsplit(".", 1)[0] for i in x.get("incipits_matched", [])}) >= 2)
    qualified = sum(1 for x in same if x["prior"] == "new" and x["attribution"] != "secure")
    burn = []
    for g in genres:
        done = [r for r in data if r["genre"] == g["slug"]]
        found = sum(1 for r in done if r["verdict"] in ("confirmed", "probable"))
        status = (f'<span class="badge confirmed">searched</span> <span class="where">{g["run"]}</span>' if g.get("run")
                  else '<span class="badge open">open</span>')
        burn.append(f'<tr><td>{html.escape(g["subject"])}</td><td data-sort="{g["anonymous_with_incipits"]:07d}">{g["anonymous_with_incipits"]:,}</td>'
                    f'<td>{len(done) if g.get("run") else ""}</td><td>{found if g.get("run") else ""}</td><td>{status}</td></tr>')
    available_genres = {slug: label for slug, label in genre_labels.items() if any(r["genre"] == slug for r in data)}
    filters = (filter_group("verdict", "Verdict", LABELS, data, {"confirmed"})
               + filter_group("genre", "Genre", available_genres, data)
               + filter_group("attribution", "Authorship", AUTHOR_FILTERS, data)
               + filter_group("prior", "RISM record", PRIOR_FILTERS, data))
    body = (
        "<header><h1>RISM: naming the anonymous</h1>"
        '<p class="lede">Finding composers for anonymous music by comparing its opening bars '
        'with attributed copies in <a href="https://rism.online/">RISM</a>.</p>'
        f'<p class="summary-line"><strong>{count["confirmed"]} anonymous copies matched</strong> to the same music in an attributed source.</p>'
        '<ul class="stats">'
        f'<li><strong>{new_secure}</strong><span>Unqualified attribution</span><small>No prior link found in RISM</small></li>'
        f'<li><strong>{qualified}</strong><span>Qualified attribution</span><small>No prior link found; authorship needs care</small></li>'
        f'<li><strong>{documented}</strong><span>Already documented</span><small>The RISM record already names or links the work</small></li></ul>'
        f'<p class="summary-line secondary">Also reviewed: <b>{count["probable"]}</b> probable matches, '
        f'<b>{count["unresolved"]}</b> unresolved copies, and <b>{count["rejected"]}</b> copies with rejected leads.</p>'
        '<p class="reading-note">A musical match does not settle disputed authorship or establish a new discovery.</p>'
        '<details class="method"><summary>How to read these results</summary>'
        '<ul><li><b>Incipits</b> are the opening bars encoded in RISM. Counts show matching openings out of all encoded openings; '
        'these may represent movements, sections, or instrumental parts.</li>'
        '<li><b>Same music</b> means a reviewed concordance with an attributed copy. <b>Probable</b> means a likely match; '
        '<b>Unresolved</b> needs more evidence; <b>Rejected</b> means the candidate match did not hold up.</li>'
        '<li><b>Authorship</b> records the strength of the attribution. “Unqualified” means a single, unqualified composer attribution '
        'in the reviewed evidence. <b>RISM record</b> says whether the work was already named or linked there. '
        '“Not noted” does not mean unknown to scholars; printed thematic catalogues may already list the copy.</li>'
        f'<li>{multi} same-music matches have two or more differently numbered incipits; {count["confirmed"] - multi} have one. '
        'Automatic matching uses pitch contour, ignoring rhythm; candidates are then reviewed against the incipit notation.</li></ul>'
        f'<p>Research by Claude; reviewed by Codex. See the <a href="{REPO}/blob/main/METHOD.md">method</a> '
        f'and <a href="{REPO}/blob/main/research/source-check-2026-09-27.md">selected manuscript checks</a>.</p></details></header>'
        '<section aria-labelledby="results-title"><div class="results-heading"><h2 id="results-title">Results</h2>'
        '<button type="button" id="reset-filters" hidden>Reset filters</button></div>'
        '<div id="filters" hidden>' + filters + '</div>'
        '<p id="result-count" role="status" aria-live="polite"></p>'
        '<noscript><p>All reviewed copies are shown. Enable JavaScript to filter and sort.</p></noscript>'
        '<div class="scroll" role="region" aria-label="Attribution results" tabindex="0">'
        '<table id="results" class="idx sortable"><colgroup><col class="col-id"><col class="col-copy"><col class="col-genre">'
        '<col class="col-match"><col class="col-incipits"><col class="col-verdict"><col class="col-note"></colgroup>'
        '<thead><tr><th scope="col" data-col="0" data-type="number">RISM ID</th><th scope="col" data-col="1">Anonymous copy</th>'
        '<th scope="col" data-col="2" title="RISM search category; the matched work may have a different genre">Genre</th><th scope="col" data-col="3">Matches</th>'
        '<th scope="col" title="Matching openings out of all encoded openings">Incipits</th>'
        '<th scope="col" data-col="5" data-type="number">Verdict</th><th scope="col">Explanation</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table></div>'
        '<p id="no-results" hidden>No copies match these filters. Select another bubble or reset the filters.</p></section>'
        "<h2>Search progress</h2>"
        '<p class="lede">Anonymous RISM sources with incipits, by subject heading. Genres with several movements went first '
        'because agreement across them gives stronger evidence.</p>'
        '<div class="scroll"><table class="idx sortable"><thead><tr><th scope="col" data-col="0">Subject</th>'
        '<th scope="col" data-col="1" data-type="number">Anonymous with incipits</th>'
        '<th scope="col">Leads reviewed</th><th scope="col">Found</th><th scope="col">Status</th></tr></thead><tbody>'
        + "".join(burn) + "</tbody></table></div>"
        f'<p class="where">Also: <a href="concordances.html">{sum(1 for c in conc if c["verdict"] in ("same", "probable"))} pairs of anonymous copies</a> '
        f'({sum(1 for c in conc if c["verdict"] in ("same", "probable") and not c.get("already_documented"))} with no prior concordance found in the checked RISM records) '
        'that agree with each other on two or more incipits, reviewed by eye. These group copies of one work without naming its composer.</p>')
    (DOCS / "index.html").write_text(page("RISM: naming the anonymous", body, results=True))
    shown_conc = [c for c in conc if c["verdict"] in ("same", "probable")]
    crows = "".join(
        f'<tr><td><a href="{RISM}{c["a"]}">{html.escape(c["a_label"])}</a></td><td><a href="{RISM}{c["b"]}">{html.escape(c["b_label"])}</a></td>'
        f'<td>{"; ".join(html.escape(m["a"].split(" ")[0] + " = " + m["b"].split(" ")[0]) for m in c["incipits"][:6])}</td>'
        f'<td><span class="badge {"confirmed" if c["verdict"] == "same" else "probable"}">{"Same music" if c["verdict"] == "same" else "Probably same music"}</span>'
        f'{" <span class=\"badge flag\">Already linked in RISM</span>" if c.get("already_documented") else ""}'
        f'<br><span class="where">{html.escape(c["note"])}</span></td></tr>' for c in shown_conc)
    (DOCS / "concordances.html").write_text(page(
        "Anonymous concordances · RISM attributions",
        "<h1>Anonymous concordances</h1><p class='lede'>Pairs of anonymous RISM sources whose incipits agree, from the start, "
        "on two or more differently numbered incipits (at least eight pitches each), each pair compared by eye. Each is "
        "probably two copies of one work; naming either copy's composer would name both. Automatic candidates judged "
        "not to be the same music are recorded but not listed.</p>"
        '<div class="scroll"><table class="idx"><tr><th>Anonymous copy</th><th>Matches anonymous copy</th><th>Incipits</th><th>Verdict</th></tr>'
        + crows + "</table></div>", '<div class="crumbs"><a href="index.html">All results</a></div>'))
    (DOCS / ".nojekyll").write_text("")


if __name__ == "__main__":
    build()
