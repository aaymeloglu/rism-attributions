# Method

## What gets searched

RISM lists about 297,000 sources under "Anonymus". Most carry incipits: the opening bars of
each movement in Plaine & Easie code, with clef, key signature and time signature. The work
goes one RISM subject heading at a time (Symphonies, Concertos, ...), starting with
multi-movement genres, because agreement across several movements is the strongest evidence
and a single short opening can match by coincidence. Only records whose main creator is
Anonymus count; RISM's Anonymus list also contains records that merely cross-reference it
(for instance a Haydn symphony with an interpolated anonymous minuet).

## Pipeline

1. **Discover** (`tools/discover.py <Subject>`). For every anonymous source in the subject,
   search RISM's incipit index with the first three bars of each movement (four if the three
   bars are very short), filtered to the same key and time signature. A movement matching more
   than 40 records is treated as a stock figure and dropped. Output: `runs/<slug>/results.json`.
2. **Leads** (`tools/leads.py <slug>`). A lead is one anonymous source paired with one
   attributed composer, kept when that composer's copies match two or more incipits, or one
   that no other named composer matches, provided two or more of the composer's copies match or
   the search returned at most two hits. For each lead the script records:
   - per incipit, the best pitch agreement with the composer's incipits, both from the start
     and with one incipit starting partway into the other (a part entering after rests);
   - which movement of the attributed copy matched, with movements counted from titles and
     numbering rather than incipit numbers (`pae.movement_ordinals`);
   - catalogue context (`tools/context.py`): whether an attributed copy's record already cites
     the anonymous copy by RISM id or call number (under its current or a former library);
     whether the attribution is qualified (conjectural, alleged, doubtful), cross-referenced to
     other composers, a bare surname, or carried only by a modern copy; whether the matched
     incipit is labelled as a vocal number; whether any match is in a different key; whether
     RISM's title key disagrees with the encoded key signature;
   - the composer's dates against the copy's, and which other composers a five-bar re-search
     returns.

   A triage class (strong, good, plausible, weak, known, date-impossible, date-early) orders
   the review. Composers who died before 1690 are flagged "date-early" for review, not
   rejected: a "symphony" can be an older sinfonia or a later arrangement.
3. **Review** (`tools/review.py <slug>` prints each lead's incipits side by side with its flags;
   verdicts go in `data/verdicts.csv`). Every candidate is judged incipit by incipit: same notes
   in the same order beyond the opening figure, compatible rhythm, and a plausible relationship.
4. **Export and build** (`tools/export.py`, `python3 docs/_build_site.py`). Joins verdicts
   with the evidence into `data/attributions.json` and builds the site.

## What the automatic score is

`tools/pae.py` reduces an incipit to a pitch sequence: rhythm, rests, ties, grace notes and all
but the first note of a chord are dropped, measure repeats (`i`) and repeated groups (`!...!f`)
are expanded, repeated pitches are collapsed, and sequences are compared by interval so a
transposed copy still agrees. It is a pitch-contour comparison. It finds candidates and
rejects obvious non-matches; a common scale or arpeggio can agree by chance, so the verdict
rests on reading the incipits, not on the number.

## Verdicts

Each lead gets three separate judgements, because the same music, a secure composer and a new
finding are different questions.

**verdict** (is it the same music?)

| Value | Meaning |
|---|---|
| confirmed | The encoded incipits agree with an attributed copy's, rhythm included, beyond the opening figure. |
| probable | Same music, but transposed, arranged, only partly matching, or matching part of a larger or vocal work. |
| unresolved | Suggestive; needs the manuscript images or a thematic catalogue. |
| rejected | Only a contour fragment, repeated notes or a stock figure agree. |

**attribution** (what does the match say about the composer?)

| Value | Meaning |
|---|---|
| secure | The attributed copies name one composer without qualification. |
| disputed | Attributed copies or catalogues name other composers too. |
| uncertain | The attribution is qualified (conjectural, doubtful) or itself unverified. |
| name-only | The attributed copy gives only a surname. |
| modern-copy | The attribution rests on a copy made after 1850. |

**prior** (is the concordance new?)

| Value | Meaning |
|---|---|
| new | Neither record notes the other copy. |
| anonymous-record | The anonymous record already names the composer or the catalogue number. |
| comparator-record | An attributed copy's record already cites the anonymous copy. |

The note says what matched: which movements, which movement of the attributed copy, and what
that is (an overture, an aria, a quartet movement).

## Checks

`tests/test_data.py` fails the build when a verdict ignores what the tools found: a lead whose
comparator already cites the anonymous copy marked new; a flagged attribution (qualifier,
cross-reference, modern copy, bare surname) marked secure without the note naming it; a match
with a different movement of the attributed copy whose note does not name that movement; a
match with a vocal number whose note does not say so; a note claiming a transposition that the
keys do not show; a title key that disagrees with the encoded key signature and goes
unmentioned. Each of these reached the site at least once before the check existed.

## Limits

- Most confirmations rest on one encoded movement, often three to five bars; the site says how
  many movements each match covers.
- A match transfers RISM's attribution of the other copy, so it cannot settle a disputed
  authorship.
- Only music with an attributed copy in RISM can be found this way. Most anonymous sources have
  none; the composers' printed thematic catalogues are the next place to look.
- "Not noted in RISM" is not "unknown to scholars": a thematic catalogue may already list a
  copy. Check before reporting.
- Unencoded movements are neither matches nor mismatches.
- The research and incipit comparison were done by Claude (an LLM). An independent review by
  Codex (another LLM) on 26 September 2026 led to the three-part verdict, the catalogue checks
  and the parser fixes. No manuscript images were examined.

## Adding a genre

```
python3 tools/genres.py                 # refresh counts; set "run" for the genre in data/genres.json
python3 tools/discover.py Concertos     # writes runs/concertos/results.json
python3 tools/leads.py concertos        # writes runs/concertos/leads.json
python3 tools/review.py concertos       # print unreviewed leads with incipits and flags
# add one row per lead to data/verdicts.csv
python3 tools/export.py                 # fails if any lead has no verdict
python3 docs/_build_site.py
uv run pytest                           # the checks above
```

RISM responses are cached in `.cache/rism/` (not committed), so reruns are cheap.
