# RISM: naming the anonymous

[RISM](https://rism.online/) (Répertoire International des Sources Musicales) catalogues about
1.6 million music manuscripts and prints. About 297,000 are listed under "Anonymus", and most
of those carry incipits, the encoded opening bars of each movement. This repository searches
those incipits against the attributed ones and compares every candidate incipit by incipit, one genre at a time.

The results, with each anonymous copy's movements rendered next to the attributed copy's, are at
**https://aaymeloglu.github.io/rism-attributions/**.

## Results so far (26 September 2026)

| | Symphonies | Concertos | Operas |
|---|---|---|---|
| Anonymous sources with incipits searched | 878 | 899 | 1,771 |
| Anonymous sources with a lead, reviewed | 119 | 97 | 174 |
| Same music as an attributed copy | 66 | 39 | 84 |
| of which new, with a single unqualified attribution | 52 | 29 | 27 |
| of which new, but the composer is disputed, uncertain, a bare surname, a modern copy or a compilation | 6 | 2 | 5 |
| of which the anonymous title already names the work (one known composer) | 0 | 0 | 34 |
| of which already noted in RISM | 8 | 8 | 18 |
| Probably the same music (transposed, arranged, partial, or part of a vocal work) | 17 | 15 | 23 |
| Unresolved | 5 | 4 | 5 |
| Rejected | 31 | 39 | 62 |

A source with leads in more than one genre is counted once. Eleven symphony and eight
concerto matches agree on two or more incipits that RISM numbers differently; the rest rest on a
single encoded incipit. Many
anonymous "symphonies" turn out to be opera overtures (Galuppi, Sacchini, Mysliveček, Cimarosa,
Paisiello, Naumann's *La clemenza di Tito*), single movements of larger works, or arrangements.
The concertos include Weber's Clarinet Concertino and Rosetti's clarinet concerto MurR C62 (both
written for B-flat clarinet, a whole tone above concert pitch), Mozart's K. 175 and a run of
Giuseppe Sammartini concertos in the British Library's Royal Music collection. Among the operas,
many anonymous arias turn out to be one composer's setting of a much-set libretto (Hasse's
*Didone abbandonata*, Sarri's, Perez's), German or Latin versions of Italian numbers (*Una cosa rara*,
a Hasse aria with the Latin words "Veni mi Jesu care"), or arias a composer reused in another opera. Twenty-eight pairs
of anonymous copies agree with each other from the start of two or more differently numbered
incipits; each was compared by eye (25 same music, 3 probable) and they are listed on the site as
[anonymous concordances](https://aaymeloglu.github.io/rism-attributions/concordances.html).

A match means RISM holds an attributed copy of the same music. It does not settle a disputed
authorship, and composers' printed thematic catalogues may already list some of these copies.
Nothing has been reported to RISM yet. See [METHOD.md](METHOD.md) for the pipeline, what each
verdict means, the checks, and the limits. The research was done by Claude (an LLM); two
independent reviews by Codex (another LLM) led to the current verdicts, checks and descriptions.

## Layout

```
data/verdicts.csv                 verdict, attribution, prior documentation and note for every lead (the source of truth)
data/attribution_resolutions.csv  written reasons why a flagged attribution is still secure
data/concordance_verdicts.csv     verdict for every automatic anonymous-to-anonymous candidate
data/attributions.json            generated: verdicts joined with RISM records and incipits (what the site shows)
data/anonymous_concordances.json  generated: anonymous copies matching each other on 2+ movements
data/genres.json                  burndown: anonymous sources with incipits per RISM subject
runs/<genre>/results.json         search hits per anonymous source
runs/<genre>/leads.json           graded leads with evidence
tools/                            rism.py (cached API client), pae.py (Plaine & Easie pitches), context.py (catalogue checks),
                                  discover/leads/export/genres (pipeline), review.py and verdict.py (reviewing leads)
docs/                             the site; python3 docs/_build_site.py regenerates it (stdlib only)
tests/                            verdicts vs catalogue flags, parser, data/site consistency; CI fails if docs/ is stale
```

## Data

Catalogue data and incipits are from RISM, licensed CC BY 4.0. Incipits on the site are rendered
in the browser with [Verovio](https://www.verovio.org/).
