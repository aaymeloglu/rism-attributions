"""Catalogue context a reviewer must see before calling a match new or an attribution secure.

prior_documentation: does an attributed copy's record already point at the anonymous copy
    (by RISM id, by its call number under its current or a former library siglum, or by its
    call number in a note that calls the copy anonymous)? Hits are for a reviewer to read.
attribution_flags: is the attributed copy's composer qualified (conjectural, alleged,
    doubtful), cross-referenced to other composers, named by surname only, or carried only by
    a modern copy (copyist or editor born after 1850)?
anonymous_creator: is Anonymus the record's main creator, or only a cross-reference?
"""
import json
import re

import rism

SIGLUM = re.compile(r"\b[A-Z]{1,3}-[A-Z][A-Za-z]{0,6}\b")
SECURE = {None, "Ascertained", "Verified"}


def _text(src):
    return json.dumps(src, ensure_ascii=False)


def shelfmark(src):
    """(siglum, call number) from a source label 'Title; Manuscript copy; D-KA Don Mus.Ms. 1808'."""
    tail = rism.label(src).split(";")[-1].strip()
    m = SIGLUM.match(tail)
    return (m.group(0), tail[m.end():].strip()) if m else ("", tail)


def _call_tail(callno):
    """Last token with a digit ('1808', 'II-369', '31/263'): what a note citing the copy must contain."""
    toks = [t.strip(".,") for t in callno.split() if re.search(r"\d", t)]
    return toks[-1] if toks else ""


