# Method

## What gets searched

RISM lists about 297,000 sources under "Anonymus". Most carry incipits: the opening bars of
each movement in Plaine & Easie code, with clef, key signature and time signature. The work
goes one RISM subject heading at a time (Symphonies, Concertos, ...), starting with
multi-movement genres, because agreement across several movements is the strongest evidence
and a single short opening can match by coincidence.

## Pipeline

1. **Discover** (`tools/discover.py <Subject>`). For every anonymous source in the subject,
   search RISM's incipit index with the first three bars of each movement (four if the three
   bars are very short), filtered to the same key and time signature. A movement matching more
   than 40 records is treated as a stock figure and dropped. Output: `runs/<slug>/results.json`.
2. **Leads** (`tools/leads.py <slug>`). A lead is one anonymous source paired with one
   attributed composer. It is kept when that composer's copies match two or more movements, or
   one movement that no other named composer matches, provided two or more of the composer's
   copies match or the search returned at most two hits. For each lead the script records:
   - notes agreeing per movement against the composer's best-matching incipit: pitch sequences,
     repeated notes collapsed, compared by interval so a transposed copy still counts;
   - whether the composer's dates are possible for the copy's date;
   - whether the record already names the composer or carries a thematic catalogue number;
   - which other named composers a five-bar re-search returns.

   These feed a triage class (strong, good, plausible, weak, known, date-impossible) written to
   `runs/<slug>/leads.json`. The class only orders the review.
3. **Review** (by hand, `data/verdicts.csv`). Every lead gets a verdict after comparing the
   incipits side by side: same notes in the same order beyond the opening figure, compatible key
   and metre, a plausible genre relationship. The note column records anything a reader should
   know (transposed copy, arrangement, overture to a named opera).
4. **Export and build** (`tools/export.py`, `python3 docs/_build_site.py`). Joins verdicts
   with RISM data into `data/attributions.json` and builds the site.

## Verdicts

| Verdict | Meaning |
|---|---|
| confirmed | The encoded incipits agree note for note with an attributed copy, and no other composer's copy matches. |
| conflicting | The music is identified, but RISM holds attributed copies under more than one composer. |
| probable | Same music, but transposed, arranged, or in a different genre (quartet version of a symphony, instrumental version of an aria). |
| unresolved | The match is suggestive and needs the manuscript images or a thematic catalogue to settle. |
| known | The anonymous record already names the composer or carries the work's catalogue number. |
| rejected | Impossible dates, fewer than six notes agreeing, or the melodies part ways after the opening figure. |

## Limits

- Most single-movement confirmations rest on an incipit of three to five bars, often the only
  movement encoded. Agreement over that span with no competing composer is strong evidence, but a
  few could be quotations or borrowings rather than the same work.
- A match transfers RISM's attribution of the other copy. Where that copy names only a surname
  ("Stamitz", "Franck"), or its own attribution is doubtful, so is ours.
- Only music with an attributed copy in RISM can be found this way. Most anonymous sources have
  none; the composers' printed thematic catalogues are the next place to look.
- "Not noted in the RISM record" is not the same as "unknown to scholars". A composer's thematic
  catalogue may already list an anonymous copy. Check before reporting.
- The research was done by Claude (an LLM). Every accepted match was compared incipit by incipit;
  no manuscript images were examined.

## Adding a genre

```
python3 tools/genres.py                 # refresh counts; set "run" for the genre in data/genres.json
python3 tools/discover.py Concertos     # writes runs/concertos/results.json
python3 tools/leads.py concertos        # writes runs/concertos/leads.json
# review every lead; add one row per lead to data/verdicts.csv
python3 tools/export.py                 # fails if any lead has no verdict
python3 docs/_build_site.py
```

RISM responses are cached in `.cache/rism/` (not committed), so reruns are cheap.
