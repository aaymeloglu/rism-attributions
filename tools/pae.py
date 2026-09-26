"""Plaine & Easie code (https://plaine-and-easie.info/v1/) to pitch sequences, and comparisons.

Only pitch is kept: rhythm, rests, ties, grace notes and all but the first note of a chord
are dropped. Measure repeats (`i`) and repeated groups (`!...!` followed by one `f` per
repetition) are expanded. Comparisons collapse repeated pitches and work on intervals, so a
transposed copy compares equal to the original. This is a pitch-contour comparison, not a
note-for-note musical one; the side-by-side rendering on the site is what a reviewer judges.
"""
import re

CHANGE = {"%": re.compile(r"%[CFG]-?\d"), "$": re.compile(r"\$(n|[xb][A-G]+)?"), "@": re.compile(r"@(c/?|\d+/\d+|\d+)")}
STEP = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def keymap(ks):
    m = {}
    if not ks or ks == "n":
        return m
    sign = 1 if ks[0] == "x" else -1 if ks[0] == "b" else 0
    for ch in ks[1:]:
        if ch in STEP:
            m[ch] = sign
    return m


def expand_groups(data):
    """`!X!fff` -> X written out four times (the group once, plus one repetition per f)."""
    return re.sub(r"!([^!]*)!(f+)", lambda m: m.group(1) * (1 + len(m.group(2))), data)


def measures(data, ks="", graces=False):
    """Pitches (MIDI numbers) per measure, with `i` measure repeats expanded. Grace notes are
    dropped unless graces=True (one copy may write out an ornament another writes as graces).

    An accidental holds for the same pitch letter in the same octave until the end of the measure
    (https://plaine-and-easie.info/v2/#accidentals); a barline or a key-signature change clears it.
    """
    km, oc, out, cur, bar = keymap(ks), 4, [], [], {}
    acc, grace, ingroup, chord = None, False, False, False
    s, i = expand_groups(data), 0
    while i < len(s):
        ch = s[i]
        if ch == "/":
            out.append(cur)
            cur, bar = [], {}
            while i < len(s) and s[i] in "/:":
                i += 1
            continue
        if ch == "i":
            cur = list(out[-1]) if out else []
            i += 1
            continue
        if ch in "',":
            j = i
            while j < len(s) and s[j] == ch:
                j += 1
            oc = 3 + (j - i) if ch == "'" else 4 - (j - i)
            i = j
            continue
        if ch in "%$@":  # clef, key signature or time signature change
            m = CHANGE[ch].match(s, i)
            if ch == "$" and m:
                km, bar = keymap(m.group(0)[1:]), {}
            i = m.end() if m else i + 1
            continue
        if ch == "x":
            acc = 2 if s[i + 1:i + 2] == "x" else 1
            i += 2 if acc == 2 else 1
            continue
        if ch == "b" and i + 1 < len(s) and (s[i + 1] in STEP or s[i + 1] == "b"):
            acc = -2 if s[i + 1] == "b" else -1
            i += 2 if acc == -2 else 1
            continue
        if ch == "n":
            acc = 0
            i += 1
            continue
        if ch == "q":
            if s[i + 1:i + 2] == "q":
                ingroup = True
                i += 2
                continue
            grace = True
            i += 1
            continue
        if ch == "r":
            ingroup = False
            i += 1
            continue
        if ch == "g":
            grace = True
            i += 1
            continue
        if ch == "^":
            chord = True
            i += 1
            continue
        if ch in STEP:
            if acc is not None:
                bar[(ch, oc)] = acc
            a = bar.get((ch, oc), km.get(ch, 0))
            if (graces or not (grace or ingroup)) and not chord:
                cur.append(12 * (oc + 1) + STEP[ch] + a)
            grace = chord = False
            acc = None
            i += 1
            continue
        i += 1
    if cur:
        out.append(cur)
    return out


def pitches(data, ks="", graces=False):
    return [p for m in measures(data, ks, graces) for p in m]


def intervals(p):
    return [b - a for a, b in zip(p, p[1:])]


def dedup(p):
    o = []
    for x in p:
        if not o or o[-1] != x:
            o.append(x)
    return o


def lcp(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def sim(p1, p2):
    """Pitches agreeing from the start of both incipits (repeated notes collapsed, by interval)."""
    a, b = dedup(p1), dedup(p2)
    return lcp(intervals(a), intervals(b)) + 1 if a and b else 0


def align(p1, p2):
    """Longest run of agreeing pitches anywhere in the two incipits: (pitches, start in p1, start in p2).

    Catches an incipit that begins after rests or mid-phrase relative to the other one.
    Starts are indices into the repeated-notes-collapsed sequences.
    """
    a, b = intervals(dedup(p1)), intervals(dedup(p2))
    best, prev = (0, 0, 0), [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best[0]:
                    best = (cur[j], i - cur[j], j - cur[j])
        prev = cur
    n, i, j = best
    return (n + 1, i, j) if n else (min(len(p1), len(p2), 1), 0, 0)


def anchored(p1, p2):
    """Longest agreement where one incipit is matched from its own start against any point of the
    other: (pitches, start in p1, start in p2), one start being 0.

    Catches a part that enters after rests or mid-phrase relative to the other incipit, without
    rewarding a scale fragment shared somewhere inside two unrelated incipits.
    """
    a, b = intervals(dedup(p1)), intervals(dedup(p2))
    best = (lcp(a, b), 0, 0)
    for j in range(1, len(b)):
        n = lcp(a, b[j:])
        if n > best[0]:
            best = (n, 0, j)
    for i in range(1, len(a)):
        n = lcp(a[i:], b)
        if n > best[0]:
            best = (n, i, 0)
    n, i, j = best
    return (n + 1 if (a or b) and dedup(p1) and dedup(p2) else 0, i, j)


def figuration(p, start, length):
    """Share of an agreeing stretch (collapsed-sequence indices) taken up by broken-chord or
    tremolo figuration: runs of four or more intervals of one size alternating in direction
    (+4 -4 +4 -4, as in E-G-E-G). Such figures agree with countless unrelated pieces; a motif
    that alternates in twos or threes with changing sizes (D-C-D-A-D-F) does not count.
    """
    seq = intervals(dedup(p))[start:start + max(length - 1, 0)]
    covered, k = set(), 0
    while k < len(seq):
        j = k
        while j + 1 < len(seq) and seq[j + 1] == -seq[j]:
            j += 1
        if j - k + 1 >= 4:
            covered.update(range(k, j + 1))
        k = j + 1
    return len(covered) / len(seq) if seq else 0.0