def _catalogue_notes(obj):
    """Prose notes, excluding display labels and the record's own shelfmark fields."""
    if isinstance(obj, dict):
        label = (obj.get("label") or {}).get("en", []) if isinstance(obj.get("label"), dict) else []
        if label and "note" in label[0].lower():
            yield from (obj.get("value") or {}).get("none", [])
        for key, value in obj.items():
            if key not in {"label", "value", "incipits", "rendered", "renderings", "encodings"}:
                yield from _catalogue_notes(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _catalogue_notes(item)


def _local_citations(src, siglum, callno):
    """Local references can omit the library siglum. Require a full shelfmark and a
    reference phrase; a note merely recording an old shelfmark is not a concordance.
    This deliberately leaves ambiguous/abbreviated references for human review.
    """
    if not siglum or shelfmark(src)[0] != siglum or not re.search(r"\d", callno):
        return
    call = re.compile(r"(?<![\w/-])" + re.escape(callno) + r"(?![\w/-]|[.,]\d)")
    reference = re.compile(r"\b(?:unter|siehe|see|concordan\w*|konkordanz\w*|manus[ck]ript\w*)\b", re.I)
    for note in _catalogue_notes(src):
        if call.search(note) and reference.search(note):
            yield note


def prior_documentation(anon_id, anon_src, comparators):
    """[(comparator id, snippet)] where a comparator record already refers to the anonymous copy."""
    siglum, callno = shelfmark(anon_src)
    tail = _call_tail(callno)
    sigla = {siglum} | set(SIGLUM.findall(_text(anon_src))) | former_sigla(anon_src)
    sigla.discard("")
    hits = []
    for cid, src in comparators:
        local = list(_local_citations(src, siglum, callno))
        if local:
            hits.append((cid, local[0]))
            continue
        text = _text(src)
        ident = re.search(r"(?<!\d)" + re.escape(anon_id) + r"(?!\d)", text)
        if ident:
            k = ident.start()
            hits.append((cid, text[max(0, k - 160):k + 40]))
            continue
        if not tail:
            continue
        for m in re.finditer(re.escape(tail), text):
            if re.match(r"[\w/-]|[.,]\d", text[m.end():]) or re.search(r"[\w/-]$", text[:m.start()]):
                continue
            window = text[max(0, m.start() - 60):m.start()]
            q0, q1 = text.rfind('"', 0, m.start()), text.find('"', m.end())
            note = text[q0 + 1:q1]  # the catalogue note containing the call number
            if any(sg in window for sg in sigla) or re.search(r"anonym", note, re.I):
                hits.append((cid, text[max(0, m.start() - 160):m.end() + 40]))
                break
    return hits


def former_sigla(src):
    """Sigla of institutions recorded as former owners: a copy may be cited under its old library."""
    out = set()
    for rel in (src.get("relationships") or {}).get("items", []):
        to = rel.get("relatedTo") or {}
        if (rel.get("role") or {}).get("value") == "fmo" and to.get("type") == "rism:Institution":
            out.add(rism.get(to["id"]).get("siglum") or "")
    out.discard("")
    return out


def creator_qualifier(src):
    return ((src.get("creator") or {}).get("qualifier") or {}).get("value")


def cross_references(src):
    """Composer cross-references on a record: [(name, qualifier)]."""
    out = []
    for rel in (src.get("relationships") or {}).get("items", []):
        if (rel.get("role") or {}).get("value") == "att":
            out.append((rism.label(rel.get("relatedTo") or {}), (rel.get("qualifier") or {}).get("value")))
    return out


def modern_hands(src):
    """Copyists or editors born after 1850: the copy may be a modern transcription, not a period witness."""
    out = []
    for rel in (src.get("relationships") or {}).get("items", []):
        if (rel.get("role") or {}).get("value") in ("scr", "edt"):
            name = rism.label(rel.get("relatedTo") or {})
            born = re.search(r"\((\d{4})", name)
            if born and int(born.group(1)) > 1850:
                out.append(name)
    return sorted(set(out))


def name_only(composer):
    """A heading with no dates and no forename ('Franck', 'Stamitz') does not identify a person."""
    return not re.search(r"\d", composer) and "," not in composer


def attribution_flags(composer, comparators):
    """Reasons the composer attribution carried by the comparators is not single and secure."""
    flags = []
    if name_only(composer):
        flags.append(f"heading '{composer}' names no identifiable person")
    for cid, src in comparators:
        for name in modern_hands(src):
            flags.append(f"{cid}: copied or edited by {name}; a modern copy, not a period witness")
        q = creator_qualifier(src)
        if q not in SECURE:
            flags.append(f"{cid}: composer qualified as {q}")
        for name, q in cross_references(src):
            if q == "Misattributed":
                continue  # recorded history, not a live alternative
            flags.append(f"{cid}: cross-reference to {name}" + (f" ({q})" if q else ""))
    return sorted(set(flags))


def anonymous_creator(src):
    return rism.creator(src) == "Anonymus"


VOCAL = re.compile(r"\b(recitativ\w*|aria|arietta|coro|chorus|duett\w*|terzett\w*|cavatina|rondò|kyrie|gloria|credo|"
                   r"sanctus|agnus|magnificat|dixit|lied|scena)\b", re.I)


def vocal_label(label):
    """The matched incipit is labelled as a vocal number: the anonymous piece may be an instrumental
    passage of a vocal work, not a separate composition."""
    m = VOCAL.search(label or "")
    return m.group(0) if m else ""


FIFTHS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7, "F": -1, "Bb": -2, "Eb": -3, "Ab": -4,
          "Db": -5, "Gb": -6, "Cb": -7}


def keysig_fifths(ks):
    if not ks or ks == "n":
        return 0
    n = sum(1 for ch in ks[1:] if ch in "ABCDEFG")
    return n if ks[0] == "x" else -n


def label_key_fifths(label):
    """Key signature implied by a RISM title key ('Symphonies–B♭ major'), or None."""
    m = re.search(r"–([A-G])([♭♯]?)\s+(major|minor)", label or "")
    if not m:
        return None
    tonic = m.group(1) + {"♭": "b", "♯": "#", "": ""}[m.group(2)]
    if tonic not in FIFTHS:
        return None
    return FIFTHS[tonic] - (3 if m.group(3) == "minor" else 0)


def key_label_mismatch(label, first_keysig):
    """The title's key disagrees with the first incipit's key signature (e.g. 'B major' over two flats)."""
    expected = label_key_fifths(label)
    return expected is not None and first_keysig is not None and expected != keysig_fifths(first_keysig)


