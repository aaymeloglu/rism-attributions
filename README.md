# RISM: naming the anonymous

[RISM](https://rism.online/) (Répertoire International des Sources Musicales) catalogues about
1.6 million music manuscripts and prints. About 297,000 are listed under "Anonymus", and most
of those carry incipits, the encoded opening bars of each movement. This repository searches
those incipits against the attributed ones and compares every candidate incipit by incipit, one genre at a time.

The results, with each anonymous copy's movements rendered next to the attributed copy's, are at
**https://aaymeloglu.github.io/rism-attributions/**.

## Results so far (symphonies, 26 September 2026)

878 anonymous symphonies with incipits were searched; 864 have Anonymus as their main creator.
123 leads covering 120 anonymous sources were reviewed:

| | Sources |
|---|---|
| Same music as an attributed copy | 67 |
| of which new, with a single unqualified attribution | 53 |
| of which new, but the composer is disputed, uncertain, a bare surname or known only from a modern copy | 6 |
| of which already noted in RISM | 8 |
| Probably the same music (transposed, arranged, partial, or part of a vocal work) | 14 |
| Unresolved | 5 |
| Rejected | 34 |

Twelve of the 67 matches cover two or more movements; the other 55 rest on a single encoded
movement. Many anonymous "symphonies" turn out to be opera overtures (Galuppi, Sacchini,
Mysliveček, Cimarosa, Paisiello, Naumann's *La clemenza di Tito*), single movements of larger
works, or arrangements. Eleven pairs of anonymous copies agree with each other on two or more
movements; they are listed on the site as
[anonymous concordances](https://aaymeloglu.github.io/rism-attributions/concordances.html).

A match means RISM holds an attributed copy of the same music. It does not settle a disputed
authorship, and composers' printed thematic catalogues may already list some of these copies.
Nothing has been reported to RISM yet. See [METHOD.md](METHOD.md) for the pipeline, what each
verdict means, the checks, and the limits. The research was done by Claude (an LLM); an
independent review by Codex (another LLM) led to the current three-part verdicts and checks.

## Layout

```
data/verdicts.csv                 verdict, attribution, prior documentation and note for every lead (the source of truth)
data/attributions.json            generated: verdicts joined with RISM records and incipits (what the site shows)
data/anonymous_concordances.json  generated: anonymous copies matching each other on 2+ movements
data/genres.json                  burndown: anonymous sources with incipits per RISM subject
runs/<genre>/results.json         search hits per anonymous source
runs/<genre>/leads.json           graded leads with evidence
tools/                            rism.py (cached API client), pae.py (Plaine & Easie pitches), context.py (catalogue checks),
                                  discover/leads/review/export/genres
docs/                             the site; python3 docs/_build_site.py regenerates it (stdlib only)
tests/                            verdicts vs catalogue flags, parser, data/site consistency; CI fails if docs/ is stale
```

## Data

Catalogue data and incipits are from RISM, licensed CC BY 4.0. Incipits on the site are rendered
in the browser with [Verovio](https://www.verovio.org/).
