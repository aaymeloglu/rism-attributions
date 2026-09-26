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


def prior_documentation(anon_id, anon_src, comparators):
    """[(comparator id, snippet)] where a comparator record already refers to the anonymous copy."""
    siglum, callno = shelfmark(anon_src)
    tail = _call_tail(callno)
    sigla = {siglum} | set(SIGLUM.findall(_text(anon_src))) | former_sigla(anon_src)
    sigla.discard("")
    hits = []
    for cid, src in comparators:
        text = _text(src)
        if anon_id in text:
            k = text.index(anon_id)
            hits.append((cid, text[max(0, k - 160):k + 40]))
            continue
        if not tail:
            continue
        for m in re.finditer(re.escape(tail), text):
            if text[m.end():m.end() + 1].isdigit() or text[m.start() - 1:m.start()].isdigit():
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