def _words(text):
    import unicodedata
    plain = "".join(c for c in unicodedata.normalize("NFKD", (text or "").lower()) if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", plain)


def work_title(label):
    """Title of a source label, without key, genre qualifiers or shelfmark: 'Didone abbandonata'."""
    t = (label or "").split(";")[0].split("–")[0]
    t = re.sub(r"\((?:excerpts|arrangement|fragments)[^)]*\)", "", t, flags=re.I)
    return " ".join(_words(t))


ARTICLES = {"le", "la", "les", "l", "il", "lo", "i", "gli", "der", "die", "das", "the", "a", "an", "un", "une"}
GENERIC = {"operas", "arias", "symphonies", "concertos", "sonatas", "overtures", "variations", "songs", "duets",
           "potpourris", "fantasies", "marches", "waltzes", "dances", "pieces", "divertimentos", "quartets", ""}


def _core(title):
    words = work_title(title).split()
    while words and words[0] in ARTICLES:
        words = words[1:]
    return " ".join(words)


def source_titles(src):
    """The record's display title, standardized title, title on source and additional titles."""
    out = [rism.label(src)]
    for item in (src.get("contents") or {}).get("summary", []):
        if (item.get("label") or {}).get("en", [""])[0] in ("Standardized title", "Title on source", "Additional title"):
            out += (item.get("value") or {}).get("none", []) or []
    return out


def _aliases():
    import csv
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "work_aliases.csv")
    groups = {}
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                a, b = _core(r["title"]), _core(r["same_as"])
                g = groups.get(a) or groups.get(b) or {a, b}
                g |= {a, b}
                for t in g:
                    groups[t] = g
    return groups


def same_work_title(anon_src, comp_src):
    """Does the anonymous record's title already name the attributed copy's work? Compares the
    anonymous title with every title the attributed record carries (standardized, as written on
    the source, additional), and with the reviewed alternative titles in data/work_aliases.csv.
    This prompts a review; it does not by itself settle that the work has one composer."""
    a = _core(rism.label(anon_src).split(";")[0])
    if not a or a in GENERIC:
        return False
    aliases = _aliases().get(a, {a})
    for t in source_titles(comp_src):
        core = _core(t.split(";")[0]) if ";" in t else " ".join(_words(t))
        padded = f" {core} "
        if any(x == core or f" {x} " in padded for x in aliases if x):
            return True
    return False


def text_agreement(a, b):
    """Compare two text incipits: 'same', 'different', or '' when either is missing.
    Two copies of one aria share their words; the same melody under different words is a
    contrafactum (or a coincidence), not the same piece as catalogued."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return ""
    n = min(len(wa), len(wb), 3)
    return "same" if wa[:n] == wb[:n] else "different"


AUTHORSHIP = re.compile(r"attribu|zuschreib|zugeschrieb|autorschaft|authorship|komponist|\bcomposer\b|"
                        r"\b(?:probably|possibly|perhaps|presumably) by\b|"
                        r"\b(?:vermutlich|wahrscheinlich|wohl|möglicherweise|evtl\.?) (?:von|vom)\b|"
                        r"nicht gesichert|not established|ignoto autore|d'autore ignoto|autore incerto", re.I)


def authorship_notes(src, composer=""):
    """Catalogue notes on the anonymous record itself that discuss who wrote it, plus its own
    composer cross-references. An anonymous heading can sit on top of an authorship discussion;
    a new concordance has to be weighed against it, not over it."""
    own = composer.split(",")[0].split(" (")[0]
    out = [f"cross-reference to {name}" + (f" ({q})" if q else "") for name, q in cross_references(src)
           if name != "Anonymus" and not (own and name.startswith(own))]
    notes = []
    for grp in (src.get("contents") or {}).get("summary", []) + [x for g in (src.get("materialGroups") or {}).get("items", []) for x in g.get("summary", [])]:
        notes += (grp.get("value") or {}).get("none", [])
    for sec in ("notes", "contents"):
        block = src.get(sec) or {}
        for item in block.get("notes", []) if isinstance(block, dict) else []:
            notes += (item.get("value") or {}).get("none", [])
    text = json.dumps(src, ensure_ascii=False)
    for m in re.finditer(r'"value": \{"none": \[((?:"(?:[^"\\]|\\.)*",? ?)+)\]', text):
        for v in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)):
            if len(v) > 25 and AUTHORSHIP.search(v) and not v.startswith("<span"):
                notes.append(v)
    seen = []
    for n in notes:
        n = n.replace('\\"', '"')
        if AUTHORSHIP.search(n) and n not in seen and len(n) > 25:
            seen.append(n[:300])
    return out + seen[:6]
