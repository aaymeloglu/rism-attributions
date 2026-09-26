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
   - per incipit, every attributed incipit that agrees with it, best first, both from the start
     and with one incipit starting partway into the other (a part entering after rests); among
     equally long agreements a same-key, same-instrument witness ranks first;
   - each incipit by RISM's own label, instrument and text incipit. No movement numbers are
     computed: RISM's numbering mixes movements, sections, instrumental parts and separate
     pieces, and only reading the record tells which. Where an anonymous incipit matches an
     attributed incipit with a different number, the note cites that number and says what it is;
   - catalogue context (`tools/context.py`): whether an attributed copy's record already cites
     the anonymous copy by RISM id or call number (under its current or a former library);
     whether the attribution is qualified (conjectural, alleged, doubtful), cross-referenced to
     other composers, a bare surname, or carried only by a modern copy; what the anonymous
     record itself says about authorship; whether the matched incipit is labelled as a vocal
     number; whether the text incipits differ (a contrafactum); whether any match is in a
     different key; whether RISM's title key disagrees with the encoded key signature;
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
transposed copy still agrees. Each pair is compared with grace notes dropped and kept, since one
copy may write out an ornament that another writes as graces. A stretch that is mostly
broken-chord or tremolo figuration (runs of four or more same-size intervals alternating in
direction, as in E-G-E-G) does not count as a match: accompaniment figures agree with countless
unrelated pieces, which the concerto run made obvious. It is a pitch-contour comparison. It finds candidates and
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
| secure | The attributed copies name one composer without qualification, and every other flag has a written resolution in `data/attribution_resolutions.csv`. |
| disputed | Attributed copies or catalogues name other composers too. |
| uncertain | The attribution is qualified (conjectural, doubtful) or itself unverified. |
| name-only | The attributed copy gives only a surname. |
| modern-copy | The attribution rests on a copy made after 1850. |
| work-only | The match identifies the work or number (a pasticcio or ballad opera catalogued under "Compilations"), not a composer. |

**prior** (is the concordance new?)

| Value | Meaning |
|---|---|
| new | Neither record notes the other copy. |
| anonymous-record | The anonymous record already names the composer or the catalogue number. |
| comparator-record | An attributed copy's record already cites the anonymous copy. |
| title-names-work | The anonymous title already names the work, and that work has one known composer. When the title is a libretto set by many composers, the find stays new and the note says whose setting it is. |

The note says what matched, in the records' own terms: which incipits, which incipit of the
attributed copy (by RISM number and title), and what that is (an overture, an aria, a keyboard
part of a first movement, the opening of a separate duet).

## Checks

`tests/test_data.py` fails the build when a verdict ignores what the tools found: a lead whose
comparator already cites the anonymous copy marked new; a qualified attribution marked secure
(never allowed); any other attribution flag, on the attributed copies or in the anonymous
record's own authorship notes, on a secure lead without a written resolution (mentioning a flag
is not resolving it); a match with a differently numbered incipit whose note does not cite it;
a computed movement numeral in a note; a match with a vocal number, or under different words,
whose note does not say so; a transposition claim the keys do not show; a title key that
disagrees with the encoded key signature and goes unmentioned; an anonymous concordance
candidate without a verdict. Each of these reached the site at least once before the check
existed.

## Anonymous concordances

Pairs of anonymous sources whose incipits agree, both from the start, on two or more
differently numbered incipits are candidates. Each gets a verdict in
`data/concordance_verdicts.csv` (same, probable, rejected) after comparison by eye; only same
and probable pairs are published, and a rejected pair stays rejected on regeneration.

## Limits

- Most confirmations rest on one encoded movement, often three to five bars; the site says how
  many movements each match covers.
- A match transfers RISM's attribution of the other copy, so it cannot settle a disputed
  authorship.
- Only music with an attributed copy in RISM can be found this way. Most anonymous sources have
  none; the composers' printed thematic catalogues are the next place to look.
- "Not noted in RISM" is not "unknown to scholars": a thematic catalogue may already list a
  copy. Check before reporting.
- Unencoded movements and sections are neither matches nor mismatches; the site reports
  matches as "k of n encoded incipits".
- The research and incipit comparison were done by Claude (an LLM). Two independent reviews by
  Codex (another LLM) on 26 September 2026 led to the three-part verdict, the catalogue checks,
  the incipit-label descriptions and the parser fixes. No manuscript images were examined.

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
